from c4de.sources.external import is_commercial
from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional, Set
import re

from c4de.common import sort_top_template, fix_redirects
from c4de.sources.domain import FullListData, PageComponents, SectionLeaf, Item, SectionComponents

NEW_APP_TEMPLATE = """{{IncompleteApp}}
{{App
|characters=
|organisms=
|droids=
|events=
|locations=
|organizations=
|species=
|vehicles=
|technology=
|miscellanea=
}}""".splitlines()

COVER_GALLERY_MEDIA = ["ComicBook", "ComicCollection", "Book", "ReferenceBook", "ReferenceMagazine", "MagazineIssue", "GraphicNovel", "VideoGame"]
PUBLISHERS = ["ComicBook", "ComicCollection"]
REMOVE_LINKS = ["Opening Crawl", "Publisher Summary", "Official Description"]
ITALICIZE = ["Book", "Audiobook", "ComicSeries", "ComicCollection", "ComicArc", "GraphicNovel", "ReferenceBook"]
ISSUE = ["Magazine", "MagazineIssue", "ComicBook", "Comic", "ReferenceMagazine"]
QUOTES = ["MagazineArticle", "MagazineDepartment", "ShortStory", "ComicStory", "Adventure", "ComicStrip", "TelevisionEpisode"]
ADD_REF = ["ReferenceBook", "Magazine", "MagazineArticle", "MagazineDepartment", "Soundtrack", "MagazineSeries",
           "ToyLine"]
PREV_OR_NEXT = ["|preceded by=", "|followed by=", "|prev=", "|next="]
MEDIA_FIELDS = ["|published in=", "|reprinted in=", "|series=", *PREV_OR_NEXT]

MEDIA_STRUCTURE = {
    "Publisher Summary": "==Publisher's summary==",
    "Official Description": "==Official description==",
    "Opening Crawl": "==Opening crawl==",
    "Plot Summary": "==Plot summary==",
    "Interactive Map": "==Interactive Map==",
    "Contents": "==Contents==",
    "Card List": "==Card list==",
    "Gameplay": "==Gameplay==",
    "Star Wars Content": "==''Star Wars'' content==",
    "Development": "==Development==",
    "Release/Reception": "==Release and reception==",
    "Continuity": "==Continuity==",
    "Adaptations": "==Adaptations and tie-in media==",
    "Legacy": "==Legacy==",
    "Media": "==Media==",
    "Credits": "==Credits==",
    "Appearances": "==Appearances==",
    "Sources": "==Sources==",
    "References": "==Notes and references==",
    "Links": "==External links=="
}

SUBSECTIONS = {
    "Contents": ["Articles", "Departments", "Features"],
    "Development": ["Conception", "Production"],
    "Media": ["Installments", "Issues", "Editions", "Shorts", "Episodes", "Seasons", "Cover gallery", "Poster gallery", "Content gallery", "Collections"],
    "Appearances": ["In-universe appearances", "Out-of-universe appearances"]
}


def remove(s, x: list):
    y = f"{s}"
    for i in x:
        y = y.replace(f"{i} ", "")
    return y


def match(s, x):
    return s.lower() == x.lower()


def match_header(header: str, infobox):
    # i = (infobox or '').replace("_", " ").lower()
    h = header.lower().strip().replace("'", "").replace("-", " ")
    if infobox and infobox == "BookSeries" and h == "novels":
        return "Contents"
    elif infobox and (infobox.startswith("Television") or infobox == "Documentary") and remove(h, ["official"]) == "description":
        return "Official Description"

    if h in ["behind the scenes", "main characters", "characters", "major characters"]:
        return None
    elif h == "sources":
        return "Sources"
    elif h == "external links" or h == "external link":
        return "Links"
    elif h == "references" or h.startswith("notes and ref") or h.startswith("notes an ref"):
        return "References"
    elif h in ["collections", "collected in"]:
        return "Collections"
    elif h in ["interactive map"]:
        return "Interactive Map"
    elif h in ["plot summary", "synopsis", "story"]:
        return "Plot Summary"
    elif remove(h, ["publisher", "publishers", "publishing", "official", "product", "manufacturers", "publication"]) in [
        "summary", "description", "from the publisher", "back cover summary", "site summary", "blurb"
    ]:
        return "Publisher Summary"
    elif h in ["opening crawl", "opening crawls", "opening inscription"]:
        return "Opening Crawl"
    elif h in ["gameplay"]:
        return "Gameplay"
    elif h in ["development", "production", "conception"]:
        return h.capitalize()
    elif h in ["continuity", "continuity errors"]:
        return "Continuity"
    elif h in ["release", "reception", "release and reception", "release & reception", "critical reception", "critical reaction"]:
        return "Release/Reception"
    elif h in ["legacy", "metaseries"]:
        return "Legacy"
    elif h in ["credits", "cast"]:
        return "Credits"
    elif h in ["appearances"]:
        return "Appearances"
    elif h in ["in universe appearances", "in universe"]:
        return "In-universe appearances"
    elif h in ["out of universe appearances", "out of universe", "real world appearances"]:
        return "Out-of-universe appearances"
    elif h in ["adaptation", "adaptations", "adaption", "adaptions", "tie in media", "merchandising", "merchandise",
               "merchandise and tie in media", "adaptations and tie in media"]:
        return "Adaptations"
    elif h in ["cover gallery", "cover art"]:
        return "Cover gallery"
    elif h in ["posters", "poster gallery"]:
        return "Poster gallery"
    elif h in ["content gallery", "media gallery"]:
        return "Content gallery"
    elif h in ["features"]:
        return "Features"
    elif h in ["departments"]:
        return "Departments"
    elif h in ["articles"]:
        return "Articles"
    elif h in ["issues", "issues with star wars content"]:
        return "Issues"
    elif h in ["edition", "editions"]:
        return "Editions"
    elif h in ["seasons"]:
        return "Seasons"
    elif h in ["shorts"]:
        return "Episodes"
    elif h in ["episodes", "videos"]:
        return "Episodes"
    elif h in ["media"]:
        return "Media"
    elif h in ["cards", "card lists", "card list", "card set", "list of cards", "cardlist"]:
        return "Card List"

    if h in ["installments", "books", "books in series", "entries"]:
        return "Installments"
    if h in ["star wars content"]:
        return "Star Wars Content"

    if h in ["content", "contents", "tracks", "track list", "track listing", "comic strip", "features", "parts",
             "stories", "short stories", "other stories", "articles", "adventures", "contains", "set list",
             "collects", "collected issues", "collected stories", "collected comic strips", "collected novellas",
             "collected short stories", "collected titles"]:
        return "Card List" if infobox == "TradingCardSet" else "Contents"
    return None


