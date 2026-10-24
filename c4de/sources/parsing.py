import re
from datetime import datetime

from pywikibot import Page
from typing import List, Tuple, Dict, Set

from c4de.common import build_redirects, fix_redirects, fix_disambigs, log_time
from c4de.sources.cleanup import initial_cleanup, EXTRA
from c4de.sources.domain import Item, FullListData, PageComponents, SectionComponents, SectionLeaf
from c4de.sources.extract import extract_item, convert_issue_to_template, is_nav_or_date_template, is_nav_template
from c4de.sources.external import is_official_link
from c4de.sources.media import match_header, check_for_cover_image, COVER_GALLERY_MEDIA, \
    SUBSECTIONS, add_plot_template, rearrange_sections, combine_sections
from c4de.sources.reference import handle_reference

BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"

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

DO_NOT_SPLIT = ["TFU", "ExclusiveTrailerCite", "CelebrationTrailer", "SliceRegion", "GalaxyMapHyperlanes"]


def is_number(d):
    return d and (d.startswith("1") or d.startswith("2"))


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def fix_template_redirects(target: Page, manual: str = None):
    redirects = build_redirects(target, manual=manual)
    template_redirects = {k: v for k, v in redirects.items() if k.startswith("Template:")}
    manual = fix_redirects(template_redirects, manual or target.get(force=True), "Template", [], {})
    return manual, redirects


def build_initial_components(target: Page, disambigs: list, all_infoboxes, bad_cats: list, manual: str = None,
                             redirects: dict = None, log=True) -> Tuple[str, Dict, PageComponents]:
    now = datetime.now()
    if not redirects:
        manual = manual or target.get(force=True)
        manual, redirects = fix_template_redirects(target, manual)
        log_time("template-redirects", now)

    before, infobox, original = initial_cleanup(target, all_infoboxes, before=manual, infobox_log=log)

    log_time("cleanup", now)
    if "{{otheruses" in before.lower() or "{{youmay" in before.lower():
        for r, t in redirects.items():
            if t in disambigs or "(disambiguation)" in t:
                before = fix_disambigs(r, t, before)

    canon, real, media, person, non_canon, unlicensed = None, False, False, False, False, False
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
            canon = False
        elif c.title(with_ns=False) == "Real-world people":
            real = True
            person = True
        elif c.title(with_ns=False) == "Real-world media":
            real = True
            media = True
            if re.search(r"\{\{Top\|(.*?\|)?(dotj|tor|thr|fotj|rote|aor|tnr|rofo|cnjo|can|ncc)(\|.*?)?}}", target.get()):
                canon = True
            elif re.search(r"\{\{Top\|(.*?\|)?(pre|btr|old|imp|reb|new|njo|lgc|inf|ncl|leg)(\|.*?)?}}", target.get()):
                canon = False
        elif c.title(with_ns=False).startswith("Real-world") and c.title(with_ns=False) not in ["Real-world restaurants", "Real-world stores"]:
            real = True

        if c.title() in bad_cats and c.title(with_ns=False) != "Legends locations with canon-only grid coordinates":
            flag.append(c.title())

    media_cat, stub = None, None
    if "{{Mediacat" in before:
        x = re.search(r"\{\{Mediacat.*?}}", before)
        media_cat = x.group(0) if x else None
    if real and media:
        if media_cat:
            before = before.replace(r"\n" + media_cat, "")
            if "|from=1" not in media_cat:
                media_cat = media_cat.replace("Mediacat", "Mediacat|from=1")
        y = re.search(r"\{\{([A-z]+-)?[Ss]tub(\|.*?)?}}", before)
        if y:
            stub = y.group(0)
            if stub.lower() == "{{stub}}" and media:
                stub = "{{Media-stub}}"
            before = before.replace(r"\n" + y.group(0), "").replace(y.group(0), "")
    elif real:
        media_cat = "Ignore"

    if real and media and before.count(r"\n==") > 3 and "==External links==\n{{Mediacat" in before:
        before = re.sub(r"(==External links==\n)\{\{Mediacat.*?\n", "\\1", before)

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
        level = len(re.search(r"^(=+)", line).group(1)) if line.startswith("==") else 0
        if current_level == 0:
            current_level = level + 0
        needs_app = (line.endswith("{{App") or "{{App|" in line) and "appearances" not in (current or '').lower() and results.infobox != "MagazineDepartment"

        if "===non-canon appearances===" in line.strip().lower() and "Appearances" not in by_section:
            z = int(line.count("=") / 2)
            intro.append("="*z + "Non-canon content" + "="*z)
        elif not results.real and level >= 2 and match_iu_header(line.strip()):
            current = match_iu_header(line.strip())
            by_section[current] = SectionLeaf(current, line.strip(), 1, level)
        elif results.real and level == 3 and current:
            # only process subheaders if it's a real-world article
            x = re.search(r"^===?([^=].*?)=+ *$", line)
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
            x = re.search(r"^===?([^=]+?)=+ *$", line)
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
                line = re.sub(r"^=+(.*?)=+$", '='*(current_level + 1) + "\\1" + '='*(current_level + 1), line)
                level = current_level + 1
            by_section[current].subsections[subheader].lines.append(line)
        else:
            by_section[current].lines.append(line)
        current_level = level + 0
    return by_section, intro, duplicates


