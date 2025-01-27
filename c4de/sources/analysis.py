import re
from datetime import datetime, timedelta

from c4de.sources.external import is_external_link, prepare_basic_url, prepare_official_link, determine_link_order
from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional

from c4de.sources.parsing import build_page_components, BY_INDEX, BY_DATE, is_number, is_official_link, build_card_text, \
    UNCHANGED
from c4de.sources.determine import determine_id_for_item, swap_parameters
from c4de.sources.engine import AUDIOBOOK_MAPPING, GERMAN_MAPPING, SERIES_MAPPING, EXPANSION
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, AnalysisResults, SectionComponents, \
    SectionItemIds, FinishedSection, NewComponents, UnknownItems
from c4de.common import is_redirect

KEEP_TEMPLATES = ["TCWA", "CalendarCite"]
DO_NOT_MOVE = ["TCWA", "GEAttr", "DatapadCite"]
LIST_AT_START = ["Star Wars: Galactic Defense", "Star Wars: Force Arena"]
DVD = ["Complete Saga", "Star Wars: The Skywalker Saga", "Clone Wars Volume", "Star Wars Trilogy: The Definitive Collection"]
STORY_COLLECTIONS = ["[[5-Minute Star Wars", "Trilogy Stories", "[[The Clone Wars: Stories", "[[From a Certain Point" 
                     "[[Tales from the ", "[[Tales of the Bounty Hunters", "Short Story Collection", "[[Tales from a",
                     "[[Canto Bight (", "[[Myths & Fables", "[[Dark Legends", ]
TOY_LINES = ["toy line", "Star Wars: Power of the Jedi", "30th Anniversary Collection", "Interactech",
             "The Legacy Collection", "Movie Heroes", "The Original Trilogy Collection", "Star Wars Saga",
             "Star Wars Unleashed", "Star Wars: The Vintage Collection", "Shadows of the Dark Side",
             "The Saga Collection", "Saga Legends", "Retro Collection", "The Black Series"]


def match_audiobook_name(a, b):
    return b == f"{a.split('(')[0].strip()} (audiobook)" or b == f"{a.split('(')[0].strip()} (unabridged audiobook)"


def remove_audiobook_from_1st(param, match, name):
    if param.strip() in ["in book", f"''{name}'' audiobook", f"in book and ''{name}'' audiobook"]:
        return "" if match else None
    elif "audiobook" not in param:
        return None
    elif re.search("^'*\[\[[^\n}|\]\[]+ \((unabridged )?audiobook\)(\|[^\n}|\]\[]+)?]]'*$", param):
        return ""

    y = re.search("^(.*?)(,|and)? ?'*\[\[[A-z0-9: -]+ \((unabridged )?audiobook\).*?]]'*(,| and)? ?(.*?)$", param)
    if not y:
        if param.count("[[") == 0 and re.search("(?<! abridged) audiobook$", param):
            return "" if match else "in book"
        elif not match and "in book" not in param:
            return f"in book, {param}" if " and " in param else f"in book and {param}"
        return None
    y1, y2 = (y.group(2) or '').replace('in book', '').strip(), (y.group(4) or '').replace('in book', '').strip()
    if y2 and y2.strip() == "and":
        y2 = ""
    if y1 and y2:
        if " and" in y2 and match:
            t = f"{y1}, {y2}"
        elif " and" in y2:
            t = f"in book, {y1}, {y2}"
        elif match:
            t = f"{y1} and {y2}"
        else:
            t = f"in book, {y1} and {y2}"
    elif y1 and y1 == "in book" and match:
        t = ""
    elif y1:
        t = f"{y1}" if match else f"in book and {y1}"
    elif y2 and y2 == "in book" and match:
        t = ""
    elif y2:
        t = f"{y2}" if match else f"in book and {y2}"
    elif match:
        t = ""
    else:
        t = "in book"

    z = re.sub(" and *$", "", re.sub("(in book )+", "in book ", re.sub("( and)+", "\\1", t)))
    return "" if (z == "and" or (z == "in book" and match)) else z


def handle_ab_first(a: ItemId, audiobook_date):
    if re.search("\{\{1stID\|[^\[{|]+\|.*?}}", a.current.extra):
        z = re.search("\{\{1stID\|[^\[{|]+(\|(simult=)?(.*?))}}", a.current.extra)
        t = remove_audiobook_from_1st(z.group(3), audiobook_date == a.master.date, a.master.target)
        if t:
            a.current.extra = a.current.extra.replace(z.group(3), t)
        elif t is not None:
            a.current.extra = a.current.extra.replace(z.group(1), "")\

    elif re.search("\{\{1stID\|simult=.*?}}", a.current.extra):
        z = re.search("\{\{1stID(\|simult=(.*?))}}", a.current.extra)
        t = remove_audiobook_from_1st(z.group(2), audiobook_date == a.master.date, a.master.target)
        if t:
            a.current.extra = a.current.extra.replace(z.group(2), t)
        elif t is not None:
            a.current.extra = a.current.extra.replace(z.group(1), "")
    elif "{{1stID}}" in a.current.extra and audiobook_date != a.master.date:
        a.current.extra = a.current.extra.replace("{{1stID}}", "{{1stID|simult=in book}}")

    if any(f"{{{{1st{x}|" in a.current.extra for x in ("", "m", "p", "c", "cm")):
        z = re.search("\{\{1stc?[mp]*\|(.*?)}}", a.current.extra)
        t = remove_audiobook_from_1st(z.group(1), audiobook_date == a.master.date, a.master.target)
        if t:
            a.current.extra = a.current.extra.replace(z.group(1), t)
        elif t is not None:
            a.current.extra = a.current.extra.replace("|" + z.group(1), "")
    elif "{{1st" in a.current.extra and audiobook_date != a.master.date:
        a.current.extra = re.sub("(\{\{1stc?[mp]*?)}}", "\\1|in book}}", a.current.extra)

    if a.current.extra and a.current.target and a.current.target.split(' (')[0] in a.current.extra:
        z = a.current.target.split(' (')[0]
        for k in ["abridged audiobook", "novelization", "film novelization"]:
            a.current.extra = a.current.extra.replace(f"|''{z}'' {k}", f"|{k}")


