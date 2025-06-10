import re
import traceback
from datetime import datetime

from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional, Set

from c4de.common import build_redirects, fix_redirects, fix_disambigs, prepare_title
from c4de.sources.cleanup import initial_cleanup
from c4de.sources.determine import determine_id_for_item
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, SectionComponents, SectionLeaf
from c4de.sources.external import prepare_basic_url
from c4de.sources.extract import extract_item, convert_issue_to_template, swap_parameters
from c4de.sources.media import match_header, check_for_cover_image, COVER_GALLERY_MEDIA, \
    SUBSECTIONS, add_plot_template, rearrange_sections, combine_sections

BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"],
    "Star Wars: The Essential Atlas Online Companion": ["''[[Star Wars: The Essential Atlas Online Companion]]''"]
}

INDEX_AND_CATS = ["{{imagecat", "{{mediacat", "{{indexpage", "{{wq", "{{incomplete", "{{quote", "<div style=",
                  "set in '''bold'''", "{{cleanup", "{{more", "{{coor title", "{{coor_title"]


MASTER_STRUCTURE = {
    "Collections": "==Collected in==",
    "Appearances": "==Appearances==",
    "Non-Canon Appearances": "===Non-canon appearances===",
    "Sources": "==Sources==",
    "Non-Canon Sources": "===Non-canon sources===",
    "References": "==Notes and references==",
    "Links": "==External links=="
}


def is_number(d):
    return d and (d.startswith("1") or d.startswith("2"))


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def is_official_link(o: Item):
    if o:
        return o.template == "OfficialSite" or o.mode == "Official" or (
                o.mode in ["Basic", "External"] and o.original and "official" in o.original.lower() and
                re.search("official .*?(site|home ?page)", o.original.lower()))
    return False


def is_nav_or_date_template(template, types: dict):
    return template.lower().replace("_", " ") in types["Nav"] or template.lower().replace("_", " ") in types["Dates"]


def is_nav_template(template, types: dict):
    return template.lower().replace("_", " ") in types["Nav"]


def check_format_text(o: ItemId, x: Item):
    if o.current.followed_redirect and o.current.original_target:
        return _check_format_text(o.current.original_target, x.format_text)
    return _check_format_text(o.master.target, x.format_text)


def _check_format_text(t, y):
    return t and y and "(" in t and (
            t.split("(")[0].strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel") and
            t.replace("(", "").replace(")", "").strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel")
    )


def fix_template_redirects(target: Page, manual: str = None):
    redirects = build_redirects(target, manual=manual)
    template_redirects = {k: v for k, v in redirects.items() if k.startswith("Template:")}
    manual = fix_redirects(template_redirects, manual or target.get(force=True), "Template", [], {})
    return manual, redirects


def build_initial_components(target: Page, disambigs: list, all_infoboxes, bad_cats: list, manual: str = None,
                             keep_page_numbers=False, redirects: dict = None) -> Tuple[str, Dict, PageComponents]:
    # now = datetime.now()
    if not redirects:
        manual = manual or target.get(force=True)
        manual, redirects = fix_template_redirects(target, manual)

    before, infobox, original = initial_cleanup(target, all_infoboxes, before=manual, keep_page_numbers=keep_page_numbers)

    # print(f"cleanup: {(datetime.now() - now).microseconds / 1000} microseconds")
    if "{{otheruses" in before.lower() or "{{youmay" in before.lower():
        for r, t in redirects.items():
            if t in disambigs or "(disambiguation)" in t:
                before = fix_disambigs(r, t, before)

    canon = False
    legends = False
    real = False
    media = False
    person = False
    non_canon = False
    unlicensed = False
    app_mode = BY_INDEX
    flag = []
    for c in target.categories():
        if "Non-canon Legends articles" in c.title() or "Non-canon articles" in c.title():
            non_canon = True
        elif "Articles from unlicensed sources" in c.title():
            unlicensed = True
        if "canon articles" in c.title().lower():
            canon = True
        elif "legends articles" in c.title().lower():
            legends = True
        elif c.title(with_ns=False) == "Real-world people":
            real = True
            person = True
        elif c.title(with_ns=False) == "Real-world media":
            real = True
            media = True
            if re.search("\{\{Top\|(.*?\|)?(dotj|tor|thr|fotj|rote|aor|tnr|rofo|cnjo|can|ncc)(\|.*?)?}}", target.get()):
                canon = True
            # elif re.search("\{\{Top\|(.*?\|)?(pre|btr|old|imp|reb|new|njo|lgc|inf|ncl|leg)(\|.*?)?}}", target.get()):
            #     canon = False
        elif c.title(with_ns=False).startswith("Real-world") and c.title(with_ns=False) not in ["Real-world restaurants", "Real-world stores"]:
            real = True

        if c.title() in bad_cats:
            flag.append(c.title())

    media_cat = None
    stub = None
    if "{{Mediacat" in before:
        x = re.search("\{\{Mediacat.*?}}", before)
        if x:
            media_cat = x.group(0)
    if real and media:
        if media_cat:
            before = before.replace("\n" + media_cat, "")
            if "|from=1" not in media_cat:
                media_cat = media_cat.replace("Mediacat", "Mediacat|from=1")
        y = re.search("\{\{([A-z]+-)?[Ss]tub(\|.*?)?}}", before)
        if y:
            stub = y.group(0)
            if stub.lower() == "{{stub}}" and media:
                stub = "{{Media-stub}}"
            before = before.replace("\n" + y.group(0), "").replace(y.group(0), "")
    elif real:
        media_cat = "Ignore"

    if real and media and before.count("\n==") > 3 and "==External links==\n{{Mediacat" in before:
        before = re.sub("(==External links==\n)\{\{Mediacat.*?\n", "\\1", before)

    if target.title().startswith("User:") and "{{Top|legends=" in target.get():
        canon = True
        app_mode = BY_INDEX
    return before, redirects, PageComponents(manual or target.get(), canon, non_canon, unlicensed, real, app_mode,
                                             media, person, infobox, original, flag, target.title(), media_cat, stub)


