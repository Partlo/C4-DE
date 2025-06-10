import codecs

from c4de.sources.domain import Item
from pywikibot import Site, Page, Category, showDiff
import re
from datetime import datetime
from typing import List, Tuple, Dict

from c4de.dates import extract_release_date, prep_date, build_date
from c4de.sources.engine import extract_item, FullListData, load_template_types
from c4de.sources.infoboxer import NEW_NAMES, load_infoboxes


SET_INFOBOXES = ["CardGame", "TabletopGame", "TradingCardSet", "ExpansionPack"]
SOURCE_INFOBOXES = ["ActivityBook", "MagazineIssue", "ReferenceMagazine", "MagazineArticle", "MagazineDepartment",
                    "Music", "ToyLine", "ReferenceBook", "WebArticle"]
APP_INFOBOXES = ["ComicBook", "ComicStory", "VideoGame", "GraphicNovel", "Audiobook", "ShortStory", "TelevisionEpisode"]
INFOBOX_SKIP = ["Character", "RealCompany", "Person", "WebArticle", "Website"]
SERIES_SKIP = ["MagazineDepartment", "MagazineSeries"]

APP_CATEGORIES = ["Future audiobooks", "Future films", "Future short stories", "Future novels",
                  "Future television episodes"]


def determine_app_or_source(text, category, infobox):
    if "|anthology=1" in text or "is an upcoming anthology" in text:
        return "Extra"
    elif "|is_appearance=1" in text:
        return "Appearances"
    elif category == "Future trade paperbacks" or infobox == "ComicCollection" or ":Book collections" in text:
        return "Collections"
    elif "series" in infobox.lower() or "season" in infobox.lower() or infobox == "ComicArc":
        return "Series"
    elif infobox == "Soundtrack":
        return "Soundtracks"
    elif infobox in INFOBOX_SKIP:
        return "SKIP"
    elif infobox in SET_INFOBOXES:
        return "CardSets"
    elif infobox in APP_INFOBOXES:
        return "Appearances"
    elif infobox in SOURCE_INFOBOXES:
        return "Sources"
    elif (category or "").replace("Category:", "") in APP_CATEGORIES:
        return "Appearances"
    elif "Category:Canon storybooks" in text:
        return "Appearances"
    return "Sources"


def identify_infobox(t, infoboxes):
    for i in infoboxes:
        if f"{{{{{i.lower()}\n" in t.lower() or f"{{{{{i.lower()}|" in t.lower():
            return i
    tx = re.sub("\{\{([A-z]+)[ _]([A-z]+)[ _]?([A-z]+?)(?=[|\n])", "{{\\1\\2\\3", t).lower()
    for i in infoboxes:
        if f"{{{{{i.lower()}\n" in tx or f"{{{{{i.lower()}|" in tx:
            return i
    for k, v in NEW_NAMES.items():
        if f"{{{{{k.lower()}\n" in tx or f"{{{{{k.lower()}|" in tx:
            return v
    return None


def analyze_page(page, text, category, infobox):
    dates, _ = extract_release_date(page.title(), text)
    if dates:
        now = datetime.now()
        if all(now > d[1] for d in dates):
            print(f"Skipping past ({dates[0][1].strftime('%Y-%m-%d')}) media: {page.title()}")
            return None
    c = re.search("{{Top.*?\|(can|leg|ncc|ncl|new|pre|btr|old|imp|reb|njo|lgc|inf)[|}]", text)
    ct = c.group(1) if c else None
    if ct in ["pre", "btr", "old", "imp", "reb", "new", "njo", "lgc", "inf"]:
        ct = "leg"
    t = determine_app_or_source(text, (category or '').replace("Category:", ""), infobox or '')
    if "audiobook)" in page.title():
        t = "Audiobooks"
    elif "soundtrack" in page.title().lower():
        t = "Soundtracks"
    print(t, page.title(), (category or '').replace("Category:", ""), infobox)
    return FutureProduct(page, category, dates, infobox, ct, t)


class FutureProduct:
    def __init__(self, page: Page, category: str, dates: List[Tuple[str, datetime, str]], infobox: str, canon_type: str, item_type: str):
        self.page = page
        self.category = category
        self.dates = dates
        self.infobox = infobox
        self.canon_type = canon_type
        self.item_type = item_type


MONTHS = {10: "A", 11: "B", 12: "C"}