def find_matching_audiobook(a: ItemId, existing: list, appearances: FullListData, abridged: list):
    if not a.master.target:
        return []
    elif f"{a.master.target} (novelization)" in existing or f"{a.master.target} (novel)" in existing:
        return []
    elif any(a.master.target.endswith(f"({z})") for z in ["audio", "short story", "comic"]):
        return []

    z = None
    if a.master.target in appearances.parentheticals:
        z = a.master.target
    elif a.master.target.endswith(")") and not a.master.target.endswith("webcomic)"):
        z = a.master.target.rsplit("(", 1)[0].strip()
    elif a.master.parent in AUDIOBOOK_MAPPING or a.master.parent in GERMAN_MAPPING:
        z = a.master.parent

    if not z:
        return []

    results = []
    if z in AUDIOBOOK_MAPPING:
        to_check = [AUDIOBOOK_MAPPING[z]]
    elif z in GERMAN_MAPPING:
        to_check = [GERMAN_MAPPING[z]]
    else:
        to_check = [f"{z} (audiobook)", f"{z} (unabridged audiobook)", f"{z} (abridged audiobook)", f"{z} (script)",
                    f"{z} (audio)", f" (audio drama)", f" (German audio drama)"]

    for y in to_check:
        if y in appearances.target and y not in abridged:
            if f"{z} (novel)" in appearances.target and f"{z} (novel)" not in existing:
                continue
            elif f"{z} (novelization)" in appearances.target and f"{z} (novelization)" not in existing:
                continue
            elif y.startswith("The Clone Wars Episode"):
                continue
            results.append(appearances.target[y][0])
    return results


def find_matching_parent_audiobook(a: ItemId, existing: list, appearances: FullListData):
    if not a.master.parent or len(appearances.target.get(a.master.target) or []) < 2:
        return []

    z = None
    if a.master.parent in appearances.parentheticals:
        z = a.master.parent
    elif a.master.parent.endswith(")"):
        z = a.master.parent.rsplit("(", 1)[0].strip()
    elif a.master.parent in AUDIOBOOK_MAPPING or a.master.parent in GERMAN_MAPPING:
        z = a.master.parent

    if not z:
        return []

    results = []
    audiobook_name = AUDIOBOOK_MAPPING.get(z, f"{z} (audiobook)") or GERMAN_MAPPING.get(z, f"{z}")
    if z and a.master.target in appearances.target:
        for t in appearances.target[a.master.target]:
            if t.parent == audiobook_name and f"{a.master.target}|{audiobook_name}" not in existing:
                results.append(t)

    return results


def augment_appearances(new_apps: SectionItemIds, appearances: FullListData, collapse_audiobooks: bool):
    app_targets = [a.master.target for a in new_apps.found if a.master.target]
    app_targets += [f"{a.master.target}|{a.master.parent}" for a in new_apps.found if
                    a.master.target and a.master.parent]
    abridged = []
    new_indexes = []
    for i, a in enumerate(new_apps.found):
        if "abridged" in a.current.extra:
            a.current.extra = re.sub("(\{\{Ab\|.*?(abridged audiobook)\|)audiobook}}", "\\1abridged audiobook}}",
                                     a.current.extra)
        if "{{po}}" in (a.current.extra or '').lower():
            handle_ab_first(a, a.master.date)
            continue
        elif a.current.target and "audiobook)" in a.current.target:
            continue
        audiobooks = find_matching_audiobook(a, app_targets, appearances, abridged)
        audiobooks += find_matching_parent_audiobook(a, app_targets, appearances)
        for b in audiobooks:
            if b.abridged:
                # print(f"Skipping abridged audiobook: {b.target}")
                if b.target not in app_targets:
                    abridged.append(b.target)
            elif "(audio)" in b.target or "(audio drama)" in b.target or (
                    not collapse_audiobooks and (b.parent if b.parent else b.target) not in app_targets):
                print(
                    f"Adding missing audiobook: {b.target} at {i}, {a.current.index}, {a.current.canon_index}, {a.current.legends_index}")
                z = ItemId(b, b, False, False, False)
                extra = a.current.extra or ''
                if "1stm" in extra:
                    extra = re.sub("\{\{1stm.*?}}", "{{Mo}}", extra)
                z.current.extra = re.sub(" ?\{\{1st[A-z]*\|.*?}}", "", extra)
                if a.master.index is not None:
                    z.master.index = a.master.index + 0.1
                    z.current.index = a.master.index + 0.1

                if a.master.canon_index is not None:
                    z.master.canon_index = a.master.canon_index + 0.1
                    z.current.canon_index = a.master.canon_index + 0.1
                elif a.master.legends_index is not None:
                    z.master.legends_index = a.master.legends_index + 0.1
                    z.current.legends_index = a.master.legends_index + 0.1
                new_indexes.append((z, i))
            elif match_audiobook_name(a.master.target, b.target):
                handle_ab_first(a, b.date)
                continue
            elif a.master.ab and f"{{{{Ab|{b.target}" in a.master.ab:
                handle_ab_first(a, b.date)
                continue
            elif a.master.template == "StoryCite" and "|audiobook=1" in a.master.original:
                handle_ab_first(a, b.date)
                continue
            elif "(script)" not in b.target:
                print(f"Unmatched audiobook {b.target} not found in {a.master.original}")
    o = 1
    for z, i in new_indexes:
        new_apps.found.insert(i + o, z)
        o += 1

    return abridged


