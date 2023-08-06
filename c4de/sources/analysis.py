import codecs
import re
import traceback
from datetime import datetime, timedelta

from pywikibot import Page, Category, showDiff
from typing import List, Dict, Tuple

from c4de.sources.engine import extract_item, determine_id_for_item, PARAN, \
    convert_issue_to_template
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, AnalysisResults, SectionComponents, \
    SectionItemIds, FinishedSection
from c4de.sources.infoboxer import handle_infobox_on_page

KEEP_TEMPLATES = ["TCWA", "Twitter", "FacebookCite"]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"],
    "Star Wars: The Essential Atlas Online Companion": ["''[[Star Wars: The Essential Atlas Online Companion]]''"]
}


def prepare_title(t):
    for i in ['(', ')', '?', '!']:
        t = t.replace(i, '\\' + i)
    return "[" + t[0].capitalize() + t[0].lower() + "]" + t[1:]


def fix_redirects(redirects: Dict[str, str], text, section_name):
    for r, t in redirects.items():
        if f"[[{r.lower()}" in text.lower() or f"={r.lower()}" in text.lower():
            print(f"Fixing {section_name} redirect {r} to {t}")
            x = prepare_title(r)
            text = re.sub("\[\[" + x + "\|('')?(" + prepare_title(t) + ")('')?\]\]", f"\\1[[\\2]]\\1", text)
            text = re.sub("\[\[" + x + "(\|.*?)\]\]", f"[[{t}\\1]]", text)
            text = re.sub("\[\[(" + x + ")\]\]", f"[[{t}|\\1]]", text)
            text = text.replace(f"set={r}", f"set={t}")
            text = text.replace(f"book={r}", f"book={t}")
    return text


def build_redirects(page: Page):
    results = {}
    for r in page.linkedPages():
        if is_redirect(r):
            results[r.title()] = r.getRedirectTarget().title()
    return results


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, redirects, log: bool):
    references = re.findall("(<ref name=.*?[^/]>(.*?)</ref>)", text)
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, redirects, log)
    return new_text


def handle_reference(full_ref, ref, page: Page, new_text, types, appearances: FullListData, sources: FullListData, remap, redirects, log: bool):
    try:
        new_ref = fix_redirects(redirects, ref, "Reference")
        new_ref = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", new_ref.replace("&ndash;", '–').replace('&mdash;', '—'))
        new_ref = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|'*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?([^\[\}\r\n]+?)'*\}\}(</small>)?",
                   "{{StarshipsVehiclesCite|\\1|\\4|\\6}}", new_ref)
        new_ref = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|('*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?(.*?)'*)\}\}(</small>)?",
                   "{{StarshipsVehiclesCite|\\1|multiple=\\4}}", new_ref)
        new_ref = convert_issue_to_template(new_ref)
        links = re.findall("(['\"]*\[\[(?![Ww]:c:).*?(\|.*?)?\]\]['\"]*)", new_ref)
        templates = re.findall("(\{\{[^\{\}\n]+\}\})", new_ref)
        templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)
        templates += re.findall("(\{\{[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\{\{[^\{\}\n]+\}\}[^\{\}\n]+\}\})", new_ref)

        new_links = []
        for link in links:
            x = extract_item(link[0], False, "reference", types)
            if x:
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique, sources.target, remap, log)
                if o and not o.use_original_text and o.replace_references:
                    if o.master.template and not x.template and x.target and not re.search("^['\"]*\[\[" + x.target + "(\|.*?)?\]\]['\"]*$", new_ref):
                        print(f"Skipping {link[0]} due to extraneous text")
                    elif link[0].startswith('"') and link[0].startswith('"') and (len(ref) - len(link[0])) > 5:
                        print(f"Skipping quote-enclosed link {link[0]} (likely an episode name)")
                    elif "{{" in o.master.original and len(templates) > 0:
                        print(f"Skipping {link[0]} due to presence of other templates in ref note")
                    elif o.master.original.isnumeric():
                        print(f"Skipping {link[0]} due to numeric text")
                    elif x.format_text and o.master.target and "(" in o.master.target and o.master.target.split("(")[0].strip().lower() not in x.format_text.replace("''", "").lower():
                        print(f"Skipping {link[0]} due to non-standard pipelink: {x.format_text}")
                    elif x.target in SPECIAL and x.text and x.text.replace("''", "") in SPECIAL[x.target]:
                        print(f"Skipping exempt {link[0]}")
                    elif x.target in SPECIAL and x.original in SPECIAL[x.target]:
                        print(f"Skipping exempt {link[0]}")
                    elif re.search("^['\"]*\[\[" + x.target.replace("(", "\(").replace(")", "\)") + "(\|.*?)?\]\]['\"]*", new_ref):
                        if "TODO" in o.master.original:
                            print(link[0], x.full_id(), o.master.original, o.current.original)
                        new_links.append((link[0], o))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", ni.master.original))

        new_templates = []
        for t in templates:
            if t == "{{'s}}" or "{{TORcite" in t or t.startswith("{{C|") or t.startswith("{{Blogspot") or t.startswith("{{Cite"):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and x.template.endswith("Date"):
                    continue
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique,
                                          sources.target, {}, log)
                if o and not o.use_original_text:
                    ex = []
                    if "|author=" in t:
                        ex += [r[0] for r in re.findall("(\|author=(\[\[.*?\|.*?\]\])?.*?)[\|\}]", t)]
                    if "|date=" in t:
                        ex += re.findall("(\|date=.*?)[\|\}]", t)
                    if "|quote=" in t:
                        ex += re.findall("(\|quote=.*?)[\|\}]", t)
                    if "TODO" in o.master.original:
                        print(t, x.full_id(), o.master.original, o.current.original)
                    new_templates.append((t, o, ex))

        for ot, ni, extra in new_templates:
            z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", ni.master.original)
            if ni.current.subset:
                z = re.sub("({{[^\|\}]*?\|(set=)?[^\|\}]*?\|(stext=.*?\|)?)", f"\\1subset={ni.current.subset}|", z)
            if extra:
                z = z[:-2] + "".join(extra) + "}}"
            if "|d=y" in ni.current.original:
                z = z[:-2] + "|d=y}}"
            new_ref = new_ref.replace(ot, z)

        final_ref = full_ref.replace(ref, new_ref).replace('–', '&ndash;').replace('—', '&mdash;').replace("film]] film", "film]]").replace("|reprint=yes", "")
        new_text = new_text.replace(full_ref, final_ref)
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return new_text


