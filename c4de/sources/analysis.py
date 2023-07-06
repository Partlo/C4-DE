import codecs
import re

from pywikibot import Site, Page
from typing import List, Dict, Tuple

from c4de.sources.engine import extract_item, determine_id_for_item, FullListData, Item, ItemId, PARAN, \
    convert_issue_to_template


KEEP_TEMPLATES = ["TCWA", "Twitter", "FacebookCite"]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"]
}


class PageComponents:
    def __init__(self, before):
        self.before = before

        self.ncs = SectionComponents([], [], [], '')
        self.src = SectionComponents([], [], [], '')
        self.nca = SectionComponents([], [], [], '')
        self.apps = SectionComponents([], [], [], '')


class AnalysisResults:
    def __init__(self, apps: List[ItemId], nca: List[ItemId], src: List[ItemId], ncs: List[ItemId], canon: bool):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.canon = canon


class SectionItemIds:
    def __init__(self, found: List[ItemId], wrong: List[ItemId], cards: Dict[str, List[ItemId]], sets: Dict[str, str]):
        self.found = found
        self.wrong = wrong
        self.cards = cards
        self.sets = sets


class SectionComponents:
    def __init__(self, items: list[Item], pre: list[str], suf: list[str], after: str):
        self.items = items
        self.preceding = pre
        self.trailing = suf
        self.after = after


def analyze_body(text, appearances: FullListData, sources: FullListData, log: bool):
    references = re.findall("(<ref name=.*?[^/]>(.*?)</ref>)", text)
    new_text = text
    for full_ref, ref in references:
        try:
            new_ref = re.sub("<!--[ 0-9/X-]+-->", "", ref.replace("&ndash;", '–').replace('&mdash;', '—'))
            new_ref = convert_issue_to_template(new_ref)
            links = re.findall("(['\"]*\[\[.*?(\|.*?)?\]\]['\"]*)", new_ref)
            templates = re.findall("(\{\{[^\{\}\n]+\}\})", new_ref)
            templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)
            templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)

            new_links = []
            for link in links:
                x = extract_item(link[0], False, "reference")
                if x:
                    o = determine_id_for_item(x, appearances.unique, appearances.target, sources.unique, sources.target, {}, log)
                    if o and not o.use_original_text:
                        if link[0].startswith('"') and link[0].startswith('"') and (len(ref) - len(link[0])) > 5:
                            print(f"Skipping quote-enclosed link {link[0]} (likely an episode name)")
                        elif "{{" in o.master.original and len(templates) > 0:
                            print(f"Skipping {link[0]} due to presence of other templates in ref note")
                        elif o.master.original.isnumeric():
                            print(f"Skipping {link[0]} due to numeric text")
                        elif x.format_text and o.master.target and "(" in o.master.target and o.master.target.split("(")[0].strip().lower() not in x.format_text.replace("''", "").lower():
                            print(f"Skipping {link[0]} due to non-standard pipelink: {x.format_text}")
                        elif x.target in SPECIAL and x.text and x.text.replace("''", "") in SPECIAL[x.target]:
                            print(f"Skipping exempt {link[0]}")
                        else:
                            if "TODO" in o.master.original:
                                print(link[0], x.full_id(), o.master.original, o.current.original)
                            new_links.append((link[0], o))

            for ot, nt in new_links:
                new_ref = new_ref.replace(ot, nt.master.original)

            new_templates = []
            for t in templates:
                if t == "{{'s}}":
                    continue
                x = extract_item(t, False, "reference")
                if x:
                    o = determine_id_for_item(x, appearances.unique, appearances.target, sources.unique, sources.target,
                                              {}, log)
                    if o and not o.use_original_text:
                        ex = []
                        if "|author=" in t:
                            ex += re.findall("(\|author=.*?)[\|\}]", t)
                        if "|date=" in t:
                            ex += re.findall("(\|date=.*?)[\|\}]", t)
                        if "|quote=" in t:
                            ex += re.findall("(\|quote=.*?)[\|\}]", t)
                        if "TODO" in o.master.original:
                            print(t, x.full_id(), o.master.original, o.current.original)
                        new_templates.append((t, o, ex))

            for ot, nt, extra in new_templates:
                z = nt.master.original
                if extra:
                    z = z[:-2] + "".join(extra) + "}}"
                if "|d=y" in nt.current.original:
                    z = z[:-2] + "|d=y}}"
                new_ref = new_ref.replace(ot, z)

            final_ref = full_ref.replace(ref, new_ref).replace('–', '&ndash;').replace('—', '&mdash;')
            new_text = new_text.replace(full_ref, final_ref)
        except Exception as e:
            print(f"Encountered {e} while handling reference", type(e))

    return new_text