def handle_non_canon_items(results: PageComponents, new_apps: SectionItemIds, new_nca: SectionItemIds,
                           new_src: SectionItemIds, new_ncs: SectionItemIds, log=False):
    if results.non_canon:
        new_apps.merge(new_nca)
        new_apps.found += new_apps.non_canon
        new_apps.non_canon = []
        new_src.merge(new_ncs)
        new_src.found += new_src.non_canon
        new_src.non_canon = []

    # move non-canon items to the appropriate lists, and swap to non-canon only if no canon entries
    if new_apps.non_canon:
        if log:
            print(f"Moving {len(new_apps.non_canon)} 'appearances' to the Non-canon Appearances")
        new_nca.found += new_apps.non_canon
    if new_nca.non_canon:
        if log:
            print(f"Moving {len(new_nca.non_canon)} 'non-canon' appearances to the main Appearances")
        new_apps.found += new_nca.non_canon
    if new_src.non_canon:
        new_ncs.found += new_src.non_canon
    if new_ncs.non_canon:
        new_src.found += new_ncs.non_canon

    if new_apps.wrong or new_nca.wrong:
        if log:
            print(f"Moving {len(new_apps.wrong) + len(new_nca.wrong)} sources from Appearances to Sources")
        for x in new_apps.wrong:
            x.current.extra = re.sub("\{\{1st([|}])", "{{1stm\\1", x.current.extra)
            (new_ncs if x.master.non_canon else new_src).found.append(x)
        if not new_apps.found:
            results.src.preceding += results.apps.preceding
            results.src.trailing += results.apps.trailing
            results.src.after += results.apps.after
        for x in new_nca.wrong:
            x.current.extra = re.sub("\{\{1st([|}])", "{{1stm\\1", x.current.extra)
            (new_ncs if x.master.non_canon else new_src).found.append(x)
    if new_src.wrong or new_ncs.wrong:
        if log:
            print(f"Moving {len(new_src.wrong) + len(new_ncs.wrong)} entries from Sources to Appearances")
        for x in new_src.wrong:
            (new_nca if x.master.non_canon else new_apps).found.append(x)
        if not new_src.found:
            results.apps.preceding += results.src.preceding
            results.apps.trailing += results.src.trailing
            results.apps.after += results.src.after
        for x in new_ncs.wrong:
            (new_nca if x.master.non_canon else new_apps).found.append(x)