def parse_section(section: str, types: dict, is_appearances: bool, unknown: list, after: str, log) -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    data = []
    unique_ids = {}
    other1, other2 = [], []
    start = True
    succession_box = False
    cs = 0
    section = re.sub("({{CardGameSet\|set=.*?)\n\|cards=", "\\1|cards=\n", section)
    section = re.sub("'*\[\[Star Wars Miniatures\]\]'*: '*\[\[(.*?)(\|.*?)?\]\]'*", "{{SWMiniCite|set=\\1}}", section)
    for s in section.splitlines():
        if succession_box:
            other2.append(s)
            continue
        if "CardGameSet" in s:
            s = re.sub("{{CardGameSet\|(set=)?.*?\|cards=", "", s)
            cs += 1
        if s.strip().startswith("<!-"):
            s = re.sub("<\!--.*?-->", "", s)

        if s.strip().startswith("*"):
            if s.endswith("}}}}") and s.count("{{") < s.count("}}"):
                s = s[:-2]
            start = False
            z = s[1:].replace("&ndash;", '–').replace('&mdash;', '—')
            z = re.sub("(\{\{InsiderCite\|[0-9]{2}\|)Ask Lobot.*?}}", "\\1Star Wars Q&A}}", z)
            ex = re.search('( ?(<small>)? ?\{+ ?(1st[A-z]*|[A-z][od]|[Ff]act|[Ll]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[\|\}].*?$)', z)
            extra = ex.group(1) if ex else ''
            if extra:
                z = z.replace(extra, '').strip()

            x = re.search("^(.*?\]\]'*) / ('*\[.*?)$", z)
            if x and log:
                print(f"Splitting multi-entry line: {s}")
            zs = [x.group(1), x.group(2)] if x else [z]
            found = False
            for y in zs:
                t = extract_item(convert_issue_to_template(y), is_appearances, "target", types)
                if t:
                    found = True
                    data.append(t)
                    t.extra = extra
                    ex = re.search("<!-- ?(Exception|Override):? ?([0-9X-]+)? ?-->", s)
                    if ex:
                        t.override = ex.group(1)
                        t.override_date = ex.group(2)
                    unique_ids[t.unique_id()] = t
            if not found:
                unknown.append(s)
                if log:
                    print(f"Unknown: {s}")
        elif "{{start_box" in s.lower() or "{{start box" in s.lower():
            succession_box = True
            other2.append(s)
        elif "{{imagecat" in s.lower() or "{{mediacat" in s.lower():
            other1.append(s)
        elif s == "}}":
            if cs > 0:
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


