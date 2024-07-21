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
DO_NOT_MOVE = ["TCWA", "GEAttr", "DatapadCite"]
LIST_AT_START = ["Star Wars: Galactic Defense", "Star Wars: Force Arena"]

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
            text = re.sub("\[\[(" + x + ")\]\]([A-z]*)", f"[[{t}|\\1\\2]]", text)
            text = text.replace(f"set={r}", f"set={t}")
            text = text.replace(f"book={r}", f"book={t}")
    return text


def build_redirects(page: Page):
    results = {}
    for r in page.linkedPages():
        if is_redirect(r):
            results[r.title()] = r.getRedirectTarget().title()
    return results


def split_section_pieces(section):
    pieces = re.split("(==|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:)", section, 1)
    section = pieces[0]
    after = (pieces[1] + pieces[2]) if len(pieces) > 1 else ''
    if "{{start_box" in section.lower() or "{{start box" in section.lower():
        pieces2 = re.split("({{[Ss]tart[_ ]box)", section, 1)
        if len(pieces2) == 3:
            section = pieces2[0]
            after = pieces2[1] + pieces2[2] + after

    if after:
        x = re.split("(==Notes? and references|\{\{DEFAULTSORT|\[\[Category:)", after, 1)
        if x and len(x) == 3:
            return section, x[0], x[1] + x[2]
    return section, after


