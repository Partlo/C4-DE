import re
import time
import traceback
from datetime import datetime, timedelta

from pywikibot import Page

from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("<br>", "<br />"),
    ("Youtube", "YouTube"), ("{{Scrollbox", "{{ScrollBox"), ("referneces", "references"), ("{{MO}}", "{{Mo}}"),
    ("{{scrollbox", "{{ScrollBox"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"), ("†", "&dagger:"),
    ("{{SWArchive|subdomain=cargobay|url=webapps/cargobay/", "{{CargoBay|url="),

    ("[[B1-Series battle droid]]", "[[B1-series battle droid/Legends|B1-series battle droid]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I/Legends|Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter/Legends|''Vulture''-class starfighter]]"),
    ("[[Variable Geometry Self-Propelled Battle Droid, Mark I]]", "[[Vulture-class starfighter|''Vulture''-class starfighter]]"),

    ("Tales of the Jedi —", "Tales of the Jedi –"), ("Tales of the Jedi &mdash;", "Tales of the Jedi –"),
    ("StarWarsKidsCite|year=1999", "Kids1999Cite"),  ("StarWarsKidsCite|year=1998", "Kids1998Cite"),
    ("StarWarsKidsCite|year=1997", "Kids1997Cite"),  ("StarWarsKidsCite", "Kids1997Cite"),


    ("Red Five (Star Wars Insider)", "Red Five (department)"),
    ("A Certain Point of View (Star Wars Insider)", "A Certain Point of View (department)"),

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
]


UNIDENTIFIED_CATEGORIES = ["Mandalorians", "Aqualish", "Bith", "Chagrians", "Chiss", "Duros", "Ewoks", "Gamorreans", "Gran", "Grysks", "Hutts", "Ithorians", "Jawas", "Mirialans", "Mon Calamari", "Neimoidians", "Patitites", "Quarren", "Rodians", "Sullustans", "Togruta", "Trandoshans", "Twi'leks", "Weequays", "Wookiees", "Yuuzhan Vong", "Zabrak", "Zeltrons", "humans", "wampas", "males", "females", "bounty hunters", "nobility", "clone troopers", "clone cadets", "clone commandos", "clone officers", "clone trooper pilots", "clone trooper sergeants", "Advanced Recon Commandos",]