def is_redirect(page):
    try:
        return page.exists() and page.isRedirectPage()
    except Exception as e:
        print(page.title(), e)
        return False


def build_item_ids_for_section(page: Page, name, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                               unknown: List[Item], log) -> SectionItemIds:

    found = []
    wrong = []
    non_canon = []
    cards = {}
    extra = {}
    real_world = any("Category:Real-world articles" == c.title() for c in page.categories())
    for i, o in enumerate(original):
        o.index = i
        d = determine_id_for_item(o, page.site, data.unique, data.target, other.unique, other.target, remap, log)
        if not d and o.parent:
            p = Page(page.site, o.parent)
            if is_redirect(p):
                if log:
                    print(f"Followed redirect {o.parent} to {p.getRedirectTarget().title()}")
                o.parent = p.getRedirectTarget().title().split('#', 1)[0]
                d = determine_id_for_item(o, page.site, data.unique, data.target, other.unique, other.target, remap, log)

        if d and o.mode == "Cards" and d.current.card == d.master.card and d.master.has_date():
            found.append(d)
        elif d and o.template == "ForceCollection":
            found.append(d)
        elif d and o.mode == "Cards":
            parent_set = d.master.parent if d.master.parent else d.master.target
            if o.template == "SWCT":
                parent_set = d.master.card or parent_set
            if parent_set == "Topps Star Wars Living Set":
                if o.card and o.card.strip().startswith('#'):
                    num = o.card.strip().split(' ')[0].replace('#', '')
                    if num.isnumeric():
                        n = int(num)
                        date = datetime(2019, 6, 4) + timedelta(days=(n - (n % 2)) / 2 * 7)
                        d.master.date = date.strftime("%Y-%m-%d")
                found.append(d)
                continue
            if parent_set not in cards:
                cards[parent_set] = []

            if parent_set and "|stext=" in d.master.original and "|stext=" not in d.current.original:
                x = re.search("(\|stext=.*?)[\|\}]", d.master.original)
                if x:
                    d.current.original = d.current.original.replace(f"|set={parent_set}", f"|set={parent_set}{x.group(1)}")

            if o.card:
                cards[parent_set].append(d)
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
                extra[d.master.target] = d
        elif d and d.current.template in KEEP_TEMPLATES:
            found.append(d)
        elif d and d.from_other_data and "databank" not in (o.extra or '').lower() and d.current.template != "TCWA" \
                and d.current.template != "DatapadCite" and not real_world and not d.master.from_extra:
            if log:
                print(f"({name}) Listed in wrong section: {o.original} -> {d.master.is_appearance} {d.master.full_id()}")
            wrong.append(d)
        elif d and d.master.non_canon and not name.startswith("Non-canon") and d.master.target != "Star Tours: The Adventures Continue":
            non_canon.append(d)
        elif "{{Hyperspace" in o.original and name == "Appearances":
            if d and d.master.template == "Hyperspace":
                found.append(d)
            else:
                found.append(ItemId(o, o, True, False))
        elif d:
            found.append(d)
        else:
            if log:
                print(f"Cannot find {o.unique_id()}: {o.original}")
            save = True
            if o.is_appearance and o.target:
                p = Page(page.site, o.target)
                if p.exists() and not p.isRedirectPage():
                    cats = [c.title() for c in p.categories()]
                    if "Category:Media that should be listed in Appearances" in cats:
                        if log:
                            print(f"Removing non-Appearance entry: {o.original}")
                        save = False

            unknown.append(o)
            if save and not name.startswith("Non-canon") and "star wars: visions" in o.original.lower():
                non_canon.append(ItemId(o, o, False))
            elif save:
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
            if c[0].current.subset:
                t[0].subset = c[0].current.subset
            found.append(ItemId(t[0], t[0], False))
            set_ids[t[0].full_id()] = s
            if t[0].target in extra:
                extra.pop(t[0].target)
        elif c[0].current.template == "Topps":
            found += c
        else:
            print(f"ERROR: Cannot find item for parent/target set: [{s}]: {c[0].current.full_id()}")
    found += list(extra.values())

    return SectionItemIds(name, found, wrong, non_canon, cards, set_ids)


def has_month_in_date(x: ItemId):
    return x and x.master and x.master.has_date() and "-XX-XX" not in x.master.date


BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"