def initial_cleanup(target: Page, all_infoboxes):
    before = target.get()
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(
            "(\]\]|\}\})(\{+ ?(1st[A-z]*|[A-z][od]|[Ll]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[\|\}])",
            "\\1 \\2", before)
    if all_infoboxes:
        before = handle_infobox_on_page(before, target, all_infoboxes)
    before = before.replace("DisneyPlusYT", "DisneyPlusYouTube")
    before = re.sub("({{[Ss]croll[_ ]box\|)\*", "{{Scroll_box|\n*", before) \
        .replace("referene", "reference").replace("Note and references", "Notes and references") \
        .replace("Notes and reference=", "Notes and references=").replace("==References==", "==Notes and references==") \
        .replace("Apearance", "Appearance").replace("Appearence", "Appearance").replace("&#40;&#63;&#41;", "(?)")
    before = re.sub("([A-z0-9\.>])(\[\[File:.*?\]\]\n)", "\\1\n\\2", before).replace("*{{Indexpage", "{{Indexpage")
    before = re.sub("=+'*Non-canonical (appearances|sources)'*=+", "===Non-canon \\1===", before)
    before = re.sub("\{\{(.*?[^\n\]])\]\}(?!\})", "{{\1}}", before)
    while "== " in before or " ==" in before:
        before = before.replace("== ", "==").replace(" ==", "==")
    if "{{C|unlicensed}}" in before:
        before = re.sub("( {{[Cc]\|[Uu]nlicensed\}\})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub("\{\{[Mm]entioned[ _]only\|?\}\}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    return before


def build_page_components(target: Page, types: dict, appearances: FullListData, sources: FullListData, remap: dict,
                          all_infoboxes, handle_references=False, log=True) -> Tuple[PageComponents, list, dict]:
    before = initial_cleanup(target, all_infoboxes)
    redirects = build_redirects(target)

    canon = False
    non_canon = False
    app_mode = BY_INDEX
    for c in target.categories():
        if "legends articles" in c.title().lower():
            app_mode = UNCHANGED
        elif "canon articles" in c.title().lower():
            canon = True
        elif "Non-canon Legends articles" in c.title() or "Non-canon articles" in c.title():
            non_canon = True
    results = PageComponents(before, canon, non_canon, app_mode)

    unknown = []
    final = ""
    x = re.split("(==Notes and references|==External links|\{\{[R]eflist|\{\{DEFAULTSORT|\[\[[Cc]ategory:)", before, 1)
    if x:
        if len(x) < 3:
            print(x)
        before = x[0]
        final = "".join(x[1:])

    if "===Non-canon sources===" in before:
        before, nc_sources_section = before.rsplit("===Non-canon sources===", 1)
        if nc_sources_section:
            nc_sources_section, after = split_section_pieces(nc_sources_section)
            nc_sources_section = fix_redirects(redirects, nc_sources_section, "Non-canon sources")
            results.ncs = parse_section(nc_sources_section, types, False, unknown, after, log)
            if results.ncs and results.ncs.after.startswith("==Behind the scenes=="):
                before += f"\n{results.ncs.after}"
                results.ncs.after = ""
            if log:
                print(f"Non-Canon Sources: {len(results.ncs.items)} --> {len(set(i.unique_id() for i in results.ncs.items))}")

    if "==Sources==" in before:
        before, sources_section = before.rsplit("==Sources==", 1)
        if sources_section:
            sources_section, after = split_section_pieces(sources_section)
            sources_section = fix_redirects(redirects, sources_section, "Sources")
            results.src = parse_section(sources_section, types, False, unknown, after, log)
            if results.src and results.src.after.startswith("==Behind the scenes=="):
                before += f"\n{results.src.after}"
                results.src.after = ""
            if log:
                print(f"Sources: {len(results.src.items)} --> {len(set(i.unique_id() for i in results.src.items))}")

    if "===Non-canon appearances===" in before:
        before, nc_app_section = before.rsplit("===Non-canon appearances===", 1)
        if nc_app_section:
            nc_app_section, after = split_section_pieces(nc_app_section)
            nc_app_section = fix_redirects(redirects, nc_app_section, "Non-canon appearances")
            results.nca = parse_section(nc_app_section, types, True, unknown, after, log)
            if results.nca and results.nca.after.startswith("==Behind the scenes=="):
                before += f"\n{results.nca.after}"
                results.nca.after = ""
            if log:
                print(f"Non-Canon Appearances: {len(results.nca.items)} --> {len(set(i.unique_id() for i in results.nca.items))}")

    if "==Appearances==" in before and "{{App\n" not in before and "{{app\n" not in before and "{{App|" not in before and "{{app|" not in before:
        before, app_section = before.rsplit("==Appearances==", 1)
        if app_section:
            app_section, after = split_section_pieces(app_section)
            app_section = fix_redirects(redirects, app_section, "Appearances")
            results.apps = parse_section(app_section, types, True, unknown, after, log)
            if results.apps and results.apps.after.startswith("==Behind the scenes=="):
                before += f"\n{results.apps.after}"
                results.apps.after = ""
            if log:
                print(f"Appearances: {len(results.apps.items)} --> {len(set(i.unique_id() for i in results.apps.items))}")

    results.before = before
    results.final = final
    if handle_references:
        results.before = analyze_body(target, results.before, types, appearances, sources, remap, redirects, canon, log)
    return results, unknown, redirects


def parse_section(section: str, types: dict, is_appearances: bool, unknown: list, after: str, log, name="Target") -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    data = []
    unique_ids = {}
    other1, other2 = [], []
    start = True
    succession_box = False
    scroll_box = False
    cs = 0
    section = re.sub("({{CardGameSet\|set=.*?)\n\|cards=", "\\1|cards=\n", section)
    section = re.sub("'*\[\[Star Wars Miniatures\]\]'*: '*\[\[(.*?)(\|.*?)?\]\]'*", "{{SWMiniCite|set=\\1}}", section)
    section = re.sub(" \((as .*?)\)", " {{C|\\1}}", section)
    for s in section.splitlines():
        if succession_box or "{{more" in s.lower():
            other2.append(s)
            continue
        if "CardGameSet" in s:
            s = re.sub("{{CardGameSet\|(set=)?.*?\|cards=", "", s)
            cs += 1
        if s.strip().startswith("<!-"):
            s = re.sub("<\!--.*?-->", "", s)

        if s.strip().startswith("*"):
            start = False
            handle_valid_line(s, is_appearances, log, types, data, other2, unknown, unique_ids, False, name)
        elif "{{scroll_box" in s.lower() or "{{scroll box" in s.lower():
            scroll_box = True
            other1.append(s)
        elif scroll_box and (s.startswith("|height=") or s.startswith("|content=")):
            other1.append(s)
        elif "{{start_box" in s.lower() or "{{start box" in s.lower() or "{{interlang" in s.lower():
            succession_box = True
            other2.append(s)
        elif "{{imagecat" in s.lower() or "{{mediacat" in s.lower() or "{{indexpage" in s.lower():
            other1.append(s)
        elif s == "}}":
            if cs > 0:
                cs = 0
        elif re.match("^<\!--.*?-->$", s):
            continue
        elif s.strip():
            if not data and not re.search("^[\{\[]+([Ii]ncomplete|[Ss]croll|[Mm]ore[_ ]|[Ff]ile:)", s.strip()):
                x = handle_valid_line(f"*{s}", is_appearances, log, types, data, other2, unknown, unique_ids, True, name)
                if x:
                    start = False
                    continue
            if start:
                other1.append(s)
            else:
                other2.append(s)
    return SectionComponents(data, other1, other2, after)


def handle_valid_line(s, is_appearances: bool, log: bool, types, data, other2, unknown, unique_ids, attempt=False, name="Target"):
    if s.endswith("}}}}") and s.count("{{") < s.count("}}"):
        s = s[:-2]
    z = s[1:].replace("&ndash;", '–').replace('&mdash;', '—')
    z = re.sub("(\{\{InsiderCite\|[0-9]{2}\|)Ask Lobot.*?}}", "\\1Star Wars Q&A}}", z)
    if "SWGTCG" in s and "scenario" in z:
        z = re.sub("(\{\{SWGTCG.*?)\}\} \{\{C\|(.*?scenario)\}\}", "\\1|scenario=\\2}}", z)
    x1 = re.search(
        '( ?(<small>)? ?\{+ ?(1st[A-z]*|V?[A-z][od]|[Ff]act|DLC|[Ll]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[\|\}].*?$)',
        z)
    extra = x1.group(1) if x1 else ''
    if extra:
        z = z.replace(extra, '').strip()
    bold = "'''" in z

    zs = [z]
    if "/" in z and "{{YJA|" in z:
        x = re.search("^(.*?\{\{YJA\|)(.*?)/(.*?)(\}\}.*?)$", z)
        if x:
            if log:
                print(f"Splitting multi-entry line: {s}")
            zs = [f"{x.group(1)}{x.group(2)}{x.group(4)}", f"{x.group(1)}{x.group(3)}{x.group(4)}"]
    elif "/" in z:
        x = re.search("^(.*?\]\]'*) / ('*\[.*?)$", z)
        if x:
            if log:
                print(f"Splitting multi-entry line: {s}")
            zs = [x.group(1), x.group(2)]

    found = False
    for y in zs:
        t = extract_item(convert_issue_to_template(y), is_appearances, name, types)
        if t:
            found = True
            data.append(t)
            t.extra = extra.strip()
            t.bold = bold
            ex = re.search("<!-- ?(Exception|Override):? ?([0-9X-]+)? ?-->", s)
            if ex:
                t.override = ex.group(1)
                t.override_date = ex.group(2)
            unique_ids[t.unique_id()] = t
    if not found:
        if "audiobook" not in s and not attempt:
            unknown.append(s)
            other2.append(s)
        if log:
            print(f"Unknown: {s}")
    return found


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, redirects, canon, log: bool):
    references = re.findall("(<ref name=.*?[^/]>(.*?)</ref>)", text)
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, redirects, canon, log)
    return new_text