def analyze_section_results(target: Page, results: PageComponents, disambigs: list, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool, include_date: bool,
                            collapse_audiobooks: bool, checked: list, log) \
        -> Tuple[NewComponents, list, UnknownItems, AnalysisResults]:
    both_continuities = appearances.both_continuities.union(sources.both_continuities)
    dates = []
    unknown_apps, unknown_src = [], []
    # now = datetime.now()
    new_src = build_item_ids_for_section(target, results.real, "Sources", results.src.items,
                                         sources, appearances, None, remap, unknown_src, results.canon, [], collapse_audiobooks, log)
    new_ncs = build_item_ids_for_section(target, results.real, "Non-canon sources", results.ncs.items,
                                         sources, appearances, None, remap, unknown_src, results.canon, [], collapse_audiobooks, log)
    new_apps = build_item_ids_for_section(target, results.real, "Appearances", results.apps.items,
                                          appearances, sources, new_src, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    new_nca = build_item_ids_for_section(target, results.real, "Non-canon appearances", results.nca.items,
                                         appearances, sources, new_ncs, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    # print(f"item IDs: {(datetime.now() - now).microseconds / 1000} microseconds")

    handle_non_canon_items(results, new_apps, new_nca, new_src, new_ncs, log)

    results.links.items = [*new_apps.links, *new_nca.links, *new_src.links, *new_ncs.links, *results.links.items]
    new_links, unknown_links, wrong = build_new_external_links(target, results.links.items, sources, appearances, remap, results.canon, log)
    if wrong:
        if log:
            print(f"Moving {len(wrong)} misclassified sources from External Links to Sources")
        new_src.found += wrong

    if new_nca.found and not (new_apps.found or new_apps.group_ids or new_apps.group_items):
        new_apps = new_nca
        new_apps.mark_as_non_canon = "{{Nc}}"
        new_nca = None
    if new_ncs.found and not (new_src.found or new_src.group_ids or new_src.group_items):
        new_src = new_ncs
        new_src.mark_as_non_canon = "{{Ncs}}"
        new_ncs = None

    # now = datetime.now()
    abridged = augment_appearances(new_apps, appearances, collapse_audiobooks)

    text = target.get()
    disambig_links = []

    actual_title = target.title().replace("/Legends", "")
    if actual_title.endswith(")"):
        actual_title = actual_title.rsplit(" (", 1)[0]

    x = re.search("\{\{Top.*?\|title=(.*?)(\|.*?)?}}", text)
    if x and x.group(1) == "''{{PAGENAME}}''":
        title = f"''{actual_title}''"
    elif x:
        title = x.group(1).replace("{{PAGENAME}}", actual_title)
    else:
        title = actual_title

    if f"'''{title[0].lower()}{title[1:]}'''" in text:
        title = f"{title[0].lower()}{title[1:]}"

    if text.count("{{1stID") > 1 and f"{{1stID|{title}".lower() in text.lower():
        title = None
    # print(f"prep: {(datetime.now() - now).microseconds / 1000} microseconds")

    mismatch = []
    unknown_final = []
    # now = datetime.now()
    targets = [t.current.target for t in [*new_apps.found, *new_src.found, *(new_nca.found if new_nca else []), *(new_ncs.found if new_ncs else [])] if t.current.target and not t.master.reprint]
    new_apps, final_apps = build_new_section("==Appearances==", new_apps, title, results.app_mode, dates, results.canon, include_date,
                                             log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_nca, final_nca = build_new_section("===Non-canon appearances===", new_nca, title, BY_DATE, dates, results.canon, include_date,
                                           log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_src, final_sources = build_new_section("==Sources==", new_src, title, BY_DATE, dates, results.canon, True,
                                               log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_ncs, final_ncs = build_new_section("===Non-canon sources===", new_ncs, title, BY_DATE, dates, results.canon, True,
                                           log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)

    reprints = prepare_reprints(appearances, sources, [*final_apps, *final_ncs, *final_ncs, *final_sources])
    analysis = AnalysisResults(final_apps, final_nca, final_sources, final_ncs, results.canon, abridged, mismatch, disambig_links, reprints)
    components = NewComponents(new_apps, new_nca, new_src, new_ncs, new_links, results.get_navs())
    unknown = UnknownItems(unknown_apps, unknown_src, unknown_final, unknown_links)
    # print(f"build: {(datetime.now() - now).microseconds / 1000} microseconds")
    return components, dates, unknown, analysis


def prepare_reprints(appearances: FullListData, sources: FullListData, items: List[ItemId]):
    reprints = {}
    for i in items:
        if i.master.target and i.master.target in appearances.reprints:
            reprints[i.master.target] = appearances.reprints[i.master.target]
        elif i.master.target and i.master.target in sources.reprints:
            reprints[i.master.target] = sources.reprints[i.master.target]

    return reprints


def _cards() -> Dict[str, List[ItemId]]:
    return {}


def should_expand(t):
    return t and (t in SERIES_MAPPING or t in EXPANSION)# and not ("Crimson Empire" in t or "Dark Empire" in t)


def build_item_ids_for_section(page: Page, real, name, original: List[Item], data: FullListData, other: FullListData, src: Optional[SectionItemIds], remap: dict,
                               unknown: List[Union[str, Item]], canon: bool, checked: list, collapse_audiobooks=True, log=True) -> SectionItemIds:

    found = []
    wrong = []
    links = []
    non_canon = []
    group_items = _cards()
    extra = {}
    page_links = []
    any_expanded = []
    unexpanded = 0
    other_extra = False
    for i, o in enumerate(original):
        o.index = i
        d = determine_id_for_item(o, page, data.unique, data.target, other.unique, other.target, remap, canon, log)
        if not d and o.parent:
            p = Page(page.site, o.parent)
            if "[[w:c:" in o.original:
                continue
            if is_redirect(p):
                if log:
                    print(f"Followed redirect {o.parent} to {p.getRedirectTarget().title()}")
                o.parent = p.getRedirectTarget().title().split('#', 1)[0]
                d = determine_id_for_item(o, page, data.unique, data.target, other.unique, other.target, remap, canon, log)

        if d and name == "Appearances" and o.template == "SWIA":
            d.from_other_data = True
        elif d and name == "Appearances" and d.master.has_content:
            wrong.append(d)
            continue

        if d and should_expand(d.master.target):
            if d.master.target in EXPANSION:
                issues = EXPANSION[d.master.target]
            else:
                n, i1, i2 = SERIES_MAPPING[d.master.target]
                issues = [f"{n} {i}" for i in range(i1, i2 + 1)]
            if not page_links:
                for p in page.getReferences(namespaces=0):
                    page_links.append(p.title())
            expanded = 0
            for p in page_links:
                if p in issues and p not in data.target:
                    print(f"ERROR: {p} not in target mapping")
                elif p in issues:
                    x = data.target[p][0].copy()
                    x.index = o.index
                    x.extra = o.extra
                    x.expanded = True
                    if expanded:
                        x.extra = re.sub("\{\{1stm.*?}}", "{{Mo}}", x.extra).strip()
                        x.extra = re.sub("\{\{1st.*?}}", "", x.extra).strip()
                    x.extra_date = o.extra_date
                    expanded += 1
                    any_expanded.append(ItemId(x, data.target[p][0], False))
            if expanded:
                print(f"Expanded series/arc listing of {d.master.target} to {expanded} issues")
                continue
            else:
                print(f"Unable to expand series/arc listing of {d.master.target} on {page.title()}")
                unexpanded += 1
        elif d and d.master.from_extra and not d.master.reprint and d.master.target not in SERIES_MAPPING and d.master.target not in EXPANSION and not d.master.non_canon and not d.master.collection_type:
            other_extra = True

        if d and (o.is_card_or_mini() or o.template == "ForceCollection"):
            handle_card_item(d, o, group_items, src.found if (src and "scenario" not in o.original) else found, src.wrong if src else wrong, extra, name, log)
        elif d and (d.current.ref_magazine or d.current.template == "FactFile"):
            if d.master.parent not in group_items:
                group_items[d.master.parent] = []
            group_items[d.master.parent].append(d)
        elif o.mode != "Toys" and is_external_link(d, o, unknown):
            if d:
                o.master_text = d.master.original
            links.append(o)
        elif d and d.current.template in KEEP_TEMPLATES:
            found.append(d)
        elif d and name == "Appearances" and d.master.master_page == "Appearances/Collections" and d.master.has_content:
            wrong.append(d)
        elif d and d.master.unlicensed:
            found.append(d)
        elif d and d.from_other_data and "databank" not in (o.extra or '').lower() \
                and d.current.template not in DO_NOT_MOVE \
                and d.current.target != 'Star Wars: Datapad (Galactic Starcruiser)'\
                and not real and (d.master.reprint or d.master.target in SERIES_MAPPING or d.master.target in EXPANSION or not d.master.from_extra):
            if log:
                print(f"({name}) Listed in wrong section: {o.original} -> {d.master.is_appearance} {d.master.full_id()}")
            wrong.append(d)
        elif d and not real and d.master.german_ad:

            found.append(d)
        elif d and not real and d.master.audiobook and not d.master.abridged and collapse_audiobooks:
            # print(f"Skipping individually-listed audiobook: {d.master.target}")
            continue
        elif d and not real and d.master.non_canon and not name.startswith("Non-canon") \
                and d.master.target != "Star Tours: The Adventures Continue" and not page.title().endswith("/LEGO"):
            non_canon.append(d)
        elif d and not real and not d.master.non_canon and name.startswith("Non-canon") and not ("cameo" in d.current.extra or "{{C|" in d.current.extra or d.current.template == "TFU" or d.current.target == "Star Wars: The Force Unleashed II"):
            if d.master.template not in ["JTC", "Tales", "TFU"] and "appearances" in name.lower():
                if "{{Nc" not in d.current.extra:
                    if "{{Mo}}" in d.current.extra:
                        d.current.extra = d.current.extra.replace("{{Mo}}", "{{Ncm}}")
                    elif "{{1stm" in d.current.extra:
                        d.current.extra += " {{Ncm}}"
                    else:
                        d.current.extra += " {{Nc}}"
            non_canon.append(d)
        elif "{{Hyperspace" in o.original and name == "Appearances":  # Hyperspace relisting of Appearances entries
            if d and d.master.template == "Hyperspace":
                found.append(d)
            else:
                o.legends_index = d.master.legends_index
                found.append(ItemId(o, o, True, False))
        elif d:
            found.append(d)
            if d.by_parent:
                unknown.append(f"Parent: {o.original}")
            elif d.current.unknown:
                unknown.append(o)
        elif o.template == "WebCite" or o.template == "WP" or "{{WP" in o.original:
            links.append(o)
        else:
            if log:
                print(f"Cannot find {o.unique_id()}: {o.original}")
            save = True
            if o.is_appearance and o.target and o.target not in checked:
                p = Page(page.site, o.target)
                if not o.target.lower().startswith("w:c:") and p.exists() and not p.isRedirectPage():
                    cats = [c.title() for c in p.categories()]
                    if "Category:Media that should be listed in Appearances" in cats:
                        if log:
                            print(f"Removing non-Appearance entry on {page.title()}: {o.original}")
                        save = False

            unknown.append(o)
            o.unknown = True
            if save and not real and not name.startswith("Non-canon") and "star wars: visions" in o.original.lower():
                non_canon.append(ItemId(o, o, False))
            elif save:
                found.append(ItemId(o, o, False))
            elif real:
                found.append(ItemId(o, o, False))

    group_ids = {}
    if name.startswith("File:"):
        pass
    elif src:
        handle_groups(group_items, data, other, src.found, src.group_ids, extra, unknown, src)
        group_items = {}
    else:
        handle_groups(group_items, data, other, found, group_ids, extra, unknown)

    found += list(extra.values())
    if any_expanded:
        targets = set(x.current.target for x in found if x.current.target)
        for x in any_expanded:
            if x.current.target not in targets:
                found.append(x)
    return SectionItemIds(name, found, wrong, non_canon, group_items, group_ids, links, len(any_expanded) > 0 or other_extra)


def handle_groups(groups: Dict[str, List[ItemId]], data: FullListData, other: FullListData, found: List[ItemId], group_ids: dict, extra: dict, unknown, src: SectionItemIds=None):
    for s, c in groups.items():
        if not c:
            continue
        t = data.target.get(s)
        if not t and other.target:
            t = other.target.get(s)
        if not t and c[0].master.parenthetical:
            t = data.target.get(s.replace(f"({c[0].master.parenthetical})", "").strip())
            if not t and other.target:
                t = other.target.get(s.replace(f"({c[0].master.parenthetical})", "").strip())
        if not t and c[0].current.template == "SWCT" and " - " in s:
            t = data.target.get(s.split(" - ", 1)[-1])
            if not t and other.target:
                t = other.target.get(s.split(" - ", 1)[-1])
        if t:
            t[0].index = c[0].current.index
            if c[0].current.subset:
                t[0].subset = c[0].current.subset
            if not any(x.current.target == s and x.current.template and x.current.ref_magazine for x in found):
                found.append(ItemId(t[0], t[0], False))
            group_ids[t[0].full_id()] = s
            if t[0].target in extra:
                extra.pop(t[0].target)
        elif c[0].current.template == "Topps":
            found += c
        else:
            print(f"ERROR: Cannot find item for parent/target set: [{s}]: {c[0].current.full_id()}")
            for i in c:
                i.current.unknown = True
            found += c
        if src and s in src.group_items:
            src.group_items[s] += c
        elif src:
            src.group_items[s] = c

        for i in c:
            if i.current.unknown and i.current.template == "SWCT":
                unknown.append(i.current)


def handle_card_item(d: ItemId, o: Item, cards: Dict[str, List[ItemId]], found: List[ItemId], wrong: List[ItemId],
                     extra: Dict[str, ItemId], name, log):
    if d.current.card and d.current.card == d.master.card and d.master.has_date() and not d.master.is_card_or_mini():
        found.append(d)
        return
    elif o.template == "ForceCollection":
        found.append(d)
        return

    parent_set = d.master.parent if d.master.parent else d.master.target
    if d.current.template == "Topps" and not d.master.has_date() and parent_set.startswith("20"):
        d.master.date = f"{parent_set[:4]}-XX-XX"
    if o.template == "SWCT" and (not parent_set or parent_set == "Star Wars: Card Trader"):
        parent_set = d.master.card or parent_set
    if parent_set == "Topps Star Wars Living Set":
        if o.card and o.card.strip().startswith('#'):
            num = o.card.strip().split(' ')[0].replace('#', '')
            if num.isnumeric():
                n = int(num)
                date = datetime(2019, 6, 4) + timedelta(days=(n - (n % 2)) / 2 * 7)
                d.master.date = date.strftime("%Y-%m-%d")
        found.append(d)
        return
    if parent_set not in cards:
        cards[parent_set] = []

    if parent_set and "|stext=" in d.master.original and "|stext=" not in d.current.original:
        x = re.search("(\|stext=.*?)[|}]", d.master.original)
        if x:
            d.current.original = d.current.original.replace(f"|set={parent_set}", f"|set={parent_set}{x.group(1)}")
            d.current.original = re.sub("\|stext=('*(.*?)'*)\|(stext|sformatt?e?d?)?'*\\3'*\|", "|stext=\\2|", d.current.original)
    elif parent_set and "|stext=" not in d.master.original:
        d.current.original = re.sub("\|s(formatt?e?d?|text)=('*(.*?)'*)\|", "|", d.current.original)

    if o.card:
        cards[parent_set].append(d)
        for _, i in o.others.items():
            cards[parent_set].append(ItemId(i, i, False, False))
    elif o.special and d.from_other_data:
        if log:
            print(f"({name}) Listed in wrong section: {o.original}")
        wrong.append(d)
    elif o.special:
        found.append(d)
    elif o.subset:
        found.append(d)
    else:
        print(f"No cards found for {parent_set}")
        if "appearance" in name.lower():
            wrong.append(d)
        else:
            extra[d.master.target] = d


# ***
#
# Sorting and Rebuilding Sections
#
# ***


def build_new_external_links(page: Page, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                             canon: bool, log: bool) -> Tuple[FinishedSection, list, List[ItemId]]:
    found = []
    done = []
    unknown = []
    wrong = []
    for i, o in enumerate(original):
        if o.mode == "Basic":
            t, zx = prepare_basic_url(o)
            unknown.append(zx.replace("*", ""))
            found.append((t, o, zx if zx.startswith("*") else f"*{zx}"))
            continue
        elif is_official_link(o):
            o.mode, o.original = prepare_official_link(o)
            if o.template == "WebCite":
                o.original = o.original.replace("WebCite", "OfficialSite")

        o.index = i
        d = determine_id_for_item(o, page, data.unique, data.target, other.unique, other.target, remap, canon, log)
        if not d and o.parent:
            p = Page(page.site, o.parent)
            if "[[w:c:" in o.original:
                continue
            if is_redirect(p):
                if log:
                    print(f"Followed redirect {o.parent} to {p.getRedirectTarget().title()}")
                o.parent = p.getRedirectTarget().title().split('#', 1)[0]
                d = determine_id_for_item(o, page, data.unique, data.target, other.unique, other.target, remap, canon, log)
        is_external_link(d, o, [])

        if d and d.master.is_internal_mode() and not d.master.external:
            wrong.append(d)
        elif d and d.master.mode == "General" and "Web" not in d.master.master_page:
            wrong.append(d)
        elif d:
            zn = d.current.original if d.use_original_text else d.master.original
            zn = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"*{zn}")
            if d.current.bold:
                zn = f"'''{zn}'''"
            if d.master.date and d.master.date.startswith("Cancel") and "{{c|cancel" not in zn.lower():
                zn += " {{C|canceled}}"
            if zn.startswith("**"):
                zn = zn[1:]
            zn = swap_parameters(zn)
            zn = zn.replace("–", "&ndash;").replace("—", "&mdash;")
            z = f"{zn} {d.current.extra}"
            if d.master.mode == "Minis" and d.master.card:
                z = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", re.sub(" ?\{\{[Cc]\|[Rr]eissued.*?}}", "", z))
            z = z if z.startswith("*") else f"*{z}"
            if z not in done:
                found.append((o.mode, d.master, z))
                done.append(z)
        else:
            print("External Link:", o.mode, o.template, o.original)
            if o.template not in ["WP"] and o.mode not in ["Interwiki", "Social", "Profile"]:
                unknown.append(o.original)
            zn = re.sub("\{\{[Ss]eriesListing.*?}} ?", "", o.original)
            # u = "{{UnknownListing|ex=1}} " if o.mode == "General" else ""
            u = ""
            z = f"*{u}{zn} {o.extra}".strip()
            if z not in done:
                found.append((o.mode, o, z))
                done.append(z)

    finished = sorted(found, key=lambda a: determine_link_order(a[0], a[1], a[2].replace("}}", "") if a[2] else a[2]))

    return FinishedSection("==External links==", 0, "\n".join(f[2].strip() for f in finished)), unknown, wrong


def build_new_section(name, section: SectionItemIds, title: str, mode: str, dates: list, canon: bool, include_date: bool, log: bool,
                      use_index: bool, mismatch: list, both_continuities: set, unknown_final: list, targets: list, real: bool,
                      unlicensed: bool, collapse_audiobooks: bool) -> Tuple[FinishedSection, List[ItemId]]:
    if section is None:
        return FinishedSection(name, 0, ""), []

    by_original_index = {o.current.index: o for o in section.found if o.current.index is not None}
    new_found, group, missing, source_names = compile_found(section, mode, canon)

    found = handle_sorting(mode, new_found, missing, canon, use_index=use_index, log=log)

    new_text = []
    final_without_extra = []
    final_items = []
    rows = 0
    sl = "" if canon else "|l=1"
    nl = "|n=1"
    for o in found:
        if mode == BY_DATE and o.current.index is None:
            if not (o.current.target and "(audio)" not in o.current.target and "(audio drama)" not in o.current.target):
                print(f"No index? {o.current.original}, {o.master.original}")
        elif mode == BY_DATE and not o.current.is_appearance and o.master.has_date() and ("-XX" in o.master.date or o.master.date.startswith("Unknown")):
            n1 = by_original_index.get(o.current.index - 1)
            n2 = by_original_index.get(o.current.index + 1)
            if (n1 and n1.master.has_date()) or (n2 and n2.master.has_date()):
                d1 = n1.master.date if n1 else None
                t1 = n1.current.original if n1 else None
                d2 = n2.master.date if n2 else None
                t2 = n2.current.original if n2 else None
                if compare_partial_dates(o.master.date, d1, d2, o.current.mode):
                    if log and not name.startswith("Non-canon"):
                        print(f"Partial date {o.master.date} found between {d1} and {d2}: {o.current.original} ({t1} & {t2})")
                    dates.append((False, o, d1, d2))
        elif mode == BY_DATE and not o.master.has_date():
            print(f"No date: {o.current.original}, {o.master.original} : {o.current.target}")
            o.unknown = True
            unknown_final.append(o)

        t = o.current.target.split("(")[0] if o.current.target else None
        if t and t in source_names and len(source_names[t]) > 1:
            if o.current.target.count("(") > 0 and o.current.original.count("[[") == 1:
                if log:
                    print(f"Switching text for {o.current.target} to ''{o.current.target}'' ({o.master.date[:4]})")
                o.current.original = f"[[{o.current.target}|''{o.current.target}'' ({o.master.date[:4]}]]"

        d = build_date_text(o, include_date).replace("E -->", " -->")
        if o.current.full_id() in section.group_ids:
            set_items = section.group_items[section.group_ids[o.current.full_id()]]
            ct = 0
            rows += 1
            block = []
            if o.master.template == "ForceCollection":
                set_items = sorted(set_items, key=lambda a: a.current.original)
            elif o.master.is_card_or_mini():
                set_items = sorted(set_items, key=lambda a: ("rulebook" not in a.current.original, "mission" not in a.current.original, a.master.index, (a.current.card if a.current.card else a.current.original).replace("''", "")))

            if any(i.master.ref_magazine for i in set_items):
                parent = f"{{{{{set_items[0].current.template}|{set_items[0].master.issue}|parent=1}}}} {o.current.extra}".strip()
            else:
                parent = o.current.original
                if "|parent=1" not in parent and (o.master.mode != "Minis" or o.master.template == "SWIA"):
                    parent = parent.replace("}}", "|parent=1}}")
            items = []
            for c in set_items:
                if c.current.card:
                    ot = build_card_text(o, c).replace("|parent=1", "")
                else:
                    # ot = re.sub("(\{\{[A-z0-9]+\|[0-9]+\|.*?)(\|.*?)?}}", "\\1}}", c.master.original)
                    ot = c.master.original
                if (o.master.mode == "Minis" or "mission=" in o.master.original) and o.master.card:
                    ot = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", ot)
                if ot not in final_without_extra:
                    items.append((c, ot))

            for c, ot in items:
                ex = c.current.extra.strip()
                if "1stID" in ex:
                    if title and re.search("\{\{1stID(}}|\|simult=)", ex):
                        ex = ex.replace("{{1stID", f"{{{{1stID|{title}")
                if "{{1st" in ex and len(items) > 1:
                    xid = re.search("(\{\{1stc?(ID|m|p|r)?[^{}]*(\{\{.*?}})?[^{}]*}})", ex)
                    if xid:
                        if xid.group(1) not in parent:
                            parent = f"{parent} {xid.group(1)}"
                        ex = ex.replace(xid.group(1), "").replace("  ", " ")
                zt = "*" + d + re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"{ot} {ex}").strip()
                ct += zt.count("{")
                ct -= zt.count("}")
                if c.master.mode == "Minis" and c.master.card:
                    zt = re.sub(" ?\{\{[Cc]\|[Rr]eissued.*?}}", "", zt)
                final_items.append(c)
                final_without_extra.append(ot)
                block.append(zt)
            if len(block) > 1:
                if o.master.is_card_or_mini():
                    block.insert(0, f"{d}{{{{CardGameSet|set={parent}|cards=")
                else:
                    block.insert(0, f"{d}{{{{SourceContents|issue={parent}|contents=")
                ct += 2
            new_text += block
            if ct:
                new_text.append("".join("}" for _ in range(ct)))
        elif not real and o.master.reprint and o.master.target in targets:
            print(f"Skipping duplicate {o.master.target} reprint with template {o.master.template} and parent {o.master.parent}")
        elif not real and o.master.reprint and o.master.original_printing:
            print(f"Replacing reprint of {o.master.target} with original version")
            rows += build_item_text(ItemId(o.current, o.master.original_printing, False), d, nl, sl, final_without_extra, final_items, new_text, section.name, title, collapse_audiobooks, section.mark_as_non_canon, unlicensed, log)
        else:
            if o.master.reprint and not real:
                print(f"Unexpected state: {o.master.target} reprint with template {o.master.template} and parent {o.master.parent} but no original-printing")
            rows += build_item_text(o, d, nl, sl, final_without_extra, final_items, new_text, section.name, title, collapse_audiobooks, section.mark_as_non_canon, unlicensed, log)

        if not real and o.master.canon is not None and o.master.canon != canon and o.master.target not in both_continuities:
            mismatch.append(o)

    return FinishedSection(name, rows, "\n".join(new_text)), final_items


def build_item_text(o: ItemId, d: str, nl: str, sl: str, final_without_extra: list, final_items: List[ItemId],
                    new_text: list, section_name, title, collapse_audiobooks: bool, nc: str, unlicensed: bool,
                    log: bool, is_file=False):
    zt = o.current.original if o.use_original_text else o.master.original
    if not zt.strip():
        return 0
    if o.master.ref_magazine:
        zt = re.sub("(\{\{(?!FactFile)[A-z0-9]+\|[0-9]+\|.*?)(\|.*?(\{\{'s?}})?.*?)?}}", "\\1}}", zt)

    if o.current.subset:
        zt = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", zt)
    while zt.count("|subset=") > 1:
        zt = re.sub("(\|subset=.*?)\\1", "\\1", zt)
    zt = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", zt)
    while zt.strip().startswith("*"):
        zt = zt[1:].strip()
    if o.current.bold:
        zt = f"'''{zt}'''"
    elif o.master.from_extra and "{{co}}" not in (o.current.extra or '').lower() \
            and "cover only" not in (o.current.extra or '').lower() and o.current.template != "HomeVideoCite":
        if "audiobook" in o.master.original:
            return 0
        elif o.master.future or is_file or o.master.has_content:
            pass
        elif o.current.extra and "{{c|cut}}" in o.current.extra.lower():
            pass
        elif o.master.collection_type:
            d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|{o.master.collection_type}}}}} "
        elif ("Complete" in o.master.original and "Season" in o.master.original) or any(s in o.master.original for s in DVD):
            print(f"Legacy DVD detection: {o.master.target}")
            d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|DVD}}}} "
        elif any(s in o.master.original for s in TOY_LINES):
            print(f"Legacy toy detection: {o.master.target}")
            d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|toy}}}} "
        elif any(s in o.master.original for s in STORY_COLLECTIONS):
            print(f"Legacy story-collection detection: {o.master.target}")
            d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|short}}}} "
        elif sl and not o.master.non_canon and o.master.target not in SERIES_MAPPING and o.master.target not in EXPANSION:
            d += f"{{{{SeriesListing|l=2}}}} "
        else:
            d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}}}}} "
    elif o.current.unknown or o.master.unknown:
        if o.current.template == "SWCT":
            d += f"{{{{UnknownListing{sl}|SWCT}}}} "
        elif not (is_file and o.current.template == "Databank" and o.current.url and "gallery" in o.current.url):
            d += f"{{{{UnknownListing{sl}}}}} "

    if d == "<!-- Unknown -->" and "{{Hyperspace" in zt and "/member/fiction" in zt:
        d = ""
    zn = f"{d}{zt}" if is_file else f"*{d}{zt}"
    if zn.startswith("**"):
        zn = zn[1:]
    zn = swap_parameters(zn).replace("–", "&ndash;").replace("—", "&mdash;")
    if o.current.template == "TCW" and "|d=y" in o.current.original and "|d=y" not in zn:
        zn = re.sub("(\{\{TCW\|.*?)}}", "\\1|d=y}}", zn)

    if zn in final_without_extra and "{{crp}}" not in o.current.extra.lower():
        if log:
            print(f"Skipping duplicate {zn}")
        return 0
    else:
        e = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", o.current.extra).strip()
        if title and "1stID" in e and re.search("\{\{1stID(}}|\|simult=)", e):
            e = e.replace("{{1stID", f"{{{{1stID|{title}")
        if not collapse_audiobooks:
            e = e.replace("|audiobook=1", "")
        elif o.master.ab:
            e = f"{o.master.ab} {e}".strip()
        if o.master.repr:
            e = f"{o.master.repr} {e}".strip()
        if o.master.crp and "{{crp}}" not in e.lower() and "{{crp}}" not in zn.lower():
            e = "{{Crp}} " + e
        if section_name.startswith("Non-canon"):
            e = re.sub("\{\{[Nn]cm}}", "{{Mo}}", re.sub("\{\{[Nn]cs?(\|.*?)?}}", "", e))
        elif nc and nc.lower() not in e.lower():
            e = f"{e} {nc}"
        if o.master.unlicensed and not unlicensed and "{{Un}}" not in e and "{{un}}" not in e:
            e += " {{Un}}"
        z = swap_parameters(f"{zn} {e}").strip()
        if not is_file and o.master.date and o.master.date.startswith("Cancel") and "{{c|cancel" not in z.lower():
            z += " {{C|canceled}}"
        if (o.master.mode == "Minis" or o.master.template == "SWIA") and o.master.card:
            z = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", re.sub(" ?\{\{[Cc]\|[Rr]eissued.*?}}", "", z))
        z = z.replace("–", "&ndash;").replace("—", "&mdash;").replace("  ", " ").replace("|parent=1", "")
        # z = re.sub("\|stext=(.*?)\|\\1\|", "|stext=\\1|", z)
        final_items.append(o)
        final_without_extra.append(zn)
        new_text.append(z)
        return 1