def parse_section(section: str, is_appearances: bool, unknown: list, after: str, log) -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    data = []
    unique_ids = {}
    other1, other2 = [], []
    start = True
    cs = 0
    for s in section.splitlines():
        if "CardGameSet" in s:
            s = re.sub("{{CardGameSet\|(set=)?.*?\|cards=", "", s)
            cs += 1
        if s.strip().startswith("<!-"):
            s = re.sub("<\!--.*?-->", "", s)
        if s.strip().startswith("*"):
            start = False
            z = s[1:].replace("&ndash;", '–').replace('&mdash;', '—')
            ex = re.search('( ?(<small>)? ?\{+ ?(1st[A-z]*|[A-z][od]|[Ff]act|[Ll]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[\|\}].*?$)', z)
            extra = ex.group(1) if ex else ''
            if extra:
                z = z.replace(extra, '').strip()

            t = extract_item(convert_issue_to_template(z), is_appearances, "target")
            if t:
                data.append(t)
                t.extra = extra
                unique_ids[t.unique_id()] = t
            else:
                unknown.append(s)
                if log:
                    print(f"Unknown: {s}")
        elif "{{imagecat" in s.lower() or "{{mediacat" in s.lower():
            other1.append(s)
        elif s == "}}" and cs > 0:
            cs = 0
        elif re.match("^<\!--.*?-->$", s):
            continue
        elif start and s.strip():
            other1.append(s)
        elif s.strip():
            other2.append(s)
    return SectionComponents(data, other1, other2, after)


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def build_item_ids_for_section(site, name, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                               unknown: List[Item], log) -> SectionItemIds:

    found = []
    wrong = []
    cards = {}
    extra = {}
    for i, o in enumerate(original):
        o.index = i
        d = determine_id_for_item(o, data.unique, data.target, other.unique, other.target, remap, log)
        if not d and (is_external_wiki(o.target) or is_external_wiki(o.parent)):
            d = ItemId(o, o, True, False)
        if not d and o.target:
            p = Page(site, o.target)
            if p.exists() and p.isRedirectPage():
                if log:
                    print(f"Followed redirect {o.target} to {p.getRedirectTarget().title()}")
                o.target = p.getRedirectTarget().title()
                d = determine_id_for_item(o, data.unique, data.target, other.unique, other.target, remap, log)
        if not d and o.parent:
            p = Page(site, o.parent)
            if p.exists() and p.isRedirectPage():
                if log:
                    print(f"Followed redirect {o.parent} to {p.getRedirectTarget().title()}")
                o.parent = p.getRedirectTarget().title()
                d = determine_id_for_item(o, data.unique, data.target, other.unique, other.target, remap, log)

        if d and o.mode == "Cards":
            parent_set = d.master.parent if d.master.parent else d.master.target
            if o.template == "SWCT":
                parent_set = d.master.card or parent_set
            if parent_set not in cards:
                cards[parent_set] = []
            if o.card:
                cards[parent_set].append(d)
            elif o.special and d.from_other_data:
                if log:
                    print(f"({name}) Listed in wrong section: {o.original}")
                wrong.append(d)
            elif o.special:
                found.append(d)
            else:
                if log:
                    print(f"No cards found for {parent_set}")
                extra[d.master.target] = d
        elif d and d.current.template in KEEP_TEMPLATES:
            found.append(d)
        elif d and d.from_other_data:
            if log:
                print(f"({name}) Listed in wrong section: {o.original} -> {d.master.is_appearance} {d.master.full_id()}")
            wrong.append(d)
        elif d:
            found.append(d)
        else:
            if log:
                print(f"Cannot find {o.unique_id()}: {o.original}")
            save = True
            if o.is_appearance and o.target:
                p = Page(site, o.target)
                if p.exists() and not p.isRedirectPage():
                    cats = [c.title() for c in p.categories()]
                    if "Category:Media that should be listed in Appearances" in cats:
                        if log:
                            print(f"Removing non-Appearance entry: {o.original}")
                        save = False

            unknown.append(o)
            if save:
                found.append(ItemId(o, o, False))

    set_ids = {}
    for s, c in cards.items():
        if not c:
            continue
        t = data.target.get(s)
        if not t and other.target:
            t = other.target.get(s)
        if not t and c[0].current.template in PARAN:
            t = data.target.get(f"{s} ({PARAN[c[0].current.template][0]})")
            if not t and other.target:
                t = other.target.get(f"{s} ({PARAN[c[0].current.template][0]})")
        if t:
            t[0].index = c[0].current.index
            found.append(ItemId(t[0], t[0], False))
            set_ids[t[0].full_id()] = s
            if t[0].target in extra:
                extra.pop(t[0].target)
        else:
            print(f"ERROR: Cannot find item for parent/target set: [{s}]: {c[0].current.full_id()}")
    found += list(extra.values())

    return SectionItemIds(found, wrong, cards, set_ids)


