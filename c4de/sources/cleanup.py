import re
import time
import traceback
from datetime import datetime, timedelta

from pywikibot import Page

from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("referene", "reference"), ("Note and references", "Notes and references"),
    ("Notes and reference=", "Notes and references="), ("==References==", "==Notes and references=="),
    ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"), ("{{MO}}", "{{Mo}}"),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("DisneyPlusYT", "DisneyPlusYouTube"), ("<br>", "<br />"),
    ("Youtube", "YouTube"), ("{{Shortstory", "{{StoryCite"), ("{{Scrollbox", "{{Scroll_box"),
    ("{{scrollbox", "{{Scroll_box"), ("FFCite", "FactFile"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"),
    ("[[B1-Series battle droid]]", "[[B1-series battle droid/Legends|B1-series battle droid]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I/Legends|Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter/Legends|''Vulture''-class starfighter]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter|''Vulture''-class starfighter]]"),

    ("Tales of the Jedi —", "Tales of the Jedi –"), ("Tales of the Jedi &mdash;", "Tales of the Jedi –"),
    ("FactFile|year=", "FactFile|y="), ("Category:Images from Star Wars Legion - Clone Wars Core Set", "Images from the Clone Wars Core Set"),
    ("Vader Immortal: A Star Wars VR Series – Episode", "Vader Immortal – Episode"),
    ("Red Five (Star Wars Insider)", "Red Five (department)"),
    ("A Certain Point of View (Star Wars Insider)", "A Certain Point of View (department)"),
    (" (Disney Gallery: The Mandalorian)}}", "}}"), ("Carlissian", "Calrissian"),
    (" (Disney Gallery: The Mandalorian episode)}}", "}}"),
    ("Star Wars: Legion - Clone Wars Core Set|Clone Wars Core Set", "set=Clone Wars Core Set"),
    ("Star Wars: Legion - Clone Wars Core Set|", "set=Clone Wars Core Set|"),
    ("set=Imperial Raider Expansion Pack (Star Wars: X-Wing Miniatures Game)", "set=Imperial Raider Expansion Pack"),

    ("[[First-degree droid]]", "[[Class one droid/Legends|Class one droid]]"),
    ("[[First-degree droid|First-degree]]", "[[Class one droid/Legends|Class one]]"),
    ("[[First-degree droid|", "[[Class one droid/Legends|"),
    ("[[first-degree droid]]", "[[Class one droid/Legends|class one droid]]"),
    ("[[Second-degree droid]]", "[[Class two droid/Legends|Class two droid]]"),
    ("[[Second-degree droid|Second-degree]]", "[[Class two droid/Legends|Class two]]"),
    ("[[Second-degree droid|", "[[Class two droid/Legends|"),
    ("[[second-degree droid]]", "[[Class two droid/Legends|class two droid]]"),
    ("[[Third-degree droid]]", "[[Class three droid/Legends|Class three droid]]"),
    ("[[Third-degree droid|Third-degree]]", "[[Class three droid/Legends|Class three]]"),
    ("[[Third-degree droid|", "[[Class three droid/Legends|"),
    ("[[third-degree droid]]", "[[Class three droid/Legends|class three droid]]"),
    ("[[Fourth-degree droid]]", "[[Class four droid/Legends|Class four droid]]"),
    ("[[Fourth-degree droid|Fourth-degree]]", "[[Class four droid/Legends|Class four]]"),
    ("[[Fourth-degree droid|", "[[Class four droid/Legends|"),
    ("[[fourth-degree droid]]", "[[Class four droid/Legends|class four droid]]"),
    ("[[Fifth-degree droid]]", "[[Class five droid/Legends|Class five droid]]"),
    ("[[Fifth-degree droid|Fifth-degree]]", "[[Class five droid/Legends|Class five]]"),
    ("[[Fifth-degree droid|", "[[Class five droid/Legends|"),
    ("[[fifth-degree droid]]", "[[Class five droid/Legends|class five droid]]"),

    ("[[First class droid]]", "[[Class one droid]]"),
    ("[[First class droid|First class]]", "[[Class one droid|Class one]]"),
    ("[[First class droid|Class 1]]", "[[Class one droid|Class one]]"),
    ("[[First class droid|class 1]]", "[[Class one droid|class one]]"),
    ("[[First class droid|Class one droid]]", "[[Class one droid]]"),
    ("[[First class droid|class one droid]]", "[[class one droid]]"),
    ("[[First class droid|", "[[Class one droid|"),
    ("[[first class droid]]", "[[class one droid]]"),

    ("[[Second class droid]]", "[[Class two droid]]"),
    ("[[Second class droid|Second class]]", "[[Class two droid|Class two]]"),
    ("[[Second class droid|Class 2]]", "[[Class two droid|Class two]]"),
    ("[[Second class droid|class 2]]", "[[Class two droid|class two]]"),
    ("[[Second class droid|Class two droid]]", "[[Class two droid]]"),
    ("[[Second class droid|class two droid]]", "[[class two droid]]"),
    ("[[Second class droid|", "[[Class two droid|"),
    ("[[second class droid]]", "[[class two droid]]"),

    ("[[Third class droid]]", "[[Class three droid]]"),
    ("[[Third class droid|Third class]]", "[[Class three droid|Class three]]"),
    ("[[Third class droid|Class 3]]", "[[Class three droid|Class three]]"),
    ("[[Third class droid|class 3]]", "[[Class three droid|Class three]]"),
    ("[[Third class droid|Class three droid]]", "[[Class three droid]]"),
    ("[[Third class droid|class three droid]]", "[[class three droid]]"),
    ("[[Third class droid|", "[[Class three droid|"),
    ("[[third class droid]]", "[[class three droid]]"),

    ("[[Fourth class droid]]", "[[Class three droid]]"),
    ("[[Fourth class droid|Fourth class]]", "[[Class three droid|Class three]]"),
    ("[[Fourth class droid|Class 4]]", "[[Class four droid|Class four]]"),
    ("[[Fourth class droid|class 4]]", "[[Class four droid|Class four]]"),
    ("[[Fourth class droid|Class four droid]]", "[[Class four droid]]"),
    ("[[Fourth class droid|class four droid]]", "[[class four droid]]"),
    ("[[Fourth class droid|", "[[Class four droid|"),
    ("[[fourth class droid]]", "[[class four droid]]"),

    ("[[Fifth class droid]]", "[[Class five droid]]"),
    ("[[Fifth class droid|Fifth class]]", "[[Class five droid|Class five]]"),
    ("[[Fifth class droid|Class 5]]", "[[Class five droid|Class five]]"),
    ("[[Fifth class droid|class 5]]", "[[Class five droid|class five]]"),
    ("[[Fifth class droid|Class five droid]]", "[[Class five droid]]"),
    ("[[Fifth class droid|class five droid]]", "[[class five droid]]"),
    ("[[Fifth class droid|", "[[Class five droid|"),
    ("[[fifth class droid]]", "[[class five droid]]"),
    ("[[2-1B-series medical droid]]", "[[2-1B surgical droid]]"),
]