def get_future_products_list(site: Site, infoboxes=None):
    cat = Category(site, "Future products")
    infoboxes = infoboxes or load_infoboxes(site)
    results = []
    unique = set()
    for page in cat.articles():
        if page.title().startswith("List of") or page.title().startswith("Timeline of"):
            continue
        elif page.title() in unique:
            continue
        t = page.get()
        infobox = identify_infobox(t, infoboxes)
        if should_check_product(infobox, t, page, cat.title()):
            x = analyze_page(page, t, None, infobox)
            if x:
                results.append(x)
                unique.add(page.title())

    now = datetime.now()
    start = MONTHS.get(now.month, str(now.month))
    for c in cat.subcategories():
        if "trade paperbacks" in c.title():
            continue
        for page in c.articles(startprefix=start if c.title(with_ns=False) == f"{now.year} releases" else None):
            if page.title().startswith("List of") or page.title().startswith("Timeline of"):
                continue
            elif page.title() in unique:
                continue
            elif c.title() == "Category:Future events":
                if len(page.title()) == 4 and page.title().startswith("20"):
                    continue
                elif any(x.title() == "Category:Official Star Wars conventions" for x in page.categories()):
                    continue
            t = page.get()
            infobox = identify_infobox(t, infoboxes)
            if should_check_product(infobox, t, page, c.title()):
                x = analyze_page(page, t, c.title(), infobox)
                if x:
                    results.append(x)
                    unique.add(page.title())
    return results


def parse_page(p: Page, types):
    text = p.get()
    for link in p.linkedPages():
        if link.exists() and link.isRedirectPage():
            x = link.getRedirectTarget()
            text = text.replace(f"[[{link.title()}|", f"[[{x.title()}|")
            text = text.replace(f"[[{link.title()}]]", f"[[{x.title()}]]")
            text = text.replace(f"|{link.title()}|", f"|{x.title()}|")
            text = text.replace(f"|{link.title()}" + "}", f"|{x.title()}" + "}")

    unique = {}
    full = {}
    target = {}
    for i, line in enumerate(text.splitlines()):
        parse_line(line, i, p, types, full, unique, target)

    return FullListData(unique, full, {}, target, {}, set(), set(), {})


def parse_line(line, i, p: Page, types, full, unique, target):
    if line and not line.startswith("==") and "/Header}}" not in line:
        z = re.search("[*#](.*?): (D: )?(.*?)$", line)
        if z:
            date = z.group(1)
            item = z.group(3)
            c = ''
            if "{{C|" in item:
                cr = re.search("({{C\|([Nn]on-canon|[Rr]epublished|[Uu]nlicensed)}})", item)
                if cr:
                    c = ' ' + cr.group(1)
                    item = item.replace(cr.group(1), '').strip()
            ab = ''
            x2 = re.search("\{\{[Aa]b\|.*?}}", item)
            if x2:
                ab = x2.group(0)
                item = item.replace(ab, '').strip()

            parenthetical = ''
            original_item = f"{item}"
            if "|p=" in item:
                pr = re.search("\|p=(.*?)(\|.*?)?}}", item)
                if pr:
                    parenthetical = pr.group(1)
                    item = item.replace(f"|p={parenthetical}", "").strip()

            x = extract_item(item, False, p.title(), types, master=True)
            if x:
                if x.original != original_item:
                    x.original = original_item
                x.index = i
                x.department = z.group(2) or ''
                x.canon = "/Canon" in p.title()
                x.date = date
                x.extra = f"{ab} {c}".strip()
                x.parenthetical = parenthetical
                if parenthetical and f"({parenthetical})" not in x.target:
                    x.target = f"{x.target} ({parenthetical})"
                full[x.full_id()] = x
                unique[x.unique_id()] = x
                if x.target:
                    if x.target not in target:
                        target[x.target] = []
                    target[x.target].append(x)
        else:
            print(f"Cannot parse line: {line}")


def dates_match(dates: List[Tuple[str, datetime, str]], master, infobox):
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
            elif infobox and "comic" in infobox.lower() and master.startswith(f"{d.year}-") and master.endswith("-XX"):
                return True
    return False


def compare_dates(title, text, target, items, mismatch, no_dates, infobox=None):
    dates, strs = extract_release_date(title, text)
    if dates:
        if not dates_match(dates, items[0].date, infobox):
            print(title, items[0].date, build_date(dates))
            mismatch[target] = (build_date(dates), items[0].date)
    elif items[0].date:
        no_dates[target] = (strs[0] if strs else None, items[0].date)
        print(f"No date? {items[0].date} -> {items[0].original}")


