import codecs

from pywikibot import Site, Page, Category
import re
from datetime import datetime
from typing import List, Tuple, Dict

from c4de.sources.engine import extract_item, FullListData


def extract_release_date(title, text):
    date_strs = []
    m = re.search("\|(publish date|publication date|airdate|release date|released|published)=(?P<d1>.*?)(?P<r1><ref.*?)?\n(\*(?P<d2>.*?)(?P<r2><ref.*?)?\n)?(\*(?P<d3>.*?)(?P<r3><ref.*?)?\n)?",
            text)
    if m:
        for i in range(1, 4):
            if m.groupdict()[f"d{i}"]:
                d = m.groupdict()[f"d{i}"].replace("[", "").replace("]", "").replace("*", "").strip().replace(',', '')
                d = re.sub("&ndash;[A-z]+ [0-9\|]+", "", d)
                d = re.sub("([A-z]+ ?[0-9]*) ([0-9]{4})( .*?)$", "\\1 \\2", d)
                date_strs.append((d.split("-")[0], m.groupdict().get(f"r{i}")))

    page_dates = []
    for d, r in date_strs:
        if d:
            t, z = None, None
            for x, df in {"day": "%B %d %Y", "month": "%B %Y", "year": "%Y"}.items():
                try:
                    z = datetime.strptime(d, df)
                    t = x
                    page_dates.append((t, z, r))
                    break
                except Exception:
                    pass
            if not z:
                print(f"Unrecognized date string on {title}: {d}")
    return page_dates


SOURCE_INFOBOXES = ["Activity book", "Magazine", "Magazine article", "Magazine department", "Music", "Toy line",
                    "Reference book", "Web article"]
APP_INFOBOXES = ["Comic book", "Comic story", "Video game", "Graphic novel"]
EXTRA_INFOBOXES = ["Comic series", "Book series", "Television series", "Comic story arc", "Television season"]
APP_CATEGORIES = ["Future audiobooks", "Future films", "Future short stories", "Future novels",
                  "Future television episodes"]


def determine_app_or_source(text, category, infobox):
    if "|anthology=1" in text or "is an upcoming anthology" in text:
        return "Extra"
    elif "|is_appearance=1" in text:
        return "Appearances"
    elif category == "Future trade paperbacks":
        return "SKIP"
    elif infobox == "Card game" or infobox == "Miniatures game":
        return "CardSets"
    elif infobox in EXTRA_INFOBOXES:
        return "Extra"
    elif infobox in APP_INFOBOXES:
        return "Appearances"
    elif infobox in SOURCE_INFOBOXES:
        return "Sources"
    elif category in APP_CATEGORIES:
        return "Appearances"
    return "Sources"


def analyze_page(page, category):
    text = page.get()
    dates = extract_release_date(page.title(), text)
    m = re.search("{{([A-z _]+)\n?(\|.*?\n)?\|image=", text)
    infobox = m.group(1) if m else None
    c = re.search("{{Top.*?\|(can|leg|ncc|ncl)[\|\}]", text)
    ct = c.group(1) if c else None
    t = determine_app_or_source(text, (category or '').replace("Category:", ""), (infobox or '').replace("_", " "))
    # print(t, page.title(), (category or '').replace("Category:", ""), (infobox or '').replace("_", " "))
    return FutureProduct(page, category, dates, infobox, ct, t)


class FutureProduct:
    def __init__(self, page: Page, category: str, dates: List[Tuple[str, datetime, str]], infobox: str, canon_type: str, item_type: str):
        self.page = page
        self.category = category
        self.dates = dates
        self.infobox = infobox
        self.canon_type = canon_type
        self.item_type = item_type


def get_future_products_list(site: Site):
    cat = Category(site, "Future products")
    results = []
    for page in cat.articles():
        if page.title().startswith("List of") or page.title().startswith("Timeline of"):
            continue
        results.append(analyze_page(page, None))

    for c in cat.subcategories():
        for page in c.articles():
            if page.title().startswith("List of") or page.title().startswith("Timeline of"):
                continue
            elif c.title() == "Category:Future events" and len(page.title()) == 4 and page.title().startswith("20"):
                continue
            results.append(analyze_page(page, c.title()))
    return results


def parse_page(p: Page):
    unique = {}
    full = {}
    target = {}
    for i, line in enumerate(p.get().splitlines()):
        if line and not line.startswith("==") and not "/Header}}" in line:
            z = re.search("[\*#](.*?): (D: )?(.*?)( {{C\|d: .*?}})?$", line)
            if z:
                date = z.group(1)
                item = z.group(3)
                c = ''
                if "{{C|" in item:
                    cr = re.search("({{C\|([Rr]epublished|[Uu]nlicensed)}})", item)
                    if cr:
                        c = ' ' + cr.group(1)
                        item = item.replace(cr.group(1), '').strip()
                x = extract_item(item, False, p.title(), master=True)
                if x:
                    if x.template == "SWCT" and not x.target:
                        x.target = x.card
                    x.index = i
                    x.canon = "/Canon" in p.title()
                    x.date = date
                    x.extra = c
                    full[x.full_id()] = x
                    unique[x.unique_id()] = x
                    if x.target:
                        if x.target not in target:
                            target[x.target] = []
                        target[x.target].append(x)
            else:
                print(f"Cannot parse line: {line}")

    return FullListData(unique, full, target, set())


def dates_match(dates: List[Tuple[str, datetime, str]], master):
    for t, d, r in dates:
        if t == "day":
            if master == d[:10].strftime("%Y-%m-%d"):
                return True
        elif t == "month":
            if master == d[:10].strftime("%Y-%m-XX"):
                return True
        elif t == "year":
            if master == d[:10].strftime("%Y-XX-XX"):
                return True
    return False