def build_date_text(o: ItemId, include_date):
    if o.current.override and o.current.override_date:
        return f"<!-- {o.current.override}: {o.current.override_date} -->"
    elif o.current.override_date:
        return f"<!-- {o.current.override_date} -->"
    elif o.current.unknown and o.current.original_date:
        return f'<!-- {o.current.original_date}? -->'
    elif not o.master.has_date() and o.current.original_date:
        return f'<!-- {o.current.original_date}? -->'
    elif not o.master.has_date():
        return '<!-- Unknown -->'
    elif include_date:
        return f"<!-- {o.master.date} -->" if o.master.date != 'Current' else ''
    elif o.master.has_date() or o.master.date == 'Future' or o.master.date == 'Canceled':
        return ''
    else:
        return '<!-- Unknown -->'


def compile_found(section: SectionItemIds, mode, canon):
    source_names = {}
    urls = {}
    missing = []
    previous = None
    group = []
    new_found = []
    i = 0

    for o in section.found:
        i += 1
        if o.current.target:
            t = o.current.target.split("(")[0].strip() if o.current.target else None
            if t and t not in source_names:
                source_names[t] = []
            source_names[t].append(o)
        if o.current.url:
            u = f"{o.current.template}|{o.current.url}"
            if "|oldversion=1" in o.current.original:
                u += "|oldversion=1"
            if u in urls:
                print(f"Skipping duplicate entry: {u}")
            else:
                urls[u] = o

        if mode == BY_INDEX:
            if section.is_appearances and o.master.timeline_index(canon) is None:
                group.append(o)
            elif not section.is_appearances and o.master.index is None:
                group.append(o)
            else:
                new_found.append(o)
                if group:
                    missing.append((previous, group))
                    group = []
                previous = o
        elif o.current.template == "TCWA" and mode == BY_DATE:
            group.append(o)
        elif o.current.old_version or o.current.template == "ForceCollection":
            group.append(o)
        elif o.current.override and not o.current.override_date:
            group.append(o)
        elif o.master.has_date():
            if o.current.index is None and "audiobook" not in o.master.original and "(audio)" not in o.master.original and "(audio drama)" not in o.master.original:
                print(f"No index? {o.current.original}, {o.master.original}")
            new_found.append(o)
            if group:
                missing.append((previous, group))
                group = []
            previous = o
        else:
            group.append(o)
    if group:
        missing.append((previous, group))

    return new_found, group, missing, source_names