def build_new_section(section: SectionItemIds, mode: str, dates: list, canon: bool, include_date: bool, log: bool,
                      use_index: bool, mismatch: list) -> Tuple[FinishedSection, List[ItemId]]:
    if section is None:
        return FinishedSection(0, ""), []

    source_names = {}
    urls = {}
    by_original_index = {o.current.index: o for o in section.found if o.current.index is not None}
    missing = []
    previous = None
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

        if o.current.template == "Topps" and "Living Set" in o.current.original:
            print(o.current.date, o.master.date, o.current.target, o.current.parent, o.master.target, o.master.parent)

        if mode == BY_INDEX and o.master.sort_index(canon) is None:
            missing.append((o, previous))
        elif mode == BY_INDEX:
            new_found.append(o)
            previous = o
        elif o.current.template == "TCWA" and mode == BY_DATE:
            missing.append((o, previous))
        elif o.current.old_version or o.current.template == "ForceCollection":
            missing.append((o, previous))
        elif o.current.override and not o.current.override_date:
            missing.append((o, previous))
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
            previous = o
        else:
            missing.append((o, previous))

    found = handle_sorting(mode, new_found, missing, canon, use_index=use_index, log=log)

    new_text = []
    final_without_extra = []
    final_items = []
    rows = 0
    for o in found:
        if mode == BY_DATE and o.current.index is None:
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
        elif mode == BY_DATE and not o.master.has_date():
            print(f"No date: {o.current.original}, {o.master.original}")

        t = o.current.target.split("(")[0] if o.current.target else None
        if t and t in source_names and len(source_names[t]) > 1:
            if o.current.target.count("(") > 0 and o.current.original.count("[[") == 1:
                if log:
                    print(f"Switching text for {o.current.target} to ''{o.current.target}'' ({o.master.date[:4]})")
                o.current.original = f"[[{o.current.target}|''{o.current.target}'' ({o.master.date[:4]}]]"

        d = build_date_text(o, include_date)
        if o.current.full_id() in section.sets:
            set_cards = section.cards[section.sets[o.current.full_id()]]
            ct = 0
            rows += 1
            if len(set_cards) > 1:
                new_text.append(f"{d}{{{{CardGameSet|set={o.current.original}|cards=")
                ct = 2
            for c in sorted(set_cards, key=lambda a: a.current.original.replace("''", "")):
                ot = c.current.original
                if c.current.subset and "subset=" not in ot:
                    ot = re.sub("({{[^\|\}]*?\|(set=)?[^\|\}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
                zt = "*" + d + re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"{ot}{c.current.extra}")
                ct += zt.count("{")
                ct -= zt.count("}")
                final_items.append(c)
                new_text.append(zt)
            if ct:
                new_text.append("".join("}" for i in range(ct)))
        else:
            zt = o.current.original if o.use_original_text else o.master.original
            if o.current.subset:
                zt = re.sub("({{[^\|\}]*?\|(set=)?[^\|\}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", zt)
            zt = re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", zt)
            if o.master.from_extra and "{{co}}" not in (o.current.extra or '').lower():
                d += "{{SeriesListing}} "
            if d == "<!-- Unknown -->" and "{{Hyperspace" in zt and "/member/fiction" in zt:
                d = ""
            zn = f"*{d}{zt}"
            if zn.startswith("**"):
                zn = zn[1:]
            zn = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", zn)
            zn = zn.replace("–", "&ndash;").replace("—", "&mdash;")
            if o.current.template == "TCW" and "|d=y" in o.current.original and "|d=y" not in zn:
                zn = re.sub("(\{\{TCW\|.*?)\}\}", "\\1|d=y}}", zn)

            if zn in final_without_extra:
                if log:
                    print(f"Skipping duplicate {zn}")
            else:
                e = re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", o.current.extra)
                if section.name.startswith("Non-canon"):
                    e = re.sub("\{\{[Nn]cm}}", "{{Mo}}", re.sub("\{\{[Nn]cs?(\|.*?)?\}\}", "", e))
                    e = e.rstrip() if e.strip() else ''
                z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", f"{zn}{e}")
                z = z.replace("–", "&ndash;").replace("—", "&mdash;")
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|'*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?([^\[\}\r\n]+?)'*\}\}(</small>)?",
                           "{{StarshipsVehiclesCite|\\1|\\4|\\6}}", z)
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|('*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?(.*?)'*)\}\}(</small>)?",
                           "{{StarshipsVehiclesCite|\\1|multiple=\\4}}", z)
                final_items.append(o)
                final_without_extra.append(zn)
                new_text.append(z)
                rows += 1

        if o.master.canon is not None:
            if o.master.canon != canon:
                mismatch.append(o)

    return FinishedSection(rows, "\n".join(new_text)), final_items