def handle_reference(full_ref, ref, page: Page, new_text, types, appearances: FullListData, sources: FullListData, remap, redirects, canon, log: bool):
    try:
        new_ref = fix_redirects(redirects, ref, "Reference")
        new_ref = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", new_ref)
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
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique, sources.target, remap, canon, log)
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
                        if link[0] != o.master.original:
                            new_links.append((link[0], o))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", ni.master.original))

        new_templates = []
        for t in templates:
            if t == "{{'s}}" or "{{TORcite" in t or "{{SWG" in t or t.startswith("{{C|") or t.startswith("{{Blogspot") or t.startswith("{{Cite"):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and x.template.endswith("Date"):
                    continue
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique,
                                          sources.target, {}, canon, log)
                if o and not o.use_original_text and t != o.master.original:
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
            new_ref = new_ref.replace(ot, z.replace("–", "&ndash;").replace("—", "&mdash;"))

        final_ref = full_ref.replace(ref, new_ref).replace("film]] film", "film]]").replace("|reprint=yes", "")
        if "series series" in final_ref:
            final_ref = re.sub(" series( series)+", " series", final_ref)
        new_text = new_text.replace(full_ref, final_ref)
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return do_final_replacements(new_text, True)


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def is_redirect(page):
    try:
        return page.exists() and page.isRedirectPage()
    except Exception as e:
        print(page.title(), e)
        return False