def handle_sorting(mode, new_found: List[ItemId], missing: List[Tuple[ItemId, List[ItemId]]], canon: bool, use_index: bool, log: bool):
    if mode == UNCHANGED:
        found = new_found
    elif mode == BY_INDEX:
        found = sorted(new_found, key=lambda a: (a.master.sort_index(canon), a.current.index or 0))
    elif use_index:
        found = sorted(new_found, key=lambda a: (a.sort_date(), a.master.sort_mode, a.master.sort_index(canon) or 100000, a.sort_text()))
    else:
        found = sorted(new_found, key=lambda a: (a.sort_date(), a.master.sort_mode, a.sort_text(), a.master.sort_index(canon)))

    start, special, jtc, end = [], [], [], []
    for previous, items in missing:
        try:
            index = found.index(previous)
        except ValueError:
            index = None

        for m in (reversed(items) if found else items):
            if m.master.date == "Canceled" or m.current.target == "Star Wars: Galaxy of Heroes":
                end.append(m)
            elif m.current.template == "JTC":
                jtc.append(m)
            elif m.current.target in LIST_AT_START:
                special.append(m)
            elif previous is None:
                start.append(m)
            elif index is None:
                end.append(m)
            else:
                if mode == BY_INDEX and not m.master.unlicensed:
                    print(f"Missing master index for current index {m.current.index} -> {index + 1}: {m.current.original}")
                found.insert(index + 1, m)
    if special:
        start = sorted(special, key=lambda a: a.master.original) + start
    if jtc:
        start += reversed(jtc)

    return start + found + end