def check_for_cover_image(lines, images: list):
    to_remove = []
    for i, ln in enumerate(lines):
        if ln.startswith("[[File:") and re.search("\[\[File:.*?\|(.*? )?[Cc]over.*?]]", ln):
            a, z = re.sub("^.*?\[\[([Ff]ile:.*?)(\|(thumb|[0-9]+px|left|right))*(\|.*?)?\.?]].*?$", "\\1\\4", ln).split("|", 1)
            a = a.replace(" ", "_")
            images.append(f"{a}|{z}" if z else a)
            to_remove.append(i)
    if to_remove:
        return [ln for i, ln in enumerate(lines) if i not in to_remove]
    return lines


def get_listings(title, appearances: FullListData, sources: FullListData) -> List[Item]:
    return (appearances.target.get(title) or sources.target.get(title)) or []


def remove_links(ln):
    if "[[" in ln:
        while re.search("\[\[([^\n\[\]|{}]*?\|)?([^\n\[\]|{}]*?)]]", ln):
            ln = re.sub("\[\[([^\n\[\]|{}]*?\|)?([^\n\[\]|{}]*?)]]", "\\2", ln)
    return ln


def rearrange_sections(target: Page, results: PageComponents, valid: Dict[str, List[SectionLeaf]],
                       appearances: FullListData, sources: FullListData):

    if not results.real:
        return {k: v[0] for k, v in valid.items()}
    novel = None
    if results.infobox:
        for x in [" (novel)", f" (novelization)", ""]:
            if f"{target.title()}{x}" in appearances.target:
                novel = Page(target.site, f"{target.title()}{x}")
                break

    sections = {}
    has_summary = False
    for key, items in valid.items():
        if key == "Publisher Summary" or key == "Official Description":
            if has_summary:
                items[0].invalid = True
            has_summary = True
            # apply italicization
            for i in items:
                if not any(ln.startswith("''") for ln in i.lines if ln):
                    i.lines = [f"''{ln}''" if ln and not ln.startswith("''") and not ln.startswith("{{") else ln for ln in i.lines]

        items = remap_sections(key, items, valid, sections, appearances, sources, results.infobox)
        if not items:
            continue

        # combine any duplicate master-header sections, and flag invalid subheaders
        if key in MEDIA_STRUCTURE:
            duplicate = key in sections
            if len(items) > 1:
                items[0].lines = combine_sections(key, items)

            if not duplicate:
                sections[key] = items[0]
            elif len(items[0].lines) > 0:
                if len(sections[key].lines) > 0:
                    sections[key].lines.append("")
                sections[key].lines += items[0].lines

            for sx, subsection in items[0].subsections.items():
                sxm = match_header(sx, results.infobox)
                if key in SUBSECTIONS and key != "Development":
                    if sxm not in SUBSECTIONS[key]:
                        subsection.invalid = key != "Contents" or results.infobox == "MagazineIssue"
                        subsection.master_num += len(items[0].subsections)
                    else:
                        subsection.master_num = SUBSECTIONS[key].index(sxm)
                if duplicate:
                    if sxm in sections[key].subsections:
                        print(f"Unexpected state: multiple {sxm} subsections for {key}")
                    sections[key].subsections[sxm] = subsection
            continue

        for parent, children in SUBSECTIONS.items():
            if key in children:
                if parent not in sections:
                    sections[parent] = SectionLeaf(parent, f"=={parent}==", items[0].num, 2)
                kx = f"{key}"
                if results.infobox in ["BoardGame", "CardGame", "TabletopGame", "ExpansionPack", "TradingCardSet"] and "Gallery" in kx:
                    kx = "Content Gallery"
                if len(items) > 1:
                    print(f"Unexpected state: multiple sections found for {kx} header")
                sections[parent].subsections[kx] = combine_and_demote_sections(items, key, kx)
                sections[parent].subsections[kx].master_num = children.index(key)

    return add_and_cleanup_sections(target, results, sections, valid, appearances, sources, novel)