def parse_data(results: PageComponents, lines: list, master_header, redirects, disambigs, types, remap, extra, unknown, log):
    section_text = "\n".join(lines)
    after = ""  # remove succession boxes from text before parsing
    if "{{start" in section_text.lower():
        pieces2 = re.split(r"({{[Ss]tart[_ ]?[Bb]ox)", section_text, 1)
        if len(pieces2) == 3:
            section_text = pieces2[0]
            after = pieces2[1] + pieces2[2]
    if master_header == "Sources" and extra and not results.real:
        for i in extra:
            if f"[[{i}]]" not in section_text:
                section_text += f"\n*''[[{i}]]'' {{{{MapPoint}}}}"

    section_text = fix_redirects(redirects, section_text, f"Parsing-{master_header}", disambigs, remap, canon=results.canon)
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
            x = re.search(r"\{\{(.*?)(\|.*?)?}}", l)
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
    now = datetime.now()
    text = analyze_body(target, text, types, appearances, sources, remap, disambigs, redirects, results, log)
    log_time("body-analyze", now)
    unknown = []
    final = ""
    rest = []

    x = re.split(r"(\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:|\{\{RelatedCategories)", text, 1)
    if x:
        text = x[0]
        final = "".join(x[1:])

    if "{{SourcesPage" in text:
        subpage = Page(target.site, f"{target.title()}/Sources")
        if subpage.exists():
            results.has_sources_subpage = True
            text = re.sub(r"\{\{SourcesPage.*?}}", subpage.get(), text)

    by_section, intro, duplicates = split_by_section(text, results)

    valid, valid_nums = _valid(), {}
    other = {}
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
            nav_lines += remove_nav_templates(section, types)
            parse_data(results, section.lines, master_header, redirects, disambigs, types, remap, extra, unknown, log)
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