def compare_partial_dates(o: str, d1: str, d2: str, mode: str):
    try:
        xn = o.count("XX")
        if d1 is None or d2 is None:
            return False
        elif d1 == o or d2 == o or mode == "Toys":
            return False    # toys or same neighbor
        elif d2.startswith(f"{o[:4]}-XX-XX"):
            return False    # next neighbor has no month/day
        elif is_number(d1) and is_number(d2) and int(d1[:4]) < int(o[:4]) < int(d2[:4]):
            return False
        elif xn == 2 and d1.count("XX") == 1 and d1[:4] != d2[:4] and d1[:4] == o[:4]:
            return False    # no month/day, and neighbors are different years
        elif xn == 1 and d1.count("XX") == 1 and d2.count("XX") == 1:
            return False    # neither neighbor has day
        elif is_number(d1) and is_number(d2) and int(d1[:4]) < int(o[:4]) and d2[:4] == o[:4] and xn < 2 and d2.count("XX") < 2 and int(o[5:7]) < int(d2[5:7]):
            return False    # prior year & same year, later month
        elif is_number(d1) and is_number(d2) and d1[:4] == o[:4] and d1.count("XX") < 2 and xn < 2 and int(d1[5:7]) < int(o[5:7]):
            return False    # same year, earlier month
    except Exception as e:
        print(f"Encountered {type(e)}: {e}")
    return True


def get_analysis_from_page(target: Page, infoboxes: dict, types, disambigs, appearances: FullListData,
                           sources: FullListData, remap: dict, log=True, collapse_audiobooks=True):
    results, unknown, redirects = build_page_components(target, types, disambigs, appearances, sources, remap,
                                                        infoboxes,False, log)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    _, _, _, analysis = analyze_section_results(target, results, disambigs, appearances, sources, remap, True,
                                                False, collapse_audiobooks, [], log)
    return analysis