def remap_sections(key, items: List[SectionLeaf], valid: Dict[str, List[SectionLeaf]], sections: Dict[str, SectionLeaf],
                   appearances: FullListData, sources: FullListData, infobox):
    new_items = []
    for it in items:
        if key != "Opening Crawl":
            if any("{{opening" in ln.lower() for ln in it.lines):
                crawl, other, ct = [], [], 0
                for ln in it.lines:
                    if "{{opening" in ln.lower() or (crawl and ct != 0):
                        crawl.append(ln)
                        ct += (ln.count("{{") - ln.count("}}"))
                    else:
                        other.append(ln)
                it.lines = other
                if len(other) == 0 and not it.subsections and not it.other:
                    it.remove = True
                add_correct_section("Opening Crawl", "==Opening crawl==", valid, sections, crawl)

        if key == "Contents" and infobox not in ["MagazineArticle"]:
            lines = []
            for ln in it.lines:
                z = re.search("\*'*\[\[(.*?)(\|.*?)?]]'*", ln)
                if z and (z.group(1) in appearances.target or z.group(1) in sources.target):
                    x = [i for i in appearances.target.get(z.group(1), sources.target.get(z.group(1), [])) if not i.is_reprint]
                    if x and '"[[' in x[0].original:
                        lines.append(ln.replace(z.group(0), f"*{x[0].original.split(' {{')[0]}"))
                        continue
                    elif x and x[0].template == "StoryCite" and "smanual" not in x[0].original:
                        y = re.search("\|(stext|sformat[a-z]+?)=(.*?)(\|.*?)?}}", x[0].original)
                        if y:
                            lines.append(ln.replace(z.group(0), f'*"[[{x[0].target}|{y.group(2)}]]"'))
                        else:
                            lines.append(ln.replace(z.group(0), f'*"[[{x[0].target}]]"'))
                        continue
                lines.append(ln)
            it.lines = lines

        if key == "Release/Reception":
            to_pop = set()
            for sx, sk in it.subsections.items():
                if sx.startswith("Merchandise") or "tie-ins" in sx:
                    if "Adaptations" in valid:
                        valid["Adaptations"][0].lines += sk.lines
                    elif "Adaptations" not in sections:
                        sections["Adaptations"] = SectionLeaf("Adaptations", MEDIA_STRUCTURE["Adaptations"], 0, 2, lines=sk.lines)
                    else:
                        sections["Adaptations"].lines += sk.lines
                    to_pop.add(sx)
            for x in to_pop:
                it.subsections.pop(x)

        if not it.remove:
            new_items.append(it)
    return new_items


def detect_adaptation(sections, title, text, appearances, sources):
    if "Plot Summary" not in sections or any("{{Plot|" in ln or "{{Plot}}" in ln for ln in sections["Plot Summary"].lines) or "{{Plot|" in text or "{{Plot}}" in text:
        if " (" in title and title.endswith(")"):
            z, _, y = title[:-1].partition(" (")
            if y in ["book", "episode", "audio drama", "German audio drama", "novelization", "audiobook", "abridged audiobook"]:
                if get_listings(z, appearances, sources):
                    return "{{Plot-link|" + z + "}}"
                if get_listings(f"{z} (novel)", appearances, sources) and y != "novel":
                    return "{{Plot-link|" + z + " (novel)}}"
                if get_listings(f"{z} (episode)", appearances, sources) and y != "episode":
                    return "{{Plot-link|" + z + " (episode)}}"

        x = re.search("(adapts|adaptation) .*?\[\[(Star Wars: Episode .*?)(\|.*?)?]]", text)
        if x:
            print(x.group(2), x.group(0))
            if any(i.template == "Film" for i in get_listings(x.group(2), appearances, sources)):
                return "{{Plot-link|" + x.group(2) + "}}"
        x = re.search("(adapts|adaptation) .*?\[\[(.*?)(\|.*?)?]]", text)
        if x:
            print(x.group(2), x.group(0))
            z = get_listings(x.group(2), appearances, sources)
            if z:
                return "{{Plot-link|" + x.group(2) + "}}"
    return None


