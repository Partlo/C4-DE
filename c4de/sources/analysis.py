import codecs
import re
import traceback
from datetime import datetime, timedelta

from pywikibot import Page, Category, showDiff
from typing import List, Tuple, Union, Dict

from c4de.sources.determine import extract_item, determine_id_for_item, convert_issue_to_template, PARAN
from c4de.sources.engine import AUDIOBOOK_MAPPING
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, AnalysisResults, SectionComponents, \
    SectionItemIds, FinishedSection
from c4de.sources.infoboxer import handle_infobox_on_page
from c4de.common import error_log, is_redirect, build_redirects, fix_redirects

KEEP_TEMPLATES = ["TCWA", "CalendarCite"]
PRODUCTS = ["LEGOWebCite", "Marvel", "DarkHorse", "FFGweb", "AMGweb", "Unlimitedweb"]
DO_NOT_MOVE = ["TCWA", "GEAttr", "DatapadCite"]
LIST_AT_START = ["Star Wars: Galactic Defense", "Star Wars: Force Arena"]
INDEX_AND_CATS = ["{{imagecat", "{{mediacat", "{{indexpage", "{{wq", "{{incomplete", "{{quote", "<div style=",
                  "set in '''bold'''", "{{cleanup", "{{more"]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"],
    "Star Wars: The Essential Atlas Online Companion": ["''[[Star Wars: The Essential Atlas Online Companion]]''"]
}


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
        x = re.split("(==Notes? and references|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:)", after, 1)
        if x and len(x) == 3:
            return section + x[0], x[1] + x[2]
    return section, after


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("referene", "reference"), ("Note and references", "Notes and references"),
    ("Notes and reference=", "Notes and references="), ("==References==", "==Notes and references=="),
    ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"), ("{{MO}}", "{{Mo}}"),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("DisneyPlusYT", "DisneyPlusYouTube"), ("<br>", "<br />"),
    ("Youtube", "YouTube"), ("{{Shortstory", "{{StoryCite"), ("{{Scrollbox", "{{Scroll_box"), ("{{scrollbox", "{{Scroll_box")
]