def compare_all_dates(site, by_target: Dict[str, List[Item]], mismatch, no_dates):
    for target, items in by_target.items():
        p = Page(site, target)
        if p.exists() and not p.isRedirectPage():
            compare_dates(p.title(), p.get(), target, items, mismatch, no_dates)
    return mismatch, no_dates


def build_tracked(a, d, tracked):
    tracked.add(a.replace('&#61;', '=').replace('&hellip;', '…').replace('&mdash;', '—'))
    for i in d:
        if i.parent:
            tracked.add(i.parent.replace('&#61;', '=').replace('&hellip;', '…'))


def search_for_missing(site, appearances, sources, infoboxes=None, check_dates=False) -> Tuple[List[FutureProduct], list, List[FutureProduct]]:
    infoboxes = infoboxes or load_infoboxes(site)
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
            if sc.title(with_ns=False) in ["Real-world albums"]:
                continue
            cats_checked.add(sc.title())
            for p in sc.articles(namespaces=0):
                pages_checked.add(p.title())

    counts = {"total": 0, "found": 0}
    diff_dates, collections = [], []
    for c in Category(site, "Media collections").subcategories():
        check_category(c, cats_checked, pages_checked, tracked, infoboxes, collections, diff_dates, counts,
                       appearances, sources, check_dates)

    for c in Category(site, "C4-DE media traversal").subcategories():
        check_category(c, cats_checked, pages_checked, tracked, infoboxes, not_found, diff_dates, counts, appearances,
                       sources, check_dates)

    finish = datetime.now()
    print(f"Found {counts['found']} in {(finish - start).seconds} seconds")
    return not_found, diff_dates, collections


def should_check_product(inf, t, p: Page, ct):
    if "Game Book" in p.title() or ("Young Jedi Adventures episodes" in ct and " / " in p.title()):
        return False
    elif inf in INFOBOX_SKIP:
        # print(f"Skipping {inf} article: {p.title()} in {c.title()}")
        return False
    elif inf in SERIES_SKIP or "(series)" in p.title() or p.title() == "Star Wars App":
        return False
    elif "{{Author-stub" in t or "{{Bio-stub" in t or "{{Author-stub" in t:
        # print(f"Skipping person article: {p.title()} in {c.title()}")
        return False
    elif inf in ["ToyLine", "MagazineIssue"] and p.title().startswith("LEGO"):
        return False
    elif f"[[{ct}| " in t or f"[[{ct}|*" in t or f"[[Category:{p.title()}| " in t:
        # print(f"Skipping root page {p.title()} for {c.title()}")
        return False
    return True


NON_RWM_PARAMS = ["rwc", "rwp", "real", "music"]


def check_category(c: Category, cats_checked, pages_checked, tracked, infoboxes, not_found: List[FutureProduct],
                   diff_dates: list, counts, appearances: FullListData, sources: FullListData, check_dates=False):
    if c.title() in cats_checked:
        return
    cats_checked.add(c.title())

    if c.title().endswith(" writers") or c.title().endswith(" artists") or c.title().endswith(" actors") \
            or c.title().endswith(" authors") or c.title().endswith(" trade paperbacks"):
        return
    elif any(cc.title(with_ns=False) == "Ignored categories for Source Engine traversal" for cc in c.categories()):
        return

    dates_mismatch, no_dates = {}, {}
    for p in c.articles(namespaces=0):
        try:
            # if counts["total"] % 50 == 0:
            #     print(counts["total"], counts["found"], p.title())
            counts["total"] += 1
            pt = p.title().replace("…", "&hellip;")
            if p.namespace().id != 0 or pt in pages_checked or not p.exists() or p.isRedirectPage():
                continue
            pages_checked.add(pt)
            if check_dates and pt in appearances.target:
                t = p.get()
                infobox = identify_infobox(t, infoboxes)
                compare_dates(pt, t, pt, appearances.target[pt], dates_mismatch, no_dates, infobox)
            elif check_dates and pt in sources.target:
                t = p.get()
                infobox = identify_infobox(t, infoboxes)
                compare_dates(pt, t, pt, sources.target[pt], dates_mismatch, no_dates, infobox)
            elif pt in tracked:
                continue
            elif pt in appearances.target or pt in sources.target:
                print(f"huh? {pt}")
            else:
                t = p.get()
                if any(f"|{r}|" in t or f"|{r}}}}}" in t for r in NON_RWM_PARAMS):
                    continue
                inf = identify_infobox(t, infoboxes) or 'article'
                if should_check_product(inf, t, p, c.title()):
                    x = analyze_page(p, t, c.title(), inf)
                    if x:
                        print(f"Found {inf}: {pt}, {pt in appearances.target}, {p.title() in appearances.target} {pt in sources.target}, {p.title() in sources.target}")
                        counts["found"] += 1
                        not_found.append(x)
        except Exception as e:
            print(p.title(), e)
    for k, v in dates_mismatch.items():
        diff_dates.append(f"Mismatch: {k}\t{v[0]}\t{v[1]}")
    for k, v in no_dates.items():
        diff_dates.append(f"No Date: {k}\t{v[0]}\t{v[1]}")
    # return

    for sc in sorted(list(c.subcategories()), key=lambda a: not a.title().endswith("by type")):
        check_category(sc, cats_checked, pages_checked, tracked, infoboxes, not_found, diff_dates, counts,
                       appearances, sources, check_dates)

    return not_found, diff_dates


