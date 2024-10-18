import re
from datetime import datetime, timedelta
from pywikibot import Category, Page, showDiff
from pywikibot.exceptions import LockedPageError

from c4de.common import log, error_log

bots = ["01miki10-bot", "C4-DE Bot", "EcksBot", "JocastaBot", "RoboCade", "PLUMEBOT", "TOM-E Macaron.ii"]


def archive_stagnant_senate_hall_threads(site, offset):
    for page in Category(site, "Senate Hall").articles(namespaces=100):
        try:
            archive_senate_hall_thread(site, page, offset)
        except LockedPageError:
            continue


def archive_senate_hall_thread(site, page: Page, offset):
    text = page.get()
    if "{{sticky}}" in text.lower():
        return

    stagnant = False
    for revision in page.revisions(total=10):
        if revision["user"] in bots:
            continue
        elif "Undo revision" in revision["comment"] and any(b in revision["comment"] for b in bots):
            continue
        duration = datetime.now() - (revision["timestamp"] - timedelta(hours=offset))
        stagnant = duration.days >= 31
        break

    if stagnant:
        new_text = text.replace("{{Shtop}}", "{{subst:SHarchive|~~~~}}\n{{Shtop-arc}}").replace("{{shtop}}", "{{subst:SHarchive|~~~~}}\n{{Shtop-arc}}")
        if text == new_text:
            print("ERROR: cannot find {{Shtop}}")
        else:
            page.put(new_text, f"Archiving stagnant Senate Hall thread", botflag=False)


def remove_spoiler_tags_from_page(site, page, tv_dates, tv_default, limit=30, offset=5):
    text = page.get()

    text = re.sub("(\{\{(Movie|Show|TV)?[Ss]poiler\|([^\n]+?)\}\})\{\{", "\\1{{", text)
    line = re.search("\n\{\{(Movie|Show|TV)?[Ss]poiler\|(.*?)\}\}.*?\n", text)
    if not line:
        print(f"Cannot find spoiler tag on {page.title()}")
        return "no-tag"

    target = line.group(2).replace("||", "|").split("|")
    fields = []
    named = {}
    for field in target:
        if field.startswith("time="):
            named["time"] = field.split("=", 1)[1]
        elif field.startswith("thr="):
            named["thr"] = field.split("=", 1)[1]
        elif field.startswith("show="):
            named["show"] = field.split("=", 1)[1]
        elif field.startswith("quote"):
            f, v = field.split("=", 1)
            named[f] = v
        else:
            fields.append(field.replace('}', ''))

    if "Star Wars Outlaws" in fields and "time" not in named:
        named['time'] = "2024-09-30"

    print(named, fields)
    if named.get("time") == "skip":
        return "skip"
    elif line.group(1) == "TV":
        time, new_text = remove_expired_tv_spoiler(text, fields, named, tv_dates, tv_default, limit=limit)
    elif not named.get("time"):
        print(f"{page.title()}: No time defined in the Spoiler template")
        return "none"
    elif len(fields) <= 2:
        t = page.title() if len(fields) == 0 else fields[0]
        time_field = named["time"]
        for i in [3, 6, 9, 11]:
            time_field = time_field.replace(f"-{str(i).zfill(2)}-31", f"-{str(i + 1).zfill(2)}-01")
        time = datetime.strptime(time_field, "%Y-%m-%d")
        if time > (datetime.now() + timedelta(hours=offset)):
            print(f"{page.title()}: Spoilers for {t} do not expire until {time}")
            return time
        new_text = re.sub("\{\{(Movie|TV|Show)?[Ss]poiler.*?}}.*?\n", "", text)
    else:
        time, new_text = remove_expired_fields(site, text, fields, named, limit=limit)

    page.put(new_text, "Removing expired spoiler notices", botflag=False)
    return time