def match_iu_header(line):
    for k, v in MASTER_STRUCTURE.items():
        if line.lower() == v.lower():
            return k
    return ""


def split_by_section(text: str, results: PageComponents) -> Tuple[Dict[str, SectionLeaf], List[str], Set[str]]:
    by_section = {}
    duplicates = set()
    intro = []
    current, subheader = "", ""
    section_num, subheader_num, current_level = 1, 1, 0
    for line in text.splitlines():
        line = line.replace(FLAG_TEMPLATE, "").replace(BTS_FLAG_TEMPLATE, "")
        level = len(re.search("^(=+)", line).group(1)) if line.startswith("==") else 0
        if current_level == 0:
            current_level = level + 0
        needs_app = (line.endswith("{{App") or "{{App|" in line) and "appearances" not in (current or '').lower() and results.infobox != "MagazineDepartment"

        if "===non-canon appearances===" in line.strip().lower() and "Appearances" not in by_section:
            intro.append(line)
        elif not results.real and level >= 2 and match_iu_header(line.strip()):
            current = match_iu_header(line.strip())
            by_section[current] = SectionLeaf(current, line.strip(), 1, level)
        elif results.real and level == 3 and current:
            # only process subheaders if it's a real-world article
            x = re.search("^===?([^=].*?)=+ *$", line)
            if x:
                subheader = x.group(1).strip()
                if subheader in by_section[current].subsections:
                    i = 2
                    while subheader in by_section[current].subsections:
                        subheader = f"{subheader} {i}"
                        i += 1
                    duplicates.add(subheader)
                by_section[current].subsections[subheader] = SectionLeaf(subheader, line.strip(), subheader_num, 3, duplicate=subheader in duplicates)
                subheader_num += 1
            else:
                print(f"Unknown header line: {line}")
        elif results.real and (2 <= level <= 3 or needs_app):
            extra_line = None
            if needs_app:
                extra_line = f"{line}"
                line, level = "==Appearances==", 2

            # store top-level section headers in a dict and store the lines for that section under that key
            x = re.search("^===?([^=]+?)=+ *$", line)
            if x:
                current = x.group(1).strip()
                if current in by_section:
                    print(f"Unexpected state: duplicate {x.group(1).strip()} header")
                    i = 2
                    while current in by_section:
                        current = f"{current} {i}"
                        i += 1
                    duplicates.add(current)
                by_section[current] = SectionLeaf(current, line.strip(), section_num, 2, duplicate=current in duplicates)
                section_num += 1
                subheader = None
                subheader_num = len(by_section[current].subsections) + 1
                if needs_app and extra_line:
                    by_section[current].lines.append(extra_line)
            else:
                print(f"Unknown header line: {line}")
        elif not current:
            intro.append(line)
        elif subheader:
            if level and level > (current_level + 1):
                line = re.sub("^=+(.*?)=+$", '='*(current_level + 1) + "\\1" + '='*(current_level + 1), line)
                level = current_level + 1
            by_section[current].subsections[subheader].lines.append(line)
        else:
            by_section[current].lines.append(line)
        current_level = level + 0
    return by_section, intro, duplicates


def parse_data(results: PageComponents, lines: list, master_header, redirects, disambigs, types, remap, extra, unknown, log):
    section_text = "\n".join(lines)
    after = ""  # remove succession boxes from text before parsing
    if "{{start_box" in section_text.lower() or "{{start box" in section_text.lower() or "{{startbox" in section_text.lower():
        pieces2 = re.split("({{[Ss]tart[_ ]?[Bb]ox)", section_text, 1)
        if len(pieces2) == 3:
            section_text = pieces2[0]
            after = pieces2[1] + pieces2[2]
    if master_header == "Sources" and extra and not results.real:
        for i in extra:
            section_text += f"\n*''[[{i}]]''"

    section_text = fix_redirects(redirects, section_text, f"Parsing-{master_header}", disambigs, remap)
    results.redirects_fixed.add(master_header)
    result = parse_section(section_text, types, "Appearances" in master_header, unknown, after, log, master_header)
    if log:
        print(f"{master_header}: {len(result.items)} --> {len(set(i.unique_id() for i in result.items))}")
    if master_header == "Collections":
        results.collections = result
    elif master_header == "Appearances":
        results.apps = result
    elif master_header == "Non-Canon Appearances":
        results.nca = result
    elif master_header == "Sources":
        results.src = result
    elif master_header == "Non-Canon Sources":
        results.ncs = result
    elif master_header == "Links":
        results.links = result