def initial_cleanup(target: Page, all_infoboxes):
    before = target.get(force=True)
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(
            "(]]|}})(\{+ ?(1st[A-z]*|[A-z][od]|[Ll]n|[Uu]n\|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[|}])",
            "\\1 \\2", before)
    if all_infoboxes and not target.title().startswith("User:"):
        before = handle_infobox_on_page(before, target, all_infoboxes)
    before = re.sub("(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub("({{[Ss]croll[_ ]box\|)\*", "{{Scroll_box|\n*", before)
    before = re.sub("([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub("=+'*Non-canonical (appearances|sources)'*=+", "===Non-canon \\1===", before)
    before = re.sub("\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub("^(.*?)[ ]+\n", "\\1\n", before)
    before = re.sub("\*[ ]+([A-z0-9'\[{])", "*\\1", before)
    before = re.sub("\{\{[Cc]ite[_ ]web", "{{WebCite", before)
    before = re.sub("<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)
    before = re.sub("([A-z'0-9\]]+) [ ]+([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub("\|image=(File:)?([A-Z0-9 _]+\..+)\n", "|image=[[File:\\2]]", before)
    before = re.sub("(\|image=\[\[File:[^\n\]]+?)\|.*?]]", "\\1]]", before)
    before = re.sub("\"/>", "\" />", before).replace("<nowiki>|</nowiki>", "&#124;")
    before = re.sub("<small>\((.*?)\)</small>", "{{C|\\1}}", before)
    before = re.sub("([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub("\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub("\{\{(Facebook|Twitter|Instagram|Discord)Cite", "{{\\1", before)
    before = re.sub("== ?Sources ?==\n\{\{[Rr]eflist", "==Sources==\n{{Reflist", before)
    before = re.sub("(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
    before = re.sub("\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub("\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)
    before = re.sub("(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)
    before = re.sub("\*('*\[\[(.*?)]]'*)[^\n\[\]]*(and|\|) '*\[\[(Star Wars: )?\\2( \(.*?\)| audio drama)(\|.*?)?]]", "*\\1\n*[[\\4\\2\\5]]", before)
    before = re.sub("(\{\{.*?\|url=[^|}\n]+)\|\|text=", "\\1|text=", before)
    before = re.sub("\*\{\{\{([A-Z])", "*{{\\1", before)

    if "{{Blog|" in before:
        before = re.sub("(\{\{Blog\|(official=true\|)?[^|\n}\]]+?\|[^|\n}\]]+?\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup)).*?)(\|(?!(archive|date|nolive|nobackup)).*?)(\|.*?)?}}",
                        "\\1\\6}}", before)
    if "{{SOTE" in before:
        before = re.sub("\{\{SOTE(\|.*?)?}}", "{{Topps|set=1996 Topps Star Wars: Shadows of the Empire|stext=1996 Topps ''Star Wars: Shadows of the Empire''\\1}}", before)
    if "|year=" in before:
        before = re.sub("(\{\{[A-z]+)\|([0-9]+)\|(year=[0-9]+)", "\\1|\\3|\\2", before)
    if "VisionsCite" in before:
        before = re.sub("(\{\{VisionsCite\|.*?focus)=(?!1).*?(\|.*?)?}}", "\\1=1\\2}}", before)
        before = re.sub("(\{\{VisionsCite.*?}}) \{\{[Aa]mbig}}", "\\1", before)
    if "simultaneous with" in before:
        before = re.sub("<small>\(First appeared(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
        before = re.sub("<small>\(First mentioned(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
    if "{{Hunters|url=arena-news" in before:
        before = re.sub("\{\{Hunters\|url=arena-news/(.*?)/?\|", "{{ArenaNews|url=\\1|", before)
    if "web.archive" in before:
        before = re.sub("(?<!\[)\[https?://(.*?) (.*?)] (\(|\{\{C\|)\[http.*?web.archive.org/web/([0-9]+)/https?://.*?\\1.*?][)}]+", "{{WebCite|url=https://\\1|text=\\2|archivedate=\\4}}", before)
    if "width=100%" in before:
        before = re.sub("(\{\{[Ss]croll[ _]box(\n?\|.*?)?)\n?\|width=100%", "\\1", before)
    if "{{BanthaCite|issue=" in before:
        before = re.sub("\{\{BanthaCite\|issue=([0-9]+)}}", "[[Bantha Tracks \\1|''Bantha Tracks'' \\1]]", before)
    if "{{Disney|books|" in before:
        before = re.sub("\{\{Disney\|books\|(.*?)\|", "{{Disney|subdomain=books|url=\\1|text=", before)
    if "w:c:" in before.lower():
        before = re.sub("\[\[:?[Ww]:c:(.*?):(.*?)\|(.*?)]] on .*?w:c:\\1\|(.*?)]]", "{{Interwiki|\\1|\\4|\\2|\\3}}", before)

    for (x, y) in REPLACEMENTS:
        before = before.replace(x, y)

    while "== " in before or " ==" in before:
        before = before.replace("== ", "==").replace(" ==", "==")
    if "{{C|unlicensed}}" in before:
        before = re.sub("( {{[Cc]\|[Uu]nlicensed}})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub("\{\{[Mm]entioned[ _]only\|?}}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    return before


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


def build_page_components(target: Page, types: dict, disambigs: list, appearances: FullListData, sources: FullListData, remap: dict,
                          all_infoboxes, handle_references=False, log=True) -> Tuple[PageComponents, list, dict]:
    before = initial_cleanup(target, all_infoboxes)
    redirects = build_redirects(target)

    canon = False
    real = False
    non_canon = False
    app_mode = BY_INDEX
    for c in target.categories():
        if "legends articles" in c.title().lower():
            app_mode = UNCHANGED
        elif "canon articles" in c.title().lower():
            canon = True
        elif "Non-canon Legends articles" in c.title() or "Non-canon articles" in c.title():
            non_canon = True
        elif "Real-world articles" in c.title():
            real = True
            if re.search("\{\{Top\|(.*?\|)?(dotj|tor|thr|fotj|rote|aor|tnr|rofo|cnjo|can|ncc)(\|.*?)?}}", target.get()):
                canon = True
            elif re.search("\{\{Top\|(.*?\|)?(pre|btr|old|imp|reb|new|njo|lgc|inf|ncl|leg)(\|.*?)?}}", target.get()):
                app_mode = UNCHANGED
    if target.title().startswith("User:") and "{{Top|legends=" in target.get():
        canon = True
        app_mode = BY_INDEX
    results = PageComponents(before, canon, non_canon, real, app_mode)

    unknown = []
    final = ""

    x = re.split("(\{\{DEFAULTSORT|\[\[[Cc]ategory:)", before, 1)
    if x:
        before = x[0]
        final = "".join(x[1:])

    if "==External links==" in before:
        before, external_links = before.rsplit("==External links==", 1)
        if external_links:
            external_links, after = split_section_pieces(external_links)
            before, after, final = move_interlang(before, after, final)
            external_links = fix_redirects(redirects, external_links, None, disambigs, remap)
            results.links = parse_section(external_links, types, False, unknown, after, log, "Links")

        x = re.split("(==Notes and references|\{\{[R]eflist)", before, 1)
        if x:
            before = x[0]
            results.links.before = "".join(x[1:])

    before, _, final = move_interlang(before, "", final)
    x = re.split("(==Notes and references|\{\{[Rr]eflist)", before, 1)
    if x:
        before = x[0]
        new_final = "".join(x[1:])
        if results.links:
            results.links.before = f"{new_final}\n{results.links.before}".strip()
        else:
            final = f"{new_final}\n{final}".strip()

    if "===Non-canon sources===" in before:
        before, nc_sources_section = before.rsplit("===Non-canon sources===", 1)
        if nc_sources_section:
            nc_sources_section, after = split_section_pieces(nc_sources_section)
            before, after, final = move_interlang(before, after, final)
            nc_sources_section = fix_redirects(redirects, nc_sources_section, "Non-canon sources", disambigs, remap)
            results.ncs = parse_section(nc_sources_section, types, False, unknown, after, log, "NC Sources")
            if results.ncs and results.ncs.after.startswith("==Behind the scenes=="):
                before += f"\n{results.ncs.after}"
                results.ncs.after = ""
            if log:
                print(f"Non-Canon Sources: {len(results.ncs.items)} --> {len(set(i.unique_id() for i in results.ncs.items))}")

    if "==Sources==" in before:
        before, sources_section = before.rsplit("==Sources==", 1)
        if sources_section:
            sources_section, after = split_section_pieces(sources_section)
            before, after, final = move_interlang(before, after, final)
            sources_section = fix_redirects(redirects, sources_section, "Sources", disambigs, remap)
            results.src = parse_section(sources_section, types, False, unknown, after, log, "Sources")
            if results.src and results.src.after.startswith("==Behind the scenes=="):
                before += f"\n{results.src.after}"
                results.src.after = ""
            if log:
                print(f"Sources: {len(results.src.items)} --> {len(set(i.unique_id() for i in results.src.items))}")

    if "===Non-canon appearances===" in before:
        before, nc_app_section = before.rsplit("===Non-canon appearances===", 1)
        if nc_app_section:
            nc_app_section, after = split_section_pieces(nc_app_section)
            before, after, final = move_interlang(before, after, final)
            nc_app_section = fix_redirects(redirects, nc_app_section, "Non-canon appearances", disambigs, remap)
            results.nca = parse_section(nc_app_section, types, True, unknown, after, log, "NC Appearances")
            if results.nca and results.nca.after.startswith("==Behind the scenes=="):
                before += f"\n{results.nca.after}"
                results.nca.after = ""
            if log:
                print(f"Non-Canon Appearances: {len(results.nca.items)} --> {len(set(i.unique_id() for i in results.nca.items))}")

    if "==Appearances==" in before and not real and "{{App\n" not in before and "{{app\n" not in before and "{{App|" not in before and "{{app|" not in before:
        before, app_section = before.rsplit("==Appearances==", 1)
        if app_section:
            app_section, after = split_section_pieces(app_section)
            before, after, final = move_interlang(before, after, final)
            app_section = fix_redirects(redirects, app_section, "Appearances", disambigs, remap)
            results.apps = parse_section(app_section, types, True, unknown, after, log, "Appearances")
            if results.apps and results.apps.after.startswith("==Behind the scenes=="):
                before += f"\n{results.apps.after}"
                results.apps.after = ""
            if log:
                print(f"Appearances: {len(results.apps.items)} --> {len(set(i.unique_id() for i in results.apps.items))}")

    results.before = before
    results.final = final
    if handle_references:
        results.before = analyze_body(target, results.before, types, appearances, sources, remap, disambigs, redirects, canon, log)
    return results, unknown, redirects


def parse_section(section: str, types: dict, is_appearances: bool, unknown: list, after: str, log, name="Target") -> SectionComponents:
    """ Parses an article's Appearances, Non-canon appearances, Sources, or External Links section, extracting an Item
    data object for each entry in the list. Also returns any preceding/trailing extra lines, such as scrollboxes. """

    external = name == "Links"
    data = []
    unique_ids = {}
    other1, other2, extra = [], [], []
    start = True
    succession_box = False
    scroll_box = False
    cs = 0
    section = re.sub("({{CardGameSet\|set=.*?)\n\|cards=", "\\1|cards=\n", section)
    section = re.sub("'*\[\[Star Wars Miniatures]]'*: '*\[\[(.*?)(\|.*?)?]]'*", "{{SWMiniCite|set=\\1}}", section)
    section = re.sub("(?<!Hamm) \((as .*?)\)", " {{C|\\1}}", section)
    section = section.replace("]]{{Mediacat", "]]\n{{Mediacat")
    for s in section.splitlines():
        if succession_box or "{{more" in s.lower():
            other2.append(s)
            continue
        if "CardGameSet" in s:
            s = re.sub("{{CardGameSet\|(set=)?.*?\|cards=", "", s)
            cs += 1
        if s.strip().startswith("<!-") or s.strip().startswith("*<!-"):
            s = re.sub("<!--.*?-->", "", s)
        if any(x in s.lower() for x in INDEX_AND_CATS):
            other1.append(s)
            continue

        if s.strip().startswith("*"):
            start = False
            x = handle_valid_line(s, is_appearances, log, types, data, [] if external else other2, unknown, unique_ids, False, name)
            if not x and external:
                z = Item(s.strip(), "Basic", False)
                if is_official_link(z):
                    z.mode = "Official"
                print(z.mode, z.original)
                data.append(z)

        elif "{{scroll_box" in s.lower() or "{{scroll box" in s.lower():
            scroll_box = True
            other1.append(s)
        elif scroll_box and (s.startswith("|height=") or s.startswith("|content=")):
            other1.append(s)
        elif "{{start_box" in s.lower() or "{{start box" in s.lower() or "{{interlang" in s.lower():
            succession_box = True
            other2.append(s)
        elif s == "}}":
            if cs > 0:
                cs = 0
        elif re.match("^<!--.*?-->$", s):
            continue
        elif s.strip():
            if not data and not re.search("^[{\[]+([Ii]ncomplete|[Cc]leanup|[Ss]croll|[Mm]ore[_ ]|[Ff]ile:)", s.strip()):
                x = handle_valid_line(f"*{s}", is_appearances, log, types, data, [] if external else other2, unknown, unique_ids, True, name)
                if x:
                    start = False
                    continue
            elif "{{" in s:
                x = re.search("\{\{(.*?)(\|.*?)?}}", s)
                if x and is_nav_or_date_template(x.group(1), types):
                    extra.append(s)
                    continue
            if start:
                other1.append(s)
            else:
                other2.append(s)
    return SectionComponents(data, other1, other2, "\n".join([*extra, after]))


def handle_valid_line(s, is_appearances: bool, log: bool, types, data, other2, unknown, unique_ids, attempt=False, name="Target"):
    if s.endswith("}}}}") and s.count("{{") < s.count("}}"):
        s = s[:-2]
    z = s.replace("&ndash;", '–').replace('&mdash;', '—').strip()
    while z.startswith("*"):
        z = z[1:].strip()
    z = re.sub("(\{\{InsiderCite\|[0-9]{2}\|)Ask Lobot.*?}}", "\\1Star Wars Q&A}}", z)
    if "SWGTCG" in s and "scenario" in z:
        z = re.sub("(\{\{SWGTCG.*?)}} \{\{C\|(.*?scenario)}}", "\\1|scenario=\\2}}", z)

    x2 = re.search("\{\{[Aa]b\|.*?}}", z)
    ab = x2.group(0) if x2 else ''
    if ab:
        z = z.replace(ab, "").replace("  ", " ").strip()
    x1 = re.search(
        '( ?(<ref.*?>)?(<small>)? ?\{+ ?(1st[A-z]*|V?[A-z][od]|[Ff]act|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}].*?$)',
        z)
    extra = x1.group(1) if x1 else ''
    if extra:
        z = z.replace(extra, '').strip()
    bold = "'''" in z and re.search("'''(?!s)", z)

    zs = [z]
    if "/" in z and ("{{YJA|" in z or "{{All-Stars|" in z):
        x = re.search("^(.*?\{\{(YJA|All-Stars)\|)(.*?)/(.*?)(}}.*?)$", z)
        if x:
            if log:
                print(f"Splitting multi-entry line: {s}")
            zs = [f"{x.group(1)}{x.group(3)}{x.group(5)}", f"{x.group(1)}{x.group(4)}{x.group(5)}"]

    y = re.search("[\"']*?\[\[(?P<p>.*?)(\|.*?)?]][\"']*? ?n?o?v?e?l? ?(and|\|) ?['\"]*\[\[(?P<t>.*?)(\|.*?)?]]['\"]*?", z)
    if y and "{{TFU|" not in z:
        if log:
            print(f"Splitting multi-entry line: {s}")
        zs = [y.groupdict()['p'], y.groupdict()['t']]
    y = re.search("(?<!\[)\[(https?.*?) (.*?)] (at|on|in) (the )?(\[https?.*? .*?])", z)
    if y:
        zs = [f"{{{{WebCite|url={y.group(1)}|text={y.group(2)}|work={y.group(5)}}}}}"]

    found = False
    for y in zs:
        t = extract_item(convert_issue_to_template(y), is_appearances, name, types)
        if t:
            if name == "Links":
                print(t.template, t.mode, t.original)
            if is_official_link(t):
                t.mode = "Official"
            found = True
            data.append(t)
            t.extra = extra.strip()
            t.ab = ab
            t.bold = bold
            ex = re.search("<!-- ?(Exception|Override):? ?([0-9X-]+)? ?-->", s)
            if ex:
                t.override = ex.group(1)
                t.override_date = ex.group(2)
            unique_ids[t.unique_id()] = t
    if not found:
        print("Not found:", s)
        if not data and s.count("[") == 0 and s.count("]") == 0:
            pass
        elif "audiobook" not in s and not attempt:
            unknown.append(s)
            other2.append(s)
        if log and name != "Links":
            print(f"Unknown: {s}")
    return found


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, disambigs, redirects, canon, log: bool):
    references = [(i[0], i[2]) for i in re.findall("(<ref name=((?!<ref).)*?[^/]>(((?!<ref).)*?)</ref>)", text)]
    references += [(i[0], i[1]) for i in re.findall("(<ref>(((?!<ref).)*?)</ref>)", text)]
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, disambigs, redirects, canon, log)
    return new_text


REF_REPLACEMENTS = [("film]] film", "film]]"), ("|reprint=yes", ""), ("|reprint=1", ""), ("|audiobook=yes", ""), ("|audiobook=1", "")]


def handle_reference(full_ref, ref, page: Page, new_text, types, appearances: FullListData, sources: FullListData,
                     remap: dict, disambigs: dict, redirects, canon, log: bool):
    try:
        new_ref = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", ref)
        x = re.search(",? (page|pg\.?|p\.|chapters?|ch\.) ([0-9-]+)", new_ref)
        if x:
            print(f"Removed page/chapter numbers from reference: \"{x.group(0)}\" -> \"{new_ref}\"")
            new_ref = new_ref.replace(x.group(0), "")
        new_ref = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?]]'* (<small>)?\{\{C\|'*\[\[(.*?)]]'* ?(-|&[mn]dash;|:) ?([^\[}\r\n]+?)'*}}(</small>)?",
                   "{{StarshipsVehiclesCite|\\1|\\4|\\6}}", new_ref)
        new_ref = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?]]'* (<small>)?\{\{C\|('*\[\[(.*?)]]'* ?(-|&[mn]dash;|:) ?(.*?)'*)}}(</small>)?",
                   "{{StarshipsVehiclesCite|\\1|multiple=\\4}}", new_ref)
        new_ref = convert_issue_to_template(new_ref)
        links = re.findall("(['\"]*\[\[(?![Ww]:c:).*?(\|.*?)?]]['\"]*)", new_ref)
        templates = re.findall("(\{\{[^{}\n]+}})", new_ref)
        templates += re.findall("(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)
        templates += re.findall("(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)

        new_links = []
        found = []
        for link in links:
            x = extract_item(link[0], False, "reference", types)
            if x:
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique, sources.target, remap, canon, log)
                if o and not o.use_original_text and o.replace_references:
                    found.append(o)
                    if o.master.template and not x.template and x.target and not re.search("^['\"]*\[\[" + x.target + "(\|.*?)?]]['\"]*$", new_ref):
                        print(f"Skipping {link[0]} due to extraneous text")
                    elif link[0].startswith('"') and link[0].startswith('"') and (len(ref) - len(link[0])) > 5:
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
                        if "TODO" in o.master.original:
                            print(link[0], x.full_id(), o.master.original, o.current.original)
                        if link[0] != o.master.original:
                            new_links.append((link[0], o.master.original))
                    elif o.current.original_target and re.search("^['\"]*\[\[" + o.current.original_target.replace("(", "\(").replace(")", "\)") + "(\|.*?)?]]['\"]*", new_ref):
                        if "TODO" in o.master.original:
                            print(link[0], x.full_id(), o.master.original, o.current.original)
                        if link[0] != o.master.original:
                            new_links.append((link[0], o.master.original))
                elif o:
                    found.append(o)
                elif x.mode == "Basic":
                    new_links.append((link[0], prepare_basic_url(x)))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, re.sub("\|reprint=.*?(\|.*?)?}}", "\\1}}", re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", ni)))

        new_templates = []
        for t in templates:
            if t == "{{'s}}" or "{{TORcite" in t or "{{SWG" in t or t.startswith("{{C|") or t.startswith("{{Blogspot") or t.startswith("{{Cite"):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and is_nav_or_date_template(x.template, types):
                    continue
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique,
                                          sources.target, {}, canon, log)
                if o and not o.use_original_text and t != o.master.original:
                    found.append(o)
                    ex = []
                    if "|author=" in t:
                        ex += [r[0] for r in re.findall("(\|author=(\[\[.*?\|.*?]])?.*?)[|}]", t)]
                    if "|date=" in t:
                        ex += re.findall("(\|date=.*?)[|}]", t)
                    if "|quote=" in t:
                        ex += re.findall("(\|quote=.*?)[|}]", t)
                    if "TODO" in o.master.original:
                        print(t, x.full_id(), o.master.original, o.current.original)
                    new_templates.append((t, o, ex))
                elif o:
                    found.append(o)

        for ot, ni, extra in new_templates:
            z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", ni.master.original)
            if ni.current.subset:
                z = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(stext=.*?\|)?)", f"\\1subset={ni.current.subset}|", z)
            if extra:
                z = z[:-2] + "".join(extra) + "}}"
            if "|d=y" in ni.current.original:
                z = z[:-2] + "|d=y}}"
            new_ref = new_ref.replace(ot, z.replace("–", "&ndash;").replace("—", "&mdash;"))

        new_ref = fix_redirects(redirects, new_ref, "Reference", disambigs, remap)
        final_ref = re.sub("\{\{[Aa]b\|.*?}}", "", full_ref.replace(ref, new_ref))
        if "<ref>" in final_ref:
            if len(found) == 1 and found[0].master.target:
                final_ref = final_ref.replace("<ref>", f"<ref name=\"{found[0].master.target}\">")
            elif len(found) == 1:
                print(f"Cannot fix nameless reference to {found[0].master.target}")
            else:
                print(f"Cannot fix nameless reference, due to {len(found)} links found in reference: {final_ref}")
        for r, x in REF_REPLACEMENTS:
            final_ref = final_ref.replace(r, x)
        if "series series" in final_ref:
            final_ref = re.sub(" series( series)+", " series", final_ref)
        new_text = new_text.replace(full_ref, final_ref)
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return do_final_replacements(new_text, True)


def check_format_text(o: ItemId, x: Item):
    if o.current.followed_redirect and o.current.original_target:
        return _check_format_text(o.current.original_target, x.format_text)
    return _check_format_text(o.master.target, x.format_text)


def _check_format_text(t, y):
    return "(" in t and (t.split("(")[0].strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel") and
                         t.replace("(", "").replace(")", "").strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel"))


def analyze_section_results(target: Page, results: PageComponents, disambigs: list, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool, include_date: bool,
                            collapse_audiobooks: bool, checked: list, log) \
        -> Tuple[FinishedSection, FinishedSection, FinishedSection, FinishedSection, FinishedSection, list, list, list, list, list, AnalysisResults]:
    both_continuities = appearances.both_continuities.union(sources.both_continuities)
    dates = []
    unknown_apps, unknown_src = [], []
    new_apps = build_item_ids_for_section(target, results.real, "Appearances", results.apps.items, appearances, sources, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    new_nca = build_item_ids_for_section(target, results.real, "Non-canon appearances", results.nca.items, appearances, sources, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    new_src = build_item_ids_for_section(target, results.real, "Sources", results.src.items, sources, appearances, remap, unknown_src, results.canon, [], collapse_audiobooks, log)
    new_ncs = build_item_ids_for_section(target, results.real, "Non-canon sources", results.ncs.items, sources, appearances, remap, unknown_src, results.canon, [], collapse_audiobooks, log)

    # move non-canon items to the appropriate lists, and swap to non-canon only if no canon entries
    if new_apps.non_canon:
        if log:
            print(f"Moving {len(new_apps.non_canon)} non-canon appearances to the Non-canon Appearances")
        new_nca.found += new_apps.non_canon
    if new_src.non_canon:
        new_ncs.found += new_src.non_canon

    results.links.items = [*new_apps.links, *new_nca.links, *new_src.links, *new_ncs.links, *results.links.items]
    new_links, unknown_links, wrong = build_new_external_links(target, results.links.items, sources, appearances, remap, results.canon, log)

    if new_apps.wrong or new_nca.wrong:
        if log:
            print(f"Moving {len(new_apps.wrong) + len(new_nca.wrong)} sources from Appearances to Sources")
        for x in new_apps.wrong:
            x.current.extra = re.sub("\{\{1st([|}])", "{{1stm\\1", x.current.extra)
            new_src.found.append(x)
        if not new_apps.found:
            results.src.preceding += results.apps.preceding
            results.src.trailing += results.apps.trailing
            results.src.after += results.apps.after
        for x in new_nca.wrong:
            x.current.extra = re.sub("\{\{1st([|}])", "{{1stm\\1", x.current.extra)
            (new_ncs if new_ncs.found else new_src).found.append(x)
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

    if wrong:
        if log:
            print(f"Moving {len(wrong)} misclassified sources from External Links to Sources")
        new_src.found += wrong

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
        elif a.current.target and "audiobook)" in a.current.target:
            continue
        audiobooks = find_matching_audiobook(a, app_targets, appearances, abridged)
        audiobooks += find_matching_parent_audiobook(a, app_targets, appearances)
        for b in audiobooks:
            if b.abridged:
                print(f"Skipping abridged audiobook: {b.target}")
                abridged.append(b.target)
            elif not collapse_audiobooks and (b.parent if b.parent else b.target) not in app_targets:
                print(f"Adding missing audiobook: {b.target} at {i}, {a.current.index}, {a.current.canon_index}, {a.current.legends_index}")
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

    text = target.get()
    disambig_links = []
    for p in target.linkedPages():
        if p.title() in disambigs:
            if f"[[{p.title()}|" in text or f"[[{p.title()}]]" in text:
                disambig_links.append(p.title())

    mismatch = []
    unknown_final = []
    nca_title = "==Appearances==" if results.non_canon and not new_apps.found else "===Non-canon appearances==="
    ncs_title = "==Sources==" if results.non_canon and not new_src.found else "===Non-canon sources==="
    new_apps, final_apps = build_new_section("==Appearances==", new_apps, results.app_mode, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final, collapse_audiobooks)
    new_nca, final_nca = build_new_section(nca_title, new_nca, BY_DATE, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final, collapse_audiobooks)
    new_src, final_sources = build_new_section("==Sources==", new_src, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final, collapse_audiobooks)
    new_ncs, final_ncs = build_new_section(ncs_title, new_ncs, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final, collapse_audiobooks)
    analysis = AnalysisResults(final_apps, final_nca, final_sources, final_ncs, results.canon, abridged, mismatch, disambig_links)
    return new_apps, new_nca, new_src, new_ncs, new_links, dates, unknown_apps, unknown_src, unknown_final, unknown_links, analysis


def match_audiobook_name(a, b):
    return b == f"{a.split('(')[0].strip()} (audiobook)" or b == f"{a.split('(')[0].strip()} (unabridged audiobook)"


def handle_ab_first(a: ItemId, audiobook_date):
    if re.search("\{\{1stID\|[^\[{|]+\|.*?}}", a.current.extra):
        if audiobook_date != a.master.date:
            a.current.extra = re.sub("(\{\{1stID\|[^\[{|]+)\|.*?audiobook.*?}}", "\\1|in book}}", a.current.extra)
        else:
            a.current.extra = re.sub("(\{\{1stID\|[^\[{|]+)\|[^}]*?audiobook.*?}}", "\\1}}", a.current.extra)
    elif re.search("\{\{1stID\|simult=.*?}}", a.current.extra):
        if audiobook_date != a.master.date:
            a.current.extra = re.sub("\{\{1stID\|simult=.*?audiobook.*?}}", "{{1stID|in book}}", a.current.extra)
        else:
            a.current.extra = re.sub("\{\{1stID\|simult=*?audiobook.*?}}", "{{1stID}}", a.current.extra)
    elif "{{1st|" in a.current.extra or "{{1stm|" in a.current.extra or "{{1stp|" in a.current.extra:
        if audiobook_date != a.master.date:
            a.current.extra = re.sub("(\{\{1st[mp]?)\|((?!in book).*?)}}", "\\1|in book and \\2}}", a.current.extra)
        else:
            a.current.extra = re.sub("(\{\{1st[mp]*?)\|[^}]*?audiobook.*?}}", "\\1}}", a.current.extra)
    elif "{{1st" in a.current.extra and audiobook_date != a.master.date:
        a.current.extra = re.sub("(\{\{1st[mp]*?)}}", "\\1|in book}}", a.current.extra)


def is_external_wiki(t):
    return t and (t.lower().startswith("w:c:") or t.lower().startswith("wikipedia:") or t.lower().startswith(":wikipedia:"))


def is_official_link(o: Item):
    return (o and o.mode in ["Basic", "External"] and o.original and "official" in o.original.lower() and
            re.search("official .*?(site|home ?page)", o.original.lower()))


def is_nav_or_date_template(template, types: dict):
    return template.lower().replace("_", " ") in types["Nav"] or template.lower().replace("_", " ") in types["Dates"]


def is_external_link(d: ItemId, o: Item, unknown):
    if not d and o.mode == "Basic":
        unknown.append(o)
        return True
    elif not d and o.original.replace("*", "").startswith("[http"):
        return True
    elif not d and o.url and any(o.url.startswith(f"{s}/") for s in ["people", "person", "leadership", "our-team", "bio", "news/contributor"]):
        o.mode = "Bio"
        return True
    elif o.template == "YouTube" and re.search("YouTube\|channel(name)?=[^|}\n]+\|channel(name)?=[^|}\n]+}}", o.original):
        o.mode = "Profile"
        return True
    elif d and d.master.external:
        o.mode = "Found-External"
        return True
    elif o.template in PRODUCTS and o.url and is_product_page(o.url.lower()):
        o.mode = "Commercial"
        return True
    elif o.template == "SWArchive" and o.url and ("=cargobay" in o.original or "=shop" in o.original):
        o.mode = "Commercial"
        return True
    elif o.template == "Blog" and o.url and "listing=true" in o.url:
        o.override_date = "Target"
        o.date = "Target"
        o.mode = "Profile"
        return True
    elif o.mode == "Social":
        if "||" in o.original or o.template == "LinkedIn":
            o.override_date = "Target"
            o.date = "Target"
            o.mode = "Profile"
        return True
    elif o.mode == "External" or o.mode == "Interwiki" or o.mode == "Commercial" or o.mode == "Profile":
        if o.template == "MobyGames":
            o.override_date = "Target"
            o.date = "Target"
        return True


def is_product_page(u: str):
    return ("/product/" in u or "/products/" in u or "/previews/" in u or u.startswith("book/") or u.startswith("books/") or u.startswith("comics/")) and "subdomain=news" not in u


def handle_card_item(d: ItemId, o: Item, cards: Dict[str, List[ItemId]], found: List[ItemId], wrong: List[ItemId],
                     extra: Dict[str, ItemId], name, log):
    if d.current.card and d.current.card == d.master.card and d.master.has_date():
        found.append(d)
        return
    elif o.template == "ForceCollection":
        found.append(d)
        return

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
        return
    if parent_set not in cards:
        cards[parent_set] = []

    if parent_set and "|stext=" in d.master.original and "|stext=" not in d.current.original:
        x = re.search("(\|stext=.*?)[|}]", d.master.original)
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


def build_item_ids_for_section(page: Page, real, name, original: List[Item], data: FullListData, other: FullListData, remap: dict,
                               unknown: List[Union[str, Item]], canon: bool, checked: list, collapse_audiobooks=True, log=True) -> SectionItemIds:

    found = []
    wrong = []
    links = []
    non_canon = []
    cards = {}
    extra = {}
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

        if d and (o.mode == "Cards" or o.template == "ForceCollection"):
            handle_card_item(d, o, cards, found, wrong, extra, name, log)
        elif is_external_link(d, o, unknown):
            if d:
                o.master_text = d.master.original
            links.append(o)
        elif d and d.current.template in KEEP_TEMPLATES:
            found.append(d)
        elif d and d.from_other_data and "databank" not in (o.extra or '').lower() and d.current.template not in DO_NOT_MOVE \
                and d.current.target != 'Star Wars: Datapad (Galactic Starcruiser)'\
                and not real and not d.master.from_extra:
            if log:
                print(f"({name}) Listed in wrong section: {o.original} -> {d.master.is_appearance} {d.master.full_id()}")
            wrong.append(d)
        elif d and not real and d.master.non_canon and not name.startswith("Non-canon") and d.master.target != "Star Tours: The Adventures Continue" and not page.title().endswith("/LEGO"):
            non_canon.append(d)
        elif "{{Hyperspace" in o.original and name == "Appearances":  # Hyperspace relisting of Appearances entries
            if d and d.master.template == "Hyperspace":
                found.append(d)
            else:
                found.append(ItemId(o, o, True, False))
        elif d and not real and d.master.audiobook and not d.master.abridged and collapse_audiobooks:
            # print(f"Skipping individually-listed audiobook: {d.master.target}")
            continue
        elif d:
            found.append(d)
            if d.by_parent:
                unknown.append(f"Parent: {o.original}")
        elif o.template == "WebCite" or o.template == "WP" or "{{WP" in o.original:
            links.append(o)
        else:
            if log:
                print(f"Cannot find {o.unique_id()}: {o.original}")
            save = True
            if o.is_appearance and o.target and o.target not in checked:
                p = Page(page.site, o.target)
                if p.exists() and not p.isRedirectPage():
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

    return SectionItemIds(name, found, wrong, non_canon, cards, set_ids, links)


def has_month_in_date(x: ItemId):
    return x and x.master and x.master.has_date() and "-XX-XX" not in x.master.date


BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"


def prepare_basic_url(o: Item):
    if re.search("official .*?(site|homepage|page)", o.original.lower()):
        if o.full_url:
            return "Official", f"[{o.full_url} Official website]"
        else:
            return "Official", o.original
    elif o.full_url:
        ad = f"|archivedate={o.archivedate}" if o.archivedate else ""
        u = o.full_url if o.full_url.startswith("http") else f"https://{o.full_url}"
        return "Basic", f"{{{{WebCite|url={u}|text={o.text}{ad}}}}} {o.extra}".strip()
    else:
        return "Basic", o.original


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
            o.mode = "Official"

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

        # if d and o.mode == "Web" and not (o.template in PRODUCTS and o.url and ("/product/" in o.url or "/Previews/" in o.url)):
        #     wrong.append(d)
        #     continue
        if d:
            zn = d.current.original if d.use_original_text else d.master.original
            zn = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"*{zn}")
            if d.current.bold:
                zn = f"'''{zn}'''"
            if d.master.date and d.master.date.startswith("Cancel") and "{{c|cancel" not in zn.lower():
                zn += " {{C|canceled}}"
            if zn.startswith("**"):
                zn = zn[1:]
            zn = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", zn)
            zn = zn.replace("–", "&ndash;").replace("—", "&mdash;")
            z = f"{zn} {d.current.extra}"
            z = z if z.startswith("*") else f"*{z}"
            if z not in done:
                found.append((o.mode, d.master, z))
                done.append(z)
        else:
            if o.template not in ["WP"] and o.mode not in ["Interwiki", "Social", "Profile"]:
                unknown.append(o.original)
            zn = re.sub("\{\{[Ss]eriesListing.*?}} ?", "", o.original)
            z = f"*{zn} {o.extra}".strip()
            if z not in done:
                found.append((o.mode, o, z))
                done.append(z)

    finished = sorted(found, key=lambda a: determine_link_order(a[0], a[1], a[2]), )

    return FinishedSection("==External links==", 0, "\n".join(f[2].strip() for f in finished)), unknown, wrong


def determine_link_order(mode, o: Item, x):
    if not o:
        return -1, None, x
    elif mode == "Official":
        return 1.1, o.date, x
    elif mode == "Bio":
        return 1.2, o.date, x
    elif mode == "Profile":
        return 2, o.date, x
    elif mode == "Commercial":
        return 3, o.date, x
    elif o.template == "WP":
        return 4.1, o.date, x
    elif mode == "Interwiki" or o.template in ["MobyGames", "BFICite", "BGG", "LCCN", "EndorExpress"]:
        return 4.2, o.date, x
    elif o.template in ["SW", "SWArchive", "Blog", "OfficialBlog", "SWBoards"]:
        return 5.1, o.date, x
    elif o.mode == "Social":
        return 5.2, o.date, x
    else:
        return 5.3, o.date, x


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
            if o.master.timeline_index(canon) is None:
                group.append(o)
            elif o.master.index is None:
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

    return new_found, group, missing, source_names


def build_new_section(name, section: SectionItemIds, mode: str, dates: list, canon: bool, include_date: bool, log: bool,
                      use_index: bool, mismatch: list, both_continuities: set, unknown_final: list,
                      collapse_audiobooks: bool) -> Tuple[FinishedSection, List[ItemId]]:
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
                    ot = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
                while ot.count("|subset=") > 1:
                    ot = re.sub("(\|subset=.*?)\1", "\1", ot)
                zt = "*" + d + re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"{ot} {c.current.extra.strip()}").strip()
                ct += zt.count("{")
                ct -= zt.count("}")
                final_items.append(c)
                new_text.append(zt)
            if ct:
                new_text.append("".join("}" for _ in range(ct)))
        else:
            zt = o.current.original if o.use_original_text else o.master.original
            if o.current.subset:
                zt = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(stext=.*?\|)?)", f"\\1subset={o.current.subset}|", zt)
            while zt.count("|subset=") > 1:
                zt = re.sub("(\|subset=.*?)\\1", "\\1", zt)
            zt = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", zt)
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
                    d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|DVD}}}} "
                elif "[[5-Minute Star Wars" in o.master.original or "Trilogy Stories" in o.master.original or \
                        "[[The Clone Wars: Stories" in o.master.original or "[[Life Day Treasury" in o.master.original \
                        or "[[Tales from the " in o.master.original:
                    d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}|short}}}} "
                else:
                    d += f"{{{{SeriesListing{nl if o.master.non_canon else sl}}}}} "
            elif o.current.unknown or o.master.unknown:
                d += f"{{{{UnknownListing{sl}}}}} "

            if d == "<!-- Unknown -->" and "{{Hyperspace" in zt and "/member/fiction" in zt:
                d = ""
            zn = f"*{d}{zt}"
            if zn.startswith("**"):
                zn = zn[1:]
            zn = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", zn)
            zn = zn.replace("–", "&ndash;").replace("—", "&mdash;")
            if o.current.template == "TCW" and "|d=y" in o.current.original and "|d=y" not in zn:
                zn = re.sub("(\{\{TCW\|.*?)}}", "\\1|d=y}}", zn)

            if zn in final_without_extra:
                if log:
                    print(f"Skipping duplicate {zn}")
            else:
                e = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", o.current.extra).strip()
                if not collapse_audiobooks:
                    e = e.replace("|audiobook=1", "")
                elif o.master.ab:
                    e = f"{o.master.ab} {e}".strip()
                if o.master.crp and "{{crp}}" not in e.lower() and "{{crp}}" not in zn.lower():
                    e = "{{Crp}} " + e
                if section.name.startswith("Non-canon"):
                    e = re.sub("\{\{[Nn]cm}}", "{{Mo}}", re.sub("\{\{[Nn]cs?(\|.*?)?}}", "", e))
                if o.master.unlicensed and "{{Un}}" not in e and "{{un}}" not in e:
                    e += " {{Un}}"
                z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", f"{zn} {e}").strip()
                if o.master.date and o.master.date.startswith("Cancel") and "{{c|cancel" not in z.lower():
                    z += " {{C|canceled}}"
                z = z.replace("–", "&ndash;").replace("—", "&mdash;").replace("  ", " ")
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?]]'* (<small>)?\{\{C\|'*\[\[(.*?)]]'* ?(-|&[mn]dash;|:) ?([^\[}\r\n]+?)'*}}(</small>)?",
                           "{{StarshipsVehiclesCite|\\1|\\4|\\6}}", z)
                z = re.sub("'*\[\[Star Wars: The Official Starships & Vehicles Collection ([0-9]+)(\|.*?)?]]'* (<small>)?\{\{C\|('*\[\[(.*?)]]'* ?(-|&[mn]dash;|:) ?(.*?)'*)}}(</small>)?",
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


def find_matching_audiobook(a: ItemId, existing: list, appearances: FullListData, abridged: list):
    if not a.master.target:
        return []
    elif f"{a.master.target} (novelization)" in existing or f"{a.master.target} (novel)" in existing:
        return []
    elif a.master.target.endswith("(short story)"):
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
    if log and items.text:
        print(f"Creating {items.name} section with {len(items.text.splitlines())} items")

    pieces = [items.name] if items.text else []
    if section.before:
        pieces.insert(0, "")
        pieces.insert(0, section.before)
    if items.rows >= 20 and not any("{{scroll" in i.lower() for i in section.preceding):
        pieces.append("{{Scroll_box|content=")

    pieces += section.preceding
    added_media_cat = False
    if media_cat and items.text:
        pieces.append(media_cat)
        added_media_cat = True

    if items.text:
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


def build_final_text(page: Page, results: PageComponents, disambigs: list, remap: dict, redirects: dict,
                     new_apps: FinishedSection, new_nca: FinishedSection, new_sources: FinishedSection,
                     new_ncs: FinishedSection, new_links: FinishedSection, log: bool):
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

    if new_apps.text or results.apps.has_text():
        t, added_media_cat = build_section_from_pieces(results.apps, new_apps, log, media_cat if mc_section_name == new_apps.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_nca.text or results.nca.has_text():
        t, added_media_cat = build_section_from_pieces(results.nca, new_nca, log, media_cat if mc_section_name == new_nca.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_sources.text or results.src.has_text():
        t, added_media_cat = build_section_from_pieces(results.src, new_sources, log, media_cat if mc_section_name == new_sources.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if new_ncs.text or results.ncs.has_text():
        t, added_media_cat = build_section_from_pieces(results.ncs, new_ncs, log, media_cat if mc_section_name == new_ncs.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)

    if "<ref" in results.before and "{{reflist" not in results.original.lower():
        if media_cat:
            pieces.append("==Notes and references==\n" + media_cat + "\n{{Reflist}}\n\n")
        else:
            pieces.append("==Notes and references==\n{{Reflist}}\n\n")

    if new_links.text or results.links.has_text():
        pieces.append("")
        t, added_media_cat = build_section_from_pieces(results.links, new_links, log, None)
        if results.final and "Notes and references" in results.final:
            snip = re.search("(==Notes and references==\n.*?\{\{[Rr]eflist.*?\n\n*)", results.final)
            if snip:
                results.final = results.final.replace(snip.group(1), "")
                pieces.append(f"{snip.group(1)}\n\n")
        pieces.append(t)

    if results.final:
        if "==\n" in results.final and media_cat:
            z = results.final.split("==\n", 1)
            pieces.append(f"{z[0]}==\n{media_cat}\n{z[1]}")
        elif media_cat:
            pieces.append(media_cat + "\n" + results.final)
        else:
            pieces.append(results.final)

    new_txt = sort_categories("\n".join(pieces))
    new_txt = re.sub("(\{\{DEFAULTSORT:.*?}})\n\n+\[\[[Cc]ategory", "\\1\n[[Category", new_txt)
    new_txt = re.sub("(?<![\n=}])\n==", "\n\n==", re.sub("\n\n+", "\n\n", new_txt)).strip()
    new_txt = new_txt.replace("\n\n}}", "\n}}").replace("{{Shortstory|", "{{StoryCite|").replace("\n\n{{More", "\n{{More")

    replace = True
    if re.sub("<!--.*?-->", "", page.get(force=True)) != re.sub("<!--.*?-->", "", new_txt):
        new_txt = fix_redirects(redirects, new_txt, "Body", remap, disambigs)
    return do_final_replacements(new_txt, replace)


def do_final_replacements(new_txt, replace):
    while replace:
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+)&mdash;", "\\1—", new_txt))
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+–[^\[\]|\r\n]+\|[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+—[^\[\]|\r\n]+\|[^\[\]|\r\n]+)&mdash;", "\\1—", new_txt2))
        new_txt2 = re.sub("\[\[(.*?)\|\\1(.*?)]]", "[[\\1]]\\2", new_txt2)
        x = re.search("\[\[([A-Z])(.*?)\|(.\\2)(.*?)]]", new_txt2)
        if x and x.group(3).lower().startswith(x.group(1).lower()):
            new_txt2 = new_txt2.replace(x.group(0), f"[[{x.group(3)}]]{x.group(4)}")
        if "'''s " in new_txt2:
            new_txt2 = re.sub("( ''[^'\n]+'')'s ", "\\1{{'s}} ", new_txt2)
        if "{{1st|" in new_txt2 or "{{1stm|" in new_txt2 or "{{1stID|" in new_txt2 or "{{1stp|" in new_txt2:
            new_txt2 = re.sub("(\[\[(.*?)( \(.*?\))?(\|.*?)?]].*?{{1st[A-z]*?(\|.*?)?\|\[\[\\2 \((.*?audiobook)\)\|).*?]]}}", "\\1\\6]]}}", new_txt2)
            new_txt2 = re.sub("(ook=(.*?)( \(.*?\))?(\|.*?)?}}.*?{{1st[A-z]*?(\|.*?)?\|\[\[\\2 \((.*?audiobook)\)\|).*?]]}}", "\\1\\6]]}}", new_txt2)
        if "{{more" in new_txt2.lower():
            new_txt2 = re.sub("(\{\{[Mm]ore[ _]sources}})\n+}}", "}}\n\\1", new_txt2)
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


def get_analysis_from_page(target: Page, infoboxes: dict, types, disambigs, appearances: FullListData,
                           sources: FullListData, remap: dict, log=True, collapse_audiobooks=True):
    results, unknown, redirects = build_page_components(target, types, disambigs, appearances, sources, remap, infoboxes,False, log)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    analysis = analyze_section_results(target, results, disambigs, appearances, sources, remap, True,
                                       False, collapse_audiobooks, [], log)
    return list(analysis)[-1]


def build_new_text(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                   sources: FullListData, remap: dict, include_date: bool, checked: list, log=True, use_index=True,
                   handle_references=False, collapse_audiobooks=True):
    results, unknown, redirects = build_page_components(target, types, disambigs, appearances, sources, remap, infoboxes, handle_references, log)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    new_apps, new_nca, new_sources, new_ncs, new_links, dates, unknown_apps, unknown_src, unknown_final, unknown_links, analysis = analyze_section_results(
        target, results, disambigs, appearances, sources, remap, use_index, include_date, collapse_audiobooks, checked, log)

    if unknown or unknown_apps or unknown_src or unknown_final or unknown_links:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/sources/unknown.txt", mode="a",
                         encoding="utf-8") as f:
            for x in unknown:
                f.write(u'%s\t%s\n' % (x, target.title()))
            z = set()
            for o in [*unknown_apps, *unknown_src]:
                z.add(o.original if isinstance(o, Item) else o)
            for o in unknown_links:
                z.add(f"Links: {o.original if isinstance(o, Item) else o}")
            for o in unknown_final:
                if isinstance(o, Item) and o.current.original not in z:
                    z.add(f"No Date: {o.current.original}")
                elif not isinstance(o, Item) and o not in z:
                    z.add(f"No Date: {o}")
            if z:
                f.writelines("\n".join([f"{o}\t{target.title()}" for o in z]) + "\n")

    return build_final_text(target, results, disambigs, remap, redirects, new_apps, new_nca, new_sources, new_ncs, new_links, log)


def analyze_target_page(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                        sources: FullListData, remap: dict, save: bool, include_date: bool,
                        log=True, use_index=True, handle_references=False, collapse_audiobooks=True):
    results, unknown, redirects = build_page_components(target, types, disambigs, appearances, sources, remap, infoboxes, handle_references, log)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    new_apps, new_nca, new_sources, new_ncs, new_links, dates, unknown_apps, unknown_src, unknown_final, unknown_links, analysis = analyze_section_results(
        target, results, disambigs, appearances, sources, remap, use_index, include_date, collapse_audiobooks, [], log)

    new_txt = build_final_text(target, results, disambigs, remap, redirects, new_apps, new_nca, new_sources, new_ncs, new_links, log)

    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if dates:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/new_dates.txt", mode="a", encoding="utf-8") as f:
            date_txt = []
            for d in dates:
                if d[2] == d[3]:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]}: -> {d[1].master.original}")
                else:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]} {d[3]}: -> {d[1].master.original}")
            f.writelines("\n" + "\n".join(date_txt))

    if save and new_txt != target.get(force=True):
        if "�" in new_txt:
            error_log(f"Unexpected characters found in changes")
            error_log(showDiff(target.get(force=True), new_txt))
        z1 = re.sub("<!--.*?-->", "", new_txt)
        z2 = re.sub("<!--.*?-->", "", target.get(force=True)).replace("text=SWCC 2022", "text=SWCA 2022")
        match = z1 == z2
        target.put(new_txt, "Source Engine analysis of Appearances, Sources and references", botflag=match, force=True)

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

        if unknown_links:
            results.append("Could not identify unknown External Links:")
            for o in unknown_links:
                results.append(f"- `{o.original if isinstance(o, Item) else o}`")
            f.writelines("\n" + "\n".join([o.original if isinstance(o, Item) else o for o in unknown_links]))

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