def remove_expired_fields(site, text, fields: list, named: dict, limit=30):
    i, j = 0, 0
    fields_to_keep = []
    quotes_to_keep = []
    release_dates = []
    now = datetime.now() + timedelta(hours=5)
    while i < len(fields):
        f1 = fields[i]
        release_date = extract_release_date(site, f1, limit)
        if release_date and release_date < now:
            log(f"{f1} has a spoiler expiration date of {release_date}; removing from template")
            i += 2
            continue
        elif release_date:
            release_dates.append(release_date)

        fields_to_keep.append(f1)
        if i < len(fields) - 1:
            fields_to_keep.append(fields[i + 1])
        j += 1
        if f"quote{j}" in named:
            quotes_to_keep.append(j)
        i += 2

    if not fields_to_keep:
        return "no-fields", re.sub("\{\{Spoiler.*?\}\}.*?\n", "", text)

    new_text = "|".join(fields_to_keep)
    for q in quotes_to_keep:
        new_text += f"|quote{q}=1"

    new_time = None
    if release_dates:
        new_time = (min(release_dates) + timedelta(days=limit)).strftime("%Y-%m-%d")
        new_text += f"|time={new_time}"

    new_text = "{{Spoiler|" + new_text + "}}\n"
    return new_time, re.sub("\{\{Spoiler\|.*?}}.*?\n", new_text, text)


def remove_expired_tv_spoiler(text, fields: list, named: dict, tv_dates: dict, tv_default, limit=30):
    i, j = 0, 0
    fields_to_keep = []
    quotes_to_keep = []
    release_dates = []
    now = datetime.now() + timedelta(hours=5)
    show = named.get("show", tv_default)
    while i < len(fields):
        f1 = fields[i]
        release_date = datetime.strptime(tv_dates[show][int(f1)], "%Y-%m-%d")
        if release_date and release_date < now:
            log(f"{f1} has a spoiler expiration date of {release_date}; removing from template")
            i += 2
            continue
        elif release_date:
            release_dates.append(release_date)

        fields_to_keep.append(f1)
        if i < len(fields) - 1:
            fields_to_keep.append(fields[i + 1])
        j += 1
        if f"quote{j}" in named:
            quotes_to_keep.append(j)
        i += 2

    if not fields_to_keep:
        return "no-fields", re.sub("\{\{TVspoiler.*?\}\}.*?\n", "", text)

    new_text = "|".join(fields_to_keep)
    for q in quotes_to_keep:
        new_text += f"|quote{q}=1"

    new_time = None
    if release_dates:
        new_time = (min(release_dates) + timedelta(days=limit)).strftime("%Y-%m-%d")

    new_text = "{{TVspoiler|" + new_text + "}}\n"
    return new_time, re.sub("\{\{TVspoiler\|.*?\}\}.*?\n", new_text, text)


def extract_release_date(site, name, limit):
    page = Page(site, name)
    if not page.exists():
        print(f"Cannot check release date for invalid page {page.title()}")
        return None
    elif page.isRedirectPage():
        page = page.getRedirectTarget()

    p_text = page.get()
    date_match = re.search(r"\n\|(publication date|release date|publish date|airdate)=(?P<t>.*?)[\n<]", p_text)
    if not date_match:
        print(f"No date field found on {name}")
        return None

    date_str = date_match.groupdict()["t"].replace("[", "").replace("]", "")
    date = None
    try:
        date = datetime.strptime(date_str, "%B %d, %Y")
    except Exception as e:
        print(type(e), e)

    if date:
        return date + timedelta(days=limit)
    else:
        print(f"No date found on {name}")
        return None