def add_and_cleanup_sections(target: Page, results: PageComponents, sections: Dict[str, SectionLeaf],
                             valid: Dict[str, List[SectionLeaf]], appearances: FullListData, sources: FullListData,
                             novel: Page):

    title = target.title()
    listing = get_listings(title, appearances, sources)
    is_appearance = any(a.is_true_appearance and not a.date == "Canceled" for a in listing) and "|anthology=1" not in target.get()
    if results.infobox in ["TelevisionEpisode", "MagazineArticle", "Adventure", "ShortStory", "ComicStory", "ComicStrip", "Documentary"]:
        handle_published_in_and_collections(target, title, results, appearances, sources)

    if results.infobox == "TradingCardSet":
        add_sections_if_missing(sections, "Card List", lines=["{{IncompleteList|oou=1}}"])
    elif results.infobox == "Expansion Pack":
        add_sections_if_missing(sections, "Contents", lines=["{{IncompleteList|oou=1}}"])
    elif results.infobox == "ReferenceMagazine":
        add_sections_if_missing(sections, "Appearances", lines=NEW_APP_TEMPLATE)

    if is_appearance and results.infobox in ["ShortStory", "ComicBook", "ComicStory", "WebStrip", "Adventure", "Book", "TelevisionEpisode"]:
        add_plot_summary(sections, results)
        add_sections_if_missing(sections, "Appearances", lines=NEW_APP_TEMPLATE)

    elif results.infobox == "Audiobook" and not (listing and listing[0].extra):
        if "Plot Summary" not in sections:
            tx = detect_adaptation(sections, title, target.get(), appearances, sources)
            if tx:
                tx = re.sub("(Plot-link\|)(.*?)( \(.*?\))}}", "\\1\\2\\3|''\\2''}}", tx)
            add_plot_summary(sections, results, link=tx)

        if "Appearances" not in valid and "(" in title and "(abridged" not in title and "radio" not in title and novel:
            sections["Appearances"] = SectionLeaf("Appearances", "==Appearances==", 0, 2)
            if novel.exists() and not novel.isRedirectPage() and "Plot summary" in novel.get() and "<onlyinclude>\n{{App" not in novel.get():
                sections["Appearances"].lines = [f"{{{{:{title.split(' (')[0]}}}}}"]
            elif "German audio drama" in title:
                sections.pop("Appearances")
            else:
                sections["Appearances"].lines = ["{{MissingAppFlag}}"]

    if results.collections.items:
        add_sections_if_missing(sections, "Media", "Collections", actual="Collected in")

    if "Contents" not in sections and listing and listing[0].collection_type == "anthology":
        children = appearances.by_parent.get(title, []) + sources.by_parent.get(title, [])
        if children:
            section_lines = ["*" + prepare_quoted_link(c) for c in children]
            add_sections_if_missing(sections, "Contents", lines=section_lines)

    for key in REMOVE_LINKS:
        if key in sections:
            sections[key].lines = [remove_links(ln) for ln in sections[key].lines]
            for sx, sb in sections[key].subsections.items():
                sections[key].subsections[sx].lines = [remove_links(ln) for ln in sb.lines]

    # Validation
    if "Contents" in sections and "Plot Summary" in sections:   # Contents & Plot Summary should not be used together
        sections["Plot Summary"].invalid = True
    if "Media" in sections and len(sections["Media"].subsections) == 0:
        sections["Media"].invalid = True
    # TODO: flag book collections/etc. with missing Contents sections

    if sections.get("Plot Summary") and any("{{Plot" in ln for ln in sections["Plot Summary"].lines):
        if "{{plot}}" in results.before.lower() or "{{plot|" in results.before.lower():
            results.before = re.sub("\{\{[Pp]lot(\|.*?)?}}\n?", "", results.before)

    return sections


def add_cover_gallery(sections: Dict[str, SectionLeaf], images, main_image):
    if "Media" in sections and "Cover gallery" not in sections["Media"].subsections and any("<gallery" in ln for ln in sections["Media"].lines):
        new_lines, gallery, done = [], [], False
        if any(main_image.replace(" ", "_") in ln.replace(" ", "_") for ln in sections["Media"].lines):
            main_image = None
        for ln in sections["Media"].lines:
            if "<gallery" in ln:
                gallery.append(ln)
                if main_image:
                    gallery.append(f"{main_image}|Cover")
                if images:
                    gallery += images
            elif "</gallery>" in ln:
                gallery.append(ln)
                done = True
            elif gallery and not done:
                gallery.append(ln)
            else:
                new_lines.append(ln)
        add_sections_if_missing(sections, "Media", "Cover gallery")
        sections["Media"].subsections["Cover gallery"].lines = gallery
        sections["Media"].lines = new_lines

    elif images:
        add_sections_if_missing(sections, "Media", "Cover gallery", child_lines=["<gallery captionalign=\"center\">"])
        sections["Media"].subsections["Cover gallery"].lines += images

    if main_image and "Media" in sections and "Cover gallery" in sections["Media"].subsections:
        if not any(main_image in ln.replace(" ", "_") for ln in sections["Media"].subsections["Cover gallery"].lines):
            sections["Media"].subsections["Cover gallery"].lines.insert(1, f"{main_image}|Cover")


def add_sections_if_missing(sections: Dict[str, SectionLeaf], name: str, child: str = None, actual: str = None,
                            other_names: List[str] = None, lines: List[str] = None, child_lines: List[str] = None):
    if name not in sections:
        sections[name] = SectionLeaf(name, MEDIA_STRUCTURE.get(name, f"=={name}=="), 0, 2)
        if lines:
            sections[name].lines = lines

    if child:
        if other_names and sections[name].has_subsections(other_names):
            return False
        elif actual and sections[name].has_subsections(actual, child):
            return False
        elif not sections[name].has_subsections(child):
            sections[name].subsections[child] = SectionLeaf(child, f"==={actual or child}===", 0, 3)
            if child_lines:
                sections[name].subsections[child].lines = child_lines
            if name in SUBSECTIONS and child in SUBSECTIONS[name]:
                sections[name].subsections[child].master_num = SUBSECTIONS[name].index(child)


def add_plot_template(infobox):
    if infobox and "Comic" in infobox:
        return "{{Plot|comic}}"
    elif infobox == "ShortStory":
        return "{{Plot|story}}"
    return "{{Plot}}"