def has_month_in_date(x: ItemId):
    return x and x.master and x.master.has_date() and "-XX-XX" not in x.master.date


BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"


def build_new_section(section: SectionItemIds, mode: str, dates: list, canon: bool, include_date: bool, log: bool,
                      use_index: bool) -> Tuple[str, List[ItemId]]:
    source_names = {}
    urls = {}
    by_original_index = {o.current.index: o for o in section.found if o.current.index is not None}
    missing = []
    new_found = []
    for o in section.found:
        if o.current.target:
            t = o.current.target.split("(")[0].strip() if o.current.target else None
            if t and t not in source_names:
                source_names[t] = []
            source_names[t].append(o)
        if o.current.url:
            u = f"{o.current.template}|{o.current.url}"
            if u in urls:
                print(f"Skipping duplicate entry: {u}")
            else:
                urls[u] = o

        if mode == BY_INDEX and o.master.sort_index(canon) is None:
            missing.append(o)
        elif mode == BY_INDEX:
            new_found.append(o)
        elif o.master.has_date():
            if o.current.index is None:
                print(f"No index? {o.current.original}, {o.master.original}")
            elif "-XX" in o.master.date:
                n1 = by_original_index.get(o.current.index - 1)
                n2 = by_original_index.get(o.current.index + 1)
                if has_month_in_date(n1) and has_month_in_date(n2) and o.current.mode == "Toys" \
                        and "-XX-XX" in o.master.date and n1.master.date[:4] == o.master.date[:4]:
                    if log:
                        print(f"Moving item from partial date {o.master.date} to {n1.master.date[:8]}XX: {o.current.original}")
                    o.master.date = n1.master.date[:8] + "XX"
            new_found.append(o)
        else:
            missing.append(o)

    found = handle_sorting(mode, new_found, missing, dates, canon, use_index=use_index, log=log)

    new_text = []
    final_items = []
    for o in found:
        if mode == BY_DATE and o.current.index is None:
            if log:
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
                    if log:
                        print(f"Partial date {o.master.date} found between {d1} and {d2}: {o.current.original} ({t1} & {t2})")
                    dates.append((False, o, d1, d2))

        t = o.current.target.split("(")[0] if o.current.target else None
        if t and t in source_names and len(source_names[t]) > 1:
            if o.current.target.count("(") > 0 and o.current.original.count("[[") == 1:
                if log:
                    print(f"Switching text for {o.current.target} to ''{o.current.target}'' ({o.master.date[:4]})")
                o.current.original = f"[[{o.current.target}|''{o.current.target}'' ({o.master.date[:4]}]]"

        d = f"<!-- {o.master.date} -->" if include_date else ''
        if o.current.full_id() in section.sets:
            set_cards = section.cards[section.sets[o.current.full_id()]]
            ct = 0
            if len(set_cards) > 1:
                new_text.append(f"{{{{CardGameSet|set={o.current.original}|cards=")
                ct = 2
            for c in sorted(set_cards, key=lambda a: a.current.original):
                zt = re.sub("<!--[ 0-9/X-]+-->", "", f"*{d}{c.current.original}{c.current.extra}")
                ct += zt.count("{")
                ct -= zt.count("}")
                final_items.append(c)
                new_text.append(zt)
            if ct:
                new_text.append("".join("}" for i in range(ct)))
        else:
            zt = o.current.original if o.use_original_text else o.master.original
            zt = re.sub("<!--[ 0-9/X-]+-->", "", zt)
            z = f"*{d}{zt}{o.current.extra}"
            if z.startswith("**"):
                z = z[1:]
            z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", z)
            z = z.replace("–", "&ndash;").replace("—", "&mdash;")
            if z in new_text:
                if log:
                    print(f"Skipping duplicate {z}")
            else:
                final_items.append(o)
                new_text.append(z)
    # TODO: Canon/Legends check

    return "\n".join(new_text), final_items