def analyze_section_results(target: Page, results: PageComponents, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool,  include_date: bool, log) \
        -> Tuple[FinishedSection, FinishedSection, FinishedSection, FinishedSection, list, list, list, list, AnalysisResults]:
    both_continuities = appearances.both_continuities.union(sources.both_continuities)
    dates = []
    unknown_apps, unknown_src = [], []
    new_apps = build_item_ids_for_section(target, "Appearances", results.apps.items, appearances, sources, remap, unknown_apps, results.canon, log)
    new_nca = build_item_ids_for_section(target, "Non-canon appearances", results.nca.items, appearances, sources, remap, unknown_apps, results.canon, log)
    new_src = build_item_ids_for_section(target, "Sources", results.src.items, sources, appearances, remap, unknown_src, results.canon, log)
    new_ncs = build_item_ids_for_section(target, "Non-canon sources", results.ncs.items, sources, appearances, remap, unknown_src, results.canon, log)

    # move non-canon items to the appropriate lists, and swap to non-canon only if no canon entries
    if new_apps.non_canon:
        if log:
            print(f"Moving {len(new_apps.non_canon)} non-canon appearances to the Non-canon Appearances")
        new_nca.found += new_apps.non_canon
    if new_src.non_canon:
        new_ncs.found += new_src.non_canon

    if new_apps.wrong or new_nca.wrong:
        if log:
            print(f"Moving {len(new_apps.wrong) + len(new_nca.wrong)} sources from Appearances to Sources")
        new_src.found += new_apps.wrong
        if not new_apps.found:
            results.src.preceding += results.apps.preceding
            results.src.trailing += results.apps.trailing
            results.src.after += results.apps.after
        if new_ncs.found:
            new_ncs.found += new_nca.wrong
        else:
            new_src.found += new_nca.wrong
    if new_src.wrong or new_ncs.wrong:
        if log:
            print(f"Moving {len(new_src.wrong) + len(new_ncs.wrong)} sources from Sources to Appearances")
        new_apps.found += new_src.wrong
        if not new_src.found:
            results.apps.preceding += results.src.preceding
            results.apps.trailing += results.src.trailing
            results.apps.after += results.src.after
        if new_ncs.found:
            new_nca.found += new_ncs.wrong
        else:
            new_apps.found += new_ncs.wrong

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
        audiobooks = find_matching_audiobook(a, app_targets, appearances, abridged)
        audiobooks += find_matching_parent_audiobook(a, app_targets, appearances)
        for b in audiobooks:
            if b.abridged:
                print(f"Skipping abridged audiobook: {b.target}")
                abridged.append(b.target)
            else:
                print(f"Adding missing audiobook: {b.target} at {i}, {a.current.index}, {a.current.canon_index}, {a.current.legends_index}")
                z = ItemId(b, b, False, False, False)
                extra = a.current.extra or ''
                if "1stm" in extra:
                    extra = re.sub("\{\{1stm.*?}}", "{{Mo}}", extra)
                z.current.extra = re.sub(" ?\{\{1st[A-z]*\|.*?\}\}", "", extra)
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

    mismatch = []
    unknown_final = []
    nca_title = "==Appearances==" if results.non_canon and not new_apps.found else "===Non-canon appearances==="
    ncs_title = "==Sources==" if results.non_canon and not new_src.found else "===Non-canon sources==="
    new_apps, final_apps = build_new_section("==Appearances==", new_apps, results.app_mode, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final)
    new_nca, final_nca = build_new_section(nca_title, new_nca, BY_DATE, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final)
    new_src, final_sources = build_new_section("==Sources==", new_src, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final)
    new_ncs, final_ncs = build_new_section(ncs_title, new_ncs, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final)
    analysis = AnalysisResults(final_apps, final_nca, final_sources, final_ncs, results.canon, abridged, mismatch)
    return new_apps, new_nca, new_src, new_ncs, dates, unknown_apps, unknown_src, unknown_final, analysis


