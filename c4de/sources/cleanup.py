import re
from datetime import datetime, timedelta

from c4de.common import log_time
from pywikibot import Page

from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"),
    ("===Non-canonical appearances===\n*", "===Non-canon appearances===\n*"), ("\n*\n{{", "\n*{{"),
    ("==Traits and personality==", "==Personality and traits=="),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("<br>", "<br />"), ("{{InvalidCategory}}", ""),
    ("Youtube", "YouTube"), ("{{Scrollbox", "{{ScrollBox"), ("referneces", "references"), ("{{MO}}", "{{Mo}}"),
    ("{{C|variant cover only}}", "{{Vco}}"), ("{{C|Variant cover only}}", "{{Vco}}"),
    ("{{scrollbox", "{{ScrollBox"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"), ("†", "&dagger:"),
    ("<nowiki>|</nowiki>", "&#124;"), ("||text=", "|text="), ("|Parent=1", "|parent=1"),
    ("[[:category:", "[[:Category:"), ("[[category:", "[[Category:"), ("[[Image:", "[[File:"),
    ("{{IntroMissingTitle}} ", ""), ("{{IntroMissingTitle}}\n", ""),
    ("==Media==\n*{{ISBN|", "==Media==\n===Editions===\n*{{ISBN|"),
    ("\n==Back-cover summary==\n", "\n===Back-cover summary===\n"),
    ("{{App|characters=", "{{App\n|characters="), ("PenguinRandomHouse|old=1", "RandomHouseOld"),
    ("<onlyinclude>\n{{Incomplete_app}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("<onlyinclude>\n{{IncompleteApp}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("{{C|non-canon|reprint=1}}", ""), ("[[Category: ", "[[Category:"),

    ("[[Black]]", "[[Color/Legends|Black]]"),

    ("{{EncyclopediaCite|Padmé Amidala Naberrie}}", "{{EncyclopediaCite|Padmé Amidala}}"),
    ("set=Twilight of the Republic (Star Wars: Unlimited)", "set=Twilight of the Republic"),
    ("|work=[[Entertainment Weekly Books|''Entertainment Weekly'']]", ""),
    ("|work=''[[Wikipedia:Entertainment Weekly|Entertainment Weekly]]''", ""),
    ("|work=[[Wikipedia:Entertainment Weekly|''Entertainment Weekly'']]", ""),
]


EXTRA = r"\{+ ?(1st[A-z]*|[Cc]|V?[A-z][od]|[Ff]act|[Bb]ts[Oo]nly|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]c[ms]?|[Aa]mbig|[Aa]dvert|[Mm]ap[Pp]oint|[Cc]osmetic|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}]"


def clean_references(before):
    before = re.sub(r"<ref name ?=([^'\">]*?) ?[\"'] ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=([^'\">]*?) ?[\"'] ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"<ref name ?=[\"']([^'\" ]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=[\"']([^'\" ]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"<ref name ?=([^'\">]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=([^'\">]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"(<ref name=\"(.*?)\")>[ \n\t]*?</ref>", "\\1 />", before)
    before = re.sub(r"</ref>([A-z])", "</ref> \\1", before)
    before = re.sub(r"(<ref( name=\".*?\")?>)\*", "\\1", before)
    if "\n</ref>" in before:
        before = re.sub(r"(<ref name=((?!</ref>).)*?)\n</ref>", "\\1</ref>", before)
    return before.replace(r"\"/>", "\" />")


def initial_cleanup(target: Page, all_infoboxes, before: str=None, infobox_log=True):
    now = datetime.now()
    if not before:
        before = target.get(force=True)
    # priority fixes
    before = before.replace(r"\u202c", "")
    before = re.sub(r"(\{\{WebCite[^\n}]*?)\|title=(.*?}})", "\\1|text=\\2", before)
    before = before.replace("\n}}</ref>", "}}</ref>")
    before = re.sub(r"(\{\{(SWGcite|TORcite).*?)\|type=", "\\1|TORTYPE=", before)
    before = re.sub(r"((\{\{Top(\|.*?)?}})(\n.*?)*?)\n\{\{Top}}", "\\1", before)    # Duplicate {{Top}}

    # whitespace/spacing issues
    before = re.sub(r"\* +([A-z0-9'\[{])", "*\\1", before)
    before = re.sub(r"\n<br ?/?>(\n+==)", "\\1", before)
    before = re.sub(r"([A-z'0-9\]]+)  +([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub(r"\n[ ]+\n", "\n\n", before)

    log_time("retrieval", now)
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(r"(]]|}})(" + EXTRA + ")","\\1 \\2", before)

    # Handle title parameters in Template:Top
    before = handle_top_title(before, target.title())

    now = datetime.now()
    while "== " in before or " ==" in before:
        before = before.replace(r"== ", "==").replace(" ==", "==")
    for (x, y) in REPLACEMENTS:
        before = before.replace(x, y)

    # inline files, text/etc. in image field
    before = re.sub(r"([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub(r"\|image=(File:)?([A-Z0-9 _]+\..+)(?=\n)", "|image=[[File:\\2]]", before)
    before = re.sub(r"(\|image=\[\[File:[^\n\]]+?)\|.+?]]", "\\1]]", before)
    before = re.sub(r"(\|image=\[\[File:.*?)(\|alt=.*?)]]\n", "\\1]]\n\\2\\n", before)

    # multi-line templates, extra/wrong brackets, etc.
    before = re.sub(r"\{\{C\|([^\[{}]+)(]]}})", "{{C|[[\\1\\2", before)
    before = re.sub(r"(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub(r"([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub(r"\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub(r"\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub(r"(?<!\{)\{(\{\{[^\n{}]+}})(?!})", "\\1", before)
    before = re.sub(r"(?<!\{)(\{\{[^\n{}]+})(?!})", "\\1}", before)
    before = re.sub(r"(?<!\{)(\{[^\n{}]+}})(?!})", "{\\1", before)
    before = re.sub(r"(\{\{1st[A-z]*)\|\n}}", "\\1}}", before)
    before = re.sub(r"(\{\{1st[A-z]*\|[^|}\n]*?)\n}}", "\\1}}", before)
    before = re.sub(r"(\{\{[A-z0-9-]+[^{}\n]+?) *\n *}}", "\\1}}", before)
    before = re.sub(r"^([^\[\]\n]+\[\[[^\[\]\n]+)]]]+('*)", "\\1]]\\1", before)
    before = re.sub(r"\[\[(.*?)\|''\1'']]([ .,<])", "''[[\\1]]''\\2", before)
    before = re.sub(r"(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)
    before = before.replace(">'>{{", ">{{")
    # missing newline between listings or templates
    before = re.sub(r"(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)
    before = re.sub(r"(\{\{Quote\|[^\n{}]+?(\{\{[^\n{}]+?}})?[^\n{}]+?}})(?!\n)", "\\1\n", before)

    # fixing same-line infobox fields
    while re.search(r"(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", before):
        before = re.sub(r"(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", "\\1\n\\2", before)
    log_time("regex-0", now)

    now = datetime.now()
    infobox, original = None, None
    if all_infoboxes and not target.title().startswith("User:") and not target.title().startswith("File:"):
        before, infobox, original = handle_infobox_on_page(before, target, all_infoboxes, add=False, log=infobox_log)
    log_time("infobox", now)

    now = datetime.now()
    # fixing bad references
    before = clean_references(before)
    log_time("references", now)

    # section header issues
    now = datetime.now()
    before = re.sub(r"\n=([A-z ]+)==", "\n==\\1==", before)
    before = re.sub(r"==((?!Notes and references).)*?==(\n\{.*?}})?\n\{\{[Rr]eflist}}", "==Notes and references==\\2\n{{Reflist}}", before)
    before = re.sub(r"=+ ?([Rr]eferences?|[Nn]otes? (and )?[Rr]ef.*?) ?=+", "==Notes and references==", before)
    before = re.sub(r"= ?([Cc]ollections?|Collected [Ii]n) ?=", "=Collected in=", before)
    # before = re.sub(r"=+ ?'*Non-canon(ical)? ([Aa]ppearances|[Ss]ources)'* ?=+", "===Non-canon \\2===", before)
    before = re.sub(r"\n===(Merchandis(e|ing)(.*?)|Adaptations?|Tie[ -]ins?( media)?)===", "\n==Adaptations==", before)
    before = re.sub(r"(\n===?.*?)<ref name=.*?(/>|</ref>)(.*?==+) ?\n", "\\1\\3\n", before)
    if "<references" in before.lower():
        before = re.sub(r"<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)

    while re.search(r"\[\[(?!File:)([^\[\]{}\n]+?)&[mn]dash;([^\[\]{}\n]+?)]]", before):
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&ndash;([^\[\]{}\n]+?)]]", "[[\\1–\\2]]", before)
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&mdash;([^\[\]{}\n]+?)]]", "[[\\1—\\2]]", before)

    before = re.sub(r"(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = re.sub(r"({{[Ss]croll[_ ]?[Bb]ox\|)\*", "{{ScrollBox|\n*", before)
    before = re.sub(r"<small>\((.*?)\)</small>", "{{C|\\1}}", before)

    before = re.sub(r"(\{\{[A-z]+YouTube\|[^\n[\]{}]*?\|[^\n[\]{}]*?) \| ([^\n[\]{}]*?(\|[a-z]+=.*?)?}})", "\\1 &#124; \\2", before)
    before = re.sub(r"(\{\{Databank[^}\n]*?)\|title=", "\\1|text=", before)

    # removing work= parameters and prioritizing
    before = re.sub(r"(\{\{((?!([wW]ebCite|OfficialSite))[^{}\n])*?\|[^{}\n]+?)\|work=(\[\[[^]]+\|.*?]])?.*?(\|.*?)?}}", "\\1\\4}}", before)
    before = re.sub(r"(\{\{[A-z]+)(\|url=[^\n{}]+?)(\|(subdomain|uk|lang)=[^\n{}]+?)(\|[^\n{}]*?)?}}", "\\1\\3\\2\\5}}", before)

    b1, b2, b3 = before.partition(r"{{App\n")
    b3 = re.sub(r"\n?(\|(c-|l-)?(characters|organisms|droids|events|locations|organizations|species|vehicles|technology|miscellanea)=)\*", "\n\\1\n*", b3)
    before = f"{b1}{b2}{b3}"

    before = re.sub(r"(\[\[[^\n\[{|]+)\|(an?) ([^\n|\[{]+?)]]", "\\2 \\1|\\3]]", before)

    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub(r"\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub(r"\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)

    before = re.sub(r"\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub(r"(\|set=(.*?))\|sformatted=''\2''", "\\1", before)
    before = re.sub(r"(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)
    before = re.sub(r"(\{\{([A-z_ ]+)\|(set=)?[^|=\n}]+?)(\|link=[^|\n}]+?)(\|cardname=[^|\n}]+?)(\|[^\n}]*?)?}}", "\\1\\5\\4\\6}}", before)

    before = re.sub(r"\{\{[Ii]ncomplete[ _]?[Ll]ist.*?}}\n?\{\{(App|Credits)", "{{Incomplete\\1}}\n{{\\1", before)
    before = re.sub(r"( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\1+", "\\1", before)

    # Visual Editor fix, can't remove
    before = re.sub(r"\[\[(.*?) (.*?)\|('*\1'*)]] \[\[\1 \2\|\2]]", "[[\\1 \\2|\\3 \\2]]", before)

    # temp fixes
    before = re.sub(r"'*\[\[Fortnite]]'* ?&[mn]dash; ?'*\[\[(.*?)(\|.*?)?]]'*", "{{Fortnite|\\1}}", before)
    before = re.sub(r"\{\{InsiderCite\|link=(.*?)(.*?)\|''\1''\2\|(.*?)}}", "{{StoryCite|book=\\1|story=\\3}}", before)
    before = re.sub(r"'*\[(https?://[w.]*?archive.org/.*?) (.*?)]'* (on|at)( the)? ('*\[https?://[w.]*archive\.org/? )?Internet Archive]?'*", "{{WebCite|url=\\1|text=\\2}}", before)
    before = re.sub(r"(\{\{GalaxyMapAppendix}})( |&.dash;)*[Bb]ased on (corresponding )?(info(rmation)?|data) for (the )?(\[\[((?! and ).)*?]]).?</ref>", "\\1 &mdash; Based on corresponding data for the \\7</ref>", before)

    before = re.sub(r">'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r">'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r"'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", "\"[[\\1]]\"", before)
    before = re.sub(r"'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", "\"[[\\1]]\"", before)

    before = re.sub(r"\{\{GameSpot\|subdomain=(.*?)\|url=(.*?)\|text=(.*?)(\|.*?)?}}", "{{WebCite|url=https://\\1.gamespot.com/\\2|text=\\3\\4}}", before)
    before = re.sub(r"\{\{GameSpot\|url=(.*?)\|text=(.*?)(\|.*?)?}}", "{{WebCite|url=https://www.gamespot.com/\\1|text=\\2\\3}}", before)
    before = re.sub(r"\[\[Category:Articles with /LEGO.*?\n", "", before)
    before = re.sub(r"\n\[\[Category:Articles with /LEGO.*?]](\{\{.*?}})?$", "", before)

    before = re.sub(r">\[\[Star Wars Galaxy Map \(poster\)\|[^\n\]\[]+]]<", ">{{GalaxyMapPoster}}<", before)
    before = re.sub(r">The \[\[Star Wars Galaxy Map \(poster\)\|[^\n\]\[]+]]", ">The {{GalaxyMapPoster}}", before)
    if "{{TradeRoute" not in before:
        before = re.sub(r"(\*\{\{(StarWarsGalaxyMap|TheStarWarsGalaxy}})}})\n", "*{{StarWarsGalaxyMap}} {{MapPoint}}\n", before)

    while re.search(r"\[\[Category:[^\n|\]_]+_", before):
        before = re.sub(r"(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
    log_time("regex-1", now)

    now = datetime.now()
    before = regex_cleanup(before)
    log_time("regex-2", now)
    if "{{C|unlicensed}}" in before:
        before = re.sub(r"( {{[Cc]\|[Uu]nlicensed}})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub(r"\{\{[Mm]entioned[ _]only\|?}}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace(r"‎", "")
        print(f"Found ‎ in {target.title()}")
    return before, infobox, original


def regex_cleanup(before: str) -> str:
    if before.count(r"==Appearances==") > 1:
        before = re.sub(r"(==Appearances==(\n.*?)+)\n==Appearances==", "\\1", before)
    if before.count(r"==Sources==") > 1:
        before = re.sub(r"(==Sources==(\n.*?)+)\n==Sources==", "\\1", before)

    if "{{SWU" in before:
        before = re.sub(r"(\{\{SWU\|.*?cardname=[^\n{}]+?)&mdash;([^\n{}]+?}})", "\\1|subtitle=\\2", before)

    if "<nowiki>|" in before:
        while re.search(r"<nowiki>(\|.*?\|.*?)</nowiki>", before):
            before = re.sub(r"<nowiki>\|(.*?)\|(.*?)?</nowiki>", "<nowiki>|\\1&#124;\\2</nowiki>", before)
        before = re.sub(r"<nowiki>\|(.*?)</nowiki>", "&#124;\\1", before)
    if "cardname=" in before:
        before = re.sub(r"(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
        before = before.replace(r"cardname=\n", "cardname=")
    if "web.archive" in before:
        before = re.sub(r"(?<!\[)\[https?://(.*?) (.*?)] (\(|\{\{C\|)\[http.*?web.archive.org/web/([0-9]+)/https?://.*?\1.*?][)}]+","{{WebCite|url=https://\\1|text=\\2|archivedate=\\4}}", before)
    if "width=100%" in before:
        before = re.sub(r"\{\{[Ss]croll[ _]?[Bb]ox(\n?\|.*?)?\n?\|width=100%", "{{ScrollBox\\1", before)
    if "simultaneous with" in before:
        before = re.sub(r"<small>\(First appeared(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
        before = re.sub(r"<small>\(First mentioned(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?)]?]? (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|\]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\9|\\4|\\5}}", before)
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?) (on|at) (the )?(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\8|\\4|\\5}}", before)

    if "oldversion=1" in before:
        before = re.sub(r"(\|archive(date|url)=([^|\n}{]+))(\|[^\n}{]*?)?\|oldversion=1", "|oldversion=\\3\\4", before)
        before = re.sub(r"\|oldversion=1(\|[^\n}{]*?)?(\|archive(date|url)=([^|\n}{]+))", "|oldversion=\\4\\1", before)

    if "|work=" in before:
        before = re.sub(r"\|work='*?(Slash Film|/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)'*?(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(E!|Empire|Encyclopædia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(E!|Empire|Encyclopædia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(TheForce\.net|Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)( \(.*?\))?\|.*?]]'*", "", before)

    return re.sub(r"(\{\{[A-z0-9 _]+\|.*?\|(.*?) \(.*?\))\|\2}}", "\\1}}", before)


def handle_top_title(before: str, target: str):
    x, _, y = target.replace("/Legends", "").replace("/Canon", "").partition(" (")
    for z in ["{{PAGENAME}}", x, target]:
        for i in ["|", "}"]:
            before = before.replace(f"|title=''{z}''{i}", f"|italics=1{i}")
            if f"Otheruses|title={z}" in before:
                before = re.sub(r"(\{\{Top.*?)\|title=" + z + r"(\|.*?)?}}", "\\1\\2", before)
            else:
                before = before.replace(f"|title={z}{i}", f"{i}")
    if y:
        y = y.replace(")", "").strip()
        if f"|title2=''{y}''" in before:
            before = before.replace(f"|title2=''{y}''", "|italics2=1")
        elif f"|title2={y}" in before:
            before = before.replace(f"|title2={y}", "")
    return before