def _valid() -> Dict[str, List[SectionLeaf]]:
    return {}


def remove_nav_templates_from_section(results, section: SectionLeaf, types):
    for l in section.lines:
        if l.startswith("{{"):
            x = re.search("\{\{(.*?)(\|.*?)?}}", l)
            if x and is_nav_template(x.group(1), types):
                results.append(l)
    if results:
        section.lines = [l for l in section.lines if l not in results]


def remove_nav_templates(section: SectionLeaf, types):
    nav_lines = []
    remove_nav_templates_from_section(nav_lines, section, types)
    for s in section.subsections.values():
        remove_nav_templates_from_section(nav_lines, s, types)
    return nav_lines


def fix_section_redirects(section: SectionLeaf, redirects, header, disambigs, remap: dict, overwrite: bool):
    section_text = fix_redirects(redirects, "\n".join(section.lines), f"Section-{header}", disambigs, remap, overwrite=overwrite)
    section.lines = section_text.splitlines()
    for k, s in section.subsections.items():
        subsection_text = fix_redirects(redirects, "\n".join(s.lines), f"Subsection-{k}", disambigs, remap, overwrite=overwrite)
        s.lines = subsection_text.splitlines()


FLAG_TEMPLATE = "{{SectionFlag}}"
BTS_FLAG_TEMPLATE = "{{SectionFlag|bts}}"


def build_page_sections(target: Page, text: str, results: PageComponents, redirects: dict, disambigs: list, types: dict,
                        appearances: FullListData, sources: FullListData, remap: dict, log: bool,
                        extra=None):
    text = analyze_body(target, text, types, appearances, sources, remap, disambigs, redirects, results, log)
    unknown = []
    final = ""
    rest = []

    x = re.split("(\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:|\{\{RelatedCategories)", text, 1)
    if x:
        text = x[0]
        final = "".join(x[1:])

    by_section, intro, duplicates = split_by_section(text, results)

    valid = _valid()
    other = {}
    valid_nums = {}
    nav_lines = []
    images = []
    do_not_validate = results.person or results.infobox == "MagazineDepartment"
    for header, section in by_section.items():
        if results.media:
            master_header = match_header(header, results.infobox)
            if results.infobox in COVER_GALLERY_MEDIA:
                section.lines = check_for_cover_image(section.lines, images)
                for _, sx in section.subsections.items():
                    sx.lines = check_for_cover_image(sx.lines, images)
            if not master_header and section.subsections:
                for p, z in SUBSECTIONS.items():
                    if all(i in z for i in section.subsections):
                        master_header = p
                        break
        elif results.real:
            master_header = match_header(header, results.infobox)
        else:
            master_header = header if header in MASTER_STRUCTURE else None

        if master_header == "References":
            section.name = "Notes and references"
            section.header_line = MASTER_STRUCTURE[master_header]
            valid["References"] = [section]
            nav_lines += remove_nav_templates(section, types)
        # the 6 master sections should be parsed by the Engine, except the Appearances section of a real-world article
        elif master_header in MASTER_STRUCTURE and not (results.real and master_header == "Appearances"):
            parse_data(results, section.lines, master_header, redirects, disambigs, types, remap, extra, unknown, log)
            nav_lines += remove_nav_templates(section, types)
            continue
        elif master_header:
            fix_section_redirects(section, redirects, header, disambigs, remap, False)
            results.redirects_fixed.add(header)
            nav_lines += remove_nav_templates(section, types)

            # Identify any master sections that are incorrectly on a subheader level, and move them up
            empty = process_subsections(master_header, section, results, redirects, disambigs, types, remap, valid,
                                        by_section, unknown, log, extra)
            if empty:
                continue

            if master_header == "Appearances" and "Out-of-universe appearances" in section.subsections and "In-universe appearances" not in section.subsections:
                section.subsections["In-universe appearances"] = SectionLeaf("In-universe appearances", "===In-universe appearances===", 0, 3, lines=section.lines)
                section.lines = []

            if master_header in valid and header.lower() != master_header.lower():
                if master_header in SUBSECTIONS and header in SUBSECTIONS[master_header]:
                    if not valid.get(master_header):
                        valid[master_header] = [SectionLeaf(master_header, f"=={master_header}==", section.num, 2)]
                    section.level = 3
                    section.header_line = f"==={header}==="
                    valid[master_header][0].subsections[header] = section
                else:
                    section.invalid = not do_not_validate
                    other[header] = section
            elif master_header in valid:
                valid[master_header].append(section)
            else:
                valid[master_header] = [section]
                valid_nums[section.num] = master_header
        elif results.real:
            section.invalid = not do_not_validate
            other[header] = section
        else:
            print(f"Unexpected state, header {header} in section map for IU article")
            continue

    for k, v in other.items():
        if k in duplicates:
            k = k.rsplit(" ", 1)[0]
        x = v.num
        found = False
        while x > 1:
            x -= 1
            if x in valid_nums:
                valid[valid_nums[x]][0].other.append(v)
                found = True
                break
        if not found:
            z = " " + (BTS_FLAG_TEMPLATE if k == 'Behind the scenes' else FLAG_TEMPLATE)
            if do_not_validate:
                z = ""
            lx = '\n' + '\n'.join(v.lines) + '\n'
            chunk = [f"=={k}{z}==" + (lx if lx.strip() else "")]
            for sx, sz in v.subsections.items():
                chunk.append(f"==={sx}===\n" + '\n'.join(sz.lines) + "\n")
            if x == 1:
                intro += chunk
            else:
                rest += chunk

    results.before = "\n".join(intro)
    if results.media:
        results.sections = rearrange_sections(target, results, valid, appearances, sources)
        results.cover_images = images
    elif valid:
        for k, v in valid.items():
            if len(v) > 1:
                v[0].lines = combine_sections(k, v)
            results.sections[k] = v[0]
    results.nav_templates = nav_lines

    final = ('\n'.join(rest) + f"\n{final}").strip()
    if results.links and results.links.after:
        final = f"{results.links.after}\n{final}"
        results.links.after = ""
    results.final = final
    return unknown