def handle_sorting(mode, new_found: List[ItemId], missing: List[ItemId], dates: list, canon: bool, use_index: bool, log: bool):
    if mode == UNCHANGED:
        return new_found
    elif mode == BY_INDEX:
        found = sorted(new_found, key=lambda a: (a.master.sort_index(canon), a.current.index or 0))
    elif use_index:
        found = sorted(new_found, key=lambda a: (a.master.date, a.master.mode == "DB", a.master.sort_index(canon), a.sort_text()))
    else:
        found = sorted(new_found, key=lambda a: (a.master.date, a.master.mode == "DB", a.sort_text(), a.master.sort_index(canon)))

    for m in missing:
        index = handle_missing_entry(m, found, mode, dates, log)
        if index == -1:
            found.append(m)
        elif index >= 0:
            found.insert(index, m)

    return found


def handle_missing_entry(m: ItemId, found: List[ItemId], mode: str, dates: list, log: bool) -> int:
    if m.master.date == "Canceled":
        return -1
    match_text = None
    if m.current.target and re.search("\(.*?audiobook.*?\)", m.current.target):
        match_text = m.current.target.split("(", 1)[0].strip()

    ix1 = None
    ix2 = None
    for i, o in enumerate(found):
        if match_text and o.master.target and o.master.target.split("(novel", 1)[0].strip() == match_text:
            print(f"Found parent for {match_text} audiobook; using index {i} for parent: {o.master.target}")
            return i + 1
        if o.current.index is not None and m.current.index == o.current.index + 1:
            ix1 = i
        elif o.current.index is not None and m.current.index == o.current.index - 1:
            ix2 = i
        if ix1 is not None and ix2 is not None:
            break

    if mode == BY_INDEX:
        print(f"Missing master index for current index {m.current.index} -> {ix1}, {ix2}: {m.current.original}")
    if ix1:
        if mode == BY_DATE:
            d1 = found[ix1 - 1].master.date if ix1 > 0 else None
            d2 = found[ix1 + 1].master.date if (ix1 + 1) < len(found) else None
            if log:
                print(f"Using {ix1} as index (between {d1} | {d2}) for missing-date entry: {m.current.original}")
            dates.append((True, m, d1, d2))
        return ix1
    elif ix2:
        if mode == BY_DATE:
            d1 = found[ix2 - 1].master.date if ix2 > 0 else None
            d2 = found[ix2 + 1].master.date if (ix2 + 1) < len(found) else None
            if log:
                print(f"Using {ix2} as index (between {d1} | {d2}) for missing-date entry: {m.current.original}")
            dates.append((True, m, d1, d2))
        return ix2
    elif m.current.index == 0:
        if mode == BY_DATE:
            d2 = found[1].master.date if len(found) > 1 else None
            if log:
                print(f"Using 0 as index (between start | {d2}) for missing-date entry: {m.current.original}")
            dates.append((True, m, None, d2))
        return 0
    else:
        print(f"Cannot find index {m.current.index} {m.current.original}")
        return -2


def compare_partial_dates(o: str, d1: str, d2: str, mode: str):
    try:
        xn = o.count("XX")
        if d1 is None or d2 is None:
            return False
        elif d1 == o or d2 == o or mode == "Toys":
            return False    # toys or same neighbor
        elif d2 == f"{o[:4]}-XX-XX":
            return False    # next neighbor has no month/day
        elif is_number(d1) and is_number(d2) and int(d1[:4]) < int(o[:4]) < int(d2[:4]):
            return False
        elif xn == 2 and d1.count("XX") == 1 and d1[:4] != d2[:4] and d1[:4] == o[:4]:
            return False    # no month/day, and neighbors are different years
        elif xn == 1 and d1.endswith("-XX") and d2.endswith("-XX"):
            return False    # neither neighbor has day
        elif is_number(d1) and is_number(d2) and int(d1[:4]) < int(o[:4]) and d2[:4] == o[:4] and xn < 2 and d2.count("XX") < 2 and int(o[5:7]) < int(d2[5:7]):
            return False    # prior year & same year, later month
        elif is_number(d1) and is_number(d2) and d1[:4] == o[:4] and d1.count("XX") < 2 and xn < 2 and int(d1[5:7]) < int(o[5:7]):
            return False    # same year, earlier month
    except Exception as e:
        print(f"Encountered {type(e)}: {e}")
    return True