def build_item_ids_for_section(page: Page, name, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                               unknown: List[Item], canon: bool, log: bool) -> SectionItemIds:

    found = []
    wrong = []
    non_canon = []
    cards = {}
    extra = {}
    real_world = any("Category:Real-world articles" == c.title() for c in page.categories())
    for i, o in enumerate(original):
        o.index = i
        d = determine_id_for_item(o, page.site, data.unique, data.target, other.unique, other.target, remap, canon, log)
        if not d and o.parent:
            p = Page(page.site, o.parent)
            if "[[w:c:" in o.original:
                continue
            if is_redirect(p):
                if log:
                    print(f"Followed redirect {o.parent} to {p.getRedirectTarget().title()}")
                o.parent = p.getRedirectTarget().title().split('#', 1)[0]
                d = determine_id_for_item(o, page.site, data.unique, data.target, other.unique, other.target, remap, canon, log)

        if d and o.mode == "Cards" and d.current.card and d.current.card == d.master.card and d.master.has_date():
            found.append(d)
        elif d and o.template == "ForceCollection":
            found.append(d)
        elif d and o.mode == "Cards":
            parent_set = d.master.parent if d.master.parent else d.master.target
            if d.current.template == "Topps" and not d.master.has_date() and parent_set.startswith("20"):
                d.master.date = f"{parent_set[:4]}-XX-XX"
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
        elif d and d.from_other_data and "databank" not in (o.extra or '').lower() and d.current.template not in DO_NOT_MOVE \
                and d.current.target != 'Star Wars: Datapad (Galactic Starcruiser)'\
                and not real_world and not d.master.from_extra:
            if log:
                print(f"({name}) Listed in wrong section: {o.original} -> {d.master.is_appearance} {d.master.full_id()}")
            wrong.append(d)
        elif d and d.master.non_canon and not name.startswith("Non-canon") and d.master.target != "Star Tours: The Adventures Continue" and not page.title().endswith("/LEGO"):
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
            o.unknown = True
            if save and not name.startswith("Non-canon") and "star wars: visions" in o.original.lower():
                non_canon.append(ItemId(o, o, False))
            elif save:
                found.append(ItemId(o, o, False))
            elif real_world:
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
        if not t and c[0].current.template == "SWCT" and " - " in s:
            t = data.target.get(s.split(" - ", 1)[-1])
            if not t and other.target:
                t = other.target.get(s.split(" - ", 1)[-1])
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


def build_new_section(name, section: SectionItemIds, mode: str, dates: list, canon: bool, include_date: bool, log: bool,
                      use_index: bool, mismatch: list, both_continuities: set, unknown_final: list) -> Tuple[FinishedSection, List[ItemId]]:
    if section is None:
        return FinishedSection(name, 0, ""), []

    source_names = {}
    urls = {}
    by_original_index = {o.current.index: o for o in section.found if o.current.index is not None}
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
            if u in urls:
                print(f"Skipping duplicate entry: {u}")
            else:
                urls[u] = o

        if mode == BY_INDEX and o.master.sort_index(canon) is None:
            group.append(o)
        elif mode == BY_INDEX:
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
            if o.current.index is None and "audiobook" not in o.master.original:
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

    found = handle_sorting(mode, new_found, missing, canon, use_index=use_index, log=log)

    new_text = []
    final_without_extra = []
    final_items = []
    rows = 0
    sl = "" if canon else "|l=1"
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
            o.unknown = True
            unknown_final.append(o)

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
            for c in sorted(set_cards, key=lambda a: (a.current.card if a.current.card else a.current.original).replace("''", "")):
                ot = c.current.original
                if c.current.subset and "subset=" not in ot:
                    ot = re.sub("({{[^\|\}]*?\|(set=)?[^\|\}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
                while ot.count("|subset=") > 1:
                    ot = re.sub("(\|subset=.*?)\1", "\1", ot)
                zt = "*" + d + re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"{ot} {c.current.extra.strip()}").strip()
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
            while zt.count("|subset=") > 1:
                zt = re.sub("(\|subset=.*?)\1", "\1", zt)
            zt = re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", zt)
            if o.current.bold:
                zt = f"'''{zt}'''"
            if o.master.from_extra and "{{co}}" not in (o.current.extra or '').lower() \
                    and "cover only" not in (o.current.extra or '').lower() and o.current.template != "HomeVideoCite":
                if "audiobook" in o.master.original:
                    continue
                elif o.master.future:
                    pass
                elif "Complete Season" in o.master.original or "Complete Saga" in o.master.original or \
                        "Star Wars: The Skywalker Saga" in o.master.original:
                    d += f"{{{{SeriesListing{sl}|DVD}}}} "
                elif "[[5-Minute Star Wars" in o.master.original or "Trilogy Stories" in o.master.original or \
                        "[[The Clone Wars: Stories" in o.master.original or "[[Life Day Treasury" in o.master.original \
                        or "[[Tales from the " in o.master.original:
                    d += f"{{{{SeriesListing{sl}|short}}}} "
                else:
                    d += f"{{{{SeriesListing{sl}}}}} "
            elif o.current.unknown or o.master.unknown:
                d += f"{{{{SeriesListing{sl}}}}} "
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
                e = re.sub("<\!--( ?Unknown ?|[ 0-9/X-]+)-->", "", o.current.extra).strip()
                if section.name.startswith("Non-canon"):
                    e = re.sub("\{\{[Nn]cm}}", "{{Mo}}", re.sub("\{\{[Nn]cs?(\|.*?)?\}\}", "", e))
                z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", f"{zn} {e}").strip()
                z = z.replace("–", "&ndash;").replace("—", "&mdash;")
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|'*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?([^\[\}\r\n]+?)'*\}\}(</small>)?",
                           "{{StarshipsVehiclesCite|\\1|\\4|\\6}}", z)
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?\]\]'* (<small>)?\{\{C\|('*\[\[(.*?)\]\]'* ?(-|&[mn]dash;|:) ?(.*?)'*)\}\}(</small>)?",
                           "{{StarshipsVehiclesCite|\\1|multiple=\\4}}", z)
                final_items.append(o)
                final_without_extra.append(zn)
                new_text.append(z)
                rows += 1

        if o.master.canon is not None and o.master.canon != canon and o.master.target not in both_continuities:
            mismatch.append(o)

    return FinishedSection(name, rows, "\n".join(new_text)), final_items