def build_date_text(o: ItemId, include_date):
    if o.current.override and o.current.override_date:
        return f"<!-- {o.current.override}: {o.current.override_date}"
    elif o.current.override:
        return f"<!-- {o.current.override} -->"
    elif include_date:
        return f"<!-- {o.master.date} -->"
    elif o.master.has_date() or o.master.date == 'Future' or o.master.date == 'Canceled':
        return ''
    else:
        return '<!-- Unknown -->'


def handle_sorting(mode, new_found: List[ItemId], missing: List[Tuple[ItemId, ItemId]], canon: bool, use_index: bool, log: bool):
    if mode == UNCHANGED:
        found = new_found
    elif mode == BY_INDEX:
        found = sorted(new_found, key=lambda a: (a.master.sort_index(canon), a.current.index or 0))
    elif use_index:
        found = sorted(new_found, key=lambda a: (a.sort_date(), a.master.sort_mode, a.master.sort_index(canon) or 100000, a.sort_text()))
    else:
        found = sorted(new_found, key=lambda a: (a.sort_date(), a.master.sort_mode, a.sort_text(), a.master.sort_index(canon)))

    start, end = [], []
    for m, previous in reversed(missing):
        if m.master.date == "Canceled" or m.current.target == "Star Wars: Galaxy of Heroes":
            end.append(m)
        elif previous is None or m.current.target == "Star Wars: Force Arena":
            start.append(m)
        else:
            try:
                index = found.index(previous)
                if mode == BY_INDEX:
                    print(f"Missing master index for current index {m.current.index} -> {index + 1}: {m.current.original}")
                found.insert(index + 1, m)
            except ValueError:
                end.append(m)

    return start + found + end


def strip_paranthetical(t):
    return t.split("(novel", 1)[0].split("(2015", 1)[0].strip()


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


def is_number(d):
    return d and (d.startswith("1") or d.startswith("2"))


