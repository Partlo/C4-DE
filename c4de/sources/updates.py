import codecs

from pywikibot import Site, Page, Category, showDiff
import re
from datetime import datetime
from typing import List, Tuple, Dict

from c4de.sources.engine import extract_item, FullListData, build_template_types


def list_all_infoboxes(site):
    results = []
    for p in Category(site, "Category:Infobox templates").articles(recurse=True):
        if "/preload" in p.title():
            continue
        results.append(p.title(with_ns=False).lower().replace("_", " "))
    return results


def extract_release_date(title, text):
    date_strs = []
    m = re.search("\|(publish date|publication date|airdate|release date|released|published)=(?P<d1>.*?)(?P<r1><ref.*?)?\n(\*(?P<d2>.*?)(?P<r2><ref.*?)?\n)?(\*(?P<d3>.*?)(?P<r3><ref.*?)?\n)?", text)
    if m:
        for i in range(1, 4):
            if m.groupdict()[f"d{i}"]:
                d = m.groupdict()[f"d{i}"].replace("[", "").replace("]", "").replace("*", "").strip().replace(',', '')
                d = re.sub("&ndash;[A-z]+ [0-9\|]+", "", d)
                d = re.sub("([A-z]+ ?[0-9]*) ([0-9]{4})( .*?)$", "\\1 \\2", d)
                date_strs.append((d.split("-")[0], m.groupdict().get(f"r{i}")))

    page_dates = []
    for d, r in date_strs:
        if d and d.lower() != "none" and d.lower() != "future" and d.lower() != "canceled":
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


SOURCE_INFOBOXES = ["activity book", "magazine", "magazine article", "magazine department", "music", "toy line",
                    "reference book", "web article"]
APP_INFOBOXES = ["comic book", "comic story", "video game", "graphic novel"]
EXTRA_INFOBOXES = ["comic series", "book series", "television series", "comic story arc", "television season"]
APP_CATEGORIES = ["Future audiobooks", "Future films", "Future short stories", "Future novels",
                  "Future television episodes"]

INFOBOX_SKIP = ["character", "oou company", "person", "comic collection", "web article", "website"]
SERIES_SKIP = ["comic story arc", "comic series", "television series", "television season", "book series", "magazine department", "magazine series"]


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
    elif "Category:Canon storybooks" in text:
        return "Appearances"
    return "Sources"


def identify_infobox(t, infoboxes):
    for i in infoboxes:
        if f"{{{{{i.lower()}\n" in t.lower() or f"{{{{{i.lower()}|" in t.lower():
            return i
        elif f"{{{{{i.replace(' ', '_').lower()}\n" in t.lower() or f"{{{{{i.replace(' ', '_').lower()}|" in t.lower():
            return i
    return None


def analyze_page(page, category, infobox):
    text = page.get()
    dates = extract_release_date(page.title(), text)
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


def get_future_products_list(site: Site, infoboxes=None):
    cat = Category(site, "Future products")
    infoboxes = infoboxes or list_all_infoboxes(site)
    results = []
    for page in cat.articles():
        if page.title().startswith("List of") or page.title().startswith("Timeline of"):
            continue
        infobox = identify_infobox(page.get(), infoboxes)
        results.append(analyze_page(page, None, infobox))

    for c in cat.subcategories():
        for page in c.articles():
            if page.title().startswith("List of") or page.title().startswith("Timeline of"):
                continue
            elif c.title() == "Category:Future events" and len(page.title()) == 4 and page.title().startswith("20"):
                continue
            infobox = identify_infobox(page.get(), infoboxes)
            results.append(analyze_page(page, c.title(), infobox))
    return results


