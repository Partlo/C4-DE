import re
import time
import traceback
from datetime import datetime, timedelta

from pywikibot import Page, showDiff
from typing import List, Tuple, Union, Dict, Optional

from c4de.sources.determine import extract_item, determine_id_for_item, convert_issue_to_template, swap_parameters
from c4de.sources.engine import AUDIOBOOK_MAPPING, GERMAN_MAPPING, SERIES_MAPPING, EXPANSION
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, AnalysisResults, SectionComponents, \
    SectionItemIds, FinishedSection, NewComponents, UnknownItems
from c4de.sources.infoboxer import handle_infobox_on_page
from c4de.common import is_redirect, build_redirects, fix_redirects, do_final_replacements, fix_disambigs, prepare_title

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
INDEX_AND_CATS = ["{{imagecat", "{{mediacat", "{{indexpage", "{{wq", "{{incomplete", "{{quote", "<div style=",
                  "set in '''bold'''", "{{cleanup", "{{more", "{{coor title", "{{coor_title"]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"],
    "Star Wars: The Essential Atlas Online Companion": ["''[[Star Wars: The Essential Atlas Online Companion]]''"]
}


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("referene", "reference"), ("Note and references", "Notes and references"),
    ("Notes and reference=", "Notes and references="), ("==References==", "==Notes and references=="),
    ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"), ("{{MO}}", "{{Mo}}"),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("DisneyPlusYT", "DisneyPlusYouTube"), ("<br>", "<br />"),
    ("Youtube", "YouTube"), ("{{Shortstory", "{{StoryCite"), ("{{Scrollbox", "{{Scroll_box"),
    ("{{scrollbox", "{{Scroll_box"), ("FFCite", "FactFile"), ("</reF>", "</ref>"),
    ("[[B1-Series battle droid]]", "[[B1-series battle droid/Legends|B1-series battle droid]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I/Legends|Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter/Legends|''Vulture''-class starfighter]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter|''Vulture''-class starfighter]]"),

    ("Tales of the Jedi —", "Tales of the Jedi –"), ("Tales of the Jedi &mdash;", "Tales of the Jedi –"),
    ("FactFile|year=", "FactFile|y="),
    ("Vader Immortal: A Star Wars VR Series – Episode", "Vader Immortal – Episode")
]

COLLECTION = [("Star Wars Universe\|Star Wars Universe\|", "Star Wars Universe|"),
    ("\{\{BustCollectionCite\|2\|(.*?Stormtroopers)", "{{BustCollectionCite|3|\\1"),
    ("\{\{BustCollectionCite\|3\|(.*?(Chewbacca|Kashyyyk))", "{{BustCollectionCite|5|\\1"),
    ("\{\{BustCollectionCite\|4\|(.*?(Searching for the Map|Kylo Ren))", "{{BustCollectionCite|15|\\1"),
    ("\{\{BustCollectionCite\|6\|(.*?(Luke Skywalker))", "{{BustCollectionCite|22|\\1"),
    ("\{\{BustCollectionCite\|7\|(.*?Boba )", "{{BustCollectionCite|2|\\1"),
    ("\{\{BustCollectionCite\|8\|(.*?From Supporting|Han Solo)", "{{BustCollectionCite|25|\\1"),
    ("\{\{BustCollectionCite\|10\|(.*?Specialized)", "{{BustCollectionCite|6|\\1"),
    ("\{\{BustCollectionCite\|12\|(.*?Trade Federation)", "{{BustCollectionCite|13|\\1"),
    ("\{\{BustCollectionCite\|14\|(.*?Endor)", "{{BustCollectionCite|36|\\1"),
    ("\{\{BustCollectionCite\|17\|(.*?Fighter Pilot)", "{{BustCollectionCite|10|\\1"),
    ("\{\{BustCollectionCite\|20\|(.*?Boush)", "{{BustCollectionCite|11|\\1"),
    ("\{\{BustCollectionCite\|34\|(.*?Greedo)", "{{BustCollectionCite|32|\\1"),
    ("\{\{HelmetCollectionCite\|([0-9]+)\|Databank\|", "{{HelmetCollectionCite|\\1|Databank A-Z|"),
    ("\{\{HelmetCollectionCite\|3\|(.*?Rescue)", "{{HelmetCollectionCite|5|\\1"),
    ("\{\{HelmetCollectionCite\|5\|(.*?Scout)", "{{HelmetCollectionCite|7|\\1"),
    ("\{\{HelmetCollectionCite\|5\|(.*?Bounty Hunters)", "{{HelmetCollectionCite|2|\\1"),
    ("\{\{HelmetCollectionCite\|5\|(.*?Imperial Fleet)", "{{HelmetCollectionCite|6|\\1"),
    ("\{\{HelmetCollectionCite\|6\|(.*?Sebulba)", "{{HelmetCollectionCite|17|\\1"),
    ("\{\{HelmetCollectionCite\|53\|(.*?Bly)", "{{HelmetCollectionCite|73|\\1")]