def build_item_type(item_type, i: FutureProduct):
    z = item_type or ''
    is_legends = (i.canon_type == 'leg' or i.canon_type == 'ncl') if i.canon_type else False
    if z.startswith("Appearances") or z.startswith("Sources") or z.startswith("CardSets"):
        z = f"{z}|{is_legends}"
    return z


def handle_results(site, results: List[FutureProduct], collections: List[FutureProduct], save=True):
    types = load_template_types(site)
    extra_page = Page(site, "Wookieepedia:Appearances/Extra")
    extra = parse_page(extra_page, types)
    series_page = Page(site, "Wookieepedia:Appearances/Series")
    series = parse_page(series_page, types)
    l_app_page = Page(site, "Wookieepedia:Appearances/Legends")
    l_apps = parse_page(l_app_page, types)
    c_app_page = Page(site, "Wookieepedia:Appearances/Canon")
    c_apps = parse_page(c_app_page, types)
    audio_page = Page(site, "Wookieepedia:Appearances/Audiobook")
    audio = parse_page(audio_page, types)
    col_page = Page(site, "Wookieepedia:Appearances/Collections")
    cols = parse_page(col_page, types)
    l_src_page = Page(site, "Wookieepedia:Sources/Legends/General")
    l_srcs = parse_page(l_src_page, types)
    c_src_page = Page(site, "Wookieepedia:Sources/Canon/General")
    c_srcs = parse_page(c_src_page, types)
    c_sets_page = Page(site, "Wookieepedia:Sources/Canon/CardSets")
    c_sets = parse_page(c_sets_page, types)
    l_sets_page = Page(site, "Wookieepedia:Sources/Legends/CardSets")
    l_sets = parse_page(l_sets_page, types)
    tracks_page = Page(site, "Wookieepedia:Sources/Soundtracks")
    tracks = parse_page(tracks_page, types)

    master_data = {
        "Audiobooks": audio, "Collections": cols, "Soundtracks": tracks, "Series": series, "Extra": extra,
        # "Legends-2010s Sources": l_srcs1, "Legends-2000s Sources": l_srcs2, "Legends-1900s Sources": l_srcs3,
        "Canon Sources": c_srcs, "Legends Appearances": l_apps, "Canon Appearances": c_apps,
        "Legends CardSets": l_sets, "Canon CardSets": c_sets, "Legends Sources": l_srcs}

    new_items = {"Audiobooks": [], "Collections": collections, "Soundtracks": []}
    changed_dates = {}

    for i in results:
        z = build_item_type(i.item_type, i)
        # if z == "Sources|True":
        #     d = build_date(i.dates)
        #     if d:
        #         if d.startswith("19") or d.startswith("2000"):
        #             z = "Sources|True|3"
        #         elif d.startswith("200") or d.startswith("2010"):
        #             z = "Sources|True|2"
        #         else:
        #             z = "Sources|True|1"
        found = False
        for t, data in master_data.items():
            if i.page.title() in data.target:
                found = True
                if i.item_type != t.split(" ")[-1]:
                    print(f"{i.item_type}: {i.page.title()} is classified as {t}")
                    z = build_item_type(t.split(" ")[-1], i)
                if i.dates and not dates_match(i.dates, data.target[i.page.title()][0].date, i.infobox):
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
            if z == "Sources|False" and (i.page.title() in master_data["Canon CardSets"].target or i.page.title() in master_data["Legends CardSets"].target):
                continue
            if z not in new_items:
                new_items[z] = []
            new_items[z].append(i)
            print(z, i.page.title())

    build_new_page(c_app_page, c_apps, "Appearances|False", new_items, changed_dates, True, save)
    build_new_page(l_app_page, l_apps, "Appearances|True", new_items, changed_dates, True, save)

    build_new_page(c_src_page, c_srcs, "Sources|False", new_items, changed_dates, True, save)
    build_new_page(l_src_page, l_srcs, "Sources|True", new_items, changed_dates, True, save)
    # build_new_page(l_src_page1, l_srcs1, "Sources|True|1", new_items, changed_dates, True, save)
    # build_new_page(l_src_page2, l_srcs2, "Sources|True|2", new_items, changed_dates, True, save)
    # build_new_page(l_src_page3, l_srcs3, "Sources|True|3", new_items, changed_dates, True, save)

    build_new_page(c_sets_page, c_sets, "CardSets|False", new_items, changed_dates, True, save)
    build_new_page(l_sets_page, l_sets, "CardSets|True", new_items, changed_dates, True, save)

    build_new_page(extra_page, extra, "Extra", new_items, changed_dates, True, save)
    build_new_page(series_page, series, "Series", new_items, changed_dates, False, save)
    build_new_page(audio_page, audio, "Audiobooks", new_items, changed_dates, True, save)
    build_new_page(tracks_page, tracks, "Soundtracks", new_items, changed_dates, True, save)
    build_new_page(col_page, cols, "Collections", new_items, changed_dates, True, save)