def add_plot_summary(sections: Dict[str, SectionLeaf], results: PageComponents, link=None):
    if "Plot Summary" not in sections and "Contents" not in sections:
        if not any(f"|{x}=1\n" in results.before for x in ["reprint", "anthology", "not_appearance"]):
            sections["Plot Summary"] = SectionLeaf("Plot summary", "==Plot summary==", 0, 2)
    if "Plot Summary" in sections and sections["Plot Summary"].is_empty_section():
        sections["Plot Summary"].lines.append(link or add_plot_template(results.infobox))


def handle_published_in_and_collections(target: Page, title: str, results: PageComponents, appearances: FullListData,
                                        sources: FullListData):
    drx = re.search(
        "\|(publish date|publication date|first aired|airdate|start date|first date|release date|released|published)=.*?(<ref name ?= ?\".*?\")/?>",
        results.before)
    date_ref = drx.group(2) + " />" if drx else None
    current = targets(results.collections)
    added = []
    links, refs, contents = set(), {}, {}

    items_to_check = [i.parent for i in get_listings(title, appearances, sources) if i.parent and i.template != "LivingForce" and i.parent not in current]
    for item in items_to_check:
        x = get_listings(item, appearances, sources)
        if x:
            results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents, date_ref))
            current.append(item)
        else:
            print(f"Unknown state: {item} not found in Sources")

    for field in ["published", "reprinted"]:
        rx = re.search("\|" + field + " in=\n?((\*?'*\[\[(.*?)(\|.*?)]]'*.*?\n)+)", results.before)
        if rx:
            zx = rx.group(1).splitlines()
            for z in zx:
                y = re.search("^\*?'*\[\[(.*?)(\|.*?)?]]", z)
                if y and y.group(1) not in current and y.group(1) != "Living Force (roleplaying campaign)":
                    x = get_listings(y.group(1), appearances, sources)
                    if x:
                        results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents, date_ref))
                        current.append(y.group(1))
                    else:
                        print(f"Unknown {field}-in value: {y.group(1)}")

    to_remove = []
    for i in range(len(results.src.items)):
        if results.src.items[i].target == title:
            print(f"Removing self-listing from Sources")
            if results.src.items[i].is_internal_mode():
                results.links.items.append(results.src.items[i])
            to_remove.append(i)
        elif results.src.items[i].target and results.src.items[i].target in current:
            print(f"Removing Collections listing from Sources (new={results.src.items[i].target in added})")
            to_remove.append(i)
        elif results.src.items[i].parent and results.src.items[i].parent in current and "{{PAGENAME}}" in results.src.items[i].original:
            print(f"Removing Collections listing from Sources (new={results.src.items[i].target in added})")
            to_remove.append(i)
    if to_remove:
        results.src.items = [x for i, x in enumerate(results.src.items) if i not in to_remove]


def copy_listing(x: Item, site, links: set, refs: dict, contents: dict, date_ref=None):
    nx = x.copy()
    date_str = None
    # if date_ref:
    #     date_str, _ = convert_date_str(nx.date, links)
    # else:
    #     rn = nx.target.replace("(", "").replace(")", "").replace("'", "")
    #     date_str, date_ref = build_date_and_ref(nx, site, links, refs, contents, ref_name=rn)
    if date_str:
        nx.extra = f" &mdash; {date_str}{date_ref}"
    return nx


def targets(s: SectionComponents):
    return [i.target for i in s.items]


def add_correct_section(key, header, valid: dict, sections: dict, lines):
    if key in sections:
        sections[key].lines.append("")
        sections[key].lines += lines
    elif key in valid:
        valid[key][0].lines.append("")
        valid[key][0].lines += lines
    else:
        sections[key] = SectionLeaf(key, header, 0, 2)
        sections[key].lines = lines


def combine_sections(key, items: List[SectionLeaf], sub=False):
    print(f"combining: {key}, {len(items)}")
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
            if ln.startswith("==") and i.level <= 3:
                new_text.append(f"={ln}=")
            else:
                new_text.append(ln)
        for sx, ss in i.subsections.items():
            if any(sx in v for k, v in SUBSECTIONS.items() if k != kx):
                continue

            if key != "Editions":
                new_text.append("")
                new_text.append(f"===={sx}====")
            for ln in ss.lines:
                if ln.startswith("==") and i.level < 3:
                    new_text.append(f"={ln}=")
                elif not ln and key == "Editions":
                    pass
                else:
                    new_text.append(ln)
        i.subsections = {}
    items[0].lines = new_text
    items[0].level = 3
    items[0].name = kx
    items[0].header_line = f"==={kx}==="
    return items[0]


def clean(s):
    return s.replace("'", "").replace('"', '').replace("#", '')


def simplify(s):
    z = s.replace("&#34;", '"').replace("&#39;", "'").replace("–", "-").replace("—", "-").replace("&mdash;", "-").replace("&ndash;", "-").replace("&hellip;", "...").replace("…", "...").split(" (")[0]
    z = re.sub("<br ?/?>", " ", z)
    return z.replace(" : ", ": ").replace("  ", " ").replace("#", "").strip()