def initial_cleanup(target: Page, all_infoboxes, before: str=None):
    # now = datetime.now()
    if not before:
        before = target.get(force=True)
    # print(f"retrieval: {(datetime.now() - now).microseconds / 1000} microseconds")
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(
            "(]]|}})(\{+ ?(1st[A-z]*|[A-z][od]|[Ll]n|[Uu]n\|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[|}])",
            "\\1 \\2", before)

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

    # now = datetime.now()
    infobox = None
    if all_infoboxes and not target.title().startswith("User:") and not target.title().startswith("File:"):
        before, infobox = handle_infobox_on_page(before, target, all_infoboxes)
    # print(f"infobox: {(datetime.now() - now).microseconds / 1000} microseconds")

    before = re.sub("= ?Non-[Cc]anon [Aa]ppearances ?=", "=Non-canon appearances=", before)
    before = re.sub("= ?([Cc]ollections?|Collected [Ii]n) ?=", "=Collections=", before)
    before = re.sub("=+'*Non-canonical (appearances|sources)'*=+", "===Non-canon \\1===", before)
    before = re.sub("\n===(Merchandis(e|ing)(.*?)|Adaptations?|Tie[ -]ins?( media)?)===", "\n==Adaptations==", before)
    if "<references" in before.lower():
        before = re.sub("<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)

    # now = datetime.now()
    before = re.sub("(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = before.replace("||text=", "|text=")
    before = before.replace("{{C|non-canon|reprint=1}}", "")
    before = before.replace("\"/>", "\" />").replace("<nowiki>|</nowiki>", "&#124;")
    before = re.sub("(\{\{1st[A-z]*)\|\n}}", "\\1}}", before)
    before = re.sub("(\{\{1st[A-z]*\|[^|}\n]*?)\n}}", "\\1}}", before)
    before = re.sub("\n=([A-z ]+)==", "\n==\\1==", before)
    before = re.sub("(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub("({{[Ss]croll[_ ]?[Bb]ox\|)\*", "{{ScrollBox|\n*", before)
    before = re.sub("([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub("\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub("^(.*?) +\n", "\\1\n", before)
    before = re.sub("\* +([A-z0-9'\[{])", "*\\1", before)
    before = re.sub("([A-z'0-9\]]+)  +([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub("\|image=(File:)?([A-Z0-9 _]+\..+)\n", "|image=[[File:\\2]]", before)
    before = re.sub("(\|image=\[\[File:[^\n\]]+?)\|.*?]]", "\\1]]", before)
    before = re.sub("<small>\((.*?)\)</small>", "{{C|\\1}}", before)
    before = re.sub("([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub("\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub("\*\{\{\{([A-Z])", "*{{\\1", before)

    before = re.sub("(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
    before = before.replace("cardname=\n", "cardname=")

    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub("\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub("\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)
    before = re.sub("(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)

    before = re.sub("(\|set=(.*?))\|sformatted=''\\2''", "\\1", before)

    before = re.sub("\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub("(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)
    before = re.sub("(\{\{([A-z_ ]+)\|set=[^|\n]+?)(\|link=[^|\n}]+?)(\|cardname=[^|\n}]+?)(\|.*?)?}}", "\\1\\4\\3\\5}}", before)

    before = re.sub("\{\{[Ii]ncomplete[ _]?[Ll]ist.*?}}\n?\{\{(App|Credits)", "{{Incomplete\\1}}\n{{\\1", before)
    before = re.sub("\{\{[Ii]ncomplete[ _][Ll]ist(.*?)}}", "{{IncompleteList\\1}", before)
    before = re.sub("\{\{[Ss]ee[ _]also", "{{SeeAlso", before)
    before = re.sub("\{\{[Mm]ore[ _]sources}}", "{{MoreSources}}", before)
    before = re.sub("\{\{[Ss](uccession|tart)[ _]box", "{{S\\1Box", before)
    before = re.sub("\{\{[Ee]nd[ _]box", "{{EndBox", before)
    before = re.sub("\{\{[Mm]ultiple[ _]issues", "{{MultipleIssues", before)
    before = re.sub("\{\{[Cc]orrect[ _]title", "{{CorrectTitle", before)

    before = re.sub("( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\\1+", "\\1", before)

    # temp fixes
    before = re.sub("\{\{([A-z _]+)\|(.*?)( \(.*?\))\|\\2\|card", "{{\\1|set=\\2\\3|card", before)
    before = re.sub("(\{\{SWMiniCite\|set=.*?) \(Star Wars Miniatures\)", "\\1", before)
    before = re.sub("(\{\{Databank.*?}})( \{\{C\|alternate:.*?}})+", "\\1", before)
    before = before.replace("(Force Pack)", "(Star Wars: The Card Game)")
    before = re.sub("FFGXW2\|set=(.*?) \(Second Edition\)", "FFGXW2|set=\\1", before)
    before = re.sub("(\{\{SWIA\|.*?)}} \{\{C\|[A-z ]*?[Rr]ulebook}}", "\\1|rulebook=1}}", before)
    before = re.sub("(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)

    while re.search("\[\[Category:[^\n|\]_]+_", before):
        before = re.sub("(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
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
    return before, infobox


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
        before = re.sub("\{\{[Ss]croll[ _]?[Bb]ox(\n?\|.*?)?\n?\|width=100%", "{{ScrollBox\\1", before)
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