DATES = {"Wookieepedia:Appearances/Legends": "1977",
         "Wookieepedia:Appearances/Canon": "2008",
         "Wookieepedia:Appearances/Audiobook": "2008",
         "Wookieepedia:Appearances/Collections": "1994",
         "Wookieepedia:Sources/Legends/General/1977-2000": "1977",
         "Wookieepedia:Sources/Legends/General/2000s": "2000",
         "Wookieepedia:Sources/Legends/General/2010s": "2010",
         "Wookieepedia:Sources/Legends/General": "1977",
         "Wookieepedia:Sources/Canon/General": "2014",
         "Wookieepedia:Sources/Legends/CardSets": "1977",
         "Wookieepedia:Sources/Canon/CardSets": "2013"}


def build_final_new_items(new_items: List[FutureProduct], audiobooks: List[str]):
    final = []
    for i in new_items:
        if i.infobox in ["ShortStory", "MagazineArticle", "MagazineDepartment"]:
            t = f'"[[{i.page.title()}]]"'
            pt = i.page.get()
            x = re.search("\|published in=.*?\[\[(.*?)(\|.*?)?]]", pt)
            if x and x.group(1) and "Star Wars Insider" in x.group(1):
                mi = x.group(1).split("Insider")[-1].strip()
                if mi.isnumeric():
                    t = f"{{{{InsiderCite|{mi}|{i.page.title()}}}}}"
                else:
                    t = f"{{{{InsiderCite|link={x.group(1)}|{i.page.title()}}}}}"
            elif x and x.group(2):
                t = f"{{{{StoryCite|book={x.group(1)}|bformatted={x.group(2)[1:]}|story={i.page.title()}}}}}"
            elif x:
                t = f"{{{{StoryCite|book={x.group(1)}|story={i.page.title()}}}}}"
        else:
            t = f"''[[{i.page.title()}]]''"
            t = re.sub("''\[\[((.*?) \((trade paperback|(u?n?abridged )?audiobook)\))]]''", "[[\\1|''\\2'' \\3]]", t)
            t = re.sub("''\[\[((.*?) (\([0-9]+\)) ([0-9]+))]]''", "[[\\1|''\\2'' \\3 \\4]]", t)
            t = re.sub("''\[\[(([^|\](]*?) \(.*?\)( [0-9]+)?)]]''", "[[\\1|''\\2''\\3]]", t)
            t = re.sub("''\[\[(.*?)\|(((?!'').)*?) ([0-9]+)]]''", "[[\\1|''\\2'' \\3]]", t)
            t = re.sub("''\[\[([^|\]]+?) ([0-9]+)]]''", "[[\\1 \\2|''\\1'' \\2]]", t)
            t = re.sub("\[\[(.*? Vol[.a-z]*?) ([0-9]+)\|''\\1'' \\2]]", "''[[\\1 \\2]]''", t)
            if "[[Untitled" in t and t.startswith("''"):
                t = t[2:-2]

            x, _, _ = i.page.title().partition(" (")
            for a in audiobooks:
                if a.startswith(f"{x} ("):
                    t = f"{t} {{{{Ab|{a}}}}}"
                    break

        d = build_date(i.dates)
        final.append([t, prep_date(d), 100, fix_numbers(t), False])
    return final