def build_date_text(o: ItemId, include_date):
    if o.current.override and o.current.override_date:
        return f"<!-- {o.current.override}: {o.current.override_date} -->"
    elif o.current.override_date:
        return f"<!-- {o.current.override_date} -->"
    elif not o.master.has_date():
        return '<!-- Unknown -->'
    elif include_date:
        return f"<!-- {o.master.date} -->" if o.master.date != 'Current' else ''
    elif o.master.has_date() or o.master.date == 'Future' or o.master.date == 'Canceled':
        return ''
    else:
        return '<!-- Unknown -->'


def sort_tuple(a: Tuple[ItemId, ItemId]):
    b, c = a
    return b.current.original


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
            elif m.current.template == "Jedi Temple Challenge":
                jtc.append(m)
            elif m.current.target in LIST_AT_START:
                special.append(m)
            elif previous is None:
                start.append(m)
            elif index is None:
                end.append(m)
            else:
                if mode == BY_INDEX:
                    print(f"Missing master index for current index {m.current.index} -> {index + 1}: {m.current.original}")
                found.insert(index + 1, m)
    if special:
        start = sorted(special, key=lambda a: a.master.original) + start
    if jtc:
        start += reversed(jtc)

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


AUDIOBOOK_MAPPING = {
    "Adventures in Wild Space: The Escape": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Snare": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Nest": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Dark": "Adventures in Wild Space: Books 4–6",
    "Adventures in Wild Space: The Cold": "Adventures in Wild Space: Books 4–6",
    "Adventures in Wild Space: The Rescue": "Adventures in Wild Space: Books 4–6",
    "Join the Resistance": "Join the Resistance: Books 1-3",
    "Join the Resistance: Escape from Vodran": "Join the Resistance: Books 1-3",
    "Join the Resistance: Attack on Starkiller Base": "Join the Resistance: Books 1-3",
    "The Prequel Trilogy Stories": "Star Wars Storybook Collection",
    "The Original Trilogy Stories": "Star Wars Storybook Collection",
    "Star Wars: Episode II Attack of the Clones (junior novelization)": "Star Wars: Episode II Attack of the Clones (audio cassette)",
}