def parse_page(p: Page, types):
    unique = {}
    full = {}
    target = {}
    for i, line in enumerate(p.get().splitlines()):
        if line and not line.startswith("==") and "/Header}}" not in line:
            z = re.search("[\*#](.*?): (D: )?(.*?)$", line)
            if z:
                date = z.group(1)
                item = z.group(3)
                c = ''
                if "{{C|" in item:
                    cr = re.search("({{C\|([Nn]on-canon|[Rr]epublished|[Uu]nlicensed)}})", item)
                    if cr:
                        c = ' ' + cr.group(1)
                        item = item.replace(cr.group(1), '').strip()
                x = extract_item(item, False, p.title(), types, master=True)
                if x:
                    if x.template == "SWCT" and not x.target:
                        x.target = x.card
                    x.index = i
                    x.department = z.group(2) or ''
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
        if d.year > 2030:
            continue
        if t == "day":
            if master == d.strftime("%Y-%m-%d"):
                return True
        elif t == "month":
            if master == d.strftime("%Y-%m-XX"):
                return True
        elif t == "year":
            if master == d.strftime("%Y-XX-XX"):
                return True
    return False


def build_tracked(a, d, tracked):
    tracked.add(a.replace('&#61;', '=').replace('&hellip;', '…'))
    for i in d:
        if i.parent:
            tracked.add(i.parent.replace('&#61;', '=').replace('&hellip;', '…'))


def search_for_missing(site, appearances, sources):
    infoboxes = list_all_infoboxes(site)
    tracked = set()
    for a, d in appearances.target.items():
        build_tracked(a, d, tracked)
    for a, d in sources.target.items():
        build_tracked(a, d, tracked)
    print(f"Analyzing media category with {len(tracked)} tracked")

    start = datetime.now()
    not_found = []
    cats_checked, pages_checked = {"Category:Computer and video games by year"}, set()
    for c in Category(site, "Ignored categories for Source Engine traversal").subcategories():
        for p in c.articles(namespaces=0):
            pages_checked.add(p.title())
        for sc in c.subcategories(recurse=True):
            cats_checked.add(sc.title())
            for p in sc.articles(namespaces=0):
                pages_checked.add(p.title())

    counts = {"total": 0, "found": 0}
    for c in Category(site, "Star Wars media by type").subcategories():
        check_category(c, cats_checked, pages_checked, tracked, infoboxes, not_found, counts)

    for c in Category(site, "Trading cards").subcategories():
        check_category(c, cats_checked, pages_checked, tracked, infoboxes, not_found, counts)

    finish = datetime.now()
    print(f"Found {counts['found']} in {(finish - start).seconds} seconds")
    return not_found


def check_category(c: Category, cats_checked, pages_checked, tracked, infoboxes, not_found, counts):
    if c.title() in cats_checked:
        return
    cats_checked.add(c.title())

    if c.title().endswith(" writers") or c.title().endswith(" artists") or c.title().endswith(" actors") \
            or c.title().endswith(" authors") or c.title().endswith(" trade paperbacks"):
        return
    elif any(cc.title(with_ns=False) == "Ignored categories for Source Engine traversal" for cc in c.categories()):
        return

    for p in c.articles(namespaces=0):
        try:
            # if counts["total"] % 50 == 0:
            #     print(counts["total"], counts["found"], p.title())
            counts["total"] += 1
            if p.namespace().id != 0 or p.title() in tracked or p.title() in pages_checked or not p.exists() or p.isRedirectPage():
                continue
            pages_checked.add(p.title())

            t = p.get()
            inf = identify_infobox(t, infoboxes) or 'article'
            if "Game Book" in p.title() or ("Young Jedi Adventures episodes" in c.title() and " / " in p.title()):
                continue
            elif inf in INFOBOX_SKIP:
                # print(f"Skipping {inf} article: {p.title()} in {c.title()}")
                continue
            elif inf in SERIES_SKIP or "(series)" in p.title() or p.title() == "Star Wars App":
                continue
            elif "{{Author-stub" in t or "{{Bio-stub" in t or "{{Author-stub" in t:
                # print(f"Skipping person article: {p.title()} in {c.title()}")
                continue
            elif inf == "toy line" and p.title().startswith("LEGO"):
                continue
            elif f"[[{c.title()}| " in t or f"[[{c.title()}|*" in t or f"[[Category:{p.title()}| " in t:
                # print(f"Skipping root page {p.title()} for {c.title()}")
                continue
            else:
                print(f"Found {inf}: {p.title()}")
                counts["found"] += 1
                not_found.append(analyze_page(p, c.title(), inf))
        except Exception as e:
            print(p.title(), e)

    for sc in sorted(list(c.subcategories()), key=lambda a: not a.title().endswith("by type")):
        check_category(sc, cats_checked, pages_checked, tracked, infoboxes, not_found, counts)

    return not_found