def process_subsections(master_header: str, section: SectionLeaf, results: PageComponents, redirects: dict,
                        disambigs: list, types: dict, remap: dict, valid: dict, by_section: dict, unknown, log: bool,
                        extra=None):
    skip = []
    for sx in set(section.subsections.keys()):
        if sx == "Collections" or sx == "Collected in":
            parse_data(results, section.subsections[sx].lines, "Collections", redirects, disambigs, types,
                       remap, extra, unknown, log)
            continue

        ms_header = match_header(sx, results.infobox)
        if ms_header:
            if ms_header != sx:
                section.subsections[ms_header] = section.subsections.pop(sx)
                section.subsections[ms_header].name = ms_header
                section.subsections[ms_header].header_line = f"==={ms_header}==="
                sx = f"{master_header}"

            if ms_header in SUBSECTIONS.get(master_header, []) or ms_header == master_header:
                continue
            elif master_header == "Contents" and ms_header == "Card List":
                continue
            elif master_header == "Appearances" and results.infobox == "ReferenceMagazine":
                continue
            elif ms_header not in valid and ms_header not in by_section:
                valid[ms_header] = [section.subsections[sx]]
                skip.append(sx)
    if skip:
        for x in skip:
            section.subsections.pop(x)
        if not section.subsections and not section.lines:
            if master_header == "Plot Summary":
                section.lines.append(add_plot_template(results.infobox))
            else:
                return True
    return False


def split_section_pieces(section):
    pieces = re.split("(==|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:|\{\{RelatedCategories)", section, 1)
    section = pieces[0]
    after = "".join(pieces[1:])
    if "{{start_box" in section.lower() or "{{start box" in section.lower() or "{{startbox" in section.lower():
        pieces2 = re.split("({{[Ss]tart[_ ]?[Bb]ox)", section, 1)
        if len(pieces2) == 3:
            section = pieces2[0]
            after = pieces2[1] + pieces2[2]
    return section, after


def move_interlang(before, after, final):
    x = re.split("(\{\{[Ii]nterlang)", before, 1)
    if x:
        before = x[0]
        final = "".join(x[1:]) + "\n" + final
    x = re.split("(\{\{[Ii]nterlang)", after, 1)
    if x:
        after = x[0]
        final = "".join(x[1:]) + "\n" + final
    return before, after, final


