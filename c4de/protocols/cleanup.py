import re
from datetime import datetime, timedelta

from c4de.sources.domain import FullListData
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

    text = re.sub("(\{\{(Movie|Show|TV)?[Ss]poiler\|([^\n]+?)}})\{\{", "\\1{{", text)
    line = re.search("\n\{\{(Movie|Show|TV)?[Ss]poiler\|(.*?)}}.*?\n", text)
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
        release_date = datetime.strptime(tv_dates[show][f1], "%Y-%m-%d")
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
        return "no-fields", re.sub("\{\{TVspoiler.*?}}.*?\n", "", text)

    new_text = "|".join(fields_to_keep)
    for q in quotes_to_keep:
        new_text += f"|quote{q}=1"

    new_time = None
    if release_dates:
        new_time = (min(release_dates) + timedelta(days=limit)).strftime("%Y-%m-%d")

    new_text = "{{TVspoiler|" + new_text + "}}\n"
    return new_time, re.sub("\{\{TVspoiler\|.*?}}.*?\n", new_text, text)


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
    for u, d in re.findall("\[['\"](.+?)/*?['\"]] ?= ?['\"]?(.*?)['\"]?[, ]*\n", page.get()):
        if u.startswith("/") and u != "/":
            u = u[1:]
        if template == "Rebelscum":
            u = re.sub("^(https?://)?w*\.?rebelscum\.com/", "", u)
        archive[u.replace("\\'", "'").replace("{{=}}", "=").lower()] = d
    return archive


def clean_archive_usages(page: Page, text, data: FullListData = None, redo=False):
    txt, _ = _clean_archive_usages(page, text, data.archive_data if data else {}, redo)
    return txt

YEARLY = ['news/happy-star-wars-day', 'news/star-wars-black-friday-and-cyber-week-deals', 'news/star-wars-day-deals', 'news/star-wars-day-merchandise', 'news/star-wars-day-video-game-deals', 'news/star-wars-fathers-day-gift-guide', 'news/star-wars-halloween-shopping-guide', 'news/star-wars-holiday-gift-guide', 'news/star-wars-mothers-day-gift-guide', 'news/star-wars-reads', 'news/star-wars-valentines-day-gift-guide']