def handle_results(site, results: List[FutureProduct], save=True):
    types = build_template_types(site)
    extra_page = Page(site, "Wookieepedia:Appearances/Extra")
    extra = parse_page(extra_page, types)
    l_app_page = Page(site, "Wookieepedia:Appearances/Legends")
    l_apps = parse_page(l_app_page, types)
    c_app_page = Page(site, "Wookieepedia:Appearances/Canon")
    c_apps = parse_page(c_app_page, types)
    l_src_page = Page(site, "Wookieepedia:Sources/Legends/General/2010s")
    l_srcs = parse_page(l_src_page, types)
    c_src_page = Page(site, "Wookieepedia:Sources/Canon/General")
    c_srcs = parse_page(c_src_page, types)
    sets_page = Page(site, "Wookieepedia:Sources/CardSets")
    sets = parse_page(sets_page, types)

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

    build_new_page(c_app_page, c_apps, "Appearances|False", new_items, changed_dates, True, save)
    build_new_page(l_app_page, l_apps, "Appearances|True", new_items, changed_dates, True, save)

    build_new_page(c_src_page, c_srcs, "Sources|False", new_items, changed_dates, True, save)
    build_new_page(l_src_page, l_srcs, "Sources|True", new_items, changed_dates, True, save)

    build_new_page(extra_page, extra, "Extra", new_items, changed_dates, True, save)
    build_new_page(sets_page, sets, "CardSets", new_items, changed_dates, True, save)


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
    new_items = all_new.get(key) or []
    changed = all_changed.get(key) or {}
    if not new_items:
        return

    final = []
    for i in new_items:
        t = f"''[[{i.page.title()}]]''"
        t = re.sub("''\[\[((.*?) \(.*?\)( [0-9]+)?)\]\]''", "[[\\1|''\\2''\\3]]", t)
        t = re.sub("''\[\[(.*?)\|(((?!'').)*?) ([0-9]+)\]\]''", "[[\\1|''\\2'' \\3]]", t)
        t = re.sub("''\[\[([^\|\]]+?) ([0-9]+)\]\]''", "[[\\1 \\2|''\\1'' \\2]]", t)
        if "[[Untitled" in t:
            t = t[2:-2]
        d = build_date(i.dates)
        final.append([t, prep_date(d), 100])
    for x, i in data.full.items():
        d = i.date
        if i.target in changed:
            d = build_date(changed[i.target].dates)
        final.append([i.department + i.original + i.extra, prep_date(d), i.index])

    start_date = DATES.get(page.title())
    section = None
    lines = ["<noinclude>{{Wookieepedia:Sources/Header}}</noinclude>"]
    post = re.search("==Post-([0-9]+)==", page.get())
    post = post.group(1) if post else None
    post_found = False
    for f in sorted(final, key=lambda a: (a[1], (a[2] or 200), a[0])):
        txt, d, i = f[0], f[1], f[2]
        if use_sections:
            if d.startswith("1") or d.startswith("2"):
                if post_found:
                    pass
                elif start_date and not section:
                    section = f"Pre-{start_date}"
                    lines.append(f"=={section}==")
                elif start_date and d[:4] == start_date:
                    start_date = None
                    section = d[:4]
                    lines.append(f"\n=={section}==")
                elif not start_date and d[:4] != section:
                    if section == post:
                        section = f"Post-{post}"
                        post_found = True
                    else:
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
    else:
        showDiff(page.get(), new_txt, context=2)


def analyze():
    site = Site(user="C4-DE Bot")
    results = get_future_products_list(site)
    handle_results(site, results)


if __name__ == "__main__":
    analyze()