def parse_section(section: str, types: dict, is_appearances: bool, unknown: list, after: str, log, name="Target") -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    external = (name == "Links" or name.startswith("File:"))
    data = []
    unique_ids = {}
    other1, other2, extra, navs = [], [], [], []
    start = True
    succession_box = False
    scroll_box = False
    cs = 0
    section = re.sub("({{CardGameSet\|set=.*?)\n\|cards=", "\\1|cards=\n", section)
    section = re.sub("({{SourceContents\|issue=.*?)\n\|contents=", "\\1|contents=\n", section)
    section = re.sub("(?<!Hamm) \((as .*?)\)", " {{C|\\1}}", section)
    section = section.replace("]]{{Mediacat", "]]\n{{Mediacat")
    for s in section.splitlines():
        if succession_box:
            other2.append(s)
            continue
        if "CardGameSet" in s:
            s = re.sub("^.*?{{CardGameSet\|(set=)?(\{\{.*?)}}( \{\{.*?}}.*?)\|cards=", "*\\2|parent=1}}\\3", s)
            s = re.sub("^.*?{{CardGameSet\|(set=)?(.*?)\|cards=", "", s)
            s = re.sub("\|parent=1(.*?)\|parent=1", "|parent=1\\1", s)
            cs += 1
        if "SourceContents" in s:
            s = re.sub("^.*?{{SourceContents\|(parent=|issue=)?(\{\{.*?)}}( \{\{.*?}}.*?)\|contents=", "*\\2|parent=1}}\\3", s)
            s = re.sub("^.*?{{SourceContents\|(parent=|issue=)?('*\[\[.*?]]'*)( \{\{.*?}}.*?)\|contents=", "*\\2}\\3", s)
            s = re.sub("^.*?{{SourceContents\|(parent=|issue=)?(.*?)\|contents=", "", s)
            s = re.sub("\|parent=1(.*?)\|parent=1", "|parent=1\\1", s)
            cs += 1

        if name.startswith("File:"):
            s = re.sub("\*'*\[+(Canon|Legends(?! of)|Star Wars Legends(?!( Epic|:)))(\|.*?)?]+[':]*", "*", s).strip()
            s = re.sub("\*'*(Canon|Legends(?! of)|Star Wars Legends(?!( Epic|:)))(\|.*?)?[':]*", "*", s).strip()
            if not s:
                continue
        # if s.strip().startswith("<!-") or s.strip().startswith("*<!-"):
        #     s = re.sub("<!--.*?-->", "", s)
        if any(x in s.lower() for x in INDEX_AND_CATS):
            z = s[1:] if s.startswith("*{{") else s
            if z not in other1:
                other1.append(z)
            continue

        if s.strip().startswith("*"):
            start = False
            x = handle_valid_line(s, is_appearances, log, types, data, [] if external else other2, unknown,
                                  unique_ids, False, name)
            if not x and external:
                z = Item(s.strip(), "Basic", False)
                if is_official_link(z):
                    z.mode = "Official"
                data.append(z)

        elif "{{scroll_box" in s.lower() or "{{scroll box" in s.lower() or "{{scrollbox" in s.lower():
            scroll_box = True
            other1.append(s)
        elif scroll_box and (s.startswith("|height=") or s.startswith("|content=")):
            other1.append(s)
        elif "{{start_box" in s.lower() or "{{start box" in s.lower() or "{{startbox" in s.lower() or "{{interlang" in s.lower():
            succession_box = True
            other2.append(s)
        elif s == "}}":  # don't include the ending }}; it'll be added by build_section_from_pieces()
            if cs > 0:
                cs = 0
        elif re.match("^<!--.*?-->$", s):
            continue
        elif s.strip():
            if not data and not re.search("^[{\[]+([Ii]ncomplete|[Cc]leanup|[Ss]croll|[Mm]ore[_ ]|[Ff]ile:)", s.strip()):
                x = handle_valid_line(f"*{s}", is_appearances, log, types, data, [] if external else other2,
                                      unknown, unique_ids, True, name)
                if x:
                    start = False
                    continue
            elif "{{" in s:
                x = re.search("\{\{(.*?)(\|.*?)?}}", s)
                if x and is_nav_template(x.group(1), types):
                    navs.append(s)
                    continue
                elif x and is_nav_or_date_template(x.group(1), types):
                    extra.append(s)
                    continue
            if start:
                other1.append(s)
            else:
                other2.append(s)
    return SectionComponents(data, other1, other2, "\n".join([*extra, after]), navs)


