from c4de.sources.engine import load_template_types
from pywikibot import Page, Category, showDiff, input_choice
import re
from c4de.common import archive_url

YEARLY = ['news/happy-star-wars-day', 'news/star-wars-black-friday-and-cyber-week-deals', 'news/star-wars-day-deals',
          'news/star-wars-day-merchandise', 'news/star-wars-day-video-game-deals', 'news/star-wars-fathers-day-gift-guide',
          'news/star-wars-halloween-shopping-guide', 'news/star-wars-holiday-gift-guide', 'news/star-wars-mothers-day-gift-guide',
          'news/star-wars-reads', 'news/star-wars-valentines-day-gift-guide']


def create_archive_categories(site, template):
    cats = [
        (f"{template} usages with archived URLs not in Archive",
         "{{Tl|<template>}} usages with an archivedate that's not recorded in [[Module:ArchiveAccess/<template>]].",
         "Unarchived URLs", "X"),
        (f"{template} usages with the same archivedate value",
         "{{Tl|<template>}} usages with the same archivedate value as [[Module:ArchiveAccess/<template>]]'s common value.",
         "Same archivedate usages", "Y"),
        (f"{template} usages with custom archivedate",
         "{{Tl|<template>}} usages that use a different archivedate than [[Module:ArchiveAccess/<template>]]'s common value.",
         "Custom archivedate usages", "Z"),
    ]

    Category(site, f"{template} archive usages").put("[[Category:Web citation archive template usages]]", "Creating category")

    for cn, cd, cc, cz in cats:
        cp = Category(site, cn)
        tx = ("""__HIDDENCAT__
__EXPECTUNUSEDCATEGORY__

<desc>

[[Category:<template> archive usages]]
[[Category:<cat_type><x>]]
[[Category:ArchiveAccess tracking categories<x>|<y>-{{PAGENAME}}]]"""
              .replace("<desc>", cd).replace("<cat_type>", cc)
              .replace("<x>", "/Empty" if cp.isEmptyCategory() else "")
              .replace("<y>", cz).replace("<template>", template))
        cp.put(tx, "Creating maintenance category")


def parse_archive(site, template):
    page = Page(site, f"Module:ArchiveAccess/{template}")
    if not page.exists():
        return None
    archive = {}
    for u, d, _ in re.findall(r"(?<!-- )\[['\"](.+?)/*?['\"]] ?= ?['\"]?(.*?)['\"]?[, ]*(--.*?)?\n", page.get()):
        if u.startswith("/") and u != "/":
            u = u[1:]
        if template == "Rebelscum":
            u = re.sub(r"^(https?://)?w*\.?rebelscum\.com/", "", u)
        archive[u.replace("\\'", "'").replace("{{=}}", "=").lower()] = d
    return archive


def prepare_text_for_cleanup(text):
    text = text.replace("Youtube", "YouTube").replace("|url=|", "|").replace("|video=|", "|").replace("</ref>", "</ref>\n")
    text = re.sub(r"((/>|</ref>)[^\n]+)<ref>", "\\1\n</ref", text)
    text = re.sub(r"(\{\{Quote[^\n]+?\|)<ref", "\\1\n<ref", text)
    text = re.sub(r"(\{\{YouTube\|.*?)\|name=\[\[Wikipedia:(.*?)\|.*?]]", "\\1|wplink=\\2", text)
    return re.sub(r"\|(archiveurl|archivedate|url)=\n?(.*?)\n?}}", "|\\1=\\2}}", text)


def check_url_options(data, x):
    current = data.get(x.lower())
    if not current:
        current = data.get(x.lower().replace("http://", "https://"))
    if not current:
        current = data.get(x.lower().replace("https://", "http://"))
    return current


def clean_target_key(x):
    x = x.replace("{{=}}", "=").strip().replace("&ndash;", "–").replace("&mdash;", "—")
    if re.search(r"^([0-9]|[a-z]+)=(...+?)$", x):
        x = re.sub(r"^([0-9]|[a-z]+)=", "", x)
    if x.startswith("/") or x.endswith("/"):
        x = re.sub("^/?(.+?)/?$", "\\1", x)
    return x.strip()


def prepare_text(k, v):
    u = k.replace('{{=}}', '=')
    if u.startswith('/') and len(u) > 1:
        u = u[1:]
    if u.endswith('/') and len(u) > 1:
        u = u[:-1]
    return f'\t["{u}"] = "{v}",'


