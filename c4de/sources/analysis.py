import codecs
import re

from pywikibot import Site, Page
from typing import List, Dict, Tuple

from c4de.sources.engine import extract_item, determine_id_for_item, FullListData, Item, ItemId, PARAN


KEEP_TEMPLATES = ["TCWA", "Twitter", "FacebookCite"]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"]
}


def analyze_body(text, appearances: FullListData, sources: FullListData, remap: dict, log: bool):
    references = re.findall("(<ref name=.*?[^/]>(.*?)</ref>)", text)
    new_text = text
    for full_ref, ref in references:
        try:
            new_ref = ref.replace("&ndash;", '–').replace('&mdash;', '—')
            links = re.findall("('*\[\[.*?(\|.*?)?\]\]'*)", new_ref)
            templates = re.findall("(\{\{[^\{\}\n]+\}\})", new_ref)
            templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)
            templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)

            new_links = []
            for link in links:
                x = extract_item(link[0], False, "reference")
                if x:
                    o = determine_id_for_item(x, appearances.unique, appearances.target, sources.unique, sources.target, remap, log)
                    if o and not o.use_original_text:
                        if "{{" in o.master.original and len(templates) > 0:
                            print(f"Skipping {link[0]} due to presence of other templates in ref note")
                        elif o.master.original.isnumeric():
                            print(f"Skipping {link[0]} due to numeric text")
                        elif x.text and o.master.target and "(" in o.master.target and o.master.target.split("(")[0].strip() not in x.text:
                            print(f"Skipping {link[0]} due to non-standard pipelink")
                        elif x.target in SPECIAL and x.text and x.text.replace("''", "") in SPECIAL[x.target]:
                            print(f"Skipping exempt {link[0]}")
                        else:
                            new_links.append((link[0], o))

            for ot, nt in new_links:
                new_ref = new_ref.replace(ot, nt.master.original)

            new_templates = []
            for t in templates:
                if t == "{{'s}}":
                    continue
                x = extract_item(t, False, "reference")
                if x:
                    o = determine_id_for_item(x, appearances.unique, appearances.target, sources.unique, sources.target, remap, log)
                    if o and not o.use_original_text:
                        ex = []
                        if "|author=" in t:
                            ex += re.findall("(\|author=.*?)[\|\}]", t)
                        if "|date=" in t:
                            ex += re.findall("(\|date=.*?)[\|\}]", t)
                        if "|quote=" in t:
                            ex += re.findall("(\|quote=.*?)[\|\}]", t)
                        new_templates.append((t, o, ex))

            for ot, nt, extra in new_templates:
                z = nt.master.original
                if extra:
                    z = z[:-2] + "".join(extra) + "}}"
                new_ref = new_ref.replace(ot, z)

            final_ref = full_ref.replace(ref, new_ref).replace('–', '&ndash;').replace('—', '&mdash;')
            new_text = new_text.replace(full_ref, final_ref)
        except Exception as e:
            print(f"Encountered {e} while handling reference", type(e))

    return new_text


def parse_section(section: str, is_appearances: bool, unknown: list, log) -> Tuple[List[Item], List[str], List[str]]:
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
        if s.strip().startswith("*"):
            start = False
            s = s[1:].replace("&ndash;", '–').replace('&mdash;', '—')
            ex = re.search('( ?(<small>)? ?\{+ ?(1st[A-z]*|[A-z][od]|[Ff]act|[Ll]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[\|\}].*?$)', s)
            extra = ex.group(1) if ex else ''
            if extra:
                s = s.replace(extra, '').strip()

            t = extract_item(s, is_appearances, "target")
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
        elif re.match("^<!--.*?-->$", s):
            continue
        elif start and s.strip():
            other1.append(s)
        elif s.strip():
            other2.append(s)
    return data, other1, other2


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def build_item_ids_for_section(site, name, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                               unknown: List[Item], log) \
        -> Tuple[List[ItemId], List[ItemId], Dict[str, List[ItemId]], Dict[str, str]]:

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

    return found, wrong, cards, set_ids


def has_month_in_date(x: ItemId):
    return x and x.master and x.master.has_date() and "-XX-XX" not in x.master.date


