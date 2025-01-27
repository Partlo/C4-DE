import re

from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional

from c4de.sources.domain import FullListData, PageComponents, SectionLeaf
from c4de.common import sort_top_template

MASTER_STRUCTURE = {
    "Collections": "==Collections==",
    "Sources": "==Sources==",
    "References": "==Notes and references==",
    "Links": "==External links=="
}

MEDIA_STRUCTURE = {
    "Publisher Summary": "==Publisher's summary==",
    "Official Description": "==Official description==",
    "Opening Crawl": "==Opening crawl==",
    "Plot Summary": "==Plot summary==",
    "Contents": "==Contents==",
    "Gameplay": "==Gameplay==",
    "Development": "==Development==",
    "Release/Reception": "==Release and reception==",
    "Continuity": "==Continuity==",
    "Adaptations": "==Adaptations and tie-in media",
    "Legacy": "==Legacy==",
    "Media": "==Media==",
    # "Issues": "===Issues===",
    # "Editions": "===Editions===",
    # "Episodes": "===Episodes===",
    # "Seasons": "===Seasons===",
    # "Cover Gallery": "===Cover gallery===",
    # "Poster Gallery": "===Poster gallery===",
    # "Content Gallery": "===Content gallery===",
    "Collections": "==Collections==",
    "Credits": "==Credits==",
    "Appearances": "==Appearances==",
    "Sources": "==Sources==",
    "References": "==Notes and references==",
    "Links": "==External links=="
}

SUBSECTIONS = {
    "Contents": ["Articles", "Departments", "Features"],
    "Development": ["Conception", "Production"],
    "Media": ["Issues", "Editions", "Episodes", "Seasons", "Cover gallery", "Poster gallery", "Content gallery"]
}


def remove(s, x):
    y = f"{s}"
    for i in x:
        y = y.replace(f"{i} ", "")
    return y


def match_header(header: str, infobox):
    i = infobox.replace("_", " ").lower()
    h = header.lower().strip().replace("'", "").replace("-", " ")
    if i == "book series" and h == "novels":
        return "Contents"
    elif i and i.startswith("television") and remove(h, "official") == "description":
        return "Official Description"

    if h in ["behind the scenes", "main characters", "characters", "major characters"]:
        return "FLAG"
    elif h == "sources":
        return "Sources"
    elif h == "external links":
        return "Links"
    elif h in ["notes and references", "references"]:
        return "References"
    elif h == "collections":
        return "Collections"

    if h in ["plot summary", "synopsis", "story"]:
        return "Plot Summary"
    elif remove(h, ["publisher", "publishers", "publishing", "official", "product", "manufacturers", "publication"]) in [
        "summary", "description", "from the publisher", "back cover summary",
    ]:
        return "Publisher Summary"
    elif h in ["opening crawl", "opening crawls"]:
        return "Opening Crawl"
    elif h in ["gameplay"]:
        return "Gameplay"
    elif h in ["development", "production", "conception"]:
        return "Development"
    elif h in ["continuity"]:
        return "Continuity"
    elif h in ["release", "reception"]:
        return "Release/Reception"
    elif h in ["legacy"]:
        return "Legacy"
    elif h in ["credits", "cast"]:
        return "Credits"
    elif h in ["appearances"]:
        return "Appearances"
    elif h in ["adaptation", "adaptations", "adaption", "adaptions", "tie in media"]:
        return "Adaptations"
    elif h in ["cover gallery", "cover art"]:
        return "Cover gallery"
    elif h in ["posters", "poster gallery"]:
        return "Poster gallery"
    elif h in ["content gallery", "media gallery"]:
        return "Content gallery"
    elif h in ["issues"]:
        return "Issues"
    elif h in ["edition", "editions"]:
        return "Editions"
    elif h in ["seasons"]:
        return "Seasons"
    elif h in ["episodes", "videos"]:
        return "Episodes"
    elif h in ["media"]:
        return "Media"

    if h in ["content", "contents", "tracks", "track list", "track listing", "comic strip", "features",
             "stories", "short stories", "other stories", "articles", "adventures",
             "collects", "collected issues", "collected stories", "collected comic strips"]:
        return "Contents"
    return None