def equals_or_starts_with(s, t):
    return s == t or s.startswith(t) or t.startswith(s) or s.endswith(t) or t.endswith(s)


def trim(s, t):
    n = ""
    for c in s:
        if not t.startswith(simplify(f"{n}{c}")):
            break
        n += c
    return n


def prepare_title_format(infobox: str, title: str, text: str, appearances: FullListData, sources: FullListData):
    fmt, top_fmt, text_fmt = None, None, None
    skip = False
    template = None
    if infobox == "Soundtrack" or "{{Conjecture}}" in text or "{{Conjecture|" in text:
        return None, None, None
    elif "(audio drama)" in title or "(radio)" in title:
        fmt = f"''{title.split(' (')[0]}''"
        return fmt, fmt, f"'''{fmt}'''"
    elif title.startswith('"') and title.startswith('"'):
        return title, title, f"'''{title}'''"
    elif title in appearances.target:
        template = appearances.target[title][0].template
        if template == "Film":
            return None, None, None
        if not template:
            fmt = appearances.target[title][0].original.replace(" German audio drama", "")
    elif title in sources.target:
        template = sources.target[title][0].template
        if sources.target[title][0].title_format_text():
            fmt = sources.target[title][0].title_format_text()
            if len(sources.target[title]) > 1 and "department" not in title:
                if len([s for s in sources.target[title] if not s.is_reprint and not s.ref_magazine and s.template == template]) == 1:
                    pass
                elif " Part " in fmt:
                    fmt = re.sub("[:,]? Part (One|Two|Three|Four|I+|[0-9]+).*?$", "", fmt)
                else:
                    fmt = None
                    skip = True
        elif not template:
            fmt = sources.target[title][0].original
        elif sources.target[title][0].text and sources.target[title][0].url and len(sources.target[title]) == 1:
            fmt = sources.target[title][0].text
            if " Part " in fmt:
                fmt = re.sub("[:,]? Part (One|Two|Three|Four|I+|[0-9]+).*?$", "", fmt)
    zx = re.search("\[\[(.*?) \((.*?)\)\|(\"\\1\") \\2]]", fmt or '')   # story/episode audio
    if zx:
        return zx.group(1), zx.group(3), f"'''{zx.group(3)}'''"

    if fmt:
        if "|" in fmt:
            fmt = re.sub("^.*\[\[.*?\|(.*?)]].*?$", "\\1", fmt)
            if '"' in fmt and '"' not in title:
                fmt = fmt.replace('"', '')
        elif "[[" in fmt:
            fmt = re.sub("^\"?('')?\[\[(.*?)]]('')?\"?$", "\\1\\2\\3", fmt)
        if not title.startswith(f"{clean(fmt)} ("):
            if abs(len(clean(fmt).replace("(", "").replace(")", "")) - len(title.replace("(", "").replace(")", ""))) > 5:
                print("Skip:", clean(fmt), clean(title))
                fmt = None

    if not fmt and infobox:
        if infobox in ISSUE:
            fmt = re.sub("^(.*?)( \([0-9]+\))? ([0-9]+)( \(.*?\))?$", "''\\1''\\2 \\3", title)
        elif infobox in ITALICIZE or (fmt and "''" in fmt):
            fmt = "''" + re.sub(" \(.*?\)$", "", title) + "''"

    fmt = fmt or title
    if " (" in title and title.endswith(")") and (" (" not in fmt or title.split(" (")[-1] not in fmt):
        fmt = truncate(fmt, title.split(" (")[0])

    fmt = "<b>" + re.sub(" \(.*?\)$", "", fmt).replace("#", "<n>") + "<b>"
    if fmt.startswith('<b>"') and fmt.endswith('"<b>'):
        fmt = fmt.replace('<b>"', '<q><b>').replace('"<b>', '<b><q>')
    elif infobox in QUOTES and not skip and not (title.startswith('"') and title.endswith('"')) \
            and not (fmt.startswith('"') and fmt.endswith('"')):
        fmt = "<q>" + fmt + "<q>"
    top_fmt = fmt.replace("<q>", "").replace("<b>", "").replace("<n>", "")
    fmt = re.sub("^(.*?) \([0-9]+\) ([0-9]+)", "\\1 \\2", fmt).replace("<n>", "#")

    if template == "EncyclopediaCite" and (title.endswith("(1)") or title.endswith("(2)")):
        fmt = f"<q><b>{title}</b></q>"
    field_fmt = fmt.replace("<q>", '"').replace("<b>", "")
    if "(audio drama)" in title:
        top_fmt = top_fmt.replace(" audio drama", "")
        field_fmt = field_fmt.replace(" audio drama", "")

    text_fmt = fmt.replace("<q>", "\"").replace("<b>", "'''")

    return top_fmt, field_fmt, text_fmt


def truncate(x, y):
    a = ""
    z = '"' if '"' in y else ''
    for c in x:
        if (c == "'" and not a.endswith("'")) or c == '"':
            a += c
        elif a and not y.startswith(f"{a}{c}".replace("''", "").replace('"', z)):
            return a
        else:
            a += c
    return a