def build_new_section(found: List[ItemId], cards: Dict[str, List[ItemId]], set_ids: Dict[str, str], should_sort: bool,
                      dates: list, include_date: bool, log, use_index):
    source_names = {}
    urls = {}
    by_original_index = {o.current.index: o for o in found if o.current.index is not None}
    missing = []
    new_found = []
    for o in found:
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
        if o.master.has_date():
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

    if should_sort:
        if use_index:
            found = sorted(new_found, key=lambda a: (a.master.date, a.master.index, a.sort_text()))
        else:
            found = sorted(new_found, key=lambda a: (a.master.date, a.sort_text(), a.master.index))
        for m in missing:
            if m.master.date == "Canceled":
                found.append(m)
                continue
            ix = None
            for i, o in enumerate(found):
                if o.current.index is not None and m.current.index == o.current.index + 1:
                    ix = i
                    break
            if ix:
                d1 = found[ix - 1].master.date if ix > 0 else None
                d2 = found[ix + 1].master.date if (ix + 1) < len(found) else None
                if log:
                    print(f"Using {ix} as index (between {d1} | {d2}) for missing-date entry: {m.current.original}")
                found.insert(ix, m)
                dates.append((True, m, d1, d2))
            elif m.current.index == 0:
                d2 = found[1].master.date if len(found) > 1 else None
                if log:
                    print(f"Using 0 as index (between start | {d2}) for missing-date entry: {m.current.original}")
                found.insert(0, m)
                dates.append((True, m, None, d2))
            else:
                print(f"Cannot find index {m.current.index} {m.current.original}")

        for o in found:
            if o.current.index is None:
                if log:
                    print(f"No index? {o.current.original}, {o.master.original}")
                continue
            elif o.current.is_appearance:
                continue
            elif o.master.has_date() and ("-XX" in o.master.date or o.master.date.startswith("Unknown")):
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

    new_text = []
    for o in found:
        t = o.current.target.split("(")[0] if o.current.target else None
        if t and t in source_names and len(source_names[t]) > 1:
            if o.current.target.count("(") > 0 and o.current.original.count("[[") == 1:
                if log:
                    print(f"Switching text for {o.current.target} to ''{o.current.target}'' ({o.master.date[:4]})")
                o.current.original = f"[[{o.current.target}|''{o.current.target}'' ({o.master.date[:4]}]]"

        d = f"<!-- {o.master.date} -->" if include_date else ''
        if o.current.full_id() in set_ids:
            set_cards = cards[set_ids[o.current.full_id()]]
            if len(set_cards) > 1:
                new_text.append(f"{{{{CardGameSet|set={o.current.original}|cards=")
            for c in sorted(set_cards, key=lambda a: a.current.original):
                new_text.append(f"*{d}{c.current.original}{c.current.extra}")
            if len(set_cards) > 1:
                new_text.append("}}")
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
                new_text.append(z)
    # TODO: Canon/Legends check

    return "\n".join(new_text)


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


def build_section_from_pieces(header: str, preceding: List[str], items: str, trailing: List[str], after: str, log):
    if log:
        print(f"Creating {header} section with {len(items.splitlines())} items")
    pieces = [header]
    pieces += preceding
    pieces.append(items)
    pieces += trailing
    diff = 0
    for s in pieces:
        diff += s.count("{{")
        diff -= s.count("}}")
    if diff > 0:
        pieces.append("}}")
    pieces.append(after)
    return "\n".join(pieces).strip() + "\n\n"