def parse_section(section: str, types: dict, is_appearances: bool, unknown: list, after: str, log, name="Target") -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    external = (name == "Links" or name.startswith("File:"))
    data = []
    unique_ids = {}
    other1, other2, extra, navs = [], [], [], []
    start, succession_box, scroll_box = True, False, False
    cs = 0
    # TODO: remove after sweep
    section = re.sub(r"({{CardGameSet\|set=.*?)\n\|cards=", "\\1|cards=\n", section)
    section = re.sub(r"({{SourceContents\|issue=.*?)\n\|contents=", "\\1|contents=\n", section)

    section = re.sub(r"\n\*\n((<!--.*?)?['\"]*[\[{]+)", "\n*\\1", section)
    section = re.sub(r"\n\*\n\n", "\n\n", section)
    section = re.sub(r"(?<!Hamm) \((as .*?)\)", " {{C|\\1}}", section)
    section = re.sub(r"(>|\n\*)(<!--.*?)?['\"]*\[\[(.*?)(\|.*?)?]]['\"]* ?(-|—|&.dash;) ?['\"]*\[\[(.*?)(\|.*?)?]]['\"]*", "\\1\\2{{StoryCite|story=\\3|book=\\6}}", section)
    section = section.replace("]]{{Mediacat", "]]\n{{Mediacat")
    for s in section.splitlines():
        if succession_box:
            other2.append(s)
            continue
        elif "{{SourcesPage" in s:
            continue
        # TODO: remove after sweep
        if "CardGameSet" in s:
            s = re.sub(r"^.*?{{CardGameSet\|(set=)?(\{\{.*?)}}( \{\{.*?}}.*?)\|cards=", "*\\2|parent=1}}\\3", s)
            s = re.sub(r"^.*?{{CardGameSet\|(set=)?(.*?)\|cards=", "", s)
            s = re.sub(r"\|parent=1(.*?)\|parent=1", "|parent=1\\1", s)
            cs += 1

        if "SourceContents-start" in s:
            s = re.sub(r"^.*?{{SourceContents-start\|(set=|parent=|issue=)?(\{\{.*?)}}( \{\{.*?}}.*?)}}", "*\\2|parent=1}}\\3", s)
            s = re.sub(r"^.*?{{SourceContents-start\|(set=|parent=|issue=)?('*\[\[.*?]]'*)( \{\{.*?}}.*?)}}", "*\\2}}\\3", s)
            s = re.sub(r"^.*?{{SourceContents-start\|(set=|parent=|issue=)?(.*?)$", "", s)
            s = re.sub(r"\|parent=1(.*?)\|parent=1", "|parent=1\\1", s)
            cs += 1
        elif "SourceContents-end" in s:
            if cs > 0:
                cs -= 1
            continue
        elif "SourceContents|" in s:
            s = re.sub(r"^.*?{{SourceContents\|(parent=|issue=)?(\{\{.*?)}}( \{\{.*?}}.*?)\|contents=", "*\\2|parent=1}}\\3", s)
            s = re.sub(r"^.*?{{SourceContents\|(parent=|issue=)?('*\[\[.*?]]'*)( \{\{.*?}}.*?)\|contents=", "*\\2}}\\3", s)
            s = re.sub(r"^.*?{{SourceContents\|(parent=|issue=)?(.*?)\|contents=", "", s)
            s = re.sub(r"\|parent=1(.*?)\|parent=1", "|parent=1\\1", s)
            cs += 1

        if name.startswith("File:"):
            s = re.sub(r"\*'*\[+(Canon|Legends(?! of)|Star Wars Legends(?!( Epic|:)))(\|.*?)?]+[':]*", "*", s).strip()
            s = re.sub(r"\*'*(Canon|Legends(?! of)|Star Wars Legends(?!( Epic|:)))(\|.*?)?[':]*", "*", s).strip()
            if not s:
                continue
        if any(x in s.lower() for x in INDEX_AND_CATS):
            z = s[1:] if s.startswith("*{{") else s
            if z not in other1:
                other1.append(z)
            continue

        if s.strip().startswith("*") or s.strip().startswith("#*"):
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
        elif "{{startbox" in s.lower() or "{{interlang" in s.lower():
            succession_box = True
            other2.append(s)
        elif s == "}}":  # don't include the ending }}; it'll be added by build_section_from_pieces()
            if cs > 0:
                cs = 0
        elif re.match(r"^<!--.*?-->$", s):
            continue
        elif s.strip():
            if not data and not re.search(r"^[{\[]+([Ii]ncomplete|[Cc]leanup|[Ss]croll|[Mm]ore[_ ]|[Ff]ile:)", s.strip()):
                x = handle_valid_line(f"*{s}", is_appearances, log, types, data, [] if external else other2,
                                      unknown, unique_ids, True, name)
                if x:
                    start = False
                    continue
            elif "{{" in s:
                x = re.search(r"\{\{(.*?)(\|.*?)?}}", s)
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
    z = re.sub(r"<!--.*?-->", "", s.replace("&ndash;", '–').replace('&mdash;', '—').strip())
    z = re.sub(r"<sup>(.*?)</sup>", "{{C|\\1}}", z)
    extra = ''
    if name == "Collections":
        zx = re.search(r"(\*[^\n\[{]*[\[{]+.*?[}\]]+['\"]*)(.*?)$", re.sub(r"\{\{(Series|Unknown)Listing.*?}} ?", "", z))
        if zx:
            z = zx.group(1)
            extra = zx.group(2)

    while z.startswith("*") or z.startswith("#"):
        z = z[1:].strip()
    if "SWGTCG" in s and "scenario" in z:
        z = re.sub(r"(\{\{SWGTCG.*?)}} \{\{C\|(.*?scenario)}}", "\\1|scenario=\\2}}", z)
    if "Wikipedia:" in z and " language" in z:
        z = re.sub(r"[Tt]he (\[\[Wikipedia:.*?language.*?]] cover) (of|to) ('*\[\[.*?]]'*)", "\\3 {{C|\\1}}", z)
        z = re.sub(r"(?<!C\|)(\[\[Wikipedia:.*?language.*?]] cover(?!s))(, taken from.*?)?\n", "{{C|\\1}}\n", z)
        z = re.sub(r"(?<!C\|)(\[\[Wikipedia:.*?language.*?]] (edition|paperback|cover|hardcover))(?!s)", "{{C|\\1}}", z)
        z = re.sub(r"(?<!C\|)(\[\[Wikipedia:.*?language.*?]])\n", "{{C|\\1 edition}}\n", z)

    x2 = re.search(r"\{\{[Aa]b\|.*?}}", z)
    ab = x2.group(0) if x2 else ''
    if ab:
        z = z.replace(ab, "").replace("  ", " ").strip()

    if not extra:
        x1 = re.search(r'( ?(<ref.*?>)?(<small>)? ?' + EXTRA + '.*?$)', z)
        extra = x1.group(1) if x1 else ''
        if extra:
            z = z.replace(extra, '').strip()

    if name.startswith("File:"):
        x = re.search(r"(]]|}})['\"]* ((image )?mirrored|promotional image|cover|via TORhead|\(.*?\))", z)
        if x:
            z = z.replace(f"{x.group(2)}", "").strip()
            extra = f"{x.group(2)} {extra}".strip()
    if " via " in z or " from " in z:
        y = re.search(r"( (via|from) \[\[(ScreenThemes|Official ?Pix)(\|.*?)?]])", z)
        if y:
            z = z.replace(y.group(1), "")
            extra = f"{y.group(1)} {extra}".strip()
    bold = "'''" in z and re.search(r"(?<!s)'''(?!s)", z) and not re.search(r" '''([A-z0-9 -:]+[^'])'' ",  z)

    zs = [z]
    if "/" in z and ("{{YJA|" in z or "{{All-Stars|" in z):
        x = re.search(r"^(.*?\{\{(YJA|All-Stars)\|)(.*?)/(.*?)(}}.*?)$", z)
        if x:
            if log:
                print(f"Splitting multi-entry line: {s}")
            zs = [f"{x.group(1)}{x.group(3)}{x.group(5)}", f"{x.group(1)}{x.group(4)}{x.group(5)}"]

    y = re.search(r"(?<!\|)(?P<p>[\"']*?\[\[.*?(\|.*?)?]][\"']*?) ?n?o?v?e?l? ?(and|\|) ?(?P<t>['\"]*\[\[.*?(\|.*?)?]]['\"]*?)", z)
    if not y and name.startswith("File:"):
        y = re.search(r"(?P<p>[\"']*?\[\[.*?(\|.*?)?]][\"']*?) via ?(?P<t>['\"]*\[\[(Star Wars Legends|Star Wars Omnibus).*?(\|.*?)?]]['\"]*?)", z)
    if y and not any(f"{{{{{x}|" in z for x in DO_NOT_SPLIT):
        if log:
            print(f"Splitting multi-entry line: {s}")
        zs = [y.groupdict()['p'], y.groupdict()['t']]
    y = re.search(r"(?<!\[)\[(https?.*?) (.*?)] (at|on|in) (the )?(\[https?.*? .*?])", z)
    if y:
        zs = [f"{{{{WebCite|url={y.group(1)}|text={y.group(2)}|work={y.group(5)}}}}}"]

    found, invalid = False, False
    for y in zs:
        t = extract_item(convert_issue_to_template(y), is_appearances, name, types)
        if t and t.invalid:
            invalid = True
        elif t:
            if is_official_link(t):
                t.mode = "Official"
            t.external = name == "Links"
            found = True
            data.append(t)
            t.extra = extra.strip()
            t.ab = ab
            t.bold = bold
            t.is_exception = is_exception
            y = re.search(r"<!-- ((([Nn]on-?)?[Cc]anon|NCA|NCS) ([Ee]xception|[Oo]verride))(:.*?)? ?-->", s)
            if y:
                t.canon_override = y.group(1)
            else:
                ex = re.search(r"<!-- ?.*?(Exception|Override)?:? ?([0-9X-]+)?\?? ?-->", s)
                if ex and ex.group(1):
                    t.override = ex.group(1)
                    t.override_date = ex.group(2)
                    t.original_date = ex.group(2)
                elif ex:
                    t.original_date = ex.group(2)

            unique_ids[t.unique_id()] = t
    if not found:
        if not data and s.count("[") == 0 and s.count("]") == 0:
            pass
        elif invalid:
            unknown.append(s)
            other2.append(re.sub(r"^(\*(<!--.*?-->)?)?( ?\{\{UnknownListing.*?}} ?)?(.*?)$", "\\1{{UnknownListing}} \\4", s))
        elif "audiobook" not in s and not attempt:
            unknown.append(s)
            other2.append(s)
        if log and name != "Links":
            print(f"Unknown: {s}")
    return found


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, disambigs, redirects, results: PageComponents, log: bool):
    references = [(i[0], i[2]) for i in re.findall(r"(<ref name=((?!<ref).)*?[^/]>(((?!<ref).)*?)</ref>)", text)]
    references += [(i[0], i[1]) for i in re.findall(r"(<ref>(((?!<ref).)*?)</ref>)", text)]
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, disambigs, redirects, results.canon, results.media, log)
    return new_text