def handle_results(site, results: List[FutureProduct]):
    extra_page = Page(site, "Wookieepedia:Appearances/Extra")
    extra = parse_page(extra_page)
    l_app_page = Page(site, "Wookieepedia:Appearances/Legends")
    l_apps = parse_page(l_app_page)
    c_app_page = Page(site, "Wookieepedia:Appearances/Canon")
    c_apps = parse_page(c_app_page)
    l_src_page = Page(site, "Wookieepedia:Sources/Legends/General/2010s")
    l_srcs = parse_page(l_src_page)
    c_src_page = Page(site, "Wookieepedia:Sources/Canon/General")
    c_srcs = parse_page(c_src_page)
    sets_page = Page(site, "Wookieepedia:Sources/CardSets")
    sets = parse_page(sets_page)

    master_data = {"Legends Appearances": l_apps, "Canon Appearances": c_apps, "Legends Sources": l_srcs,
                   "Canon Sources": c_srcs, "Extra": extra, "CardSets": sets}

    new_items = {}
    changed_dates = {}
    for i in results:
        is_legends = (i.canon_type == 'leg' or i.canon_type == 'ncl') if i.canon_type else False
        z = f"{i.item_type}|{is_legends}"
        if i.item_type == "CardSets" or i.item_type == "Extra":
            z = i.item_type

        found = False
        for t, data in master_data.items():
            if i.page.title() in data.target:
                found = True
                if i.item_type != t.split(" ")[-1]:
                    print(f"{i.item_type}: {i.page.title()} is classified as {t}")
                if i.dates and not dates_match(i.dates, data.target[i.page.title()][0].date):
                    if z not in changed_dates:
                        changed_dates[z] = {}
                    changed_dates[z][i.page.title()] = i
                    print(f"New date {i.dates[0][1]} found for {i.page.title()} (previously {data.target[i.page.title()][0].date})")
        if found:
            continue
        elif i.item_type == "SKIP":
            print(f"Skipping {i.page.title()}")
        else:
            print(f"Unknown: {i.item_type}: {i.page.title()}")
            if z not in new_items:
                new_items[z] = []
            new_items[z].append(i)

    build_new_page(c_app_page, c_apps, "Appearances|False", new_items, changed_dates, True, True)
    build_new_page(l_app_page, l_apps, "Appearances|True", new_items, changed_dates, True, True)

    build_new_page(c_src_page, c_srcs, "Sources|False", new_items, changed_dates, True, True)
    build_new_page(l_src_page, l_srcs, "Sources|False", new_items, changed_dates, True, True)

    build_new_page(extra_page, extra, "Extra", new_items, changed_dates, True, True)
    build_new_page(sets_page, sets, "CardSets", new_items, changed_dates, True, True)


DATES = {"Wookieepedia:Appearances/Legends": "1977", "Wookieepedia:Appearances/Canon": "2008",
         "Wookieepedia:Sources/Canon/General": "2014"}


def prep_date(d):
    return re.sub("-([0-9])$", "-0\\1", re.sub("-([0-9])([:-])", "-0\\1\\2", d))


def build_date(dates):
    if dates and dates[0][0] == "day":
        return dates[0][1].strftime('%Y-%m-%d')
    elif dates and dates[0][0] == "month":
        return f"{dates[0][1].strftime('%Y-%m')}-XX"
    elif dates and dates[0][0] == "year":
        return f"{dates[0][1].strftime('%Y')}-XX-XX"
    return "Future"


def build_new_page(page, data: FullListData, key, all_new: Dict[str, List[FutureProduct]], all_changed: Dict[str, Dict[str, FutureProduct]], use_sections, save=False):
    new_items = all_new.get(key)
    changed = all_changed.get(key) or {}
    if not new_items:
        return

    final = []
    for i in new_items:
        t = f"''[[{i.page.title()}]]''"
        t = re.sub("''\[\[((.*?) \(.*?\))\]\]''", "[[\\1|''\\2'']]", t)
        t = re.sub("''\[\[(.*?)\|(.*?) ([0-9]+)\]\]''", "[[\\1|''\\2'' \\3]]", t)
        t = re.sub("''\[\[([^\|\]]+?) ([0-9]+)\]\]''", "[[\\1 \\2|''\\1'' \\2]]", t)
        if "[[Untitled" in t:
            t = t[2:-2]
        d = build_date(i.dates)
        final.append((t, prep_date(d), 100))
    for x, i in data.full.items():
        d = i.date
        if i.target in changed:
            d = build_date(changed[i.target].dates)
        final.append((i.original, prep_date(d), i.index))

    start_date = DATES.get(page.title())
    section = None
    lines = []
    for txt, d, i in sorted(final, key=lambda a: (a[1], (a[2] or 200), a[0])):
        if use_sections:
            if d.startswith("1") or d.startswith("2"):
                if start_date and not section:
                    section = f"Pre-{start_date}"
                    lines.append(f"=={section}==")
                elif start_date and d[:4] == start_date:
                    start_date = None
                    section = d[:4]
                    lines.append(f"\n=={section}==")
                elif not start_date and d[:4] != section:
                    section = d[:4]
                    lines.append(f"\n=={section}==")
            elif section:
                section = None
                lines.append("\n==Other==")
        lines.append(f"#{d}: {txt}")

    new_txt = re.sub("(?<![\n=])\n==", "\n\n==", re.sub("\n\n+", "\n\n", "\n".join(lines))).strip()
    with codecs.open("C:/Users/Michael/Documents/projects/C4DE/c4de/sources/test.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if save:
        page.put(new_txt, "Updating Source Engine Masterlist with new future products")


def analyze():
    site = Site(user="C4-DE Bot")
    results = get_future_products_list(site)
    handle_results(site, results)


if __name__ == "__main__":
    analyze()