def is_number(d):
    return d and (d.startswith("1") or d.startswith("2"))


def build_section_from_pieces(header: str, section: SectionComponents, items: str, log):
    if log:
        print(f"Creating {header} section with {len(items.splitlines())} items")
    pieces = [header]
    pieces += section.preceding
    pieces.append(items)
    pieces += section.trailing
    diff = 0
    for s in pieces:
        diff += s.count("{{")
        diff -= s.count("}}")
    if diff > 0:
        pieces.append("}}")
    pieces.append(section.after)
    return "\n".join(pieces).strip() + "\n\n"


def build_final_text(results: PageComponents, new_apps: str, new_nca: str, new_sources: str, new_ncs: str, log: bool):
    pieces = [results.before.strip(), ""]
    if new_apps:
        pieces.append(build_section_from_pieces("==Appearances==", results.apps, new_apps, log))
    if new_nca:
        pieces.append(build_section_from_pieces("===Non-canon appearances===", results.nca, new_nca, log))
    if new_sources:
        pieces.append(build_section_from_pieces("==Sources==", results.src, new_sources, log))
    if new_ncs:
        pieces.append(build_section_from_pieces("===Non-canon sources===", results.ncs, new_ncs, log))

    new_txt = re.sub("(?<![\n=])\n==", "\n\n==", re.sub("\n\n+", "\n\n", "\n".join(pieces))).strip()
    replace = True
    while replace:
        new_txt2 = re.sub("(\[\[[^\[\]\r\n]+)&ndash;", "\\1–", re.sub("(\[\[[^\[\]\n]+)&mdash;", "\\1—", new_txt))
        replace = new_txt != new_txt2
        new_txt = new_txt2
    return new_txt


def analyze_section_results(site, target: Page, results: PageComponents, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool, include_date: bool, log) \
        -> Tuple[str, str, str, str, list, list, list, AnalysisResults]:
    dates = []
    unknown_apps, unknown_src = [], []
    new_apps = build_item_ids_for_section(site, "Appearances", results.apps.items, appearances, sources, remap, unknown_apps, log)
    new_nca = build_item_ids_for_section(site, "NC Appearances", results.nca.items, appearances, sources, remap, unknown_apps, log)
    new_src = build_item_ids_for_section(site, "Sources", results.src.items, sources, appearances, remap, unknown_src, log)
    new_ncs = build_item_ids_for_section(site, "Non-canon sources", results.ncs.items, sources, appearances, remap, unknown_src, log)

    if new_apps.wrong or new_nca.wrong:
        if log:
            print(f"Moving {len(new_apps.wrong) + len(new_nca.wrong)} sources from Appearances to Sources")
        new_src.found += new_apps.wrong
        if new_ncs.found:
            new_ncs.found += new_nca.wrong
        else:
            new_src.found += new_nca.wrong
    if new_src.wrong or new_ncs.wrong:
        if log:
            print(f"Moving {len(new_src.wrong) + len(new_ncs.wrong)} sources from Sources to Appearances")
        new_apps.found += new_src.wrong
        if new_ncs.found:
            new_nca.found += new_ncs.wrong
        else:
            new_apps.found += new_ncs.wrong

    canon = False
    app_mode = BY_INDEX
    for c in target.categories():
        if "legends articles" in c.title().lower():
            app_mode = UNCHANGED
        elif "canon articles" in c.title().lower():
            canon = True
    new_apps, final_apps = build_new_section(new_apps, app_mode, dates, canon, include_date, log, use_index)
    new_nca, final_nca = build_new_section(new_nca, UNCHANGED, dates, canon, include_date, log, use_index)
    new_sources, final_sources = build_new_section(new_src, BY_DATE, dates, canon, include_date, log, use_index)
    new_ncs, final_ncs = build_new_section(new_ncs, BY_DATE, dates, canon, include_date, log, use_index)
    analysis = AnalysisResults(final_apps, final_nca, final_sources, final_ncs, canon)
    return new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, analysis