def determine_field_format(x: str, title: str, current: Item, types: dict, appearances: FullListData, sources: FullListData, remove_prefix=False):
    ns = _determine_field_format(x, types, appearances, sources)
    if ns:
        if " (" in ns:
            ns = re.sub("'*\[\[([^\n\]\[]*?)( \([0-9]+\))? ([0-9]+)(\|[^\n\]\[]*?)?]]'*", "[[\\1\\2 \\3|''\\1'' \\3]]",
                        ns)
        if remove_prefix and title:
            z, d, e = None, title.rsplit(": ", 1)[0], x.rsplit(": ", 1)[0]
            if d == e:
                z = f"{e}: "
            elif d.rsplit(" ", 1)[-1].isnumeric() and e.rsplit(" ", 1)[0].isnumeric():
                d1, _, d2 = d.rpartition(" ")
                e1, _, e2 = e.rpartition(" ")
                if d1 and d2 and e1 and e2 and d2 == e2:
                    z = f"{e}: "

            if z and "|" in ns:
                a, _, b = ns.partition("|")
                ns = f"{a}|{b.replace(z, '')}"
            elif z:
                ns = re.sub("('')?\[\[(.*?)]]('')?", "[[\\2|\\1" + x.replace(z, "") + "\\3]]", ns)
            elif "|" in ns and current:
                y = ns.rsplit("'' ", 1)[-1].replace("]]", "")
                w = current.original.rsplit("'' ", 1)[-1].replace("]]", "")
                if y == w and not (y.isnumeric() and w.isnumeric()):
                    ns = ns.replace(f"'' {y}", "''")

    return ns


def prepare_quoted_link(z: Item):
    if z.format_text:
        return f"\"[[{z.target}|{z.format_text}]]\""
    elif "(" in z.target:
        return f"\"[[{z.target}|{z.target.split(' (')[0]}]]\""
    else:
        return f"\"[[{z.target}]]\""


def _determine_field_format(x, types: dict, appearances: FullListData, sources: FullListData):
    z = get_listings(x, appearances, sources)
    if not z:
        return None
    elif not z[0].template:
        return z[0].original.replace(" comic adaptation]]", "]]").replace(" comic series]]", "]]")\
            .replace(" booklet series]]", "]]")\
            .replace(" abridged audiobook]]", "]]").replace(" audiobook]]", "]]")
    elif z[0].template in ["DoD", "StoryCite"] or z[0].tv or z[0].template in types.get("Magazine", []):
        return prepare_quoted_link(z[0])
    return None


def is_infobox_field(ln, prev, fields):
    for x in fields:
        if ln.startswith(x) or (not ln.startswith("|") and prev.startswith(x)):
            return x
    return None