def find_matching_audiobook(a: ItemId, existing: list, appearances: FullListData, abridged: list):
    if not a.master.target:
        return []
    elif f"{a.master.target} (novelization)" in existing or f"{a.master.target} (novel)" in existing:
        return []

    z = None
    if a.master.target in appearances.parantheticals:
        z = a.master.target
    elif a.master.target.endswith(")") and not a.master.target.endswith("webcomic)"):
        z = a.master.target.rsplit("(", 1)[0].strip()
    elif a.master.parent in AUDIOBOOK_MAPPING:
        z = a.master.parent

    if not z:
        return []

    results = []
    if z in AUDIOBOOK_MAPPING:
        to_check = [AUDIOBOOK_MAPPING[z]]
    else:
        to_check = [f"{z} (audiobook)", f"{z} (unabridged audiobook)", f"{z} (abridged audiobook)", f"{z} (script)",
                    f" (audio drama)", f" (German audio drama)"]

    for y in to_check:
        if y in appearances.target and y not in existing and y not in abridged:
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
    elif a.master.parent in AUDIOBOOK_MAPPING:
        z = a.master.parent

    if not z:
        return []

    results = []
    audiobook_name = AUDIOBOOK_MAPPING.get(z, f"{z} (audiobook)")
    if z and a.master.target in appearances.target:
        for t in appearances.target[a.master.target]:
            if t.parent == audiobook_name and f"{a.master.target}|{audiobook_name}" not in existing:
                results.append(t)

    return results


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


def build_section_from_pieces(section: SectionComponents, items: FinishedSection, log, media_cat):
    if log:
        print(f"Creating {items.name} section with {len(items.text.splitlines())} items")

    pieces = [items.name]
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
    return do_final_replacements("\n".join(pieces).strip() + "\n\n", True), added_media_cat


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
    media_cat = ''

    section = sorted([new_nca, new_apps, new_ncs, new_sources], key=lambda a: a.rows)[-1]
    mc_section_name = section.name if section.rows > 3 else None

    if new_apps.text:
        t, added_media_cat = build_section_from_pieces(results.apps, new_apps, log, media_cat if mc_section_name == new_apps.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_nca.text:
        t, added_media_cat = build_section_from_pieces(results.nca, new_nca, log, media_cat if mc_section_name == new_nca.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_sources.text:
        t, added_media_cat = build_section_from_pieces(results.src, new_sources, log, media_cat if mc_section_name == new_sources.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_ncs.text:
        t, added_media_cat = build_section_from_pieces(results.ncs, new_ncs, log, media_cat if mc_section_name == new_ncs.name else None)
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

    new_txt = sort_categories("\n".join(pieces))
    new_txt = re.sub("(\{\{DEFAULTSORT:.*?\}\})\n\n+\[\[[Cc]ategory", "\\1\n[[Category", new_txt)
    new_txt = re.sub("(?<![\n=}])\n==", "\n\n==", re.sub("\n\n+", "\n\n", new_txt)).strip()
    new_txt = new_txt.replace("\n\n}}", "\n}}").replace("{{Shortstory|", "{{StoryCite|").replace("\n\n{{More", "\n{{More")

    replace = False
    if re.sub("<!--.*?-->", "", page.get()) != re.sub("<!--.*?-->", "", new_txt):
        new_txt = fix_redirects(redirects, new_txt, "Body")
        replace = True
    return do_final_replacements(new_txt, replace)


def do_final_replacements(new_txt, replace):
    while replace:
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+)&mdash;", "\\1—", new_txt))
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+–[^\[\]|\r\n]+\|[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+—[^\[\]|\r\n]+\|[^\[\]|\r\n]+)&mdash;", "\\1—", new_txt2))
        new_txt2 = re.sub("\[\[(.*?)\|\\1(.*?)\]\]", "[[\\1]]\\2", new_txt2)
        x = re.search("\[\[([A-Z])(.*?)\|(.\\2)(.*?)\]\]", new_txt2)
        if x and x.group(3).lower().startswith(x.group(1).lower()):
            new_txt2 = new_txt2.replace(x.group(0), f"[[{x.group(3)}]]{x.group(4)}")
        if "'''s " in new_txt2:
            new_txt2 = re.sub("( ''[^'\n]+'')'s ", "\\1{{'s}} ", new_txt2)
        if "{{1st|" in new_txt2 or "{{1stm|" in new_txt2 or "{{1stID|" in new_txt2 or "{{1stp|" in new_txt2:
            new_txt2 = re.sub("(\[\[(.*?)( \(.*?\))?(\|.*?)?\]\].*?{{1st[A-z]*?(\|.*?)?\|\[\[\\2 \((.*?audiobook)\)\|).*?\]\]\}\}", "\\1\\6]]}}", new_txt2)
            new_txt2 = re.sub("(ook=(.*?)( \(.*?\))?(\|.*?)?\}\}.*?{{1st[A-z]*?(\|.*?)?\|\[\[\\2 \((.*?audiobook)\)\|).*?\]\]\}\}", "\\1\\6]]}}", new_txt2)
        if "{{more" in new_txt2.lower():
            new_txt2 = re.sub("(\{\{[Mm]ore[ _]sources\}\})\n+\}\}", "}}\n\\1", new_txt2)
        replace = new_txt != new_txt2
        new_txt = new_txt2
    return new_txt


def sort_categories(text):
    final = []
    categories = []
    related_cats = []
    rc_count = 0
    for line in text.splitlines():
        if "{{relatedcategories" in line.lower():
            rc_count += line.count("{")
            related_cats.append(line)
        elif rc_count > 0:
            related_cats.append(line)
            rc_count += line.count("{")
            rc_count -= line.count("}")
        elif line.strip().lower().startswith("[[category:"):
            categories.append(line)
        else:
            final.append(line)

    final += sorted(categories, key=lambda a: a.lower())
    if related_cats:
        final.append("")
        final += related_cats
    return "\n".join(final)


def get_analysis_from_page(target: Page, infoboxes: dict, types, appearances: FullListData,
                           sources: FullListData, remap: dict, log=True):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, False, log)

    _, _, _, _, _, _, _, _, analysis = analyze_section_results(target, results, appearances, sources, remap, True, False, log)
    return analysis


def build_new_text(target: Page, infoboxes: dict, types: dict, appearances: FullListData,
                   sources: FullListData, remap: dict, include_date: bool,
                   log=True, use_index=True, handle_references=False):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, handle_references, log)

    new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, unknown_final, analysis = analyze_section_results(
        target, results, appearances, sources, remap, use_index, include_date, log)

    if unknown or unknown_apps or unknown_src or unknown_final:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/sources/unknown.txt", mode="a",
                         encoding="utf-8") as f:
            for x in unknown:
                f.write(u'%s\t%s\n' % (x, target.title()))
            z = set()
            for o in [*unknown_apps, *unknown_src]:
                z.add(o.original)
            for o in unknown_final:
                if o.current.original not in z:
                    z.add(f"No Date: {o.current.original}")
            if z:
                f.writelines("\n".join([f"{o}\t{target.title()}" for o in z]) + "\n")

    return build_final_text(target, results, redirects, new_apps, new_nca, new_sources, new_ncs, log)