def check_for_cover_image(item: SectionLeaf, valid: dict, images: list):
    to_remove = []
    for i in range(len(item.lines)):
        if item.lines[i].startswith("[[File:") and re.search("\[\[File:.*?\|.*?[Cc]over.*?]]", item.lines[i]):
            if "Cover Gallery" not in valid:
                images.append(item.lines[i])
                to_remove.append(i)
            else:
                print(f"Possible false positive: {item.lines[i]}")
    if to_remove:
        item.lines = [ln for i, ln in enumerate(item.lines)]


def rearrange_sections(valid: Dict[str, List[SectionLeaf]], infobox):
    sections = {}
    has_summary = False
    images = []
    for key, items in valid.items():
        if key == "Publisher Summary" or key == "Official Description":
            if has_summary:
                items[0].flag = True
            has_summary = True

        for it in items:
            check_for_cover_image(it, valid, images)

        if key in MEDIA_STRUCTURE and key in sections:
            if len(items) > 0:
                items[0].lines = combine_sections(items)
            if len(items[0].lines) > 0 and len(sections[key].lines) > 0:
                sections[key].lines.append("")
                sections[key].lines += items[0].lines
            for sx, subsection in items[0].subsections.items():
                if sx in sections[key].subsections:
                    print(f"Unexpected state: multiple {sx} subsections for {key}")
                sections[key].subsections[sx] = subsection
            continue
        elif key in MEDIA_STRUCTURE:
            sections[key] = items[0]
            continue

        for parent, children in SUBSECTIONS.items():
            if key in children:
                if parent not in sections:
                    sections[parent] = SectionLeaf(parent, f"=={parent}==", items[0].num, 2)
                kx = f"{key}"
                if infobox in ["board game", "card game"] and "Gallery" in kx:
                    kx = "Content Gallery"
                if len(items) > 1:
                    print(f"Unexpected state: multiple sections found for {kx} header")
                sections[parent].subsections[kx] = combine_and_demote_sections(items, key, kx)

    return sections


def combine_sections(items: List[SectionLeaf], sub=False):
    lines = [*items[0].lines]
    for ix in items[1:]:
        lines.append("")
        lines += ix.lines
        if sub:
            for sx, si in ix.subsections.items():
                lines.append("")
                lines.append(si.header_line)
                lines += si.lines
    return lines


def combine_and_demote_sections(items, key, kx):
    new_text = []
    for i in items:
        for ln in i.lines:
            if ln.startswith("=="):
                new_text.append(f"={ln}=")
            else:
                new_text.append(ln)
        for sx, ss in i.subsections.items():
            if key != "Editions":
                new_text.append("")
                new_text.append(f"===={sx}====")
            for ln in ss.lines:
                if ln.startswith("=="):
                    new_text.append(f"={ln}=")
                elif not ln and key == "Editions":
                    pass
                else:
                    new_text.append(ln)
    items[0].lines = new_text
    items[0].level = 3
    items[0].name = kx
    items[0].header_line = f"==={kx}==="
    return items[0]


ITALICIZE = ["book", "audiobook", "comic series", "comic collection", "comic story arc", "graphic novel", "reference book"]
ISSUE = ["magazine", "comic", "comic book"]
QUOTES = ["magazine article", "magazine department", "short story", "comic story", "rpg adventure", "comic strip"]


def simplify(s):
    return s.replace("–", "-").replace("—", "-").replace("&mdash;", "-").replace("&ndash;", "-")