def _clean_archive_usages(page: Page, text, archive_data: dict, redo=False):
    templates_to_check = set()
    if redo:
        for x in re.findall("\{\{([^\n|{}]+?)\|[^\n{}]+?\|archive(url|date)=.*?}}", text):
            if x[0] != "WebCite":
                templates_to_check.add(x[0])
    else:
        for c in page.categories():
            if c.title().endswith("same archivedate value") or c.title().endswith("with custom archivedate"):
                templates_to_check.add(re.search("^(.*?) usages with.*?$", c.title(with_ns=False)).group(1))
    if not templates_to_check:
        return text, archive_data

    if "SWArchive" in templates_to_check and "CargoBay" not in templates_to_check:
        templates_to_check.add("CargoBay")
    if "SWYouTube" in templates_to_check:
        templates_to_check.add("ThisWeek")
        templates_to_check.add("HighRepublicShow")
        templates_to_check.add("StarWarsShow")
    chunks = text.split("</ref>")
    for t in templates_to_check:
        if t not in archive_data:
            archive_data[t] = parse_archive(page.site, t)
        archive = archive_data.get(t) or {}
        if not archive:
            continue

        for c in chunks:
            if archive and t == "Blogspot":
                for x in re.findall("(\{\{" + t + "\|(.*?\|)?(url|id|a?l?t?link)=([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or (x[3].lower() not in archive and f"search/label/{x[3]}".lower() not in archive):
                        continue
                    # elif "nolive=" in x[0] and x[8] != archive[x[3].lower()]:
                    #     continue
                    text = text.replace(x[5], "")
                for x in re.findall("(\{\{" + t + "\|(.*?\|)?(blogspoturl)=([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[3].lower() not in archive or "|url=" in x[0]:
                        continue
                    text = text.replace(x[5], "")
            elif archive and "YouTube" in t:
                for x in re.findall("(\{\{.*?\|video=([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[1].lower() not in archive:
                        continue
                    text = text.replace(x[3], "")
                for x in re.findall("(\{\{.*?YouTube\|(channel=)([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or "video=" in x[0] or x[2].lower() not in archive:
                        continue
                    text = text.replace(x[4], "")
                for x in re.findall("(\{\{.*?YouTube\|(video=)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[2].lower() not in archive:
                        continue
                    text = text.replace(x[4], "")
            elif archive and t == "SWE":
                for x in re.findall("(\{\{" + t + "\|(url=)?([^\n{}|]*?)/?\|([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]*?) ?)(\|[^\n{}]*?)? ?}})", c):
                    z = f"{x[2]}/{x[3]}"
                    if "oldversion" in x[0] or z.lower() not in archive:
                        continue
                    # elif "nolive=" in x[0] and x[7] != archive[x[2].lower()]:
                    #     continue
                    text = text.replace(x[5], "")
            elif archive and t == "Databank":
                for x in re.findall("(\{\{" + t + "\|(url=)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]*?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[2].lower() not in archive:
                        continue
                    # elif "nolive=" in x[0] and x[7] != archive[x[2].lower()]:
                    #     continue
                    text = text.replace(x[4], "")
            elif archive:
                for x in re.findall("(\{\{" + t + "\|(subdomain=|username=)([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or "|url=" in x[0] or x[2].lower() not in archive:
                        continue
                    text = text.replace(x[4], "")
                for x in re.findall("(\{\{" + t + "\|(.*?\|)?(url|id|a?l?t?link)=([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[3].lower() not in archive or x[3].lower() in YEARLY:
                        continue
                    # elif "nolive=" in x[0] and x[8] != archive[x[3].lower()]:
                    #     continue
                    text = text.replace(x[5], "")
                for x in re.findall("(\{\{" + t + "\|((?!(url|id|a?l?t?link)=)[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+?)? ?\|archive(url|date)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if "oldversion" in x[0] or x[1].lower() not in archive or x[1].lower() in YEARLY:
                        continue
                    # elif "nolive=" in x[0] and x[7] != archive[x[1].lower()]:
                    #     continue
                    text = text.replace(x[4], "")
                if t == "Rebelscum":
                    for x in re.findall(
                            "(\{\{KennerCite\|(.*?\|)?link=(h?t?t?.*?rebelscum\.com/)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url)=([^\n{}|]+?) ?)(\|[^\n{}]*?)?}})",
                            c):
                        if "oldversion" in x[0] or x[3].lower() not in archive:
                            continue
                        # elif "nolive=" in x[0] and x[7] != archive[x[3].lower()]:
                        #     continue
                        text = text.replace(x[5], "").replace(f"link={x[2]}{x[3]}", f"link={x[3]}")
                    for x in re.findall(
                            "(\{\{[A-z0-9 _]+\|(.*?\|)?(url|a?l?t?link)=([^\n{}|]*?rebelscum[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url)=[^\n{}|]*? ?)(\|[^\n{}]*?)?}})",
                            c):
                        if "nolive=" in x[0] or "oldversion" in x[0]:
                            continue
                        if re.sub("(https?://)?w*\.?rebelscum\.com/", "", x[3].lower()) not in archive:
                            continue
                        text = text.replace(x[5], "")
    return text, archive_data


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


MAINTENANCE_CATS = ["High-priority template and page issues", "Low-priority template and page issues", "File maintenance",
                    "ArchiveAccess tracking categories", "Tracking maintenance categories"]
ARCHIVEDATE_CATS = ["Custom archivedate usages", "Same archivedate usages", "Unarchived URLs"]


def mark_as_empty(text):
    for t in [*ARCHIVEDATE_CATS, *MAINTENANCE_CATS]:
        text = text.replace(f"[[Category:{t}|", f"[[Category:{t}/Empty|").replace(f"[[Category:{t}]]", f"[[Category:{t}/Empty]]")
    return text


def mark_as_non_empty(text):
    for t in [*ARCHIVEDATE_CATS, *MAINTENANCE_CATS]:
        text = text.replace(f"[[Category:{t}/Empty|", f"[[Category:{t}|").replace(f"[[Category:{t}/Empty]]", f"[[Category:{t}]]")
    return text


def clean_up_archive_categories(site):
    done = []

    for tx in [*ARCHIVEDATE_CATS, *MAINTENANCE_CATS]:
        done.append(f"{tx}")
        done.append(f"{tx}/Empty")
        for c in Category(site, f"{tx}/Empty").subcategories():
            if c.title() in done or c.title().endswith("/Empty"):
                continue
            done.append(c.title())
            if not c.isEmptyCategory():
                text = mark_as_non_empty(c.get())
                if text != c.get():
                    c.put(text, "Marking as non-empty")

        for c in Category(site, tx).subcategories():
            if c.title() in done or c.title().endswith("/Empty"):
                continue
            done.append(c.title())
            if c.isEmptyCategory():
                text = mark_as_empty(c.get())
                if text != c.get():
                    c.put(text, "Marking as empty")