def check_preload_for_missing_fields(site, template: Page, apply: bool):
    text = template.get()
    if "Category:Infoboxes without preloads" in text:
        return [], []

    o = re.search("InfoboxParamCheck\|main\|(.*?)(\|optional=(.*?))?}}", text)
    required = []
    optional = []
    if o:
        required = o.group(1).split("|")
        if o.group(3):
            optional = o.group(3).split("|", 1)[0].split(",")

    preload = Page(site, f"{template.title()}/preload")
    if not preload.exists() and " infobox" in template.title():
        preload = Page(site, f"{template.title().replace(' infobox', '')}/preload")
    if preload.isRedirectPage():
        preload = preload.getRedirectTarget()
    if not preload.exists():
        return None, None

    preload_text = preload.get()
    missing_from_preload = []
    missing_from_check = []
    order = {}
    previous = "{{"
    for field in re.findall('<data[ ]*source[ ]*?=[ ]*?"(.*?)"', text):
        if f"|{field.strip()}=" not in preload_text:
            if field in optional:
                print(f"{field} is optional for {template.title()}; skipping")
                continue
            elif field not in required:
                missing_from_check.append(field)
            missing_from_preload.append(field)
            order[previous] = field
        previous = f"|{field.strip()}="

    if missing_from_check:
        print(f"{template.title()}: {missing_from_check}")

    if order:
        lines = preload_text.splitlines()
        new_lines = []
        for line in lines:
            new_lines.append(line)
            if line.startswith("{{") and order.get("{{"):
                new_lines.append(f"|{order['{{']}=")
            elif line.strip() in order:
                new_lines.append(f"|{order[line.strip()]}=")

        new_text = "\n".join(new_lines)
        showDiff(preload_text, new_text)
        if apply:
            preload.put(new_text, "Updating preload with new parameters", botflag=False)

    return missing_from_preload, missing_from_check


def check_infobox_category(site):
    preload_results = {}
    check_results = {}

    parent_category = Category(site, "Infobox templates")
    templates = list(parent_category.articles(namespaces=10))
    for subcategory in parent_category.subcategories(recurse=True):
        if subcategory.title() in ["Category:Preload templates", "Category:Event infobox subtemplates"]:
            continue
        templates += list(subcategory.articles(recurse=True, namespaces=10))

    for template in templates:
        if "/" in template.title() or template.title() == "Template:Game reviews":
            continue
        missing_from_preload, missing_from_check = check_preload_for_missing_fields(site, template, False)
        if missing_from_check:
            check_results[template.title()] = missing_from_check
        if missing_from_preload:
            preload_results[template.title()] = missing_from_preload

    return preload_results, check_results


def parse_archive(site, template):
    page = Page(site, f"Module:ArchiveAccess/{template}")
    if not page.exists():
        return None
    archive = {}
    for u, d in re.findall("\[['\"](.*?)/?['\"]] ?= ?['\"]?(.*?)['\"]?", page.get()):
        archive[u.replace("\\'", "'")] = d
    return archive


def clean_up_archive_dates(site, t=None):
    mapping = {}
    pages = set()
    for category in Category(site, "Same archivedate usages").subcategories(recurse=True):
        if category.isEmptyCategory():
            continue
        template = category.title(with_ns=False).split(" usages")[0]
        if template == t:
            pages = set(category.articles())
        elif not t:
            pages = pages.union(category.articles())
        mapping[template] = parse_archive(site, template)

    for page in pages:
        text = page.get()
        for template, data in mapping.items():
            if f"{{{{{template}|" in text or f"{{{{{template.replace(' ', '_')}|" in text:
                for x in re.findall("(({{" + template + "\|(url=|domain=.*?\|(url=)?)?(.*?)\|.*?)\|archivedate=([0-9]+)(\|.*?)?}})", text):
                    if x[4] in data and x[5] == data[x[4]]:
                        text = text.replace(x[0], x[1] + x[6] + "}}")
        page.put(text, "Clearing stored archivedates")


def clean_up_archive_categories(site):
    for mc in Category(site, "Archivedate usages").subcategories():
        for c in mc.subcategories():
            if c.title().endswith("/Empty"):
                for cx in c.subcategories():
                    if not cx.isEmptyCategory():
                        text = cx.get().replace(f"{mc.title()}/Empty]]", f"{mc.title()}]]")
                        cx.put(text, "Marking as non-empty")

            if c.isEmptyCategory():
                text = c.get().replace(f"{mc.title()}]]", f"{mc.title()}/Empty]]")
                c.put(text, "Marking as empty")