def prepare_media_infobox_and_intro(page: Page, results: PageComponents, appearances: FullListData,
                                    sources: FullListData) -> List[str]:
    fmt = None
    if page.title() in appearances.target:
        if not appearances.target[page.title()][0].template:
            fmt = appearances.target[page.title()][0].original
    elif page.title() in sources.target:
        if not sources.target[page.title()][0].template:
            fmt = sources.target[page.title()][0].original
    if not fmt and results.infobox:
        if results.infobox in ISSUE:
            fmt = re.sub("^(.*?)( \([0-9]+\))? ([0-9]+)( \(.*?\))?$", "<b>''\\1''\\2 \\3<b>", page.title())
        if results.infobox in ITALICIZE or (fmt and "''" in fmt):
            fmt = "<b>''" + re.sub(" \(.*?\)$", "", page.title()) + "''<b>"
        if results.infobox in QUOTES:
            fmt = "\"<b>" + re.sub(" \(.*?\)$", "", page.title()) + "<b>\""
    if fmt:
        fmt = fmt.replace("<b>", "'''")

    pieces = []
    ct = 0
    infobox_found, infobox_done, title_found = False, False, False
    for ln in results.before.strip().splitlines():
        if "{{top" in ln.lower():
            ln = sort_top_template(ln)
        elif f"{{{{{results.infobox}" in ln.lower() or f"{{{{{results.infobox.replace(' ', '_')}" in ln.lower():
            infobox_found = True
        elif ln.startswith("|title=") and fmt:
            if "''" in fmt and "''" not in ln:
                ln = f"|title={fmt}"
        elif "|series=" in ln:
            x = re.search("series='*\[\[(.*?)(\|.*?)?]]'*", ln)
            if x and x.group(1) in appearances.target:
                ln = ln.replace(x.group(0), f"series={appearances.target[x.group(1)][0].original}")
        elif "|preceded by" in ln or "|followed by" in ln or "|prev" in ln or "|next" in ln:
            if results.infobox == "television episode":
                ln = re.sub("\|(preceded by|followed by|prev|next) ?= ?[\"']*(\[\[.*?]])[\"']*",
                            '|\\1="\\2"', ln)
            else:
                # TODO: check appearances/sources and use correct formatting
                ln = re.sub("\|(preceded by|followed by|prev|next) ?= ?'*\[\[(.*?)( \([0-9]+\))? ([0-9]+)(\|.*?)?]]'*",
                            "|\\1=[[\\2\\3 \\4|''\\2''\\3 \\4]]", ln)
        if infobox_found:
            ct += (ln.count("{") - ln.count("}"))
            if ct == 0:
                infobox_found = False
                infobox_done = True
        if infobox_done and not title_found and fmt and fmt not in ln and "'''" in ln:
            if ln.count("'''") > 2:
                ft = False
                for x, y in re.findall("(\"?'''+\"?(.*?)\"?'''+\"?)", ln):
                    if simplify(y).lower() == simplify(page.title()).lower():
                        ln = ln.replace(x, fmt)
                        ft = True
                if not ft:
                    print(f"Multiple bolded titles in intro, but no close match; cannot replace title")
            else:
                ln = re.sub("\"?'''+\"?(.*?)\"?'''+\"?", fmt, ln)
            title_found = True

        pieces.append(ln)
    return pieces


# TODO: italicize publisher's summary
# TODO: detect publisher's listing for comic in infobox and add to ExL; tag issues without DH & Marvel
# TODO: use Masterlist formatting for Contents sections
# TODO: parse and standardize ISBN lines in Editions
# TODO: build prettytable for issues sections?
# TODO: archivedate fixing based on category
# TODO: check for Contents and Plot Summary
# TODO: check combine flag
# TODO: Flag Media sections with no subcats
# TODO: convert Introduction to a Contents bullet
# TODO: Fix redirects in the Contents section without preserving the original pipelink, UNLESS it's a department
# TODO: flag articles with multiple sections for the same master header for review (Star Wars Gamer 7)