def build_new_page(page, data: FullListData, key, all_new: Dict[str, List[FutureProduct]],
                   all_changed: Dict[str, Dict[str, FutureProduct]], use_sections, save=False, override=False):
    new_items = all_new.get(key) or []
    changed = all_changed.get(key) or {}
    if not (new_items or changed or override):
        return

    audiobooks = [a.page.title() for a in all_new["Audiobooks"] if key != "Audiobooks"]

    final = build_final_new_items(new_items, audiobooks)
    if page.title().endswith("/Extra") or page.title().endswith("/Series"):
        text = page.get() + "\n"
        for txt, d, _, _, _ in final:
            text += f"\n#{d}: {txt}"
        if save and text != page.get():
            page.put(text, "Updating Source Engine Masterlist with new future products", botflag=False)
        return

    for x, i in data.full.items():
        d = i.date
        if i.target in changed:
            print(changed[i.target].dates)
            d = build_date(changed[i.target].dates)
        z = re.sub(" [ ]+", " ", i.department + i.original + " " + i.ab + " " + i.extra)
        if i.target and key.startswith("Appearances"):
            x, _, _ = i.target.partition(" (")
            for a in audiobooks:
                if a.startswith(f"{x} ("):
                    z = f"{z} {{{{Ab|{a}}}}}"
                    break
        final.append([z, prep_date(d), i.index, fix_numbers(z), False])

    start_date = DATES.get(page.title())
    section = None
    canceled = []
    lines = ["<noinclude>{{Wookieepedia:Sources/Header}}</noinclude>"]
    post = re.search("==Post-([0-9]+)==", page.get())
    post = post.group(1) if post else None
    post_found = False
    for f in sorted(final, key=lambda a: (a[4], "StoryCite" in a[0] if key == "Audiobook" else False, " abridged" not in a[0], a[1], (a[2] or 200), a[3], a[0])):
        txt, d, i = f[0], f[1], f[2]
        if use_sections:
            if d.startswith("Cancel"):
                if section != "Canceled":
                    section = "Canceled"
                    canceled.append("\n==Canceled==")
                canceled.append(f"#{d}: {txt}")
                continue

            if key == "Audiobooks" and " abridged" in txt:
                if not section:
                    section = "Abridged"
                    lines.append("\n==Abridged==")
            elif key == "Audiobooks" and "StoryCite" in txt:
                if not section:
                    section = "Stories"
                    lines.append("\n==Stories==")
            elif d.startswith("1") or d.startswith("2"):
                if post_found:
                    pass
                elif start_date and d[:4] == start_date:
                    start_date = None
                    section = d[:4]
                    lines.append(f"\n=={section}==")
                elif start_date and (not section or section == "Abridged" or section == "Stories"):
                    section = f"Pre-{start_date}"
                    lines.append(f"=={section}==")
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
    if canceled:
        lines += canceled

    new_txt = re.sub("(?<![\n=])\n==", "\n\n==", re.sub("\n\n+", "\n\n", "\n".join(l.strip() for l in lines))).strip()
    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/sources/test.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if save:
        page.put(new_txt, "Updating Source Engine Masterlist with new future products", botflag=False)
    else:
        showDiff(page.get(), new_txt, context=2)


NUMBERS = {"first": "01", "second": "02", "third": "03", "fourth": "04", "fifth": "05", "sixth": "06", "seventh": "07",
           "eighth": "08", "ninth": "09", "tenth": "10"}


def fix_numbers(t):
    for x, y in NUMBERS.items():
        t = t.replace(x, y).replace(x.capitalize(), y)
    return t