def handle_valid_line(s, is_appearances: bool, log: bool, types, data, other2, unknown, unique_ids, attempt=False, name="Target"):
    if s.endswith("}}}}") and s.count("{{") < s.count("}}"):
        s = s[:-2]
    is_exception = "<!-- Exception -->" in s
    z = re.sub("<!--.*?-->", "", s.replace("&ndash;", '–').replace('&mdash;', '—').strip())
    z = re.sub("<sup>(.*?)</sup>", "{{C|\\1}}", z)
    extra = ''
    if name == "Collections":
        zx = re.search("(\*[^\n\[{]*[\[{]+.*?[}\]]+['\"]*)(.*?)$", re.sub("\{\{(Series|Unknown)Listing.*?}} ?", "", z))
        if zx:
            z = zx.group(1)
            extra = zx.group(2)

    while z.startswith("*"):
        z = z[1:].strip()
    z = re.sub("(\{\{InsiderCite\|[0-9]{2}\|)Ask Lobot.*?}}", "\\1Star Wars Q&A}}", z)
    if "SWGTCG" in s and "scenario" in z:
        z = re.sub("(\{\{SWGTCG.*?)}} \{\{C\|(.*?scenario)}}", "\\1|scenario=\\2}}", z)
    if "Wikipedia:" in z and " language" in z:
        z = re.sub("[Tt]he (\[\[Wikipedia:.*?language.*?]] cover) (of|to) ('*\[\[.*?]]'*)", "\\3 {{C|\\1}}", z)
        z = re.sub("(?<!C\|)(\[\[Wikipedia:.*?language.*?]] cover(?!s))(, taken from.*?)?\n", "{{C|\\1}}\n", z)
        z = re.sub("(?<!C\|)(\[\[Wikipedia:.*?language.*?]] (edition|paperback|cover|hardcover))(?!s)", "{{C|\\1}}", z)
        z = re.sub("(?<!C\|)(\[\[Wikipedia:.*?language.*?]])\n", "{{C|\\1 edition}}\n", z)

    if name.startswith("File:"):
        z = re.sub("\[\[(The )?Topps( Company.*?)?]]'? ('*\[\[)", "\\3", z)

    x2 = re.search("\{\{[Aa]b\|.*?}}", z)
    ab = x2.group(0) if x2 else ''
    if ab:
        z = z.replace(ab, "").replace("  ", " ").strip()

    if not extra:
        x1 = re.search(
            '( ?(<ref.*?>)?(<small>)? ?\{+ ?(1st[A-z]*|V?[A-z][od]|[Ff]act|[Bb]ts[Oo]nly|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]cm?|[Cc]|[Aa]mbig|[Cc]osmetic|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}].*?$)',
            z)
        extra = x1.group(1) if x1 else ''
        if extra:
            z = z.replace(extra, '').strip()

    if name.startswith("File:"):
        x = re.search("(]]|}})['\"]* ((image )?mirrored|promotional image|cover|via TORhead|\(.*?\))", z)
        if x:
            z = z.replace(f"{x.group(2)}", "").strip()
            extra = f"{x.group(2)} {extra}".strip()
    if " via " in z or " from " in z:
        y = re.search("( (via|from) \[\[(ScreenThemes|Official ?Pix)(\|.*?)?]])", z)
        if y:
            z = z.replace(y.group(1), "")
            extra = f"{y.group(1)} {extra}".strip()
    bold = "'''" in z and re.search("(?<!s)'''(?!s)", z) and not re.search(" '''([A-z0-9 -:]+[^'])'' ",  z)

    zs = [z]
    if "/" in z and ("{{YJA|" in z or "{{All-Stars|" in z):
        x = re.search("^(.*?\{\{(YJA|All-Stars)\|)(.*?)/(.*?)(}}.*?)$", z)
        if x:
            if log:
                print(f"Splitting multi-entry line: {s}")
            zs = [f"{x.group(1)}{x.group(3)}{x.group(5)}", f"{x.group(1)}{x.group(4)}{x.group(5)}"]

    y = re.search("(?<!\|)(?P<p>[\"']*?\[\[.*?(\|.*?)?]][\"']*?) ?n?o?v?e?l? ?(and|\|) ?(?P<t>['\"]*\[\[.*?(\|.*?)?]]['\"]*?)", z)
    if not y and name.startswith("File:"):
        y = re.search("(?P<p>[\"']*?\[\[.*?(\|.*?)?]][\"']*?) via ?(?P<t>['\"]*\[\[(Star Wars Legends|Star Wars Omnibus).*?(\|.*?)?]]['\"]*?)", z)
    if y and "{{TFU|" not in z:
        if log:
            print(f"Splitting multi-entry line: {s}")
        zs = [y.groupdict()['p'], y.groupdict()['t']]
    y = re.search("(?<!\[)\[(https?.*?) (.*?)] (at|on|in) (the )?(\[https?.*? .*?])", z)
    if y:
        zs = [f"{{{{WebCite|url={y.group(1)}|text={y.group(2)}|work={y.group(5)}}}}}"]

    found = False
    for y in zs:
        print(y)
        t = extract_item(convert_issue_to_template(y), is_appearances, name, types)
        if t and not t.invalid:
            if is_official_link(t):
                t.mode = "Official"
            t.external = name == "Links"
            found = True
            data.append(t)
            t.extra = extra.strip()
            t.ab = ab
            t.bold = bold
            t.is_exception = is_exception
            ex = re.search("<!-- ?(Exception|Override)?:? ?([0-9X-]+)?\?? ?-->", s)
            if ex and ex.group(1):
                t.override = ex.group(1)
                t.override_date = ex.group(2)
            elif ex:
                t.original_date = ex.group(2)
            unique_ids[t.unique_id()] = t
    if not found:
        if not data and s.count("[") == 0 and s.count("]") == 0:
            pass
        elif "audiobook" not in s and not attempt:
            unknown.append(s)
            other2.append(s)
        if log and name != "Links":
            print(f"Unknown: {s}")
    return found


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, disambigs, redirects, results: PageComponents, log: bool):
    references = [(i[0], i[2]) for i in re.findall("(<ref name=((?!<ref).)*?[^/]>(((?!<ref).)*?)</ref>)", text)]
    references += [(i[0], i[1]) for i in re.findall("(<ref>(((?!<ref).)*?)</ref>)", text)]
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, disambigs, redirects, results.canon, results.media, log)
    # return do_final_replacements(new_text, True)
    return new_text


REF_REPLACEMENTS = [("film]] film", "film]]"), ("|reprint=yes", ""), ("|reprint=1", ""), ("|audiobook=yes", ""), ("|audiobook=1", "")]