def analyze_target_page(target: Page, infoboxes: dict, types: dict, appearances: FullListData,
                        sources: FullListData, remap: dict, save: bool, include_date: bool,
                        log=True, use_index=True, handle_references=False):
    results, unknown, redirects = build_page_components(target, types, appearances, sources, remap, infoboxes, handle_references, log)

    new_apps, new_nca, new_sources, new_ncs, dates, unknown_apps, unknown_src, unknown_final, analysis = analyze_section_results(
        target, results, appearances, sources, remap, use_index, include_date, log)

    new_txt = build_final_text(target, results, redirects, new_apps, new_nca, new_sources, new_ncs, log)

    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if dates:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/new_dates.txt", mode="a", encoding="utf-8") as f:
            date_txt = []
            for d in dates:
                if d[2] == d[3]:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]}:  -> {d[1].master.original}")
                else:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]} {d[3]}:  -> {d[1].master.original}")
            f.writelines("\n" + "\n".join(date_txt))

    if save and new_txt != target.get():
        z1 = re.sub("<!--.*?-->", "", new_txt)
        z2 = re.sub("<!--.*?-->", "", target.get()).replace("text=SWCC 2022", "text=SWCA 2022")
        match = z1 == z2
        target.put(new_txt, "Source Engine analysis of Appearances, Sources and references", botflag=match)

    results = []
    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/unknown.txt", mode="a",
                     encoding="utf-8") as f:
        if len(analysis.abridged) == 1:
            results.append(f"1 abridged audiobook was missing from Appearances: {analysis.abridged[0]}")
        elif analysis.abridged:
            results.append(f"{len(analysis.abridged)} abridged audiobooks were missing from Appearances:")
            results.append("\n".join(f"- {a}" for a in analysis.abridged))

        if analysis.mismatch and target.namespace().id == 0:
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

    final_results = []
    for i in results:
        if len(i) > 500:
            x = i.split("\n")
            for z in x:
                if len(z) > 500:
                    final_results += [z[o:o+500] for o in range(0, len(z), 500)]
                else:
                    final_results.append(z)
        else:
            final_results.append(i)

    return results
