import re
from datetime import datetime
from pywikibot import Page

from c4de.common import log_time
from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("Souces", "Sources"),  ("referneces", "references"),
    ("=Source=", "=Sources="), ("===Non-canonical appearances===\n*", "===Non-canon appearances===\n*"),
    ("==Work==", "==Works=="), ("==Traits and personality==", "==Personality and traits=="),
    ("==Media==\n*{{ISBN|", "==Media==\n===Editions===\n*{{ISBN|"),
    ("\n==Back-cover summary==\n", "\n===Back-cover summary===\n"),
    ("&#40;&#63;&#41;", "(?)"), ("<nowiki>|</nowiki>", "&#124;"), ("†", "&dagger:"), ("<br>", "<br />"),
    ('">*{{', '">{{'), (">*''[[", ">''[["), (">*[[", ">[["), (">'>{{", ">{{"), ("|Url=", "|url="),
    ("{{Scrollbox", "{{ScrollBox"), ("{{scrollbox", "{{ScrollBox"), ("{{mO}}", "{{Mo}}"), ("{{MO}}", "{{Mo}}"),
    ("{{c|", "{{C|"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"), ("\n*\n{{", "\n*{{"),
    ("||text=", "|text="), ("|Parent=1", "|parent=1"), ("Youtube", "YouTube"),
    ("[[:category:", "[[:Category:"), ("[[category:", "[[Category:"), ("[[Category: ", "[[Category:"), ("[[Image:", "[[File:"),

    ("{{C|variant cover only}}", "{{Vco}}"), ("{{C|Variant cover only}}", "{{Vco}}"), ("*{{Indexpage", "{{Indexpage"),
    ("{{InvalidCategory}}", ""), ("{{IntroMissingTitle}} ", ""), ("{{IntroMissingTitle}}\n", ""),
    ("{{App|characters=", "{{App\n|characters="), ("PenguinRandomHouse|old=1", "RandomHouseOld"),
    ("<onlyinclude>\n{{Incomplete_app}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("<onlyinclude>\n{{IncompleteApp}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("{{C|non-canon|reprint=1}}", ""),

    ("The Empire Strike Back", "The Empire Strikes Back"),
    ("[[Black]]", "[[Color/Legends|Black]]"), ("[[black]]", "[[Color/Legends|black]]"),
    ("parent=Riddell mini-helmet", "parent=Riddell"),

    ("''[[Order 66: A Republic Commando Novel]]''", "''[[Republic Commando: Order 66]]''"),
    ("''[[Republic Commando]]''", "[[Star Wars: Republic Commando (novel series)|''Star Wars: Repbulic Commando'']]"),
    ("[[The Jedi Path: A Manual for Students of the Force (real-life book)|''The Jedi Path: A Manual for Students of the Force'']]", "''[[Star Wars: The Jedi Path]]''"),
    ("[[The Jedi Path: A Manual for Students of the Force (real-life book)|''The Jedi Path'']]", "''[[Star Wars: The Jedi Path]]''"),
    ("[[Book of Sith: Secrets from the Dark Side|''Book of Sith'']]", "''[[Star Wars: Book of Sith]]''"),
    ("[[Book of Sith: Secrets from the Dark Side]]", "[[Star Wars: Book of Sith]]"),
    ("[[Star Wars: Imperial Handbook: A Commander's Guide]]", "[[Star Wars: Imperial Handbook]]"),
    ("[[The Bounty Hunter Code: From the Files of Boba Fett]]", "[[Star Wars: The Bounty Hunter Code]]"),
    ("{{EncyclopediaCite|Padmé Amidala Naberrie}}", "{{EncyclopediaCite|Padmé Amidala}}"),
]

EXTRA = r"\{+ ?(1st[A-z]*|[Cc]|V?[A-z][od]|[Bb]ts[Oo]nly|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]c[ms]?|[Aa]mbig|[Aa]dvert|[Mm]ap[Pp]oint|[Cc]osmetic|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}]"


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
    before = re.sub(r" ?\{\{(1st[A-z]*|[Mm]o)}}</ref>", "</ref>", before)
    if "\n</ref>" in before:
        before = re.sub(r"(<ref name=((?!</ref>).)*?)\n</ref>", "\\1</ref>", before)
    before = before.replace(r"\"/>", "\" />")
    before = handle_repeated_ve_references(before)
    before = handle_dupe_ve_references(before)
    return before


def initial_cleanup(target: Page, all_infoboxes, before: str=None, infobox_log=True):
    now = datetime.now()
    if not before:
        before = target.get(force=True)
    # priority fixes
    before = before.replace(r"\u202c", "")
    before = re.sub(r"(\{\{WebCite[^\n}]*?)\|title=(.*?}})", "\\1|text=\\2", before)
    before = before.replace("\n}}</ref>", "}}</ref>")
    before = re.sub(r"(\{\{(BookCite).*?)\|date=", "\\1|BOOKDATE=", before)
    before = re.sub(r"(\{\{(BookCite)[^}]*?)\n?\|date=", "\\1|BOOKDATE=", before)
    before = re.sub(r"(\{\{(SWGcite|TORcite).*?)\|type=", "\\1|TORTYPE=", before)
    before = re.sub(r"(\{\{(SWGcite|TORcite)[^}]*?)\n?\|type=", "\\1|TORTYPE=", before)
    before = re.sub(r"((\{\{Top(\|.*?)?}})(\n.*?)*?)\n\{\{Top}}", "\\1", before)    # Duplicate {{Top}}

    # whitespace/spacing issues
    before = re.sub(r"\* +([A-z0-9'\[{])", "*\\1", before)
    before = re.sub(r"\n<br ?/?>(\n+==)", "\\1", before)
    before = re.sub(r"([A-z'0-9\]]+)  +([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub(r"\n[ ]+\n", "\n\n", before)

    log_time("retrieval", now)
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(r"(]]|}})(" + EXTRA + ")","\\1 \\2", before)

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
    before = re.sub(r"^([^\[\]\n]+\[\[[^\[\]\n]+)]]]+('*)", "\\1]]\\2", before)
    before = re.sub(r"(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)
    # small-parentheses within wikilinks, unnecessary pipelink
    before = re.sub(r"\[\[(.*?)\|''\1'']]([ .,<])", "''[[\\1]]''\\2", before)
    before = re.sub(r"(\[\[[^\n[\]{}|]+\|[^\n[\]{}|]+) ?\{\{[Cc]\|(.*?)}}(.*?]])", "\\1(\\2)\\3", before)
    before = re.sub(r"(\[\[[^\n[\]{}|]+\|[^\n[\]{}|]+)<small>(\(.*?\))</small>(.*?]])", "\\1\\2\\3", before)
    # missing newline between listings or templates
    before = re.sub(r"(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)
    before = re.sub(r"(\{\{Quote\|[^\n{}]+?(\{\{[^\n{}]+?}})?[^\n{}]+?}})(?!\n)", "\\1\n", before)
    # Visual Editor fix, can't remove
    before = re.sub(r"\[\[(.*?) (.*?)\|('*\1'*)]] \[\[\1 \2\|\2]]", "[[\\1 \\2|\\3 \\2]]", before)
    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub(r"\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub(r"\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)

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

    # converting HTML dashes to the characters for ease of parsing
    while re.search(r"\[\[(?!File:)([^\[\]{}\n]+?)&[mn]dash;([^\[\]{}\n]+?)]]", before):
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&ndash;([^\[\]{}\n]+?)]]", "[[\\1–\\2]]", before)
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&mdash;([^\[\]{}\n]+?)]]", "[[\\1—\\2]]", before)

    before = re.sub(r"(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = re.sub(r"({{[Ss]croll[_ ]?[Bb]ox\|)\*", "{{ScrollBox|\n*", before)
    before = re.sub(r"<small>\((.*?)\)</small>", "{{C|\\1}}", before)

    # removing work= parameters and reordering parameters according to priority
    before = re.sub(r"(\{\{((?!([wW]ebCite|OfficialSite))[^{}\n])*?\|[^{}\n]+?)\|work=(\[\[[^]]+\|.*?]])?.*?(\|.*?)?}}", "\\1\\4}}", before)
    before = re.sub(r"(\{\{[A-z]+)(\|url=[^\n{}]+?)(\|(subdomain|uk|lang)=[^\n{}]+?)(\|[^\n{}]*?)?}}", "\\1\\3\\2\\5}}", before)
    before = re.sub(r"(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)
    before = re.sub(r"(\{\{([A-z_ ]+)\|(set=)?[^|=\n}]+?)(\|link=[^|\n}]+?)(\|cardname=[^|\n}]+?)(\|[^\n}]*?)?}}", "\\1\\5\\4\\6}}", before)

    b1, b2, b3 = before.partition(r"{{App\n")
    b3 = re.sub(r"\n?(\|(c-|l-)?(characters|organisms|droids|events|locations|organizations|species|vehicles|technology|miscellanea)=)\*", "\n\\1\n*", b3)
    before = f"{b1}{b2}{b3}"

    before = re.sub(r"(an? )?\[\[([^\n\[{|]+)\|(an?) ([^\n|\[{]+?)]]", "\\3 [[\\2|\\4]]", before).replace(" a a ", " a ").replace(" an an ", " an ")

    before = re.sub(r"\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub(r"(\|set=(.*?))\|sformatted=''\2''", "\\1", before)

    before = re.sub(r"( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\1+", "\\1", before)
    before = re.sub(r"( \{\{(Reprint|Ab)\|.*?}})\1+", "\\1", before)

    # temp fixes
    before = temp_regex_cleanup(before)
    while re.search(r"\[\[Category:[^\n|\]_]+_", before):
        before = re.sub(r"(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
    log_time("regex-1", now)

    if before.count(r"==Appearances==") > 1:
        before = re.sub(r"(==Appearances==(\n.*?)+)\n==Appearances==", "\\1", before)
    if before.count(r"==Sources==") > 1:
        before = re.sub(r"(==Sources==(\n.*?)+)\n==Sources==", "\\1", before)

    if "{{c|first" in before.lower():
        before = re.sub(r"\{\{[Cc]\|First appeared(, simultaneous with (.*?))?}}", "{{1st|\\2}}", before)
        before = re.sub(r"\{\{[Cc]\|First mentioned(, simultaneous with (.*?))?}}", "{{1st|\\2}}", before)
        before = re.sub(r"\{\{[Cc]\|First mentione?d?,? before (\[\[Retroac.*?\|)?[Rr]etcon]*, simultaneous with (.*?)}}", "{{1stmr|\\2}}", before)
        before = re.sub(r"\{\{[Cc]\|First mentione?d?,? before (\[\[Retroac.*?\|)?[Rr]etcon]*.*?}}", "{{1stmr}}", before)

    if "{{SWU" in before:
        before = re.sub(r"(\{\{SWU\|.*?cardname=[^\n{}]+?)&mdash;([^\n{}]+?}})", "\\1|subtitle=\\2", before)

    before = re.sub(r"(\{\{[A-z]*You[Tt]ube\|[^\n[\]{}]*?\|[^\n[\]{}]*?) \| ([^\n[\]{}]*?(\|[a-z]+=.*?)?}})", "\\1 &#124; \\2", before)
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
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?)]?]? (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|\]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\9|\\4|\\5}}", before)
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?) (on|at) (the )?(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\8|\\4|\\5}}", before)

    if "oldversion=1" in before:
        before = re.sub(r"(\|archive(date|url)=([^|\n}{]+))(\|[^\n}{]*?)?\|oldversion=1", "|oldversion=\\3\\4", before)
        before = re.sub(r"\|oldversion=1(\|[^\n}{]*?)?(\|archive(date|url)=([^|\n}{]+))", "|oldversion=\\4\\1", before)

    if "|work=" in before:
        before = re.sub(r"\|work='*?(Slash Film|/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|CBR|CBR\.com|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)'*?(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(E!|Empire|Encyclopædia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(E!|Empire|Encyclop.*?dia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(TheForce\.net|Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"(url=.*?//(.*?\.)?(ew|collider|aiptcomics|npr|rollingstonaveleyman|ign|cbr|theforce|nerdist|gameinformer|latimes|inverse|starwarsinterviews|jedi-bibliothek|swtor\.jedipedia)\..*?)\|work=.*?(\|[a-z ]+=.*?)?}}", "\\1\\4}}", before)

    before = re.sub(r"(\{\{[A-z0-9 _]+\|.*?\|(.*?) \(.*?\))\|\2}}", "\\1}}", before)

    if "{{c|unlicensed}}" in before.lower():
        before = re.sub(r"( {{[Cc]\|[Uu]nlicensed}})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub(r"\{\{[Mm]entioned[ _]only\|?}}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace(r"‎", "")
        print(f"Found ‎ in {target.title()}")
    return before, infobox, original


def temp_regex_cleanup(before):
    before = re.sub(r"(\{\{Databank[^}\n]*?)\|title=", "\\1|text=", before)
    before = re.sub(r"'*\[\[Fortnite]]'* ?&[mn]dash; ?'*\[\[(.*?)(\|.*?)?]]'*", "{{Fortnite|\\1}}", before)
    before = re.sub(r"(\{\{GalaxyMapAppendix}})( |&.dash;)*[Bb]ased on (corresponding )?(info(rmation)?|data) for (the )?(\[\[((?! and ).)*?]]).?</ref>", "\\1 &mdash; Based on corresponding data for the \\7</ref>", before)

    before = re.sub(r"'*\[\[Star Wars: Force Collection]]'* \{\{C\|Card: (.*?)}}", "{{ForceCollection|\\1}}", before)
    if "{{ForceCollection" in before:
        before = re.sub(r"(\{\{ForceCollection\|.*?) ?\(Special\)}}", "\\1|star=S}}", before)
    before = re.sub(r">'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r"'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", "\"[[\\1]]\"", before)
    before = re.sub(r">'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r"'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", "\"[[\\1]]\"", before)

    before = re.sub(r"\[\[(Star Wars: (A New Hope|The Empire Strikes Back|Return of the Jedi|Revenge of the Sith) \(novelization\))\|'*Star Wars[: ']+Episode [IV]+[: ']+\2'*( \(?novel[a-z]*\)?)?]]", "[[\\1|''Star Wars: \\2'' novelization]]", before)
    before = re.sub(r"\[\[((Star Wars: Shadows of the Empire) \(([a-z ]+?)\))\|'*(Star Wars: )?Shadows of the Empire'*( [a-z ]+)?]]", "[[\\1|''\\2'' \\3]]", before)
    before = re.sub(r"'*\[\[Star.Wars:.X-Wing.vs..TIE.Fighter#Expansion.pack\|.*?]]'*", "''[[Star Wars: X-Wing vs. TIE Fighter: Balance of Power]]''", before)
    before = re.sub(r"\[\[The Official Star Wars Fact File Part ([0-9]+)(\|.*?)?]]'* \{\{C\|(([0-9]+ )?[A-Z0-9]{2}[A-Z0-9]? .*?}})", "{{FactFile2014|\\1|\\3", before)
    before = re.sub(r"\{\{SWIA\|set=Star Wars: Imperial Assault Core Set(\|text=Core Set)?(\|.*?)?}}", "{{SWIA|set=Core Set\\2}}", before)

    return before


def do_final_replacements(new_txt, replace, is_status):
    new_txt = remove_links_from_quotes(new_txt)
    new_txt = new_txt.replace("TORTYPE", "type")
    new_txt = new_txt.replace("BOOKDATE", "date")
    new_txt = re.sub(r"(==(Sources|Appearances)==)\n\n(===Non-canon (appearances|sources)===)", "\\1\n\\3", new_txt)

    while replace:
        # restoring m/n dashes in wikilinks
        new_txt2 = re.sub(r"(\[\[(?!File:)[^\[\]|\n]+)&mdash;", "\\1—", new_txt)
        new_txt2 = re.sub(r"(\[\[(?!File:)[^\[\]|\n]+)&ndash;", "\\1–", new_txt2)
        new_txt2 = re.sub(r"(\[\[(?!File:)[^\[\]|\n]+—[^\[\]|\n]+\|[^\[\]|\n]+)&mdash;", "\\1—", new_txt2)
        new_txt2 = re.sub(r"(\[\[(?!File:)[^\[\]|\n]+–[^\[\]|\n]+\|[^\[\]|\n]+)&ndash;", "\\1–", new_txt2)

        new_txt2 = re.sub(r"\[\[([A-Z])(.*?)\|([a-z])\2(s)?]]", "[[\\3\\2]]\\4", new_txt2)
        new_txt2 = handle_repeated_references(new_txt2, is_status)
        new_txt2 = re.sub(r"----\n\n+\{\{", "----\n{{", new_txt2)
        # italicization & apostrophes
        new_txt2 = re.sub(r"([^']''[^' ][^']+?'')'s ", "\\1{{'s}} ", new_txt2)
        new_txt2 = re.sub(r"([^']''((?!-class)[^' ])+?[^']+?s'')' ", "\\1{{'}} ", new_txt2)
        new_txt2 = new_txt2.replace("{{'}}s", "{{'s}}")
        new_txt2 = new_txt2.replace("{{'}}\n", "{{'}}")
        new_txt2 = new_txt2.replace("\n\n*{{ISBN", "\n*{{ISBN")
        new_txt2 = new_txt2.replace(" </ref>", "</ref>")
        if "'''s " in new_txt2:
            new_txt2 = re.sub(r"( ''[^'\n]+'')'s ", "\\1{{'s}} ", new_txt2)

        new_txt2 = re.sub(r"(\|url=[^\n|{}]+?)/\|", "\\1|", new_txt2)
        if "stext=" in new_txt2 or "sformat" in new_txt2:
            new_txt2 = re.sub(r"(\|set=(.*?) \(.*?\))\|(s?text|sformatt?e?d?)=\2([|}])", "\\1\\4", new_txt2)
            new_txt2 = re.sub(r"(\|set=[^|{}\n]*?)(\|stext=[^|{}\n]*?)}}", "\\1}}", new_txt2)

        new_txt2 = re.sub(r"(\[\[((.*?) \((.*?)\)).*?]].*?)(\{\{Ab\|.*?)\[\[\2\|''\3'' \4]]", "\\1\\5[[\\2|\\4]]", new_txt2)
        new_txt2 = re.sub(r"(\{\{[^\n{}]+?)(\|nolive=1)([^\n{}]*?(\|nobackup=1)?[^\n{}]*?)}}", "\\1\\3\\2}}", new_txt2)
        new_txt2 = re.sub(r"(\{\{[^\n{}]+?)(\|nobackup=1)([^\n{}]+?)}}", "\\1\\3\\2}}", new_txt2)
        new_txt2 = re.sub(r"([\n[]File:[^ \n|\]\[]+) ", "\\1_", new_txt2)
        new_txt2 = re.sub(r"(\{\{1st[a-z]*)\|}}", "\\1}}", new_txt2)
        new_txt2 = re.sub(r"(\|[a-z]+=[^|{}\n]*)\1+", "\\1", new_txt2)

        if "''{{Film|" in new_txt2:
            new_txt2 = re.sub(r"(?<!')''(\{\{Film\|.*?}})'*", "\\1", new_txt2)

        new_txt2 = re.sub(r"(\{\{SWMiniCite\|set=[^\n}]+?\|)cardname=", "\\1pack=", new_txt2)
        new_txt2 = new_txt2.replace("[[Ochi]] of Bestoon", "[[Ochi|Ochi of Bestoon]]")
        new_txt2 = new_txt2.replace("[[Battle station/Legends|battlestation", "[[Battle station/Legends|battle station")
        if "{{more" in new_txt2.lower():
            new_txt2 = re.sub(r"\{\{[Mm]ore[Ss]ources}}\n+}}", "}}\n{{MoreSources}}", new_txt2)
        replace = new_txt != new_txt2
        new_txt = new_txt2
    return new_txt


def remove_links_from_quotes(new_txt):
    for x in re.findall(r"((\{\{[Qq]uote\|[^{}\[\]|\n]*)(\[\[([^{}\[\]\n]*?\|)?[^{}\[\]\n]*?]][^{}\n]*?)(\|audio=[^|{}\[\]]*?)?\|<ref.*?}})", new_txt):
        new_quote, attr, link, bc = "", "", "", 0
        for c in x[2]:
            if (c == "|" and bc == 0) or attr:
                attr += c
            elif c == "[":
                bc += 1
            elif c == "]":
                bc -= 1
                if bc == 0:
                    new_quote += link
                    link = ""
            elif bc > 0 and c == "|":
                link = ""
            elif bc > 0:
                link += c
            else:
                new_quote += c
        new_txt = new_txt.replace(x[2], f"{new_quote}{attr}")
    return new_txt


def handle_repeated_references(text, status):
    if "{{FamilyTree" not in text and "{{TradeRoute" not in text and re.search(r"(?<!>)((<ref name=\"[^\"\n>]+?\")(>(?!(<ref|\{\{Fact}})[^\n])*?</ref>| ?/>)(((?!<ref).)*?)\2 ?/>)(?!<ref)", text):
        nx = text.splitlines()
        for i in range(len(nx)):
            if nx[i].startswith("|") or "{{RepeatedRef" in nx[i]:
                continue
            nx[i] = re.sub(r"(?<!>)((<ref name=\"[^\"\n>]+?\")(>(?!(<ref|\{\{Fact}})[^\n])*?</ref>| ?/>)(((?!<ref).)*?)\2 ?/>)(?!<ref)", "{{RepeatedRef}}\\1" if status else "\\5\\2\\3", nx[i])
        return "\n".join(nx)
    return text


def handle_repeated_ve_references(text):
    z = re.search(r"((<ref name=\":[0-9]+\")>.*?</ref>)((.*?\n)*?.*?)\1", text)
    if z:
        a, b, c = text.partition(z.group(1))
        text = a + b + c.replace(z.group(1), z.group(2) + " />")
    return text


def handle_dupe_ve_references(text):
    i = 0
    done = False
    while not done and i < 10:
        i += 1
        z = re.search(r"(<ref name=(\"[^:<>\"\n\[\]][^><\"\n\[\]]*?\")>(.*?)</ref>.*?((\n.*?)*?))(<ref (name=\":[0-9]*?\")>\\3</ref>)", text)
        if z:
            text = text.replace(z.group(6), f"<ref name={z.group(2)} />")
            text = text.replace(z.group(7), f"name={z.group(2)}")
        else:
            done = True
    return text


# ***
#
# Top template handling
#
# ***


TOP_ORDER = [
    ["fa", "pfa", "ffa", "ga", "pga", "fga", "ca", "pca", "fca"],
    ["fprot", "sprot", "ssprot", "mprot"],
    ["real", "rwm", "rwp", "rwc", "music"],
    ["noncanon", "can", "leg", "ncc", "ncl", "ref"],
    ["dotj", "tor", "thr", "fotj", "rote", "aor", "tnr", "rofo", "cnjo"],
    ["pre", "btr", "old", "imp", "reb", "new", "njo", "lgc", "inf"],
    ["canon", "legends", "hide"],
    ["italics", "title", "italics2", "title2", "notitle"],
    ["notoc", "audio"]
]
FULL_ORDER = [tp for pgroup in TOP_ORDER for tp in pgroup]


def sort_top_template(title, t, add_ref=False, fmt=None):
    t = handle_top_title(t, title)
    if t and add_ref and "|ref" not in t:
        t = t.replace("{{Top|", "{{Top|ref|")
    px = re.search(r"^(.*?\{\{Top\|)(.*?)(}}.*?)$", t)
    replacement = handle_title_format(fmt)
    new_params = [(k, v) for k, v in (replacement or {}).items()]
    unknown = []
    if px:
        p1, p2 = px.group(1), px.group(3)
        for p in (px.group(2) or '').split("|"):
            v = ""
            if "=" in p:
                p, v = p.split("=", 1)
            if replacement is not None and p in ["title", "italics"]:
                continue
            if p in new_params or p in unknown:
                continue
            elif p in FULL_ORDER:
                new_params.append((p, v))
            else:
                unknown.append((p, v))
    elif new_params:
        p1, p2 = "{{Top|", "}}"
    else:
        return t
    params = sorted(new_params, key=lambda a: FULL_ORDER.index(a[0]))
    new_text = "|".join(f"{a}={b}" if b else a for a, b in [*params, *unknown])
    return p1 + new_text + p2


def prep_title_parameter(repl, val, p=""):
    if val.count("''") == 2 and val.startswith("''") and val.endswith("''"):
        repl[f"italics{p}"] = "1"
    elif "''" in val:
        repl[f"title{p}"] = val


def handle_title_format(fmt):
    replacement = None
    if fmt:
        replacement = {}
        if fmt.startswith('"') and fmt.endswith('"'):
            fmt = fmt[1:-1]
        if "(" in fmt and fmt.endswith(")"):
            title, _, paren = fmt.partition(" (")
        else:
            title, paren = fmt, ""
        paren = paren[:-1] if paren.endswith(")") else paren
        prep_title_parameter(replacement, title)
        if paren:
            prep_title_parameter(replacement, paren, "2")
    return replacement


def handle_top_title(before: str, target: str):
    x, _, y = target.replace("/Legends", "").replace("/Canon", "").partition(" (")
    for z in ["{{PAGENAME}}", x, target]:
        for i in ["|", "}"]:
            before = before.replace(f"|title=''{z}''{i}", f"|italics=1{i}")
            before = before.replace(f"|title={z}{i}", f"{i}")
    if y:
        y = y.replace(")", "").strip()
        if f"|title2=''{y}''" in before:
            before = before.replace(f"|title2=''{y}''", "|italics2=1")
        elif f"|title2={y}" in before:
            before = before.replace(f"|title2={y}", "")
    return before