def analyze_target_page(site: Site, target: Page, appearances: FullListData, sources: FullListData, remap: dict,
                        save: bool, include_date: bool, log=True, use_index=True, handle_references=False):
    before = target.get()
    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    ncs_after, src_after, nca_after, app_after = '', '', '', ''

    unknown = []
    ncs, ncs_pre, ncs_suf = [], [], []
    if "===Non-canon sources===" in before:
        before, nc_sources_section = before.rsplit("===Non-canon sources===", 1)
        if nc_sources_section:
            nc_sources_pieces = nc_sources_section.split("==", 1)
            nc_sources_section = nc_sources_pieces[0]
            ncs_after = ("==" + nc_sources_pieces[1]) if len(nc_sources_pieces) > 1 else ''
            ncs, ncs_pre, ncs_suf = parse_section(nc_sources_section, False, unknown, log)
            if log:
                print(f"Non-Canon Sources: {len(ncs)} --> {len(set(i.unique_id() for i in ncs))}")

    src, src_pre, src_suf = [], [], []
    if "==Sources==" in before:
        before, sources_section = before.rsplit("==Sources==", 1)
        if sources_section:
            sources_pieces = sources_section.split("==", 1)
            sources_section = sources_pieces[0]
            src_after = ("==" + sources_pieces[1]) if len(sources_pieces) > 1 else ''
            src, src_pre, src_suf = parse_section(sources_section, False, unknown, log)
            if log:
                print(f"Sources: {len(src)} --> {len(set(i.unique_id() for i in src))}")

    nca, nca_pre, nca_suf = [], [], []
    if "===Non-canon appearances===" in before:
        before, nc_app_section = before.rsplit("===Non-canon appearances===", 1)
        if nc_app_section:
            nc_app_pieces = nc_app_section.split("==", 1)
            nc_app_section = nc_app_pieces[0]
            nca_after = ("==" + nc_app_pieces[1]) if len(nc_app_pieces) > 1 else ''
            nca, nca_pre, nca_suf = parse_section(nc_app_section, True, unknown, log)
            if log:
                print(f"Non-Canon Appearances: {len(nca)} --> {len(set(i.unique_id() for i in nca))}")

    apps, apps_pre, apps_suf = [], [], []
    if "==Appearances==" in before and "{{App" not in before and "{{app" not in before:
        before, app_section = before.rsplit("==Appearances==", 1)
        if app_section:
            app_pieces = app_section.split("==", 1)
            app_section = app_pieces[0]
            app_after = ("==" + app_pieces[1]) if len(app_pieces) > 1 else ''
            apps, apps_pre, apps_suf = parse_section(app_section, True, unknown, log)
            if log:
                print(f"Appearances: {len(apps)} --> {len(set(i.unique_id() for i in apps))}")

    dates = []
    unknown_apps, unknown_src = [], []
    found_apps, wrong_apps, apps_cards, apps_sets = build_item_ids_for_section(
        site, "Appearances", apps, appearances, sources, remap, unknown_apps, log)
    found_nca, wrong_nca, nca_cards, nca_sets = build_item_ids_for_section(
        site, "NC Appearances", nca, appearances, sources, remap, unknown_apps, log)
    found_src, wrong_src, src_cards, src_sets = build_item_ids_for_section(
        site, "Sources", src, sources, appearances, remap, unknown_src, log)
    found_ncs, wrong_ncs, ncs_cards, ncs_sets = build_item_ids_for_section(
        site, "Non-canon sources", ncs, sources, appearances, remap, unknown_src, log)

    if handle_references:
        before = analyze_body(before, appearances, sources, remap, log)

    if wrong_apps or wrong_nca:
        if log:
            print(f"Moving {len(wrong_apps) + len(wrong_nca)} sources from Appearances to Sources")
        found_src += wrong_apps
        if found_ncs:
            found_ncs += wrong_nca
        else:
            found_src += wrong_nca
    if wrong_src or wrong_ncs:
        if log:
            print(f"Moving {len(wrong_src) + len(wrong_ncs)} sources from Sources to Appearances")
        found_apps += wrong_src
        if found_ncs:
            found_nca += wrong_ncs
        else:
            found_apps += wrong_ncs

    new_apps = build_new_section(found_apps, apps_cards, apps_sets, False, dates, include_date, log, use_index)
    new_nca = build_new_section(found_nca, nca_cards, nca_sets, False, dates, include_date, log, use_index)
    new_sources = build_new_section(found_src, src_cards, src_sets, True, dates, include_date, log, use_index)
    new_ncs = build_new_section(found_ncs, ncs_cards, ncs_sets, True, dates, include_date, log, use_index)

    pieces = [before.strip(), ""]
    if new_apps:
        pieces.append(build_section_from_pieces("==Appearances==", apps_pre, new_apps, apps_suf, app_after, log))
    if new_nca:
        pieces.append(build_section_from_pieces("===Non-canon appearances===", nca_pre, new_nca, nca_suf, nca_after, log))
    if new_sources:
        pieces.append(build_section_from_pieces("==Sources==", src_pre, new_sources, src_suf, src_after, log))
    if new_ncs:
        pieces.append(build_section_from_pieces("===Non-canon sources===", ncs_pre, new_ncs, ncs_suf, ncs_after, log))

    new_txt = re.sub("(?<![\n=])\n==", "\n\n==", re.sub("\n\n+", "\n\n", "\n".join(pieces))).strip()
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

    # showDiff(target.get(), new_txt)
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