def decide_archive_template(template, types: dict, skip: list, archives: dict, patterns: dict, site):
    youtube = "YouTube" in template or types.get(template.lower()) == "YT"
    archive_template = "YouTube" if youtube else template
    youtube = youtube or template == "Twitch"
    archive_template = "SideshowCite" if template in ["HotToysCite", "IronStudiosCite"] else archive_template
    if archive_template not in archives:
        if types.get(template.lower()) not in ["Web", "YT", "DB", "Publisher", "Commercial", "External", "Social",
                                               "Cards", "Toys"]:
            if types.get(template.lower()):
                print(f"Skipping {types.get(template.lower())} template {template}")
            skip.append(template)
            return None, None, None
        archives[archive_template] = parse_archive(site, archive_template)
    if archives.get(archive_template) is None:
        print(f"No archive found for Template:{template}")
        skip.append(template)
        return None, None, None

    if template not in patterns:
        patterns[template] = get_template_patterns(site, template)
    is_toy, base, full, target = patterns[template]
    return archive_template, youtube, target


def build_missing_and_new(page, types, archives, patterns, new_data, skip):
    if not new_data:
        new_data = {}
    text = prepare_text_for_cleanup(page.get())
    actual = []
    for tx in page.templates():
        title = tx.title(with_ns=False)
        if title not in types:
            if tx.isRedirectPage():
                t1 = tx.title(with_ns=False)
                t2 = tx.getRedirectTarget().title(with_ns=False)
                text = text.replace("{{" + t1 + "|", "{{" + t2 + "|")
                if " " in t1:
                    text = text.replace("{{" + t1.replace(" ", "_") + "|", "{{" + t2 + "|")
                continue
        if not tx.title().startswith("Template:") or title in skip or title in types["Nav"] or title in types["Dates"]:
            continue
        actual.append(tx.title(with_ns=False))

    for template in actual:
        archive_template, youtube, target = decide_archive_template(template, types, skip, archives, patterns, page.site)
        if not archive_template:
            continue

        if youtube:
            zx = [(i[0], i[4]) for i in re.findall(r"(\{\{" + template + r"\|((subdomain|channel|username|name|text|wplink|link|series|parameter)=.*?\|)*?(video=)?([^|\n}=]+?)([&?].*?)?(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
            for i in re.findall(r"(\{\{" + template + r"\|(.*?\|)?channel=([^|\n}=]+?)(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text):
                if "video=" not in i[0]:
                    zx.append((i[0], i[2]))
            if not zx:
                for z in re.findall(r"\{\{YouTube\|.*?}}", text):
                    print(z)
        elif template == "Databank":
            zx = [(i[0], i[2]) for i in re.findall(r"(\{\{Databank\|(url=)?([^|\n}]+?)(\|.*?)(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
        else:
            zx = [(i[0], i[3]) for i in re.findall(r"(\{\{" + template + r"(\|[^\n}]*?)?\|(url|link|altlink)==?/?([^|\n}]+?(\{\{=}})?[^|\n}]*?)/* *(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
            if template in ["Bluesky", "Threads", "TikTok", "Twitter"]:
                for i in re.findall(r"(\{\{" + template + r".*?\|/?((post|statuse?s?|video|playlist)/[^|\n}]+?)/*(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text):
                    zx.append((i[0], i[1]))
            if template in ["ArtStation", "Blogspot", "Bluesky", "Cara", "DeviantArt", "Facebook", "Instagram", "LinkedIn", "Threads", "TikTok", "Tumblr", "Twitter", "WordPress"]:
                for i in re.findall(r"(\{\{" + template + r"(\|[^\n}]*?)?\|(subdomain|username)=/?([^|\n}]+?)/*(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text):
                    if "|url=" not in i[0]:
                        zx.append((i[0], i[3]))
        for a, x in zx:
            if "na=video file" in a or "oldversion" in a or "nobackup=1" in a:
                continue
            x = clean_target_key(x)
            if template != "Rebelscum" and ("rebelscum" in a or ("|link=" in a and template in ["Galoob", "KennerCite"])):
                if "Rebelscum" not in archives:
                    archives["Rebelscum"] = parse_archive(page.site, "Rebelscum")

                if check_url_options(archives[archive_template], x):
                    continue

                if archives.get("Rebelscum") and template != "Topps":
                    y = re.sub(r"^.*?rebelscum\.com/", "", x)
                    if y.lower() in archives.get("Rebelscum", {}):
                        continue
                    elif y.lower() in new_data.get(template, {}) or y.lower() in new_data.get("Rebelscum", {}):
                        continue
                    check_url(y, archives, "Rebelscum", new_data, a)
                    if "Rebelscum" in new_data and y in new_data["Rebelscum"]:
                        continue

            key = clean_target_key(prepare_url(target.group(1), a)) if target else x
            if key and key != x:
                # print(f"{x} --> {key}")
                x = key

            check_url(x, archives, archive_template, new_data, a)

    return new_data


def check_url(x, archives, template, new_data, a):
    replace = False
    y = re.search(r"\|archiveurl=(.*?)(\|.*?)?}}", a)
    if not (y and y.group(1)):
        y = re.search(r"\|archivedate=(.*?)(\|.*?)?}}", a)
    values = ["File:" + v for v in re.findall(r"\|archivefile[0-9]*=:?[Ff][Ii][Ll][Ee]:(.*?)[|}]", a) if v]
    if y and y.group(1):
        values.insert(0, y.group(1))
    full_value = "|".join(values)

    current = check_url_options(archives[template], x)
    if current == full_value:
        return
    elif current and "archivefile" in a and "File:" not in current and full_value:
        replace = True
        if current not in full_value:
            full_value = f"{current}|{full_value}"
    elif current:
        if full_value:
            print(f"DIFF: {template}: {x} --> {current} != {full_value}")
        return

    if template not in new_data:
        new_data[template] = {}
    other = [v for k, v in new_data[template].items() if k.lower() == x.lower()]
    if any(z['value'] for z in other):
        return

    if not y and template == "Hyperspace":
        return
    print("NEW:" if not full_value else "Found:", template, x, a, replace, full_value, "->", current)

    new_data[template][x] = {"value": full_value or None, "full": a, "replace": replace}


def handle_parameters(ux: str, a):
    unnamed = {}
    i = 1
    for x in re.findall(r"\|([^|{}]+)", a):
        if "=" not in x:
            unnamed[str(i)] = x
            i += 1

    z = re.search(r"\{\{\{([A-z0-9_ ]+)(\|([^{]*?))?}}}", ux)
    while z:
        if z.group(1) in unnamed:
            ux = ux.replace(z.group(0), unnamed[z.group(1)])
        else:
            bx = "/?" if z.group(1) in ["url", "link", "altlink"] else ""
            b = re.search(r"\|" + z.group(1) + "=" + bx + r"(.*?)" + bx + r"(\|.*?)?}}", a)
            if b:
                ux = ux.replace(z.group(0), b.group(1))
            elif z.group(3):
                ux = ux.replace(z.group(0), z.group(3))
            else:
                ux = ux.replace(z.group(0), "")
        z = re.search(r"\{\{\{([A-z0-9_ ]+)(\|([^{]*?))?}}}", ux)
    return ux


def handle_if_statement(ux):
    past = f"{ux}-1"
    result = f"{ux}"
    while (ux.count("#if:") + ux.count("#ifeq:")) > 0 and past != result:
        past = f"{result}"
        z = re.search(r"^.*(\{\{#if:(.*?)\|([^|{}]*)\|([^|{}]*)}})", result)
        if z and "{{" not in z.group(2):
            if z.group(2).strip():
                result = result.replace(z.group(1), z.group(3))
            else:
                result = result.replace(z.group(1), z.group(4))
        z = re.search(r"^.*(\{\{#ifeq:(.*?)\|([^|{}]*)\|([^|{}]*)\|([^|{}]*)}})", result)
        if z and "{{" not in z.group(3):
            if z.group(2).strip() == z.group(3).strip():
                result = result.replace(z.group(1), z.group(4))
            else:
                result = result.replace(z.group(1), z.group(5))
    while ux.count("#switch") > 0 and past != result:
        past = f"{result}"
        z = re.search(r"\{\{#switch:([^{}]*?)\|([^{}]*)*?}}", result)
        if z:
            y = {x.split("=", 1)[0].strip(): x.split("=", 1)[1].strip() for x in z.group(2).split("|")}
            if z.group(2) in y:
                result = result.replace(z.group(0), y[z.group(2)])
            else:
                result = result.replace(z.group(0), y.get("#default", ""))
    return result


def prepare_url(ux, full):
    ux = handle_parameters(ux, full)
    return handle_if_statement(ux)


def get_template_patterns(site, t):
    tx = Page(site, f"Template:{t}").get()
    if "ToyCitation" in tx:
        base = re.search(r"\|baseUrl=(.*?)\n", tx)
        full = re.search(r"\|url=(.*?)\n", tx)
        target = re.search(r"\|link=(.*?[^]])\n", tx)
        return True, base, full, target
    else:
        base = re.search(r"\|base_url=(.*?)\n", tx)
        full = re.search(r"\|full_url=(.*?)\n", tx)
        target = re.search(r"\|target_url=((.*?)\{\{\{(url|video|1).*?)\n", tx)
        return False, base, full, target


def build_to_check(site, data, patterns):
    to_check = {}
    to_pop = {}
    for t, urls in data.items():
        to_check[t] = {}
        to_pop[t] = {}
        if "YouTube" in t:
            for k, v in urls.items():
                if not (v and v.get('url')):
                    to_check[t][k] = f"https://www.youtube.com/watch?v={k}"
        elif t == "SWU":
            continue
        else:
            if t in patterns:
                is_toy, base, full, target = patterns[t]
            else:
                is_toy, base, full, target = get_template_patterns(site, t)

            if is_toy:
                for k, v in urls.items():
                    if not (v and v.get('value')):
                        if "|link=" in v['full'] and base and target:
                            ux = base.group(1) + "/" + target.group(1)
                        elif full:
                            ux = full.group(1)
                        else:
                            print(f"unknown: {t} -> {base}, {target}, {full}, {v['full']}")
                            continue

                        new_url = prepare_url(ux, v['full'])
                        to_check[t][k] = new_url
            else:
                for k, v in urls.items():
                    mode, new_url = None, None
                    key = prepare_url(target.group(1), v['full']) if target else k
                    if full:
                        new_url = prepare_url(full.group(1), v['full'])
                        mode = "full"
                    elif base:
                        ux = prepare_url(base.group(1), v['full'])
                        new_url = f"{ux}/{key}" if not (ux.endswith("/") or k.startswith("/")) else f"{ux}{key}"
                        mode = "base"
                    if new_url and new_url.endswith("/"):
                        new_url = new_url[:-1]

                    print(mode, f"{k} -> {key}" if k != key else key, new_url, v.get('value') if v else None, v.get('replace') if v else None)
                    if key != k:
                        to_pop[t][k] = key
                    if new_url and not (v and v.get('value')):
                        to_check[t][key] = new_url

    for t, vx in to_pop.items():
        for old_key, new_key in vx.items():
            data[t][new_key] = data[t].pop(old_key)

    return to_check


def populate_archives(to_check, skip=False, start=None):
    archives = {}
    try:
        for t, dx in to_check.items():
            for k, v in dx.items():
                if k in archives:
                    continue
                try:
                    success, archivedate = archive_url(v, skip=skip, start=start)
                    if success:
                        archives[k] = archivedate
                except KeyboardInterrupt:
                    return archives
                except Exception as e:
                    print(f"Encountered {str(e)} for {v}")
    except KeyboardInterrupt:
        pass
    return archives


def build_archive_module_text(text, new_items: dict):
    new_text = []
    in_map, found, start = False, False, False
    skip = []
    for line in text.splitlines():
        if not start:
            start = line.strip().startswith("[") or "knownArchiveDates" in line.strip()
        elif not found:
            x = [(k, v['replace'], v['value']) for k, v in new_items.items() if (f"['{k.lower()}']" in line.lower() or f'["{k.lower()}"]' in line.lower())]
            replaced = False
            for i, r, val in x:
                if r:
                    new_text.append(prepare_text(i, val))
                    replaced = True
                else:
                    print(f"URL {i} is already archived")
                skip.append(i)
            if replaced:
                continue
            elif not x and line.strip().startswith("}"):
                if "[" in new_text[-1] and not new_text[-1].strip().endswith(","):
                    new_text[-1] = new_text[-1].rstrip() + ","
                for k, v in sorted(new_items.items()):
                    if k in skip:
                        continue
                    new_text.append(prepare_text(k, v['value']))
                found = True
        new_text.append(line)
    return new_text


def add_data_to_archive(site, data, archives, ask=False):
    for t, new_urls in data.items():
        p = Page(site, f"Module:ArchiveAccess/{t}")
        if not p.exists():
            continue
        text = p.get()
        archive = archives.get(t, {})
        to_add = {k: v for k, v in new_urls.items() if v and v.get('value') and (k not in archive or (v and v.get('replace')))}
        new_text = build_archive_module_text(text, to_add)
        if text != "\n".join(new_text):
            if ask:
                showDiff(text, "\n".join(new_text), context=2)
                choice = input_choice(
                    f'Do you want to accept these changes to {p.title()}?',
                    [('Yes', 'y'), ('No', 'n'), ('Quit', 'q')],
                    default='N')
                if choice == 'q':
                    break
                if choice == 'y':
                    p.put("\n".join(new_text), "Recording missing archivedates")
            else:
                p.put("\n".join(new_text), "Recording missing archivedates")


def do_work(site, types=None):
    types = types or load_template_types(site)
    archives, patterns = {}, {}
    data = {}
    skip, done = [], []
    cx = list(Category(site, "Unarchived URLs").subcategories())
    for c in [Category(site, "Pages with missing shared permanent archival links"), *cx]:
        for p in c.articles():
            if p.title() in done:
                continue
            data = build_missing_and_new(p, types, archives, patterns, data, skip)
            done.append(p.title())

    to_check = build_to_check(site, data, patterns)
    new_info = populate_archives(to_check)

    for t, dx in new_info.items():
        for k, v in dx.items():
            if v:
                y = data[t].get(k, {})
                y['value'] = v
                data[t][k] = y


def is_old_or_not_in_archive(original, x, archive):
    if "oldversion=" in original:
        return True
    if x.lower() in archive:
        return False
    if "http" in x:
        z = x.lower().replace("http://", "").replace("https://", "").replace("www.", "")
        return not any(y.endswith(z) for y in archive)
    return True


def determine_templates(text):
    templates_to_check = set()
    for x in re.findall(r"\{\{([^\n|{}]+?)\|[^\n{}]+?\|archive(url|date|file)=.*?}}", text):
        if x[0] != "WebCite":
            templates_to_check.add(x[0])
    return templates_to_check


def clean_archive_usages(page: Page, text, archive_data: dict, redo=False):
    templates_to_check = set()
    if redo:
        templates_to_check = determine_templates(text)
    else:
        for c in page.categories():
            if c.title().endswith("same archivedate value") or c.title().endswith("with custom archivedate"):
                templates_to_check.add(re.search(r"^(.*?) usages with.*?$", c.title(with_ns=False)).group(1))
            elif c.title().endswith("Internet citations with custom archivedate and nolive flag"):
                redo = True
    if redo:
        templates_to_check = determine_templates(text)
    if not templates_to_check:
        return text, archive_data

    if "Topps" in templates_to_check:
        templates_to_check.add("ToppsLivingSet")
        templates_to_check.add("ForceAttax")
        templates_to_check.add("ToppsNow")
    if "SWArchive" in templates_to_check and "CargoBay" not in templates_to_check:
        templates_to_check.add("CargoBay")
    if "SWYouTube" in templates_to_check:
        templates_to_check.add("ThisWeek")
        templates_to_check.add("HighRepublicShow")
        templates_to_check.add("StarWarsShow")
    text = re.sub(r"\|url=/([^|{}\[\]].*?)\|", "|url=\\1|", text)
    chunks = text.split("</ref>")
    for t in templates_to_check:
        tx = "SWYouTube" if t in ["ThisWeek", "HighRepublicShow", "StarWarsShow"] else t
        tx = "Topps" if tx in ["ToppsNow", "ToppsLivingSet", "ForceAttax"] else tx
        if tx not in archive_data:
            archive_data[tx] = parse_archive(page.site, tx)
        archive = archive_data.get(tx) or {}
        if not archive:
            continue

        for c in chunks:
            if archive and t == "Rebelscum":
                for x in re.findall(r"(\{\{KennerCite\|(.*?\|)?link=(h?t?t?.*?rebelscum\.com/)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url|file)=([^\n{}|]+?) ?)(\|[^\n{}]*?)?}})", c):
                    if is_old_or_not_in_archive(x[0], x[3], archive):
                        continue
                    text = text.replace(x[5], "").replace(f"link={x[2]}{x[3]}", f"link={x[3]}")
                for x in re.findall(r"(\{\{[A-z0-9 _]+\|(.*?\|)?(url|a?l?t?link)=([^\n{}|]*?rebelscum[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url|file)=[^\n{}|]*? ?)(\|[^\n{}]*?)?}})", c):
                    if "nolive=" in x[0] or "oldversion" in x[0]:
                        continue
                    if re.sub(r"(https?://)?w*\.?rebelscum\.com/", "", x[3].lower()) not in archive:
                        continue
                    text = text.replace(x[5], "")
            elif archive and (tx == "Blogspot" or tx == "Tumblr"):
                blogs = []
                for x in re.findall(r"(\{\{" + t + r"\|(.*?\|)?subdomain=([^\n{}|]*?)(\|[^\n{}]*?)?\|url=([^\n{}|]*?)(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    blogs.append((x[0], f"{x[2]}.{tx.lower()}.com/{x[4]}", x[6]))
                for x in re.findall(r"(\{\{" + t + r"\|(.*?\|)?url=([^\n{}|]*?)(\|[^\n{}]*?)?|subdomain=([^\n{}|]*?)(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    blogs.append((x[0], f"{x[4]}.{tx.lower()}.com/{x[2]}", x[6]))
                for x in re.findall(r"(\{\{" + t + r"\|(.*?\|)?url=([^\n{}|]*?)(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    blogs.append((x[0], f"{tx.lower()}.com/{x[2]}", x[4]))
                for x in re.findall(r"(\{\{" + t + r"\|(.*?\|)?subdomain=([^\n{}|]*?)(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    blogs.append((x[0], f"{x[2]}.{tx.lower()}.com", x[4]))

                for o1, o2, o3 in blogs:
                    if is_old_or_not_in_archive(o1, o2, archive):
                        continue
                    text = text.replace(o3, "")
            elif archive and "YouTube" in t:
                for x in re.findall(r"(\{\{.*?\|video=([^\n{}|]*?)/?(&t=[0-9]+s)?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[1], archive):
                        continue
                    if x[2] and x[1].lower() in archive and f"{x[1]}{x[2]}".lower() not in archive:
                        text = text.replace(x[2], "")
                    text = text.replace(x[4], "")
                for x in re.findall(r"(\{\{.*?YouTube\|(channel=)([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[2], archive) or "video=" in x[0]:
                        continue
                    text = text.replace(x[4], "")
                for x in re.findall(r"(\{\{(.*?YouTube|ThisWeek|StarWarsShow|HighRepublicShow)\|(video=)?([^\n{}|]*?)/?(&t=[0-9]+s)?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[3], archive):
                        continue
                    if x[4] and x[3].lower() in archive and f"{x[3]}{x[4]}".lower() not in archive:
                        text = text.replace(x[4], "")
                    text = text.replace(x[6], "")
            elif archive and t == "SWE":
                for x in re.findall(r"(\{\{" + t + r"\|(url=)?([^\n{}|]*?)/?\|([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]*?) ?)(\|[^\n{}]*?)? ?}})", c):
                    z = f"{x[2]}/{x[3]}"
                    if is_old_or_not_in_archive(x[0], z, archive):
                        continue
                    text = text.replace(x[5], "")
            elif archive and t == "Databank":
                for x in re.findall(r"(\{\{" + t + r"\|(url=)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]*?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[2], archive):
                        continue
                    text = text.replace(x[4], "")
            elif archive:
                for x in re.findall(r"(\{\{" + t + r"\|(subdomain=|username=)([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[2], archive) or "|url=" in x[0]:
                        continue
                    text = text.replace(x[4], "")
                for x in re.findall(r"(\{\{" + t + r"\|(.*?\|)?(url|id|a?l?t?link)=([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                    if is_old_or_not_in_archive(x[0], x[3], archive) or x[3].lower() in YEARLY:
                        continue
                    text = text.replace(x[5], "")
                if t in ["Bluesky", "Twitter", "Threads"]:
                    for x in re.findall(r"(\{\{" + t + r"\|[^\n{}|]*?\|((post|statuse?s?)/[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+?)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                        if is_old_or_not_in_archive(x[0], x[1], archive) or x[1].lower() in YEARLY:
                            continue
                        text = text.replace(x[4], "")
                else:
                    for x in re.findall(r"(\{\{" + t + r"\|((?!(url|id|a?l?t?link)=)[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?(\|archivedate=[0-9]+-[0-9-]+?)? ?\|archive(url|date|file[0-9]?)=([^\n{}|]+?) ?)(\|[^\n{}]*?)? ?}})", c):
                        if is_old_or_not_in_archive(x[0], x[1], archive) or x[1].lower() in YEARLY:
                            continue
                        text = text.replace(x[4], "")
    return text, archive_data