def build_page_components(target: Page, appearances: FullListData, sources: FullListData, handle_references=False,
                          log=True) -> Tuple[PageComponents, list]:
    before = re.sub("({{[Ss]croll[_ ]box\|)\*", "{{Scroll_box|\n*", target.get())
    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    results = PageComponents(before)

    unknown = []
    if "===Non-canon sources===" in before:
        before, nc_sources_section = before.rsplit("===Non-canon sources===", 1)
        if nc_sources_section:
            nc_sources_pieces = nc_sources_section.split("==", 1)
            nc_sources_section = nc_sources_pieces[0]
            after = ("==" + nc_sources_pieces[1]) if len(nc_sources_pieces) > 1 else ''
            results.ncs = parse_section(nc_sources_section, False, unknown, after, log)
            if log:
                print(
                    f"Non-Canon Sources: {len(results.ncs.items)} --> {len(set(i.unique_id() for i in results.ncs.items))}")

    if "==Sources==" in before:
        before, sources_section = before.rsplit("==Sources==", 1)
        if sources_section:
            sources_pieces = sources_section.split("==", 1)
            sources_section = sources_pieces[0]
            after = ("==" + sources_pieces[1]) if len(sources_pieces) > 1 else ''
            results.src = parse_section(sources_section, False, unknown, after, log)
            if log:
                print(f"Sources: {len(results.src.items)} --> {len(set(i.unique_id() for i in results.src.items))}")

    if "===Non-canon appearances===" in before:
        before, nc_app_section = before.rsplit("===Non-canon appearances===", 1)
        if nc_app_section:
            nc_app_pieces = nc_app_section.split("==", 1)
            nc_app_section = nc_app_pieces[0]
            after = ("==" + nc_app_pieces[1]) if len(nc_app_pieces) > 1 else ''
            results.nca = parse_section(nc_app_section, True, unknown, after, log)
            if log:
                print(
                    f"Non-Canon Appearances: {len(results.nca.items)} --> {len(set(i.unique_id() for i in results.nca.items))}")

    if "==Appearances==" in before and "{{App" not in before and "{{app" not in before:
        before, app_section = before.rsplit("==Appearances==", 1)
        if app_section:
            app_pieces = app_section.split("==", 1)
            app_section = app_pieces[0]
            after = ("==" + app_pieces[1]) if len(app_pieces) > 1 else ''
            results.apps = parse_section(app_section, True, unknown, after, log)
            if log:
                print(
                    f"Appearances: {len(results.apps.items)} --> {len(set(i.unique_id() for i in results.apps.items))}")

    results.before = before
    if handle_references:
        results.before = analyze_body(results.before, appearances, sources, log)
    return results, unknown


def get_analysis_from_page(site: Site, target: Page, appearances: FullListData, sources: FullListData, remap: dict,
                           log=True):
    results, unknown = build_page_components(target, appearances, sources, False, log)

    _, _, _, _, _, _, _, analysis = analyze_section_results(site, target, results, appearances, sources, remap, True, False, log)
    return analysis


def analyze_target_page(site: Site, target: Page, appearances: FullListData, sources: FullListData, remap: dict,
                        save: bool, include_date: bool, log=True, use_index=True, handle_references=False):
    results, unknown = build_page_components(target, appearances, sources, handle_references, log)

    new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, analysis = analyze_section_results(
        site, target, results, appearances, sources, remap, use_index, include_date, log)

    new_txt = build_final_text(results, new_apps, new_nca, new_sources, new_ncs, log)

    with codecs.open("C:/Users/Michael/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if dates:
        with codecs.open("C:/Users/Michael/Documents/projects/C4DE/c4de/protocols/new_dates.txt", mode="a", encoding="utf-8") as f:
            date_txt = []
            for d in dates:
                if d[2] == d[3]:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]}:  -> {d[1].master.original}")
                else:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]} {d[3]}:  -> {d[1].master.original}")
            f.writelines("\n" + "\n".join(date_txt))

    if save:
        target.put(new_txt, "Source Engine analysis of Appearances, Sources and references")

    results = []
    with codecs.open("C:/Users/Michael/Documents/projects/C4DE/c4de/protocols/unknown.txt", mode="a",
                     encoding="utf-8") as f:
        if unknown_apps:
            results.append("Could not identify unknown appearances:")
            for o in unknown_apps:
                results.append(f"- `{o.original}`")
                if o.original.startswith("*"):
                    print(target.title(), o.original)
            f.writelines("\n" + "\n".join([o.original for o in unknown_apps]))

        if unknown_src:
            results.append("Could not identify unknown sources:")
            for o in unknown_src:
                results.append(f"- `{o.original}`")
                if o.original.startswith("*"):
                    print(target.title(), o.original)
            f.writelines("\n" + "\n".join([o.original for o in unknown_src]))

    return results