def find_media_categories(page: Page):
    cc = page.title().replace("/Legends", "")
    lc = f"{page.title()[0].lower()}{cc[1:]}"
    image_cat = ""
    audio_cat = ""
    for t in ["of", "of the", "from", "from the"]:
        if not image_cat:
            if Category(page.site, f"Category:Images {t} {cc}").exists():
                image_cat = f"|imagecat=Images {t} {cc}"
            elif Category(page.site, f"Category:Images {t} {lc}").exists():
                image_cat = f"|imagecat=Images {t} {lc}"
            if Category(page.site, f"Category:Images {t} {cc}s").exists():
                image_cat = f"|imagecat=Images {t} {cc}s"
            elif Category(page.site, f"Category:Images {t} {lc}s").exists():
                image_cat = f"|imagecat=Images {t} {lc}s"
        if not audio_cat:
            if Category(page.site, f"Category:Audio files {t} {cc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}"
            if Category(page.site, f"Category:Audio files {t} {lc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}"
            if Category(page.site, f"Category:Audio files {t} {cc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}s"
            if Category(page.site, f"Category:Audio files {t} {lc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}s"
    return image_cat, audio_cat


def build_section_from_pieces(header: str, section: SectionComponents, items: FinishedSection, log, media_cat):
    if log:
        print(f"Creating {header} section with {len(items.text.splitlines())} items")

    pieces = [header]
    if items.rows >= 20 and not any("{{scroll" in i.lower() for i in section.preceding):
        pieces.append("{{Scroll_box|content=")

    pieces += section.preceding
    added_media_cat = False
    if media_cat:
        pieces.append(media_cat)
        added_media_cat = True

    pieces.append(items.text)
    if section.trailing:
        pieces.append("")
        pieces += section.trailing
    diff = 0
    for s in pieces:
        diff += s.count("{{")
        diff -= s.count("}}")
    if diff > 0:
        pieces.append("}}")
    pieces.append("")
    pieces.append(section.after)
    return "\n".join(pieces).strip() + "\n\n", added_media_cat


def check_for_media_cat(section: SectionComponents):
    return any("{{mediacat" in i.lower() or "{{imagecat" in i.lower() for i in section.preceding) or \
           "{{mediacat" in section.after.lower() or "{{imagecat" in section.after.lower()


def build_final_text(page: Page, results: PageComponents, redirects, new_apps: FinishedSection, new_nca: FinishedSection,
                     new_sources: FinishedSection, new_ncs: FinishedSection, log: bool):
    pieces = [results.before.strip(), ""]

    if "{{mediacat" in results.final.lower() or "{{imagecat" in results.final.lower():
        media_cat = None
    elif any(check_for_media_cat(s) for s in [results.apps, results.nca, results.src, results.ncs]):
        media_cat = None
    else:
        ic, ac = find_media_categories(page)
        media_cat = f"{{{{Mediacat{ic}{ac}}}}}" if (ic or ac) else None

    if new_apps.text:
        t, added_media_cat = build_section_from_pieces("==Appearances==", results.apps, new_apps, log, media_cat if new_apps.rows >= 3 and new_apps.rows > new_sources.rows else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_nca.text:
        t, added_media_cat = build_section_from_pieces("===Non-canon appearances===", results.nca, new_nca, log, media_cat if new_nca.rows >= 3 else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_sources.text:
        t, added_media_cat = build_section_from_pieces("==Sources==", results.src, new_sources, log, media_cat if new_sources.rows >= 3 else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_ncs.text:
        t, added_media_cat = build_section_from_pieces("===Non-canon sources===", results.ncs, new_ncs, log, media_cat if new_ncs.rows >= 3 else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)

    if "<ref" in results.before and "{{reflist" not in results.original.lower():
        if media_cat:
            pieces.append("==Notes and references==\n" + media_cat + "\n{{Reflist}}\n\n")
        else:
            pieces.append("==Notes and references==\n{{Reflist}}\n\n")

    if results.final:
        if "==\n" in results.final and media_cat:
            z = results.final.split("==\n", 1)
            pieces.append(f"{z[0]}==\n{media_cat}\n{z[1]}")
        elif media_cat:
            pieces.append(media_cat + "\n" + results.final)
        else:
            pieces.append(results.final)

    new_txt = re.sub("(?<![\n=}])\n==", "\n\n==", re.sub("\n\n+", "\n\n", "\n".join(pieces))).strip()
    new_txt = new_txt.replace("\n\n}}", "\n}}").replace("{{Shortstory|", "{{StoryCite|")

    replace = False
    if page.get() != new_txt:
        new_txt = fix_redirects(redirects, new_txt, "Body")
        replace = True
    while replace:
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+)&ndash;", "\\1–", re.sub("(\[\[(?!File:)[^\[\]|\n]+)&mdash;", "\\1—", new_txt))
        new_txt2 = re.sub("(\{\{[A-z0-9]+\|(ye?a?r?=[0-9]+\|)?[0-9]+\|[^\[\]\|\r\n]+)&ndash;", "\\1–", re.sub("(\{\{[A-z0-9]+\|(ye?a?r?=[0-9]+\|)?[0-9]+\|[^\[\]\|\r\n]+)&mdash;", "\\1—", new_txt2))
        new_txt2 = re.sub("( ''[^'\n]+'')'s ", "\\1{{'s}} ", new_txt2)
        replace = new_txt != new_txt2
        new_txt = new_txt2

    return new_txt


def analyze_section_results(target: Page, results: PageComponents, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool,  include_date: bool, log) \
        -> Tuple[FinishedSection, FinishedSection, FinishedSection, FinishedSection, list, list, list, AnalysisResults]:
    dates = []
    unknown_apps, unknown_src = [], []
    new_apps = build_item_ids_for_section(target, "Appearances", results.apps.items, appearances, sources, remap, unknown_apps, log)
    new_nca = build_item_ids_for_section(target, "Non-canon appearances", results.nca.items, appearances, sources, remap, unknown_apps, log)
    new_src = build_item_ids_for_section(target, "Sources", results.src.items, sources, appearances, remap, unknown_src, log)
    new_ncs = build_item_ids_for_section(target, "Non-canon sources", results.ncs.items, sources, appearances, remap, unknown_src, log)

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

    # move non-canon items to the appropriate lists, and swap to non-canon only if no canon entries
    if new_apps.non_canon:
        if log:
            print(f"Moving {len(new_apps.non_canon)} non-canon appearances to the Non-canon Appearances")
        new_nca.found += new_apps.non_canon
    if new_src.non_canon:
        new_ncs.found += new_src.non_canon

    if new_nca.found and not (new_apps.found or new_apps.sets or new_apps.cards):
        new_apps = new_nca
        new_nca = None
    if new_ncs.found and not (new_src.found or new_src.sets or new_src.cards):
        new_src = new_ncs
        new_ncs = None

    app_targets = [a.master.target for a in new_apps.found if a.master.target]
    app_targets += [f"{a.master.target}|{a.master.parent}" for a in new_apps.found if a.master.target and a.master.parent]
    abridged = []
    new_indexes = []
    for i, a in enumerate(new_apps.found):
        if "{{po}}" in (a.current.extra or '').lower():
            continue
        audiobooks = find_matching_audiobook(a, app_targets, appearances)
        audiobooks += find_matching_parent_audiobook(a, app_targets, appearances)
        for b in audiobooks:
            if b.abridged:
                print(f"Skipping abridged audiobook: {b.target}")
                abridged.append(b.target)
            else:
                print(f"Adding missing audiobook: {b.target} at {i}, {a.current.index}, {a.current.canon_index}, {a.current.legends_index}")
                z = ItemId(b, b, False, False, False)
                z.current.extra = a.current.extra
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
    o = 1
    for z, i in new_indexes:
        new_apps.found.insert(i + o, z)
        o += 1

    canon = False
    app_mode = BY_INDEX
    for c in target.categories():
        if "legends articles" in c.title().lower():
            app_mode = UNCHANGED
        elif "canon articles" in c.title().lower():
            canon = True
    mismatch = []
    new_apps, final_apps = build_new_section(new_apps, app_mode, dates, canon, include_date, log, use_index, mismatch)
    new_nca, final_nca = build_new_section(new_nca, UNCHANGED, dates, canon, include_date, log, use_index, mismatch)
    new_sources, final_sources = build_new_section(new_src, BY_DATE, dates, canon, include_date, log, use_index, mismatch)
    new_ncs, final_ncs = build_new_section(new_ncs, BY_DATE, dates, canon, include_date, log, use_index, mismatch)
    analysis = AnalysisResults(final_apps, final_nca, final_sources, final_ncs, canon, abridged, mismatch)
    return new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, analysis


def find_matching_audiobook(a: ItemId, existing: list, appearances: FullListData):
    if not a.master.target:
        return []
    elif f"{a.master.target} (novelization)" in existing or f"{a.master.target} (novel)" in existing:
        return []

    z = None
    if a.master.target in appearances.parantheticals:
        z = a.master.target
    elif a.master.target.endswith(")"):
        z = a.master.target.rsplit("(", 1)[0].strip()

    if not z:
        return []

    results = []
    for y in [f"{z} (audiobook)", f"{z} (unabridged audiobook)", f"{z} (abridged audiobook)"]:
        if y in appearances.target and y not in existing:
            if f"{z} (novel)" in appearances.target and f"{z} (novel)" not in existing:
                continue
            elif f"{z} (novelization)" in appearances.target and f"{z} (novelization)" not in existing:
                continue
            results.append(appearances.target[y][0])
    return results


def find_matching_parent_audiobook(a: ItemId, existing: list, appearances: FullListData):
    if not a.master.parent or len(appearances.target.get(a.master.target) or []) < 2:
        return []

    z = None
    if a.master.parent in appearances.parantheticals:
        z = a.master.parent
    elif a.master.parent.endswith(")"):
        z = a.master.parent.rsplit("(", 1)[0].strip()

    results = []
    if z and a.master.target in appearances.target:
        for t in appearances.target[a.master.target]:
            if t.parent == f"{z} (audiobook)" and f"{a.master.target}|{z} (audiobook)" not in existing:
                results.append(t)

    return results


def split_section_pieces(section, final):
    pieces = section.split("==", 1)
    section = pieces[0]
    after = ("==" + pieces[1]) if len(pieces) > 1 else ''
    if "{{start_box" in section.lower() or "{{start box" in section.lower():
        pieces2 = re.split("({{[Ss]tart[_ ]box)", section, 1)
        if len(pieces2) == 3:
            section = pieces2[0]
            after = pieces2[1] + pieces2[2] + after

    if after:
        x = re.split("(==Notes and references|\{\{DEFAULTSORT|\[\[Category:)", after, 1)
        if x and len(x) == 3:
            return section, x[0], x[1] + x[2]
    return section, after, final


def build_page_components(target: Page, types: dict, appearances: FullListData, sources: FullListData, remap: dict,
                          all_infoboxes, handle_references=False, log=True) -> Tuple[PageComponents, list, dict]:
    before = handle_infobox_on_page(target, all_infoboxes)
    before = before.replace("DisneyPlusYT", "DisneyPlusYouTube")
    redirects = build_redirects(target)
    before = re.sub("({{[Ss]croll[_ ]box\|)\*", "{{Scroll_box|\n*", before)
    if "== " in before or " ==" in before:
        before = re.sub("== ?(.*?) ?==", "==\\1==", before)

    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    results = PageComponents(before)

    unknown = []
    final = ""
    if "===Non-canon sources===" in before:
        before, nc_sources_section = before.rsplit("===Non-canon sources===", 1)
        if nc_sources_section:
            nc_sources_section, after, final = split_section_pieces(nc_sources_section, final)
            nc_sources_section = fix_redirects(redirects, nc_sources_section, "Non-canon sources")
            results.ncs = parse_section(nc_sources_section, types, False, unknown, after, log)
            if log:
                print(f"Non-Canon Sources: {len(results.ncs.items)} --> {len(set(i.unique_id() for i in results.ncs.items))}")

    if "==Sources==" in before:
        before, sources_section = before.rsplit("==Sources==", 1)
        if sources_section:
            sources_section, after, final = split_section_pieces(sources_section, final)
            sources_section = fix_redirects(redirects, sources_section, "Sources")
            results.src = parse_section(sources_section, types, False, unknown, after, log)
            if log:
                print(f"Sources: {len(results.src.items)} --> {len(set(i.unique_id() for i in results.src.items))}")

    if "===Non-canon appearances===" in before:
        before, nc_app_section = before.rsplit("===Non-canon appearances===", 1)
        if nc_app_section:
            nc_app_section, after, final = split_section_pieces(nc_app_section, final)
            nc_app_section = fix_redirects(redirects, nc_app_section, "Non-canon appearances")
            results.nca = parse_section(nc_app_section, types, True, unknown, after, log)
            if log:
                print(f"Non-Canon Appearances: {len(results.nca.items)} --> {len(set(i.unique_id() for i in results.nca.items))}")

    if "==Appearances==" in before and "{{App" not in before and "{{app" not in before:
        before, app_section = before.rsplit("==Appearances==", 1)
        if app_section:
            app_section, after, final = split_section_pieces(app_section, final)
            app_section = fix_redirects(redirects, app_section, "Appearances")
            results.apps = parse_section(app_section, types, True, unknown, after, log)
            if log:
                print(f"Appearances: {len(results.apps.items)} --> {len(set(i.unique_id() for i in results.apps.items))}")

    results.before = before
    results.final = final
    if handle_references:
        results.before = analyze_body(target, results.before, types, appearances, sources, remap, redirects, log)
    return results, unknown, redirects


def get_analysis_from_page(target: Page, infoboxes: dict, types, appearances: FullListData,
                           sources: FullListData, remap: dict, log=True):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, False, log)

    _, _, _, _, _, _, _, analysis = analyze_section_results(target, results, appearances, sources, remap, True, False, log)
    return analysis


def build_new_text(target: Page, infoboxes: dict, types: dict, appearances: FullListData,
                   sources: FullListData, remap: dict, include_date: bool,
                   log=True, use_index=True, handle_references=False):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, handle_references, log)

    new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, analysis = analyze_section_results(
        target, results, appearances, sources, remap, use_index, include_date, log)

    return build_final_text(target, results, redirects, new_apps, new_nca, new_sources, new_ncs, log)


def analyze_target_page(target: Page, infoboxes: dict, types: dict, appearances: FullListData,
                        sources: FullListData, remap: dict, save: bool, include_date: bool,
                        log=True, use_index=True, handle_references=False):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, handle_references, log)

    new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, analysis = analyze_section_results(
        target, results, appearances, sources, remap, use_index, include_date, log)

    new_txt = build_final_text(target, results, redirects, new_apps, new_nca, new_sources, new_ncs, log)

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

    if save and new_txt != target.get():
        target.put(new_txt, "Source Engine analysis of Appearances, Sources and references", botflag=False)

    results = []
    with codecs.open("C:/Users/Michael/Documents/projects/C4DE/c4de/protocols/unknown.txt", mode="a",
                     encoding="utf-8") as f:
        if len(analysis.abridged) == 1:
            results.append(f"1 abridged audiobook was missing from Appearances: {analysis.abridged[0]}")
        elif analysis.abridged:
            results.append(f"{len(analysis.abridged)} abridged audiobooks were missing from Appearances:")
            results.append("\n".join(f"- {a}" for a in analysis.abridged))

        if analysis.mismatch:
            c, d = ("Canon", "Legends") if analysis.canon else ("Legends", "Canon")
            results.append(f"The following {len(analysis.mismatch)} entries are marked as {d} in the Masterlist, but are listed on this {c} article: (experimental feature)")
            results.append("\n".join(f"- `{a.master.original}`" for a in analysis.mismatch))

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