def build_card_text(o: ItemId, c: ItemId, replace_parent=True):
    ot = c.current.original
    if c.master.template and c.master.mode == "Minis" and c.master.card:
        ot = c.master.original
    if c.current.subset and "subset=" not in ot:
        ot = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(s?text=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
    while ot.count("|subset=") > 1:
        ot = re.sub("(\|subset=.*?)\\1", "\\1", ot)
    if o.master.template and o.master.master_page:
        ot = re.sub("\{\{([A-z0-9]+)\|.*?\|(url=|subset=|scenario=|pack=|mission=|cardname=|(swg)?(alt)?link=)", re.sub("\|p=.*?(\|.*?)?}}", "\\1", o.master.original.replace("}}", "")) + "|\\2", ot)
        if (o.master.mode == "Minis" or o.master.template == "SWIA") and c.master.card:
            ot = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", ot)
            if "link=" in ot:
                ot = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", ot)
            ot = re.sub("(\|(cardname|mission)=.*?)(\|.*?)?\|\\2=.*?(\|.*?)?}}", "\\1\\3\\4}}", ot)
    if o.master.template == "SWIA" and "text" in ot:
        ot = re.sub("\|set=(.*?)\|text=''\\1''", "|set=\\1", ot)
    ot = re.sub("(\{\{.*?\|set=(.*?))\|s?text=\\2\|", "\\1|", ot)
    ot = re.sub("(\|set='*?(.*?)\|stext=.*?)\|'*?\\2'*?\|", "\\1", ot)
    ot = re.sub("\{\{SWU\|(.*?)( \(.*?\))?\|'*\\1'*\|", "{{SWU|set=\\1|", ot)
    ot = re.sub("\{\{SWU\|(?!(cardname=|set=))", "{{SWU|set=", ot)
    ot = re.sub("\|stext=(.*?)\|\\1\|", "|stext=\\1|", ot)
    ot = re.sub("(\|(ship|pack|cardname)=.*?)\\1(\|.*?)?}}", "\\1\\3}}", ot)
    ot = ot.replace("–", "&ndash;").replace("—", "&mdash;").replace("  ", " ")
    if replace_parent:
        ot = ot.replace("|parent=1", "")
    return ot


def handle_reference(full_ref, ref: str, page: Page, new_text, types, appearances: FullListData, sources: FullListData,
                     remap: dict, disambigs: dict, redirects, canon: bool, media: bool, log: bool):
    try:
        new_ref = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", ref).replace("{{PageNumber}} ", "")
        new_ref = re.sub("\|set=(.*?) \(.*?\)\|(sformatt?e?d?|stext)=.*?\|", "|set=\\1|", new_ref)
        if "<ref>" in full_ref and new_ref.count('[') == 0 and new_ref.count("]") == 0:
            x = re.search("^'*(.*?)'*$", new_ref)
            if x and x.group(1) in appearances.target:
                new_ref = appearances.target[x.group(1)][0].original
            elif x and x.group(1) in sources.target:
                new_ref = sources.target[x.group(1)][0].original
        if not media:
            x = re.search(",? (page|pg\.?|p?p\.|chapters?|ch\.) ?([0-9-]+|one|two|three|four|five)(?!])[,.]?", new_ref)
            if x:
                print(f"Found page/chapter numbers in reference: \"{x.group(0)}\" -> \"{new_ref}\"")
                # new_ref = new_ref.replace(x.group(0), "")
                new_ref = "{{PageNumber}} " + new_ref
        new_ref = convert_issue_to_template(new_ref).replace("{{=}}", "=")
        links = re.findall("(['\"]*\[\[(?![Ww]:c:).*?(\|.*?)?]]['\"]*)", new_ref)
        templates = re.findall("(\{\{[^{}\n]+}})", new_ref)
        templates += re.findall("(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)
        templates += re.findall("(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)

        new_links = []
        found = []
        for link in links:
            x = extract_item(link[0], False, "reference", types)
            if x:
                o = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target, sources.unique, sources.urls, sources.target, remap, canon, log)
                if o and not o.use_original_text and o.replace_references:
                    found.append(o)
                    if o.master.template and not x.template and x.target and not re.search("^['\"]*\[\[" + prepare_title(x.target) + "(\|.*?)?]]['\"]*$", new_ref):
                        if o.master.template != "Film" and f'"[[{x.target}]]"' not in new_ref:
                            print(f"Skipping {link[0]} due to extraneous text")
                    elif link[0].startswith('"') and link[0].endswith('"') and (len(ref) - len(link[0])) > 5:
                        if o.master.template != "StoryCite":
                            print(f"Skipping quote-enclosed link {link[0]} (likely an episode name)")
                    elif "{{" in o.master.original and len(templates) > 0:
                        print(f"Skipping {link[0]} due to presence of other templates in ref note")
                    elif o.master.original.isnumeric():
                        print(f"Skipping {link[0]} due to numeric text")
                    elif check_format_text(o, x):
                        print(f"Skipping {link[0]} due to non-standard pipelink: {x.format_text}")
                    elif x.target in SPECIAL and x.text and x.text.replace("''", "") in SPECIAL[x.target]:
                        print(f"Skipping exempt {link[0]}")
                    elif x.target in SPECIAL and x.original in SPECIAL[x.target]:
                        print(f"Skipping exempt {link[0]}")
                    elif re.search("^['\"]*\[\[" + x.target.replace("(", "\(").replace(")", "\)") + "(\|.*?)?]]['\"]*", new_ref):
                        if link[0] != o.master.original:
                            new_links.append((link[0], o.master.original))
                    elif o.current.original_target and re.search("^['\"]*\[\[" + o.current.original_target.replace("(", "\(").replace(")", "\)") + "(\|.*?)?]]['\"]*", new_ref):
                        if link[0] != o.master.original:
                            new_links.append((link[0], o.master.original))
                elif o:
                    found.append(o)
                elif x.mode == "Basic":
                    new_links.append((link[0], prepare_basic_url(x)))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, swap_parameters(ni))

        new_templates = []
        for t in templates:
            if ("bypass=1" in t or t == "{{'s}}" or "{{TORcite" in t or "{{TCWA" in t or "{{SWG" in t or t.startswith("{{C|") or
                    t.startswith("{{Blogspot") or t.startswith("{{Cite") or t.startswith("{{PageNumber")):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and is_nav_or_date_template(x.template, types):
                    continue
                o = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target, sources.unique, sources.urls, sources.target, {}, canon, log, ref=True)
                if o and o.current.is_card_or_mini():
                    new_templates.append((t, o, []))
                elif o and not (o.use_original_text or o.current.collapsed) and t != (o.master.original.replace(f"|int={page.title()}|", "|").replace(f"|int={page.title()}" + "}", "}") if media else o.master.original):
                    found.append(o)
                    ex = []
                    if "|author=" in t:
                        ex += [r[0] for r in re.findall("(\|author=(\[\[.*?\|.*?]])?.*?)[|}]", t)]
                    if "|date=" in t:
                        ex += re.findall("(\|date=.*?)[|}]", t)
                    if "|quote=" in t:
                        ex += re.findall("(\|quote=.*?)[|}]", t)
                    new_templates.append((t, o, ex))
                elif o:
                    found.append(o)

        for ot, ni, extra in new_templates:
            if ni.master.is_card_or_mini():
                z = build_card_text(ni, ni, replace_parent=page.title() != ni.master.target)
            elif ni.master.ref_magazine:
                z = re.sub("(\{\{(?!FactFile)[A-z0-9]+\|[0-9]+\|.*?)(\|.*?(\{\{'s?}})?.*?)?}}", "\\1}}", ni.master.original)
            else:
                z = swap_parameters(ni.master.original)
            z = z.replace(f"|int={page.title()}|", "|").replace(f"|int={page.title()}" + "}", "}")
            if extra:
                for i in extra:
                    z = z.replace(i, "")
                z = z[:-2] + "".join(extra) + "}}"
            if "|d=y" in ni.current.original:
                z = z[:-2] + "|d=y}}"
            new_ref = new_ref.replace(ot, z.replace("–", "&ndash;").replace("—", "&mdash;"))
            if page.title() != ni.master.target or ni.current.card:
                new_ref = re.sub("\|parent=1(?!}}( is set| \{\{C\|))", "", new_ref)

        new_ref = fix_redirects(redirects, new_ref, "Reference", disambigs, remap)
        final_ref = re.sub("\{\{[Aa]b\|.*?}}", "", full_ref.replace(ref, new_ref))
        if "<ref>" in final_ref:
            if len(found) == 1 and found[0].master.target:
                z = found[0].master.target.replace('"', '').replace('(', '').replace(')', '')
                final_ref = final_ref.replace("<ref>", f"<ref name=\"{z}\">")
            elif len(found) == 1 and found[0].master.template and found[0].master.text:
                z = found[0].master.text.replace('"', '').replace('(', '').replace(')', '').replace("'''", "").replace("''", "")
                final_ref = final_ref.replace("<ref>", f"<ref name=\"{found[0].master.template}-{z}\">")
            elif len(found) == 1:
                print(f"Cannot fix nameless reference to {found[0].master.target}: {ref}")
            elif "|cardname=" in final_ref:
                z = re.sub("^.*?\{\{(.*?)\|.*?cardname=(.*?)(\|.*?)?}}.*?$", "\\1-\\2", final_ref).replace('"', '').replace('(', '').replace(')', '').replace("'''", "").replace("''", "")
                if f'="{z}"' in new_text:
                    i = 2
                    while f'="{z}-{i}"' in new_text:
                        i += 1
                    z = f"{z}-{i}"
                final_ref = final_ref.replace("<ref>", f"<ref name=\"Card-{z}\">")
            elif "WebCite" not in final_ref:
                print(f"Cannot fix nameless reference, due to {len(found)} links found in reference: {final_ref}")
        for r, x in REF_REPLACEMENTS:
            if not ("reprint" in r and "reprint" in full_ref):
                final_ref = final_ref.replace(r, x)
        if "series series" in final_ref:
            final_ref = re.sub(" series( series)+", " series", final_ref)
        new_text = new_text.replace(full_ref, final_ref)
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return new_text
