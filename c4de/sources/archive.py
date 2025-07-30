from c4de.sources.engine import load_template_types
from pywikibot import Page, Site, Category, showDiff
import re
import requests
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
    for u, d in re.findall("\[['\"](.+?)/*?['\"]] ?= ?['\"]?(.*?)['\"]?[, ]*\n", page.get()):
        if u.startswith("/") and u != "/":
            u = u[1:]
        if template == "Rebelscum":
            u = re.sub("^(https?://)?w*\.?rebelscum\.com/", "", u)
        archive[u.replace("\\'", "'").replace("{{=}}", "=").lower()] = d
    return archive


def build_missing_and_new(page, types, archives, new_data, skip):
    if not new_data:
        new_data = {}
    text = page.get().replace("Youtube", "YouTube").replace("|url=|", "|").replace("|video=|", "|")
    actual = []
    for tx in page.templates():
        if tx.isRedirectPage():
            t1 = tx.title(with_ns=False)
            t2 = tx.getRedirectTarget().title(with_ns=False)
            text = text.replace("{{" + t1 + "|", "{{" + t2 + "|")
            if " " in t1:
                text = text.replace("{{" + t1.replace(" ", "_") + "|", "{{" + t2 + "|")
            continue
        if not tx.title().startswith("Template:") or tx.title(with_ns=False) in skip:
            continue
        elif tx.title(with_ns=False) in types["Nav"]:
            continue
        elif tx.title(with_ns=False) in types["Dates"]:
            continue
        actual.append(tx)
    for tx in actual:
        template = tx.title(with_ns=False)
        youtube = "YouTube" in template or types.get(template.lower()) == "YT"
        archive_template = "YouTube" if youtube else template
        archive_template = "SideshowCite" if template in ["HotToysCite", "IronStudiosCite"] else archive_template
        if archive_template not in archives:
            if types.get(template.lower()) not in ["Web", "YT", "DB", "Publisher", "Commercial", "External", "Social", "Cards", "Toys"]:
                print(f"Skipping {types.get(template.lower())} template {template}")
                skip.append(tx.title(with_ns=False))
                continue
            archives[archive_template] = parse_archive(page.site, archive_template)
        if archives.get(archive_template) is None:
            print(f"No archive found for {tx.title()}")
            skip.append(tx.title(with_ns=False))
            continue
        if youtube:
            zx = [(i[0], i[4]) for i in re.findall("(\{\{" + template + "\|((subdomain|channel|username|name|text|wplink|link|series|parameter)=.*?\|)*?(video=)?([^|\n}=]+?)([&?].*?)?(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
            for i in re.findall("(\{\{" + template + "\|(.*?\|)?channel=([^|\n}=]+?)(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text):
                if "video=" not in i[0]:
                    zx.append((i[0], i[2]))
            if not zx:
                for z in re.findall("\{\{YouTube\|.*?}}", text):
                    print(z)
        elif template == "Databank":
            zx = [(i[0], i[2]) for i in re.findall("(\{\{Databank\|(url=)?([^|\n}]+?)(\|.*?)(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
        else:
            zx = [(i[0], i[3]) for i in re.findall("(\{\{" + template + "(\|[^\n}]*?)?\|(url|link|altlink)=/?([^|\n}]+?(\{\{=}})?[^|\n}]*?)/*(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text)]
            if template == "Blogspot" or template == "DeviantArt" or template == "Tumblr" or template == "ArtStation":
                for i in re.findall("(\{\{" + template + "(\|[^\n}]*?)?\|(subdomain|username)=/?([^|\n}]+?)/*(\|[^{]*?(\{\{[^}]*?}}[^{]*?)?)?}})", text):
                    if "|url=" not in i[0]:
                        zx.append((i[0], i[3]))
        for a, x in zx:
            if "na=video file" in a:
                continue
            x = x.replace("{{=}}", "=").strip()
            if re.search("^([0-9]|[a-z]+)=(...+?)$", x):
                x = re.sub("^([0-9]|[a-z]+)=", "", x)

            if "oldversion" in a or "nobackup=1" in a:
                continue
            if template != "Rebelscum" and ("rebelscum" in a or ("|link=" in a and template in ["Galoob", "KennerCite"])):
                if "Rebelscum" not in archives:
                    archives["Rebelscum"] = parse_archive(page.site, "Rebelscum")

                if x.lower() in archives[archive_template] or x.lower().replace("http://", "https://") in archives[archive_template] or x.lower().replace("https://", "http://") in archives[archive_template]:
                    continue

                if archives.get("Rebelscum") and template != "Topps":
                    y = re.sub("^.*?rebelscum\.com/", "", x)
                    if y.lower() in archives.get("Rebelscum", {}):
                        continue
                    elif y.lower() in new_data.get(template, {}) or y.lower() in new_data.get("Rebelscum", {}):
                        continue
                    check_url(y, archives, "Rebelscum", new_data, a)
                    if "Rebelscum" in new_data and y in new_data["Rebelscum"]:
                        continue

            check_url(x, archives, archive_template, new_data, a)

    return new_data


def check_url(x, archives, template, new_data, a):
    if x.lower() in archives[template] or x.lower().replace("http://", "https://") in archives[template] or x.lower().replace("https://", "http://") in archives[template]:
        return

    if template not in new_data:
        new_data[template] = {}
    elif any(k.lower() == x.lower() for k in new_data[template]):
        return
    y = re.search("\|archiveurl=(.*?)(\|.*?)?}}", a)
    if not (y and y.group(1)):
        y = re.search("\|archivedate=(.*?)(\|.*?)?}}", a)

    if not y and template == "Hyperspace":
        return
    print("NEW:" if y is None else "Found:", template, x, a, y)
    new_data[template][x] = {"value": y.group(1) if y and y.group(1) else None, "full": a}


def handle_parameters(ux, a, param):
    if "{{{" + param + "|" in ux and f"|{param}=" in a:
        b = re.search("\|" + param + "=(.*?)(\|.*?)?}}", a)
        if b:
            ux = re.sub("\{\{\{" + param + "\|(\{\{.*?}}})?.*?}}}", b.group(1), ux)
    if "{{{" + param + "|" in ux:
        ux = re.sub("\{\{\{" + param + "\|((\{\{.*?}}})?.*?)}}}", "\\1", ux)
    return ux


def handle_if_statement(ux):
    past = f"{ux}-1"
    result = f"{ux}"
    while (ux.count("#if:") + ux.count("#ifeq:")) > 0 and past != result:
        past = f"{result}"
        z = re.search("^.*(\{\{#if:(.*?)\|([^|{}]*)\|([^|{}]*)}})", result)
        if z and "{{" not in z.group(2):
            if z.group(2).strip():
                result = result.replace(z.group(1), z.group(3))
            else:
                result = result.replace(z.group(1), z.group(4))
        z = re.search("^.*(\{\{#ifeq:(.*?)\|([^|{}]*)\|([^|{}]*)\|([^|{}]*)}})", result)
        if z and "{{" not in z.group(3):
            if z.group(2).strip() == z.group(3).strip():
                result = result.replace(z.group(1), z.group(4))
            else:
                result = result.replace(z.group(1), z.group(5))
    while ux.count("#switch") > 0 and past != result:
        past = f"{result}"
        z = re.search("\{\{#switch:([^{}]*?)\|([^{}]*)*?}}", result)
        if z:
            y = {x.split("=", 1)[0].strip(): x.split("=", 1)[1].strip() for x in z.group(2).split("|")}
            if z.group(2) in y:
                result = result.replace(z.group(0), y[z.group(2)])
            else:
                result = result.replace(z.group(0), y.get("#default", ""))
    return result


def build_to_check(site, data):
    to_check = {}
    for t, urls in data.items():
        to_check[t] = {}
        if "YouTube" in t:
            for k, v in urls.items():
                if not (v and v.get('url')):
                    to_check[t][k] = f"https://www.youtube.com/watch?v={k}"
        else:
            tx = Page(site, f"Template:{t}").get()
            if "ToyCitation" in tx:
                x = re.search("\|baseUrl=(.*?)\n", tx)
                y = re.search("\|link=(.*?[^\]])\n", tx)
                z = re.search("\|url=(.*?)\n", tx)
                for k, v in urls.items():
                    if not (v and v.get('value')):
                        if "|link=" in v['full'] and x and y:
                            ux = x.group(1) + "/" + y.group(1)
                        elif z:
                            ux = z.group(1)
                        else:
                            print(f"unknown: {t} -> {x}, {y}, {z}, {v['full']}")
                            continue

                        for px in set(re.findall("\{\{\{(.*?)(?=[|}])", ux)):
                            ux = handle_parameters(ux, v['full'], px)
                            print(ux, px)
                        new_url = handle_if_statement(ux)
                        print(k, new_url)
                        to_check[t][k] = new_url
            else:
                y = re.search("\|base_url=(.*?)\n", tx)
                z = re.search("\|target_url=(.*?)\{\{\{(url|1)", tx)
                w = re.search("\|full_url=(.*?)\n", tx)
                if y and z:
                    for k, v in urls.items():
                        ux = y.group(1)
                        if not (v and v.get('value')):
                            for px in re.findall("\{\{\{(.*?)(?=[|}])", ux):
                                ux = handle_parameters(ux, v['full'], px)
                            ux = handle_if_statement(ux)
                            new_url = f"{ux}/{k}" if not (ux.endswith("/") or k.startswith("/")) else f"{ux}{k}"
                            print(k, new_url)
                            to_check[t][k] = new_url
                elif w:
                    for k, v in urls.items():
                        ux = w.group(1)
                        if not (v and v.get('value')):
                            for px in re.findall("\{\{\{(.*?)(?=[|}])", ux):
                                ux = handle_parameters(ux, v['full'], px)
                            new_url = handle_if_statement(ux)
                            print(k, new_url)
                            to_check[t][k] = new_url

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
            x = [k for k in new_items.keys() if f"['{k.lower()}']" in line.lower() or f'["{k.lower()}"]' in line.lower()]
            for i in x:
                print(f"URL {i} is already archived")
                skip.append(i)
            if not x and line.strip().startswith("}"):
                if "[" in new_text[-1] and not new_text[-1].strip().endswith(","):
                    new_text[-1] = new_text[-1].rstrip() + ","
                for k, v in sorted(new_items.items()):
                    if k in skip:
                        continue
                    u = k.replace('{{=}}', '=').lower()
                    if u.startswith('/') and len(u) > 1:
                        u = u[1:]
                    if u.endswith('/') and len(u) > 1:
                        u = u[:-1]
                    new_text.append(f'\t["{u}"] = "{v}",')
                found = True
        new_text.append(line)
    return new_text


def add_data_to_archive(site, data, archives, save=True):
    for t, new_urls in data.items():
        p = Page(site, f"Module:ArchiveAccess/{t}")
        if not p.exists():
            continue
        text = p.get()
        archive = archives.get(t, {})
        to_add = {k: v['value'] for k, v in new_urls.items() if v and v.get('value') and k not in archive}
        new_text = build_archive_module_text(text, to_add)
        if text != "\n".join(new_text):
            if save:
                p.put("\n".join(new_text), "Recording missing archivedates")
            else:
                showDiff(text, "\n".join(new_text), context=2)


def do_work(site, types=None):
    types = types or load_template_types(site)
    archives = {}
    data = {}
    skip, done = [], []
    cx = list(Category(site, "Unarchived URLs").subcategories())
    for c in [Category(site, "Pages with missing shared permanent archival links"), *cx]:
        for p in c.articles():
            if p.title() in done:
                continue
            data = build_missing_and_new(p, types, archives, data, skip)
            done.append(p.title())

    to_check = build_to_check(site, data)
    new_info = populate_archives(to_check)

    for t, dx in new_info.items():
        for k, v in dx.items():
            if v:
                y = data[t].get(k, {})
                y['value'] = v
                data[t][k] = y


def clean_archive_usages(page: Page, text, archive_data: dict, redo=False):
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
    chunks = text.split("</ref>")
    for t in templates_to_check:
        tx = "SWYouTube" if t in ["ThisWeek", "HighRepublicShow", "StarWarsShow"] else t
        tx = "Topps" if t in ["ToppsNow", "ToppsLivingSet", "ForceAttax"] else t
        tx = "Blogspot" if tx == "DailyswCite" else tx
        if tx not in archive_data:
            archive_data[tx] = parse_archive(page.site, tx)
        archive = archive_data.get(tx) or {}
        if not archive:
            continue

        for c in chunks:
            if archive and t == "Rebelscum":
                for x in re.findall("(\{\{KennerCite\|(.*?\|)?link=(h?t?t?.*?rebelscum\.com/)?([^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url)=([^\n{}|]+?) ?)(\|[^\n{}]*?)?}})", c):
                    if "oldversion" in x[0] or x[3].lower() not in archive:
                        continue
                    # elif "nolive=" in x[0] and x[7] != archive[x[3].lower()]:
                    #     continue
                    text = text.replace(x[5], "").replace(f"link={x[2]}{x[3]}", f"link={x[3]}")
                for x in re.findall("(\{\{[A-z0-9 _]+\|(.*?\|)?(url|a?l?t?link)=([^\n{}|]*?rebelscum[^\n{}|]*?)/?(\|[^\n{}]*?)?( ?\|archive(date|url)=[^\n{}|]*? ?)(\|[^\n{}]*?)?}})", c):
                    if "nolive=" in x[0] or "oldversion" in x[0]:
                        continue
                    if re.sub("(https?://)?w*\.?rebelscum\.com/", "", x[3].lower()) not in archive:
                        continue
                    text = text.replace(x[5], "")
            elif archive and tx == "Blogspot":
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
    return text, archive_data