def prepare_media_infobox_and_intro(page: Page, results: PageComponents, redirects, disambigs, types,
                                    remap, appearances: FullListData, sources: FullListData):
    top_fmt, field_fmt, text_fmt = prepare_title_format(results.infobox, page.title(), page.get(), appearances, sources)
    # print(page.title(), top_fmt, field_fmt, text_fmt)

    text = fix_redirects(redirects, results.before.strip(), "Intro", disambigs, remap,
                         appearances=appearances.target, sources=sources.target)

    pieces = []
    image = ""
    ct = 0
    publisher_listing = set()
    book_publishers = set()
    infobox_found, infobox_done, title_found = not results.infobox, not results.infobox, False
    prev = ""
    flagged = False
    current = get_listings(page.title(), appearances, sources)
    current = current[0] if current else None
    if "{{Conjecture" in text:
        text_fmt = None
    for ln in text.splitlines():
        if "{{top|" in ln.lower() or "{{top}}" in ln.lower():
            ln = sort_top_template(page.title(), ln, results.infobox in ADD_REF, top_fmt)
        elif not infobox_done:  # infobox field handling
            if results.original_infobox and (f"{{{{{results.original_infobox}".lower() in ln.lower() or f"{{{{{results.original_infobox.replace(' ', '_')}".lower() in ln.lower()):
                infobox_found = True
            elif f"{{{{{results.infobox}".lower() in ln.lower() or f"{{{{{results.infobox.replace(' ', '_')}".lower() in ln.lower():
                infobox_found = True
            elif ln.startswith("|"):
                media_field = is_infobox_field(ln, prev, MEDIA_FIELDS)
                if ln.startswith("|season="):
                    ln = re.sub("season=\[\[(.*? Season )(One|Two|Three|Four|Five|Six|Seven|[0-9]+)\|(?!\\2).*?]]", "season=[[\\1\\2|\\2]]", ln)
                elif media_field:
                    x = re.search("^((\|[a-z ]+=)?\*?)'*\[\[(.*?)(\|'*(.*?)'*)?]]'*", ln)
                    if x:
                        ns = determine_field_format(x.group(3), page.title(), current, types, appearances, sources, media_field in PREV_OR_NEXT)
                        if ns:
                            ln = ln.replace(x.group(0), f"{x.group(1)}{ns}")
                elif ln.startswith("|title=") and field_fmt:
                    if ("''" in field_fmt and "''" not in ln) or ("''" in ln and "''" not in field_fmt) or f"|title={simplify(field_fmt)}" != simplify(ln) or (ln == f"|title=\"{field_fmt}\"" and '"' not in field_fmt):
                        ln = f"|title={field_fmt}"
                elif ln.startswith("|image="):
                    x = re.search("\|image=\[*([Ff]ile:.*?)[|\n\]]", ln)
                    if x:
                        image = x.group(1).replace("file:", "File").replace(" ", "_")
                prev = ln

            if ln.startswith("|publisher=") or prev.startswith("|publisher="):
                x = re.search("(\|publisher=\*|\*)\[\[(.*?)(\|.*?)?]]", ln)
                if x and "Disney" in x.group(1):
                    book_publishers.add("Disney")
                elif x and "Random House" in x.group(1):
                    book_publishers.update({"PenguinBooks", "RandomHouseOld", "PenguinRandomHouse", "RandomHouseBooks"})

            if infobox_found:
                ct += (ln.count("{") - ln.count("}"))
                infobox_done = ct == 0

            if results.infobox in PUBLISHERS:
                if "{{Marvel|url=comics/" in ln or "{{DarkHorse|url=Comics/" in ln or "{{IDW|url=product/" in ln:
                    x = re.search("\{\{(DarkHorse|Marvel|IDW)\|url=((product/|[Cc]omics/(?!Preview)).*)\|.*?}}", ln)
                    if x:
                        publisher_listing.add((x[0], x[1], x[2]))

        # introduction handling
        elif not title_found and text_fmt and text_fmt in ln and not f"'{text_fmt}'" in ln:
            title_found = True
        elif not title_found and text_fmt and ("'''" in ln or simplify(page.title()) in ln):
            ft = False
            if ln.count("'''") >= 2:
                for x, y in re.findall("(\"?'''+\"?(.*?)\"?'''+,?\"?)", ln):
                    if equals_or_starts_with(simplify(y.replace('"', '').replace("''", "")).lower(), simplify(page.title().replace('"', '').replace("''", "")).lower()) and "[[" not in y:
                        if x.replace(',"', '"') != text_fmt:
                            ln = ln.replace(x, text_fmt)
                        ft = True
                        break
                if not ft and re.search("'''''.*?'''.*?'' ", ln):
                    ln = re.sub("'''.*?'''.*?'' ", f"{text_fmt} ", ln)
                    ft = True
                if not ft and re.search("^ ?\"?''''*\"?.*?\"?''''*\" ", ln):
                    ln = re.sub("^ ?\"?''''*\"?.*?\"?''''*\" ", f"{text_fmt} ", ln)
                    ft = True
                if not ft:
                    print(f"Multiple bolded titles in intro, but no close match; cannot replace title with {text_fmt}")
                    if not flagged:
                        if "IntroMissingTitle" not in ln:
                            ln = "{{IntroMissingTitle}} " + ln.strip()
                        flagged = True
            if ft or flagged:
                pass
            elif re.search("\"?'''+\"?(.*?)\"?'''+\"?", ln):
                ln = re.sub("\"?'''+\"?(.*?)\"?'''+\"?", text_fmt, ln)
            else:
                z = re.search("\"(.*?)\"", re.sub("<ref name=\".*?\"(>.*?</ref>| ?/>)", "", ln))
                if z and simplify(page.title()) in z.group(1):
                    ln = ln.replace(z.group(0), text_fmt)
            title_found = True

        multiple_and_redlink = "{{multiple" in ln.lower() and ("|redlink|" in ln or "|redlink}}" in ln)
        if multiple_and_redlink or "{{redlink" in ln.lower():
            count = get_redlink_count(page)
            if count <= 5:
                print(f"{page.title()} has {count} redlinks; removing Redlink template")
                if multiple_and_redlink:
                    ln = re.sub("\|redlink(?=(\||}}))", "", ln)
                else:
                    ln = re.sub("\{\{[Rr]edlink.*?}}", "", ln)
                if not ln.strip():
                    continue

        pieces.append(ln)

    for p, template, url in publisher_listing:
        if any(url == o.url for o in results.links.items):
            continue
        print(f"Found publisher listing: {p} ({url})")
        tz = re.search("\|text=(.*?)(\|.*?)?}}", p)
        results.links.items.append(Item(p, "Publisher", False, template=template, url=url, text=tz.group(1) if tz else None))
    if book_publishers:
        for x in results.links.items:
            if x.template in book_publishers and is_commercial(x):
                x.mark_as_publisher()
    elif results.infobox == "VideoGame" and ("Category:Web-based" in page.get() or " web-based games" in page.get()):
        for x in results.links.items:
            if x.template == "LEGOWeb" and "games/" in x.url:
                x.mark_as_publisher()
            elif "domain=games" in x.original:
                x.mark_as_publisher()

    if results.stub:
        pieces.append("")
        pieces.append(results.stub)
    add_cover_gallery(results.sections, results.cover_images, image)

    return pieces


def get_redlink_count(page: Page):
    count = 0
    for x in page.linkedPages():
        if not x.exists():
            count += 1
    return count

# TODO: split Appearances subsections by length
# TODO: handle multi-issue parents
# TODO: use Masterlist formatting for Contents sections
# TODO: Fix redirects in the Contents section without preserving the original pipelink, UNLESS it's a department
# TODO: convert "Introduction" to a Contents bullet

# TODO - Advanced
# TODO: parse and standardize ISBN lines in Editions
# TODO: build prettytable for issues sections?
# TODO: flag release date reference with Amazon, Previews, etc.
# TODO: parse Editions and sort ExL publisher listings by that order
# TODO: load comic magazines and add to Collections