def initial_cleanup(target: Page, all_infoboxes, before: str=None, keep_page_numbers=False):
    # now = datetime.now()
    if not before:
        before = target.get(force=True)
    before = before.replace("\u202c", "")
    # print(f"retrieval: {(datetime.now() - now).microseconds / 1000} microseconds")
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(
            "(]]|}})(\{+ ?(1st[A-z]*|[A-z][od]|[Ll]n|[Uu]n\|[Nn]cm?|[Cc]|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Nn]cs?|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene) ?[|}])",
            "\\1 \\2", before)

    for c in UNIDENTIFIED_CATEGORIES:
        if f"Category:Unidentified {c}" in before:
            before = before.replace(f"Category:Unidentified {c}|", f"Category:{c[0].capitalize()}{c[1:]}|").replace(f"Category:Unidentified {c}]", f"Category:{c[0].capitalize()}{c[1:]}]")
    for c in ["fathers", "brothers", "grandfathers", "husbands", "nephews", "sons", "uncles"]:
        if f"Category:Unidentified {c}" in before:
            before = before.replace(f"Category:Unidentified {c}", "Category:Males")
    for c in ["mothers", "sisters", "grandmothers", "wives", "daughters", "aunts"]:
        if f"Category:Unidentified {c}" in before:
            before = before.replace(f"Category:Unidentified {c}", "Category:Females")

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
        before, infobox = handle_infobox_on_page(before, target, all_infoboxes, False)
    # print(f"infobox: {(datetime.now() - now).microseconds / 1000} microseconds")

    before = re.sub("=+ ?([Rr]eferences?|[Nn]otes? (and )?[Rr]ef.*?) ?=+", "==Notes and references==", before)
    before = re.sub("= ?Non-[Cc]anon [Aa]ppearances ?=", "=Non-canon appearances=", before)
    before = re.sub("= ?([Cc]ollections?|Collected [Ii]n) ?=", "=Collections=", before)
    before = re.sub("=+ ?'*Non-canonical (appearances|sources)'* ?=+", "===Non-canon \\1===", before)
    before = re.sub("\n===(Merchandis(e|ing)(.*?)|Adaptations?|Tie[ -]ins?( media)?)===", "\n==Adaptations==", before)
    if "<references" in before.lower():
        before = re.sub("<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)

    # now = datetime.now()
    before = re.sub("(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = before.replace("||text=", "|text=").replace("|Parent=1", "|parent=1")
    before = before.replace("{{C|non-canon|reprint=1}}", "")
    before = before.replace("\"/>", "\" />").replace("<nowiki>|</nowiki>", "&#124;")
    before = re.sub("</ref>([A-z])", "</ref> \\1", before)
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

    before = re.sub("(\[\[[^\n\[{|]+)\|(an?) ([^\n|\[{]+?)]]", "\\2 \\1|\\3]]", before)

    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub("\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub("\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)
    before = re.sub("(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)

    before = re.sub("(\|set=(.*?))\|sformatted=''\\2''", "\\1", before)

    before = re.sub("\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub("(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)
    before = re.sub("(\{\{([A-z_ ]+)\|(set=)?[^|=\n}]+?)(\|link=[^|\n}]+?)(\|cardname=[^|\n}]+?)(\|[^\n}]*?)?}}", "\\1\\5\\4\\6}}", before)

    before = re.sub("\{\{[Ii]ncomplete[ _]?[Ll]ist.*?}}\n?\{\{(App|Credits)", "{{Incomplete\\1}}\n{{\\1", before)
    before = re.sub("\{\{[Ii]ncomplete[ _][Ll]ist(.*?)}}", "{{IncompleteList\\1}}", before)
    before = re.sub("\{\{[Ss]ee[ _]also", "{{SeeAlso", before)
    before = re.sub("\{\{[Mm]ore[ _]sources}}", "{{MoreSources}}", before)
    before = re.sub("\{\{[Ss](uccession|tart)[ _]box", "{{S\\1Box", before)
    before = re.sub("\{\{[Ee]nd[ _]box", "{{EndBox", before)
    before = re.sub("\{\{[Mm]ultiple[ _]issues", "{{MultipleIssues", before)
    before = re.sub("\{\{[Cc]orrect[ _]title", "{{CorrectTitle", before)

    before = re.sub("( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\\1+", "\\1", before)

    # temp fixes
    before = re.sub("(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)

    # before = re.sub("(\{\{TOMCite\|[0-9]+\|Database)\|.*?}}", "\\1}}", before)
    before = re.sub("\{\{(Legion|Armada|FFGXW2?|SWIA|Shatterpoint|Destiny)\|([^\n|{}=]+)}}", "{{\\1|set=\\2}}", before)

    while re.search("\[\[Category:[^\n|\]_]+_", before):
        before = re.sub("(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
    # print(f"regex-1: {(datetime.now() - now).microseconds / 1000} microseconds")

    if not keep_page_numbers:
        check_multi = False
        if "{{PageNumber}}" in before:
            before = re.sub("\">(((?!\{\{PageNumber)[^\n<])+? ?(['\"]*[\[{]+[^\n\[{]*?[}\]]+['\"]*),? ?(pa?ge?\.?|p?p\.|chapters?|ch\.) ?([0-9-]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen)(?!]),?</ref>)", "\">{{PageNumber}} \\1", before)
            for x in re.findall("((<ref name=\"([^\"\n>]+?)\")>\{\{PageNumber}} ?(['\"]*[\[{]+[^\n\[{]*?[}\]]+['\"]*),? ?(pa?ge?\.?|p?p\.|[Cc]hapters?|ch\.) ?([0-9-]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen)(?!])[,.]?</ref>)", before):
                if before.count(f"\">{x[3]}") == 0:
                    zy = x[1].replace(f":{x[5]}\"", '"')
                    if zy.endswith(f"{x[5]}\"") and x[5] not in x[3]:
                        zy = zy.replace(f"{x[5]}\"", '"')
                    before = before.replace(x[0], f"{zy}>{x[3]}</ref>")
                    before = before.replace(x[1], zy)
                elif before.count(f"\">{x[3]}<") > 0:
                    z = re.search("(<ref name=\"[^\"\n>]+?\")>" + re.escape(x[3]) + "</ref>", before)
                    if z:
                        before = before.replace(x[0], f"{z.group(1)} />").replace(x[1], z.group(1))
                        check_multi = True

            # before = re.sub("(<ref name=\"[^\"\n>]\">)\{\{PageNumber}} ?(((?!</ref>)[^\n])*?\[+((?!</ref>)[^\n])*?]+'*),? ?(pa?ge?\.?|p?p\.|chapters?|ch\.) ?([0-9-]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen)[,.]?( [A-z0-9, \[\]'-]{5}.*?</ref>)",
            #                 "\\1\\2\\7", before)
        if check_multi:
            before = re.sub("(<ref name=\"[^\"\n>]+?\")(>((?!<ref)[^\n])*?</ref>| ?/>)(((?!<ref).)*?)\\1 ?/>", "\\4\\1\\2", before)

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
    if "<nowiki>|" in before:   # TODO: check if still necessary
        while re.search("<nowiki>(\|.*?\|.*?)</nowiki>", before):
            before = re.sub("<nowiki>\|(.*?)\|(.*?)?</nowiki>", "<nowiki>|\\1&#124;\\2</nowiki>", before)
        before = re.sub("<nowiki>\|(.*?)</nowiki>", "&#124;\\1", before)
    if "cardname=" in before:
        before = re.sub("(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
        before = before.replace("cardname=\n", "cardname=")
    if "web.archive" in before:
        before = re.sub("(?<!\[)\[https?://(.*?) (.*?)] (\(|\{\{C\|)\[http.*?web.archive.org/web/([0-9]+)/https?://.*?\\1.*?][)}]+","{{WebCite|url=https://\\1|text=\\2|archivedate=\\4}}", before)
    if "width=100%" in before:
        before = re.sub("\{\{[Ss]croll[ _]?[Bb]ox(\n?\|.*?)?\n?\|width=100%", "{{ScrollBox\\1", before)
    if "simultaneous with" in before:
        before = re.sub("<small>\(First appeared(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
        before = re.sub("<small>\(First mentioned(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
    # if "*[[wikipedia:" in before.lower() or "source=[[wikipedia:" in before.lower():
    #     before = re.sub("(\n\*|\">|ref>|source=)\[\[[Ww]ikipedia:(.*?)\|(.*?)]]( on (\[\[Wikipedia.*?]]|Wikipedia))?","\\1{{WP|\\2|\\3}}", before)
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub("\*'*\[\[:?([Ww]|Wikia):c:([^\n|]]*?):([^\n|]]*?)\|([^\n]]*?)]] (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\2|\\8|\\3|\\4}}", before)
    if "memoryalpha:" in before.lower():
        before = re.sub("\[\[([Mm]emory[Aa]lpha|w:c:memory-alpha):(.*?)\|(.*?)]] (on|at) (the )?.*?([Mm]emory[Aa]lpha:|Wikipedia:Memory Alpha).*?\|.*?]](,.*?$)?", "{{MA|\\2|\\3}}", before)

    if "oldversion=1" in before:
        before = re.sub("(\|archive(date|url)=([^|\n}{]+))(\|[^\n}{]*?)?\|oldversion=1", "|oldversion=\\3\\4", before)
        before = re.sub("\|oldversion=1(\|[^\n}{]*?)?(\|archive(date|url)=([^|\n}{]+))", "|oldversion=\\4\\1", before)

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
    if "{{Blog|" in before:
        before = re.sub("(\{\{Blog\|(official=true\|)?[^|\n}\]]+?\|[^|\n}\]]+?\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
        before = re.sub("(\{\{Blog\|listing=true\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
    if "SWGTCG" in before:
        before = re.sub("(\{\{SWGTCG\|.*?)}} {{C\|(.*?scenario.*?)}}", "\\1|scenario=\\2}}", before)
    if "{{Visions" in before:
        before = re.sub("\{\{Visions(Cite)?(\|.*?focus)=(?!1).*?(\|.*?)?}}", "{{Visions\\2=1\\3}}", before)
        before = re.sub("\{\{Visions(Cite)?(\|.*?}}) \{\{[Aa]mbig}}", "{{Visions\\1", before)
    if "{{Hunters|url=arena-news" in before:
        before = re.sub("\{\{Hunters\|url=arena-news/(.*?)/?\|", "{{ArenaNews|url=\\1|", before)
    if "{{Disney|books|" in before:
        before = re.sub("\{\{Disney\|books\|(.*?)\|", "{{Disney|subdomain=books|url=\\1|text=", before)
    if "ArtStation" in before:
        before = re.sub("(\{\{ArtStation(\|.*?)?)\|url=(.*?)(\|.*?)\|profile=\\1(\|.*?)?}}", "\\1|profile=\\2\\3\\4}}", before)
        before = re.sub("\{\{ArtStation\|url=(((?!profile=).)*?)}}", "{{ArtStation|profile=\\1}}", before)
    if "Rebelscum.com" in before or "TheForce.net" in before:
        before = re.sub("\*'*?\[(http.*?) (.*?)]'*? (on|at|-).*?\[\[(Rebelscum\.com|TheForce\.net).*]].*?\n","{{WebCite|url=\\1|text=\\2|work=\\4}}", before)
    return before