def initial_cleanup(target: Page, all_infoboxes, before: str=None):
    # now = datetime.now()
    if not before:
        before = target.get(force=True)
    # print(f"retrieval: {(datetime.now() - now).microseconds / 1000} microseconds")
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(
            "(]]|}})(\{+ ?(1st[A-z]*|[A-z][od]|[Ll]n|[Uu]n\|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[|}])",
            "\\1 \\2", before)
    if "{{Facebook" in before or "{{WebCite" in before or "{{Twitter" in before or "{{Instagram" in before:
        while re.search("\{\{(Facebook|WebCite|Instagram|Twitter)(Cite)?([^}\n]*?)\n([^}\n]+)([\n}])", before):
            before = re.sub("\{\{(Facebook|WebCite|Instagram|Twitter)(Cite)?([^}\n]*?)\n([^}\n]+)([\n}])", "{{\\1\\3\\4 \\5", before)
        before = re.sub("(\{\{(Facebook|WebCite|Instagram|Twitter)(Cite)?[^}\n]+)\n}}", "\\1}}", before)
        before = before.replace("FacebookCite", "Facebook")

    x, _, y = target.title().replace("/Legends", "").replace("/Canon", "").partition(" (")
    for z in ["{{PAGENAME}}", x, target.title()]:
        for i in ["|", "}"]:
            before = before.replace(f"|title=''{z}''{i}", f"|italics=1{i}")
            if f"Otheruses|title={z}" in before:
                before = re.sub("(\{\{Top.*?)\|title=" + z + "(\|.*?)?}}", "\\1\\2", before)
            else:
                before = before.replace(f"|title={z}{i}", f"{i}")
    if y:
        y = y.replace(")", "").strip()
        if f"|title2=''{y}''" in before:
            before = before.replace(f"|title2=''{y}''", "|italics2=1")
        elif f"|title2={y}" in before:
            before = before.replace(f"|title2={y}", "")

    # if "(" in target.title() and "|title=''{{PAGENAME}}''" in before:
    #     x, _, _ = target.title().partition(" (")
    #     before = before.replace("|title=''{{PAGENAME}}''", f"|title=''{x}''")

    # now = datetime.now()
    if all_infoboxes and not target.title().startswith("User:") and not target.title().startswith("File:"):
        before = handle_infobox_on_page(before, target, all_infoboxes)
    # print(f"infobox: {(datetime.now() - now).microseconds / 1000} microseconds")

    before = re.sub("= ?Non-[Cc]anon [Aa]ppearances ?=", "=Non-canon appearances=", before)

    # now = datetime.now()
    before = re.sub("(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = before.replace("||text=", "|text=")
    before = re.sub("(\{\{1st[A-z]*)\|\n}}", "\\1}}", before)
    before = re.sub("(\{\{1st[A-z]*\|[^|}\n]*?)\n}}", "\\1}}", before)
    before = re.sub("\n=([A-z ]+)==", "\n==\\1==", before)
    before = re.sub("(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub("({{[Ss]croll[_ ]box\|)\*", "{{Scroll_box|\n*", before)
    before = re.sub("([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub("=+'*Non-canonical (appearances|sources)'*=+", "===Non-canon \\1===", before)
    before = re.sub("\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub("^(.*?) +\n", "\\1\n", before)
    before = re.sub("\* +([A-z0-9'\[{])", "*\\1", before)
    if "<references" in before.lower():
        before = re.sub("<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)
    before = re.sub("([A-z'0-9\]]+) [ ]+([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub("\|image=(File:)?([A-Z0-9 _]+\..+)\n", "|image=[[File:\\2]]", before)
    before = re.sub("(\|image=\[\[File:[^\n\]]+?)\|.*?]]", "\\1]]", before)
    before = re.sub("\"/>", "\" />", before).replace("<nowiki>|</nowiki>", "&#124;")
    before = re.sub("<small>\((.*?)\)</small>", "{{C|\\1}}", before)
    before = re.sub("([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub("\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub("\{\{(Facebook|Twitter|Instagram|Discord)Cite", "{{\\1", before)
    before = re.sub("\*\{\{\{([A-Z])", "*{{\\1", before)

    before = re.sub("(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub("\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub("\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)
    before = re.sub("(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)

    before = re.sub("(\|set=(.*?))\|sformatted=''\\2''", "\\1", before)

    before = re.sub("\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub("(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)

    # temp fixes
    before = re.sub("\{\{Topps\|set=Star Wars: Card Trader\|(cardname=)?", "{{SWCT|", before)
    before = re.sub("(\{\{Databank.*?}})( \{\{C\|alternate:.*?}})+", "\\1", before)
    before = before.replace("(Force Pack)", "(Star Wars: The Card Game)")

    # Galaxies fixes
    while re.search("\[\[Category:[^\n|\]_]+_", before):
        before = re.sub("(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)

    if "CollectionCite" in before:
        for (x, y) in COLLECTION:
            before = re.sub(x, y, before)
    # print(f"regex-1: {(datetime.now() - now).microseconds / 1000} microseconds")

    # now = datetime.now()
    before = regex_cleanup(before)
    # print(f"regex-2: {(datetime.now() - now).microseconds / 1000} microseconds")

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


def regex_cleanup(before: str) -> str:
    if before.count("==Appearances==") > 1:
        before = re.sub("(==Appearances==(\n.*?)+)\n==Appearances==", "\\1", before)
    if before.count("==Sources==") > 1:
        before = re.sub("(==Sources==(\n.*?)+)\n==Sources==", "\\1", before)

    if "\n</ref>" in before:
        before = re.sub("(<ref name=((?!</ref>).)*?)\n</ref>", "\\1</ref>", before)
    if "<nowiki>|" in before:
        while re.search("<nowiki>(\|.*?\|.*?)</nowiki>", before):
            before = re.sub("<nowiki>\|(.*?)\|(.*?)?</nowiki>", "<nowiki>|\\1&#124;\\2</nowiki>", before)
        before = re.sub("<nowiki>\|(.*?)</nowiki>", "&#124;\\1", before)
    if "web.archive" in before:
        before = re.sub("(?<!\[)\[https?://(.*?) (.*?)] (\(|\{\{C\|)\[http.*?web.archive.org/web/([0-9]+)/https?://.*?\\1.*?][)}]+","{{WebCite|url=https://\\1|text=\\2|archivedate=\\4}}", before)
    if "width=100%" in before:
        before = re.sub("(\{\{[Ss]croll[ _]box(\n?\|.*?)?)\n?\|width=100%", "\\1", before)
    if "simultaneous with" in before:
        before = re.sub("<small>\(First appeared(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
        before = re.sub("<small>\(First mentioned(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
    if "*[[wikipedia:" in before.lower() or "source=[[wikipedia:" in before.lower():
        before = re.sub("(\n\*|\">|ref>|source=)\[\[[Ww]ikipedia:(.*?)\|(.*?)]]( on (\[\[Wikipedia.*?]]|Wikipedia))?","\\1{{WP|\\2|\\3}}", before)
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub("\*'*\[\[:?([Ww]|Wikia):c:([^\n|]]*?):([^\n|]]*?)\|([^\n]]*?)]] (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\2|\\8|\\3|\\4}}", before)
    if "memoryalpha:" in before.lower():
        before = re.sub("\[\[([Mm]emory[Aa]lpha|w:c:memory-alpha):(.*?)\|(.*?)]] (on|at) (the )?.*?([Mm]emory[Aa]lpha:|Wikipedia:Memory Alpha).*?\|.*?]](,.*?$)?", "{{MA|\\2|\\3}}", before)

    before = re.sub("(\{\{[A-z0-9 _]+\|.*?\|(.*?) \(.*?\))\|\\2}}", "\\1}}", before)
    if "Star Wars Galaxies" in before or "GalaxiesAED" in before:
        before = re.sub("([*>]) ?'*\[\[Star Wars Galaxies: An Empire Divided]]'*", "\\1{{GalaxiesAED}}", before)
        before = re.sub("([*>]) ?'*\[\[Star Wars Galaxies\|'*Star Wars Galaxies: An Empire Divided'*]]'*?(: An Empire Divided'*)?","\\1{{GalaxiesAED}}", before)
        before = re.sub("([*>]) ?'*\[\[Star Wars Galaxies(\|.*?)?]]'*: An Empire Divided'*", "\\1{{GalaxiesAED}}", before)
        before = re.sub("\{\{GalaxiesAED}}'*: An Empire Divided'*", "{{GalaxiesAED}}", before)
        before = re.sub("([*>]) ?'*\[\[Star Wars Galaxies]]'*", "\\1{{GalaxiesNGE}}", before)
        before = before.replace("[[Star Wars Galaxies: The Complete Online Adventures|''Star Wars Galaxies: The Complete Online Adventures'' bonus DVD]]","[[Star Wars Galaxies Bonus DVD|''Star Wars Galaxies'' Bonus DVD]]")

    if "{{SWGcite" in before:
        before = before.replace("|exp=SK|", "|exp=NGE|").replace("|exp=TCOA|", "|exp=NGE|").replace("|exp=TTE|", "|exp=RotW|")
    before = before.replace("StarWarsAdventuresMagazineCite", "SWAdventuresCite")
    if "{{Blog|" in before:
        before = re.sub("(\{\{Blog\|(official=true\|)?[^|\n}\]]+?\|[^|\n}\]]+?\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
        before = re.sub("(\{\{Blog\|listing=true\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
    if "|year=" in before:
        before = re.sub("(\{\{[A-z]+)\|([0-9]+)\|(year=[0-9]+)", "\\1|\\3|\\2", before)
    if "SWGTCG" in before:
        before = re.sub("(\{\{SWGTCG\|.*?)}} {{C\|(.*?scenario.*?)}}", "\\1|scenario=\\2}}", before)
    if "VisionsCite" in before:
        before = re.sub("(\{\{VisionsCite\|.*?focus)=(?!1).*?(\|.*?)?}}", "\\1=1\\2}}", before)
        before = re.sub("(\{\{VisionsCite.*?}}) \{\{[Aa]mbig}}", "\\1", before)
    if "{{Hunters|url=arena-news" in before:
        before = re.sub("\{\{Hunters\|url=arena-news/(.*?)/?\|", "{{ArenaNews|url=\\1|", before)
    if "{{Disney|books|" in before:
        before = re.sub("\{\{Disney\|books\|(.*?)\|", "{{Disney|subdomain=books|url=\\1|text=", before)
    if "ArtStation" in before:
        before = re.sub("(\{\{ArtStation(\|.*?)?)\|url=(.*?)(\|.*?)\|profile=\\1(\|.*?)?}}", "\\1|profile=\\2\\3\\4}}", before)
        before = re.sub("\{\{ArtStation\|url=(((?!profile=).)*?)}}", "{{ArtStation|profile=\\1}}", before)
    if "Rebelscum.com" in before or "TheForce.net" in before:
        before = re.sub("\*'*?\[(http.*?) (.*?)]'*? (on|at|-).*?\[\[(Rebelscum\.com|TheForce\.net).*]].*?\n","{{WebCite|url=\\1|text=\\2|work=\\4}}", before)
    if "FactFile" in before:
        before = re.sub("\{\{FactFile\|([0-9]+)\|(y=[0-9]+)", "{{FactFile|\\2|\\1", before)
        before = re.sub("(\{\{FactFile\|(y=[0-9]+\|)?[0-9]+)}} \{\{C\|", "\\1|", before)
        before = re.sub("(\{\{FactFile\|y=2013\|[0-9]+\|)([A-Z]+) ?([0-9]+), '*(.*?)'*}}", "\\1\\2 \\3|\\4}}", before)
        before = re.sub("(\{\{FactFile\|y=2013\|[0-9]+\|)([A-Z]+) ?([0-9]+)( ?(-|&.dash;) ?[A-Z]*? ?([0-9]+))?, '*(.*?)'*}}", "\\1\\2 \\3-\\6|\\7}}", before)
        while re.search("\n(.*?FactFile\|[0-9]+\|)([A-Z]+ ?[0-9]+[^\n]*?, ((?!dash)[^\n])*?); ([A-Z]+ ?[0-9]+[^\n]*?, [^\n]*?)}}\n", before):
            before = re.sub("\n(.*?FactFile\|[0-9]+\|)([A-Z]+ ?[0-9]+[^\n]*?, ((?!dash)[^\n])*?); ([A-Z]+ ?[0-9]+[^\n]*?, [^\n]*?)}}\n", "\n\\1\\2}}\n\\1\\4}}\n", before)
    return before


STRUCTURE = {
    "Appearances": "==Appearances==",
    "Non-Canon Appearances": "===Non-canon appearances===",
    "Sources": "==Sources==",
    "Non-Canon Sources": "===Non-canon sources===",
    "References": "==Notes and references==",
    "Links": "==External links=="
}


def build_page_components(target: Page, types: dict, disambigs: list, appearances: FullListData, sources: FullListData, remap: dict,
                          all_infoboxes, handle_references=False, log=True, manual: str = None, extra=None) -> Tuple[PageComponents, list, dict]:
    # now = datetime.now()
    before = initial_cleanup(target, all_infoboxes, before=manual)
    # print(f"cleanup: {(datetime.now() - now).microseconds / 1000} microseconds")
    redirects = build_redirects(target, manual=manual)
    if "{{otheruses" in before.lower() or "{{youmay" in before.lower():
        for r, t in redirects.items():
            if t in disambigs or "(disambiguation)" in t:
                before = fix_disambigs(r, t, before)

    canon = False
    legends = False
    real = False
    non_canon = False
    unlicensed = False
    app_mode = BY_INDEX
    for c in target.categories():
        if "Non-canon Legends articles" in c.title() or "Non-canon articles" in c.title():
            non_canon = True
        elif "Articles from unlicensed sources" in c.title():
            unlicensed = True
        if "canon articles" in c.title().lower():
            canon = True
        elif "legends articles" in c.title().lower():
            legends = True
        elif c.title(with_ns=False).startswith("Real-world ") and c.title(with_ns=False) not in ["Real-world restaurants", "Real-world stores"]:
            real = True
            if re.search("\{\{Top\|(.*?\|)?(dotj|tor|thr|fotj|rote|aor|tnr|rofo|cnjo|can|ncc)(\|.*?)?}}", target.get()):
                canon = True
            elif re.search("\{\{Top\|(.*?\|)?(pre|btr|old|imp|reb|new|njo|lgc|inf|ncl|leg)(\|.*?)?}}", target.get()):
                legends = True
    if target.title().startswith("User:") and "{{Top|legends=" in target.get():
        canon = True
        app_mode = BY_INDEX
    # if legends:
    #     app_mode = UNCHANGED
    results = PageComponents(before, canon, non_canon, unlicensed, real, app_mode)

    unknown = []
    final = ""

    x = re.split("(\{\{DEFAULTSORT|\[\[[Cc]ategory:)", before, 1)
    if x:
        before = x[0]
        final = "".join(x[1:])

    ref_section = ""
    rest = ""
    # now = datetime.now()
    for name, header in STRUCTURE.items():
        if name == "Appearances" and ("{{app\n" in before.lower() or "{{app|" in before.lower()):
            continue
        if header in rest:
            rest, section_text = rest.rsplit(header, 1)
        elif header in before:
            before, section_text = before.rsplit(header, 1)
        else:
            continue

        pieces = re.split("(==|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:|\{\{RelatedCategories)", section_text, 1)
        section = pieces[0]
        after = ""
        next_or_last = "".join(pieces[1:])
        if "{{start_box" in section.lower() or "{{start box" in section.lower():
            pieces2 = re.split("({{[Ss]tart[_ ]box)", section, 1)
            if len(pieces2) == 3:
                section = pieces2[0]
                after = pieces2[1] + pieces2[2]
        if "==Behind the scenes==" in next_or_last:
            before = f"{before}\n{next_or_last}"
        else:
            rest = f"{next_or_last}\n{rest}"

        if name == "References":
            ref_section = f"{header}{section}\n{after}"
            continue
        elif name == "Sources" and extra:
            for i in extra:
                section += f"\n*''[[{i}]]''"

        # section, after = split_section_pieces(section_text)
        # before, after, final = move_interlang(before, after, final)
        section = fix_redirects(redirects, section, name, disambigs, remap)
        result = parse_section(section, types, "Appearances" in header, unknown, after, log, name)

        if result and result.after.startswith("==Behind the scenes=="):
            before += f"\n{result.after}"
            result.after = ""
        if log:
            print(f"{name}: {len(result.items)} --> {len(set(i.unique_id() for i in result.items))}")

        if name == "Appearances":
            results.apps = result
        elif name == "Non-Canon Appearances":
            results.nca = result
        elif name == "Sources":
            results.src = result
        elif name == "Non-Canon Sources":
            results.ncs = result
        elif name == "Links":
            results.links = result
            # x = re.split("(==Notes and references|\{\{[R]eflist)", before, 1)
            # if x:
            #     before = x[0]
            #     results.links.before = "".join(x[1:])
            # x = re.split("(==Notes and references|\{\{[R]eflist)", rest, 1)
            # if x:
            #     rest = x[0]
            #     results.links.before = "".join(x[1:])

    if ref_section and results.links:
        results.links.before = f"{ref_section}\n{results.links.before}"
    elif ref_section:
        final = f"\n{ref_section}\n{final}".strip()

    final = f"{rest}\n{final}".strip()
    if results.links and results.links.after:
        final = f"{results.links.after}\n{final}"
        results.links.after = ""
    # print(f"parse: {(datetime.now() - now).microseconds / 1000} microseconds")

    results.before = before
    results.final = final
    if handle_references:
        results.before = analyze_body(target, results.before, types, appearances, sources, remap, disambigs, redirects, canon, log)
    return results, unknown, redirects


def split_section_pieces(section):
    pieces = re.split("(==|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:|\{\{RelatedCategories)", section, 1)
    section = pieces[0]
    after = "".join(pieces[1:])
    if "{{start_box" in section.lower() or "{{start box" in section.lower():
        pieces2 = re.split("({{[Ss]tart[_ ]box)", section, 1)
        if len(pieces2) == 3:
            section = pieces2[0]
            after = pieces2[1] + pieces2[2]
    # if after:
    #     x = re.split("(==.*?==|\{\{DEFAULTSORT|\{\{[Ii]nterlang|\[\[Category:)", after, 1)
    #     if x and len(x) == 3:
    #         return section + x[0], x[1] + x[2]
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
    # x = re.split("(==.*?==)", final, 1)
    # if x:
    #     print(x)
    #     print(f"Splitting off {x[1]} section")
    #     after += f"\n{x[0]}"
    #     final = "".join(x[1:]) + "\n" + final
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
    section = re.sub("'*\[\[Star Wars Miniatures]]'*: '*\[\[(.*?)(\|.*?)?]]'*", "{{SWMiniCite|set=\\1}}", section)
    section = re.sub("(?<!Hamm) \((as .*?)\)", " {{C|\\1}}", section)
    section = section.replace("]]{{Mediacat", "]]\n{{Mediacat")
    for s in section.splitlines():
        if succession_box:
            other2.append(s)
            continue
        if "CardGameSet" in s:
            s = re.sub("{{CardGameSet\|(set=)?.*?\|cards=", "", s)
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
            x = handle_valid_line(s, is_appearances, log, types, data, [] if external else other2, unknown, unique_ids, False, name)
            if not x and external:
                z = Item(s.strip(), "Basic", False)
                if is_official_link(z):
                    z.mode = "Official"
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
                if x and is_nav_template(x.group(1), types):
                    navs.append(s)
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
    z = re.sub("<!--.*?-->", "", s.replace("&ndash;", '–').replace('&mdash;', '—').strip())
    z = re.sub("<sup>(.*?)</sup>", "{{C|\\1}}", z)
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
    x1 = re.search(
        '( ?(<ref.*?>)?(<small>)? ?\{+ ?(1st[A-z]*|V?[A-z][od]|[Ff]act|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}].*?$)',
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
        t = extract_item(convert_issue_to_template(y), is_appearances, name, types)
        if t and not t.invalid:
            if is_official_link(t):
                t.mode = "Official"
            found = True
            data.append(t)
            t.extra = extra.strip()
            t.ab = ab
            t.bold = bold
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


def analyze_body(page: Page, text, types, appearances: FullListData, sources: FullListData, remap, disambigs, redirects, canon, log: bool):
    references = [(i[0], i[2]) for i in re.findall("(<ref name=((?!<ref).)*?[^/]>(((?!<ref).)*?)</ref>)", text)]
    references += [(i[0], i[1]) for i in re.findall("(<ref>(((?!<ref).)*?)</ref>)", text)]
    new_text = text
    for full_ref, ref in references:
        new_text = handle_reference(full_ref, ref, page, new_text, types, appearances, sources, remap, disambigs, redirects, canon, log)
    return do_final_replacements(new_text, True)


REF_REPLACEMENTS = [("film]] film", "film]]"), ("|reprint=yes", ""), ("|reprint=1", ""), ("|audiobook=yes", ""), ("|audiobook=1", "")]


def handle_reference(full_ref, ref: str, page: Page, new_text, types, appearances: FullListData, sources: FullListData,
                     remap: dict, disambigs: dict, redirects, canon, log: bool):
    try:
        new_ref = re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", ref).replace("{{PageNumber}} ", "")
        if "HomeVideoCite" not in new_ref:
            new_ref = re.sub("\|set=(.*?) \(.*?\)\|(sformatt?e?d?|stext)=.*?\|", "|set=\\1|", new_ref)
        if "<ref>" in full_ref and new_ref.count('[') == 0 and new_ref.count("]") == 0:
            x = re.search("^'*(.*?)'*$", new_ref)
            if x and x.group(1) in appearances.target:
                new_ref = appearances.target[x.group(1)][0].original
            elif x and x.group(1) in sources.target:
                new_ref = sources.target[x.group(1)][0].original
        x = re.search(",? (page|pg\.?|p?p\.|chapters?|ch\.) ([0-9-]+|one|two|three|four|five)(?!]),?", new_ref)
        if x:
            print(f"Found page/chapter numbers in reference: \"{x.group(0)}\" -> \"{new_ref}\"")
            # new_ref = new_ref.replace(x.group(0), "")
            new_ref = "{{PageNumber}} " + new_ref
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
                    if o.master.template and not x.template and x.target and not re.search("^['\"]*\[\[" + prepare_title(x.target) + "(\|.*?)?]]['\"]*$", new_ref):
                        if o.master.template != "Film" and f'"[[{x.target}]]"' not in new_ref:
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
            new_ref = new_ref.replace(ot, swap_parameters(ni))

        new_templates = []
        for t in templates:
            if t == "{{'s}}" or "{{TORcite" in t or "{{SWG" in t or t.startswith("{{C|") or t.startswith("{{Blogspot") or t.startswith("{{Cite") or t.startswith("{{PageNumber"):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and is_nav_or_date_template(x.template, types):
                    continue
                o = determine_id_for_item(x, page.site, appearances.unique, appearances.target, sources.unique,
                                          sources.target, {}, canon, log)
                if o and o.current.mode == "Cards":
                    new_templates.append((t, o, []))
                elif o and not (o.use_original_text or o.current.collapsed) and t != o.master.original:
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
            if ni.master.mode == "Cards":
                z = build_card_text(ni, ni)
            else:
                z = swap_parameters(ni.master.original)
            if extra:
                for i in extra:
                    z = z.replace(i, "")
                z = z[:-2] + "".join(extra) + "}}"
            if "|d=y" in ni.current.original:
                z = z[:-2] + "|d=y}}"
            new_ref = new_ref.replace(ot, z.replace("–", "&ndash;").replace("—", "&mdash;"))
            new_ref = re.sub("\|parent=1(?!}}( is set| \{\{C\|))", "", new_ref)

        new_ref = fix_redirects(redirects, new_ref, "Reference", disambigs, remap)
        final_ref = re.sub("\{\{[Aa]b\|.*?}}", "", full_ref.replace(ref, new_ref))
        if "<ref>" in final_ref:
            if len(found) == 1 and found[0].master.target:
                z = found[0].master.target.replace('"', '').replace('(', '').replace(')', '')
                final_ref = final_ref.replace("<ref>", f"<ref name=\"{z}\">")
            elif len(found) == 1 and found[0].master.template and found[0].master.text:
                z = found[0].master.text.replace('"', '').replace('(', '').replace(')', '')
                final_ref = final_ref.replace("<ref>", f"<ref name=\"{found[0].master.template}-{z}\">")
            elif len(found) == 1:
                print(f"Cannot fix nameless reference to {found[0].master.target}: {ref}")
            else:
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


def check_format_text(o: ItemId, x: Item):
    if o.current.followed_redirect and o.current.original_target:
        return _check_format_text(o.current.original_target, x.format_text)
    return _check_format_text(o.master.target, x.format_text)


def _check_format_text(t, y):
    return t and y and "(" in t and (
            t.split("(")[0].strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel") and
            t.replace("(", "").replace(")", "").strip().lower().replace("novelization", "novel") not in y.replace("''", "").lower().replace("novelization", "novel")
    )


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


def prepare_official_link(o: Item):
    if o.full_url:
        ad = f"|archivedate={o.archivedate}" if o.archivedate else ""
        if "web.archive" in o.extra:
            x = re.search("web/([0-9]+)/", o.extra)
            if x:
                ad = f"|archivedate={x.group(1)}"
                o.extra = re.sub("\{\{C\|\[http.*?web\.archive\.org/.*?}}", "", o.extra)
        return "Official", f"{{{{OfficialSite|url={o.full_url}{ad}}}}}"
    else:
        return "Official", o.original.replace("WebCite", "OfficialSite")


def prepare_basic_url(o: Item):
    if o.original and re.search("official .*?(site|homepage|page)", o.original.lower()):
        return prepare_official_link(o)
    elif o.full_url:
        ad = f"|archivedate={o.archivedate}" if o.archivedate else ""
        u = o.full_url if o.full_url.startswith("http") else f"https://{o.full_url}"
        return "Basic", f"{{{{WebCite|url={u}|text={o.text}{ad}}}}} {o.extra}".strip()
    else:
        return "Basic", o.original


def is_product_page(u: str):
    return ("/product/" in u or "/products/" in u or "/previews" in u or "/preview.php" in u or
            u.startswith("profile/profile.php") or "/themes/star-wars" in u or
            u.startswith("book/") or u.startswith("books/") or u.startswith("comics/")) and "subdomain=news" not in u


SUBDOMAINS = ["books", "comicstore", "shop", "digital", "squadbuilder", "comicvine", "cargobay"]
SOLICITS = ["ign.com", "aiptcomics", "gamesradar", "cbr.com", "newsarama", "bleedingcool"]
PRODUCT_DOMAINS = ["phrcomics", "advancedgraphics", "advancedgraphics.com", "blacksabercomics", "comicselitecomics",
                   "inningmoves", "eastsidecomicsdiscogs.com", "blackwells.co.uk", "birdcitycomics", "bigtimecollectibles",
                   "comiccollectorlive", "comics\.org", "phrcomics", "the616comics", "thecomiccornerstore", "thecomicmint",
                   "universal-music.de", "unknowncomicbooks", "frankiescomics", "geekgusher", "hachettebookgroup",
                   "jedi-bibliothek", "kiddinx-shop", "lizzie.audio", "luxor.cz", "midtowncomics", "mikemayhewstudio"]
PRODUCTS = ["LEGOWebCite", "Marvel", "DarkHorse", "FFGweb", "AMGweb", "Unlimitedweb"]
PRODUCT_CHECKS = {
    "AMGweb": {"S": ["character/"], "E": []},
    "FFGweb": {"S": [], "E": ["-showcase"]}
}


def is_commercial(d: ItemId, o: Item):
    if o.template in PRODUCT_CHECKS and o.url and (any(o.url.lower().endswith(s) for s in PRODUCT_CHECKS[o.template]["E"]) or
                                                   any(o.url.lower().startswith(s) for s in PRODUCT_CHECKS[o.template]["S"])):
        return True
    if o.template in PRODUCTS and o.url and is_product_page(o.url.lower()):
        return True
    if "subdomain=" in o.original and any(f"subdomain={s}" in o.original for s in SUBDOMAINS):
        return True
    if o.template == "SWArchive" and o.url and "/downloads" in o.original:
        return True
    if o.template == "WebCite" and o.url:
        if "/product/" in o.url or "/products/" in o.url or "/collections/" in o.url:
            return True
        if any(f"{s}." in o.url for s in PRODUCT_DOMAINS):
            return True
        if "-solicitations" in o.url and any(s in o.url for s in SOLICITS):
            return True
    return False


def is_nav_or_date_template(template, types: dict):
    return template.lower().replace("_", " ") in types["Nav"] or template.lower().replace("_", " ") in types["Dates"]


def is_nav_template(template, types: dict):
    return template.lower().replace("_", " ") in types["Nav"]


def is_external_link(d: ItemId, o: Item, unknown):
    if not d and o.mode == "Basic":
        unknown.append(o)
        return True
    elif d and d.master.template and "ToyCite" in d.master.template:
        return False
    elif not d and o.original.replace("*", "").startswith("[http"):
        return True
    elif not d and o.url and any(o.url.startswith(f"{s}/") for s in ["people", "person", "leadership", "our-team", "bio", "news/contributor"]):
        o.mode = "Bio"
        return True
    elif (o.mode == "Commercial" or o.mode == "Web") and any(x in o.original.lower() for x in ["authors/", "author/", "comics/creators", "book-author"]):
        o.mode = "Profile" if o.template in ["SW", "SWArchive"] else "Commercial"
        return True
    elif o.template == "YouTube" and re.search("YouTube\|channel(name)?=[^|}\n]+\|channel(name)?=[^|}\n]+}}", o.original) and "video=" not in o.original:
        o.mode = "Profile"
        return True
    elif d and d.master.external:
        o.mode = "Found-External"
        return True
    elif "Folio" not in o.original and o.url and ("images-cdn" in o.url or (("subdomain=dmedmedia" in o.original or "subdomain=press" in o.original) and "news/" not in o.original)):
        o.mode = "CDN"
        return True
    elif is_commercial(d, o):
        o.mode = "Commercial"
        return True
    elif o.template == "Blog" and "listing=true" in o.original:
        o.mode = "Profile"
        return True
    elif o.mode == "Social":
        if "||" in o.original or "| |" in o.original or o.template == "LinkedIn" or "isprofile=" in o.original:
            o.mode = "Profile"
        elif o.template == "ArtStation" and "artwork/" not in o.original:
            o.mode = "Profile"
        elif o.template == "Twitch" and "video=" not in o.original:
            o.mode = "Profile"
        return True
    elif o.mode == "External" or o.mode == "Interwiki" or o.mode == "Commercial" or o.mode == "Profile":
        if o.template == "MobyGames":
            o.override_date = "Target"
            o.date = "Target"
        return True


def analyze_section_results(target: Page, results: PageComponents, disambigs: list, appearances: FullListData,
                            sources: FullListData, remap: dict, use_index: bool, include_date: bool,
                            collapse_audiobooks: bool, checked: list, log) \
        -> Tuple[NewComponents, list, UnknownItems, AnalysisResults]:
    both_continuities = appearances.both_continuities.union(sources.both_continuities)
    dates = []
    unknown_apps, unknown_src = [], []
    # now = datetime.now()
    new_src = build_item_ids_for_section(target, results.real, "Sources", results.src.items, sources, appearances, None, remap, unknown_src, results.canon, [], collapse_audiobooks, log)
    new_ncs = build_item_ids_for_section(target, results.real, "Non-canon sources", results.ncs.items, sources, appearances, None, remap, unknown_src, results.canon, [], collapse_audiobooks, log)
    new_apps = build_item_ids_for_section(target, results.real, "Appearances", results.apps.items, appearances, sources, new_src, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    new_nca = build_item_ids_for_section(target, results.real, "Non-canon appearances", results.nca.items, appearances, sources, new_ncs, remap, unknown_apps, results.canon, checked, collapse_audiobooks, log)
    # print(f"item IDs: {(datetime.now() - now).microseconds / 1000} microseconds")

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

    results.links.items = [*new_apps.links, *new_nca.links, *new_src.links, *new_ncs.links, *results.links.items]
    new_links, unknown_links, wrong = build_new_external_links(target, results.links.items, sources, appearances, remap, results.canon, log)
    if wrong:
        if log:
            print(f"Moving {len(wrong)} misclassified sources from External Links to Sources")
        new_src.found += wrong

    if new_nca.found and not (new_apps.found or new_apps.sets or new_apps.cards):
        new_apps = new_nca
        new_apps.mark_as_non_canon = "{{Nc}}"
        new_nca = None
    if new_ncs.found and not (new_src.found or new_src.sets or new_src.cards):
        new_src = new_ncs
        new_src.mark_as_non_canon = "{{Ncs}}"
        new_ncs = None

    # now = datetime.now()
    app_targets = [a.master.target for a in new_apps.found if a.master.target]
    app_targets += [f"{a.master.target}|{a.master.parent}" for a in new_apps.found if a.master.target and a.master.parent]
    abridged = []
    new_indexes = []
    for i, a in enumerate(new_apps.found):
        if "abridged" in a.current.extra:
            a.current.extra = re.sub("(\{\{Ab\|.*?(abridged audiobook)\|)audiobook}}", "\\1abridged audiobook}}", a.current.extra)
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
            elif "(audio)" in b.target or "(audio drama)" in b.target or (not collapse_audiobooks and (b.parent if b.parent else b.target) not in app_targets):
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
    # now2 = datetime.now()
    # for p in target.linkedPages():
    #     if p.title() in disambigs:
    #         if f"[[{p.title()}|" in text or f"[[{p.title()}]]" in text:
    #             disambig_links.append(p.title())
    # print(f"disambig: {(datetime.now() - now2).microseconds / 1000} microseconds")

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
    new_apps, final_apps = build_new_section("==Appearances==", new_apps, title, results.app_mode, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_nca, final_nca = build_new_section("===Non-canon appearances===", new_nca, title, BY_DATE, dates, results.canon, include_date, log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_src, final_sources = build_new_section("==Sources==", new_src, title, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
    new_ncs, final_ncs = build_new_section("===Non-canon sources===", new_ncs, title, BY_DATE, dates, results.canon, True, log, use_index, mismatch, both_continuities, unknown_final, targets, results.real, results.unlicensed, collapse_audiobooks)
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
    cards = _cards()
    extra = {}
    page_links = []
    any_expanded = []
    unexpanded = 0
    other_extra = False
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

        if d and name == "Appearances" and "Core Set" in o.original and o.template == "SWIA":
            wrong.append(d)
            continue
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

        if d and (o.mode == "Cards" or o.template == "ForceCollection"):
            handle_card_item(d, o, cards, src.found if (src and "scenario" not in o.original) else found, src.wrong if src else wrong, extra, name, log)
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

    set_ids = {}
    if name.startswith("File:"):
        pass
    elif src:
        handle_cards(cards, data, other, src.found, src.sets, extra, unknown, src)
        cards = {}
    else:
        handle_cards(cards, data, other, found, set_ids, extra, unknown)

    found += list(extra.values())
    if any_expanded:
        targets = set(x.current.target for x in found if x.current.target)
        for x in any_expanded:
            if x.current.target not in targets:
                found.append(x)
    return SectionItemIds(name, found, wrong, non_canon, cards, set_ids, links, len(any_expanded) > 0 or other_extra)


def handle_cards(cards: Dict[str, List[ItemId]], data: FullListData, other: FullListData, found: list, set_ids: dict, extra: dict, unknown, src: SectionItemIds=None):
    for s, c in cards.items():
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
            found.append(ItemId(t[0], t[0], False))
            set_ids[t[0].full_id()] = s
            if t[0].target in extra:
                extra.pop(t[0].target)
        elif c[0].current.template == "Topps":
            found += c
        else:
            print(f"ERROR: Cannot find item for parent/target set: [{s}]: {c[0].current.full_id()}")
            for i in c:
                i.current.unknown = True
            found += c
        if src and s in src.cards:
            src.cards[s] += c
        elif src:
            src.cards[s] = c

        for i in c:
            if i.current.unknown and i.current.template == "SWCT":
                unknown.append(i.current)


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

BY_INDEX = "Use Master Index"
UNCHANGED = "Leave As Is"
BY_DATE = "Use Master Date"


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
        if o.current.full_id() in section.sets:
            set_cards = section.cards[section.sets[o.current.full_id()]]
            ct = 0
            rows += 1
            if len(set_cards) > 1:
                new_text.append(f"{d}{{{{CardGameSet|set={o.current.original}|cards=")
                ct = 2
            for c in sorted(set_cards, key=lambda a: (a.current.card if a.current.card else a.current.original).replace("''", "")):
                ot = build_card_text(o, c).replace("|parent=1", "")
                zt = "*" + d + re.sub("<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", f"{ot} {c.current.extra.strip()}").strip()
                if title and "1stID" in zt and re.search("\{\{1stID(}}|\|simult=)", zt):
                    zt = zt.replace("{{1stID", f"{{{{1stID|{title}")
                ct += zt.count("{")
                ct -= zt.count("}")
                final_items.append(c)
                new_text.append(zt)
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


def build_card_text(o: ItemId, c: ItemId):
    ot = c.current.original
    if c.current.subset and "subset=" not in ot:
        ot = re.sub("({{[^|}]*?\|(set=)?[^|}]*?\|(s?text=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
    while ot.count("|subset=") > 1:
        ot = re.sub("(\|subset=.*?)\1", "\1", ot)
    if o.master.template and o.master.master_page:
        ot = re.sub("\{\{([A-z0-9]+)\|.*?\|(url=|subset=|scenario=|pack=|cardname=|(swg)?(alt)?link=)", re.sub("\|p=.*?(\|.*?)?}}", "\\1", o.master.original.replace("}}", "")) + "|\\2", ot)
    if o.master.template == "SWIA" and "text" in ot:
        ot = re.sub("\|set=(.*?)\|text=''\\1''", "|set=\\1", ot)
    ot = re.sub("(\{\{.*?\|set=(.*?))\|s?text=\\2\|", "\\1|", ot)
    ot = re.sub("(\|set='*?(.*?)\|stext=.*?)\|'*?\\2'*?\|", "\\1", ot)
    ot = re.sub("\{\{SWU\|(.*?)( \(.*?\))?\|'*\\1'*\|", "{{SWU|set=\\1|", ot)
    ot = re.sub("\{\{SWU\|(?!(cardname=|set=))", "{{SWU|set=", ot)
    ot = re.sub("\|stext=(.*?)\|\\1\|", "|stext=\\1|", ot)
    ot = ot.replace("–", "&ndash;").replace("—", "&mdash;").replace("  ", " ").replace("|parent=1", "")
    return ot


def build_item_text(o: ItemId, d: str, nl: str, sl: str, final_without_extra: list, final_items: List[ItemId],
                    new_text: list, section_name, title, collapse_audiobooks: bool, nc: str, unlicensed: bool,
                    log: bool, is_file=False):
    zt = o.current.original if o.use_original_text else o.master.original
    if not zt.strip():
        return 0
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


def find_matching_audiobook(a: ItemId, existing: list, appearances: FullListData, abridged: list):
    if not a.master.target:
        return []
    elif f"{a.master.target} (novelization)" in existing or f"{a.master.target} (novel)" in existing:
        return []
    elif any(a.master.target.endswith(f"({z})") for z in ["audio", "short story", "comic"]):
        return []

    z = None
    if a.master.target in appearances.parantheticals:
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
    if a.master.parent in appearances.parantheticals:
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


def get_analysis_from_page(target: Page, infoboxes: dict, types, disambigs, appearances: FullListData,
                           sources: FullListData, remap: dict, log=True, collapse_audiobooks=True):
    results, unknown, redirects = build_page_components(target, types, disambigs, appearances, sources, remap,
                                                        infoboxes,False, log)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    _, _, _, analysis = analyze_section_results(target, results, disambigs, appearances, sources, remap, True,
                                                False, collapse_audiobooks, [], log)
    return analysis
