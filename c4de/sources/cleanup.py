import codecs
import re
import time
import traceback
from datetime import datetime, timedelta

from pywikibot import Page

from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("<br>", "<br />"), ("{{InvalidCategory}}", ""),
    ("Youtube", "YouTube"), ("{{Scrollbox", "{{ScrollBox"), ("referneces", "references"), ("{{MO}}", "{{Mo}}"),
    ("{{C|variant cover only}}", "{{Vco}}"), ("{{C|Variant cover only}}", "{{Vco}}"),
    ("{{scrollbox", "{{ScrollBox"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"), ("†", "&dagger:"),
    ("{{Visions|focus=1", "{{VisionsFocus"), ("{{Visions|focus=4", "{{VisionsFocus"), ("{{Visions|focus=8", "{{VisionsFocus"),
    ("[[:category:", "[[:Category:"), ("[[category:", "[[Category:"), ("[[Image:", "[[File:"),
    ("{{IntroMissingTitle}} ", ""), ("{{IntroMissingTitle}}\n", ""),
    ("==Media==\n*{{ISBN|", "==Media==\n===Editions===\n*{{ISBN|"),
    ("\n==Back-cover summary==\n", "\n===Back-cover summary===\n"),
    ("{{App|characters=", "{{App\n|characters="), ("PenguinRandomHouse|old=1", "RandomHouseOld"),
    ("<onlyinclude>\n{{Incomplete_app}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("<onlyinclude>\n{{IncompleteApp}}", "{{IncompleteApp}}\n<onlyinclude>"),

    ("|work=[[Entertainment Weekly Books|''Entertainment Weekly'']]", ""),
    ("|work=''[[Wikipedia:Entertainment Weekly|Entertainment Weekly]]''", ""),
    ("|work=[[Wikipedia:Entertainment Weekly|''Entertainment Weekly'']]", ""),
    ("{{SWKidsYouTube|0eKgIHtzphA|Fett's Flying Lesson &#124; LEGO Star Wars &#124; @StarWarsKids}}", "{{CelebrateTheSeason|Fett's Flying Lesson}}"),
    ("{{SideshowCite|set=Sixth Scale Figures|pack=Boba Fett|link=collectibles/star-wars-boba-fett-deluxe-version-hot-toys-907747?var=907834}}",
     "{{HotToysCite|set=Television Masterpiece Series|packtype=Sixth Scale Figure|pack=#033: Boba Fett (Deluxe Version)|link=collectibles/star-wars-boba-fett-deluxe-version-hot-toys-907747}}"),
    ("{{SideshowCite|set=Sixth Scale Figures|pack=Anakin Skywalker and STAP|link=collectibles/star-wars-anakin-skywalker-and-stap-hot-toys-906795?var=906795}}",
     "{{HotToysCite|set=Television Masterpiece Series|packtype=Sixth Scale Figure|pack=#020: Anakin Skywalker and STAP|link=collectibles/star-wars-anakin-skywalker-and-stap-hot-toys-906795}}"),
    ("{{SideshowCite|set=Sixth Scale Figures|pack=Cad Bane (Deluxe Version)|link=collectibles/star-wars-cad-bane-hot-toys-911275?var=9112752}}",
     "{{HotToysCite|set=Television Masterpiece Series|packtype=Sixth Scale Figure|pack=#080: Cad Bane (Deluxe Version)|link=collectibles/star-wars-cad-bane-hot-toys-911275}}"),
    ("{{SideshowCite|set=Sixth Scale Figures|pack=The Mandalorian and the Child (Deluxe)|link=collectibles/star-wars-the-mandalorian-and-the-child-hot-toys-906135?var=905873}}",
     "{{HotToysCite|set=Television Masterpiece Series|packtype=Sixth Scale Figure|pack=#015: The Mandalorian and the Child (Deluxe)|link=collectibles/star-wars-the-mandalorian-and-the-child-hot-toys-906135}}"),
]


EXTRA = "\{+ ?(1st[A-z]*|[Cc]|V?[A-z][od]|[Ff]act|[Bb]ts[Oo]nly|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]c[ms]?|[Aa]mbig|[Mm]ap[Pp]oint|[Cc]osmetic|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}]"


def clean_references(before):
    before = re.sub("<ref name ?=([^'\">]*?) ?[\"'] ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub("<ref name ?=([^'\">]*?) ?[\"'] ?>", "<ref name=\"\\1\">", before)
    before = re.sub("<ref name ?=[\"']([^'\" ]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub("<ref name ?=[\"']([^'\" ]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub("<ref name ?=([^'\">]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub("<ref name ?=([^'\">]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub("(<ref name=\"(.*?)\")>[ \n\t]*?</ref>", "\\1 />", before)
    before = re.sub("</ref>([A-z])", "</ref> \\1", before)
    before = re.sub("(<ref( name=\".*?\")?>)\*", "\\1", before)
    if "\n</ref>" in before:
        before = re.sub("(<ref name=((?!</ref>).)*?)\n</ref>", "\\1</ref>", before)
    return before.replace("\"/>", "\" />")


def initial_cleanup(target: Page, all_infoboxes, before: str=None):
    # now = datetime.now()
    if not before:
        before = target.get(force=True)
    # priority fixes
    before = before.replace("\u202c", "")
    before = re.sub("(\{\{WebCite[^\n}]*?)\|title=(.*?}})", "\\1|text=\\2", before)
    before = before.replace("\n}}</ref>", "}}</ref>")
    before = re.sub("(\{\{(SWGcite|TORcite).*?)\|type=", "\\1|TORTYPE=", before)

    # whitespace/spacing issues
    before = re.sub("\* +([A-z0-9'\[{])", "*\\1", before)
    before = re.sub("\n<br ?/?>(\n+==)", "\\1", before)
    before = re.sub("([A-z'0-9\]]+)  +([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub("\n[ ]+\n", "\n\n", before)

    # print(f"retrieval: {(datetime.now() - now).microseconds / 1000} microseconds")
    if "]]{{" in before or "}}{{" in before:
        before = re.sub("(]]|}})(" + EXTRA + ")","\\1 \\2", before)

    # Handle title parameters in Template:Top
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

    for (x, y) in REPLACEMENTS:
        before = before.replace(x, y)

    # inline files, text/etc. in image field
    before = re.sub("([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub("\|image=(File:)?([A-Z0-9 _]+\..+)(?=\n)", "|image=[[File:\\2]]", before)
    before = re.sub("(\|image=\[\[File:[^\n\]]+?)\|.+?]]", "\\1]]", before)
    before = re.sub("(\|image=\[\[File:.*?)(\|alt=.*?)]]\n", "\\1]]\n\\2\\n", before)

    # multi-line templates, extra/wrong brackets, etc.
    before = re.sub("(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub("([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub("\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub("\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub("(?<!\{)\{(\{\{[^\n{}]+}})(?!})", "\\1", before)
    before = re.sub("(?<!\{)(\{\{[^\n{}]+})(?!})", "\\1}", before)
    before = re.sub("(?<!\{)(\{[^\n{}]+}})(?!})", "{\\1", before)
    before = re.sub("(\{\{1st[A-z]*)\|\n}}", "\\1}}", before)
    before = re.sub("(\{\{1st[A-z]*\|[^|}\n]*?)\n}}", "\\1}}", before)
    before = re.sub("(\{\{[A-z0-9-]+[^{}\n]+?) *\n *}}", "\\1}}", before)

    # fixing same-line infobox fields
    while re.search("(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", before):
        before = re.sub("(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", "\\1\n\\2", before)

    # now = datetime.now()
    infobox, original = None, None
    if all_infoboxes and not target.title().startswith("User:") and not target.title().startswith("File:"):
        before, infobox, original = handle_infobox_on_page(before, target, all_infoboxes, add=False)
    # print(f"infobox: {(datetime.now() - now).microseconds / 1000} microseconds")

    # fixing bad references
    before = clean_references(before)

    # section header issues
    before = re.sub("\n=([A-z ]+)==", "\n==\\1==", before)
    before = re.sub("==((?!Notes and references).)*?==(\n\{.*?}})?\n\{\{[Rr]eflist}}", "==Notes and references==\\2\n{{Reflist}}", before)
    before = re.sub("=+ ?([Rr]eferences?|[Nn]otes? (and )?[Rr]ef.*?) ?=+", "==Notes and references==", before)
    before = re.sub("= ?([Cc]ollections?|Collected [Ii]n) ?=", "=Collected in=", before)
    # before = re.sub("=+ ?'*Non-canon(ical)? ([Aa]ppearances|[Ss]ources)'* ?=+", "===Non-canon \\2===", before)
    before = re.sub("\n===(Merchandis(e|ing)(.*?)|Adaptations?|Tie[ -]ins?( media)?)===", "\n==Adaptations==", before)
    before = re.sub("(\n===?.*?)<ref name=.*?(/>|</ref>)(.*?==+) ?\n", "\\1\\3\n", before)
    if "<references" in before.lower():
        before = re.sub("<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)

    # now = datetime.now()
    while re.search("\[\[(?!File:)([^\[\]{}\n]+?)&[mn]dash;([^\[\]{}\n]+?)]]", before):
        before = re.sub("\[\[(?!File:)([^\[\]{}\n]+?)&ndash;([^\[\]{}\n]+?)]]", "[[\\1–\\2]]", before)
        before = re.sub("\[\[(?!File:)([^\[\]{}\n]+?)&mdash;([^\[\]{}\n]+?)]]", "[[\\1—\\2]]", before)

    before = re.sub("(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = before.replace("||text=", "|text=").replace("|Parent=1", "|parent=1")
    before = before.replace("{{C|non-canon|reprint=1}}", "")
    before = before.replace("<nowiki>|</nowiki>", "&#124;")
    before = re.sub("({{[Ss]croll[_ ]?[Bb]ox\|)\*", "{{ScrollBox|\n*", before)
    before = re.sub("<small>\((.*?)\)</small>", "{{C|\\1}}", before)

    # removing work= parameters and prioritizing
    before = re.sub("(\{\{((?!([wW]ebCite|OfficialSite))[^{}\n])*?\|[^{}\n]+?)\|work=(\[\[[^]]+\|.*?]])?.*?(\|.*?)?}}", "\\1\\4}}", before)
    before = re.sub("(\{\{[A-z]+)(\|url=[^\n{}]+?)(\|(subdomain|uk|lang)=[^\n{}]+?)(\|[^\n{}]*?)?}}", "\\1\\3\\2\\5}}", before)
    before = re.sub("(\{\{Quote\|[^\n{}]+?(\{\{[^\n{}]+?}})?[^\n{}]+?}})(?!\n)", "\\1\n", before)

    b1, b2, b3 = before.partition("{{App\n")
    b3 = re.sub("\n?(\|(c-|l-)?(characters|organisms|droids|events|locations|organizations|species|vehicles|technology|miscellanea)=)\*", "\n\\1\n*", b3)
    before = f"{b1}{b2}{b3}"

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

    before = re.sub("( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\\1+", "\\1", before)

    # Visual Editor fix, can't remove
    before = re.sub("\[\[(.*?) (.*?)\|('*\\1'*)]] \[\[\\1 \\2|\\2]]", "[[\\1 \\2|\\3 \\2]]", before)

    # temp fixes
    before = re.sub("\|name=\[\[Friends of the Force(\|Friends of the Force|]]): A Star Wars Podcast]*\|", "|name=[[Friends of the Force]]|", before)
    before = re.sub("\{\{InsiderCite\|link=(.*?)(.*?)\|''\\1''\\2\|(.*?)}}", "{{StoryCite|book=\\1|story=\\3}}", before)
    before = re.sub("(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)
    before = re.sub("\[\[K-Zone\|'*K-Zone'* (Volume [0-9]+, Number [0-9]+)]]", "[[K-Zone \\1|''K-Zone'' \\1]]", before)
    before = re.sub("'*\[(https?://[w.]*?archive.org/.*?) (.*?)]'* (on|at)( the)? ('*\[https?://[w.]*archive\.org/? )?Internet Archive]?'*",
                    "{{WebCite|url=\\1|text=\\2}}", before)
    before = re.sub("(\{\{GalaxyMapAppendix}})( |&.dash;)*[Bb]ased on (corresponding )?(info(rmation)?|data) for (the )?(\[\[((?! and ).)*?]]).?</ref>", "\\1 &mdash; Based on corresponding data for the \\7</ref>", before)
    before = re.sub("''\[\[(The Acolyte|The Mandalorian|The Book of Boba Fett)]]''", "''[[Star Wars: \\1]]''", before)
    before = re.sub("'?'?\[\[(Andor|Ahsoka|Obi-Wan Kenobi) \(television series\)\|'?'?\\1'?'?]]'?'?", "''[[Star Wars: \\1]]''", before)
    before = re.sub("\*(\{\{SeriesListing.*?}} )?\[\[Star Wars Rebels \(webcomic\)\|.*?{{C\|Appears through imagination}}\n", "", before)
    before = re.sub("(\{\{EncyclopediaCite\|.*?) \(reference book\)}}", "\\1}}", before)

    while re.search("\[\[Category:[^\n|\]_]+_", before):
        before = re.sub("(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
    # print(f"regex-1: {(datetime.now() - now).microseconds / 1000} microseconds")

    # now = datetime.now()
    before = regex_cleanup(before)
    # print(f"regex-2: {(datetime.now() - now).microseconds / 1000} microseconds")

    while "== " in before or " ==" in before:
        before = before.replace("== ", "==").replace(" ==", "==")
    if "{{C|unlicensed}}" in before:
        before = re.sub("( {{[Cc]\|[Uu]nlicensed}})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub("\{\{[Mm]entioned[ _]only\|?}}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace("‎", "")
        print(f"Found ‎ in {target.title()}")
    return before, infobox, original


PAGE_NUMBER_REGEX = "[,;: (]*?(pa?ge?\.?|p?p\.|[Cc]hapters?|ch\.) ?(([0-9-]+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)|(,|&.dash;|–|—|and) ?)+(?!])[),. ']*</ref>"


def clear_page_numbers(before, in_src=None):
    rp = "(['\"]*[\[{]+[^\n\[{]*?[}\]]+['\"]*)" + PAGE_NUMBER_REGEX
    if "{{PageNumber}}" in before:
        if in_src:
            x = re.findall("((<ref name=\".*?\">'')(.*?)'')", before)
            for i in x:
                if i in in_src:
                    before = before.replace(x[1], f"{x[2]}[[{i}]]''")
                else:
                    z = [o for o in in_src if o.startswith(f"{i} (")]
                    if z:
                        before = before.replace(x[1], f"{x[2]}[[{z[0]}|''{i}'']]")

        before = re.sub("\">(((?!\{\{PageNumber)[^\n<])+? ?" + rp + ")", "\">{{PageNumber}} \\1", before)
        before = re.sub("\">\{\{PageNumber}} ''(\[\[.*?]])( .+?)''</ref>", "\">{{PageNumber}} ''\\1''\\2</ref>", before)
        skip = []
        for x in re.findall("((<ref name=\"([^\"\n>]+?)\")>\{\{PageNumber}} ?(\{\{UnlinkedRef}} )?" + rp + ")", before):
            unlinked = None
            if in_src:
                if not any(a in x[0] if a.startswith("{{") else (f"[[{a}|" in x[0] or f"[[{a}]]") for a in in_src):
                    z = [(f">''{a.split(' (')[0]}''", a) for a in in_src if f">''{a.split(' (')[0]}''" in x[0]]
                    if z:
                        unlinked = z[0]
                    else:
                        print(f"Skipping reference due to source not being present in Appearances/Sources: {x}")
                        skip.append(x[2])
                        continue
            if unlinked and unlinked[0] in before:
                before = before.replace(unlinked[0], f">[[{unlinked[1]}|''{unlinked[1].split(' (')[1]}]]" if " (" in unlinked[1] else f">''[[{unlinked[1]}]]''")

        for x in re.findall("((<ref name=\"([^\"\n>]+?)\")>\{\{PageNumber}} ?(\{\{UnlinkedRef}} )?" + rp + ")", before):
            if x[2] in skip:
                continue
            zy = re.sub("[_:\- ]p?" + x[7] + "\"", '"', x[1])
            if zy.endswith(f"{x[7]}\"") and x[7] not in x[4]:
                zy = zy.replace(f"{x[7]}\"", '"')
            if zy != x[1] and before.count(zy + ">") > 0:
                before = before.replace(x[0], f"{zy} />")
                before = before.replace(x[1], zy)
                continue
            elif before.count(f"\">{x[4]}<") > 0:
                z = re.search("(<ref name=\"[^\"\n>]+?\")>" + re.escape(x[4]) + "</ref>", before)
                if z:
                    before = before.replace(x[0], f"{z.group(1)} />").replace(x[1], z.group(1))
            else:
                before = before.replace(x[0], f"{zy}>{x[4]}</ref>")
                before = before.replace(x[1], zy)

            # if before.count(f"\">{x[4]}<") >= 1:
            #     z = re.search("(<ref name=\"[^\"\n>]+?\")>" + re.escape(x[4]) + "</ref>", before)
            #     if z:
            #         before = before.replace(x[0], f"{z.group(1)} />").replace(x[1], z.group(1))
            #         check_multi = True
            #
            # replace = before.count(f"\">{x[4]}<") == 0
            # if not replace and before.count(f"\">{x[4]} ") <= 2:
            #     z = re.search("\">" + re.escape(x[4]) + " (((?![/<]ref).)*?\[\[((?![/<]ref).)*?)</ref>", before)
            #     replace = z and len(z.group(1)) > 10
            #
            # if before.count(f"\">{x[4]}<") > 1:
            #     z = re.search("(<ref name=\"[^\"\n>]+?\")>" + re.escape(x[4]) + "</ref>", before)
            #     if z:
            #         before = before.replace(x[0], f"{z.group(1)} />").replace(x[1], z.group(1))
            #         check_multi = True
            # elif replace:
            #     zy = x[1].replace(f":{x[7]}\"", '"').replace(f"-{x[7]}\"", '"').replace(f" {x[7]}\"", '"')
            #     if zy.endswith(f"{x[7]}\"") and x[7] not in x[4]:
            #         zy = zy.replace(f"{x[7]}\"", '"')
            #     before = before.replace(x[0], f"{zy}>{x[4]}</ref>")
            #     before = before.replace(x[1], zy)

        before = re.sub("(\">''\[\[[^]]+?]])</ref>", "\\1''</ref>", before)

    return before


def regex_cleanup(before: str) -> str:
    if before.count("==Appearances==") > 1:
        before = re.sub("(==Appearances==(\n.*?)+)\n==Appearances==", "\\1", before)
    if before.count("==Sources==") > 1:
        before = re.sub("(==Sources==(\n.*?)+)\n==Sources==", "\\1", before)

    if "{{SWU" in before:
        before = re.sub("(\{\{SWU\|.*?cardname=[^\n{}]+?)&mdash;([^\n{}]+?}})", "\\1|subtitle=\\2", before)

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
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub("\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?)]?]? (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|\]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\9|\\4|\\5}}", before)
        before = re.sub("\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?) (on|at) (the )?(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\8|\\4|\\5}}", before)

    if "oldversion=1" in before:
        before = re.sub("(\|archive(date|url)=([^|\n}{]+))(\|[^\n}{]*?)?\|oldversion=1", "|oldversion=\\3\\4", before)
        before = re.sub("\|oldversion=1(\|[^\n}{]*?)?(\|archive(date|url)=([^|\n}{]+))", "|oldversion=\\4\\1", before)

    before = re.sub("(\{\{[A-z0-9 _]+\|.*?\|(.*?) \(.*?\))\|\\2}}", "\\1}}", before)
    if "{{Blog|" in before:
        before = re.sub("(\{\{Blog\|(official=true\|)?[^|\n}\]]+?\|[^|\n}\]]+?\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
        before = re.sub("(\{\{Blog\|listing=true\|[^|\n}\]]+?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|(?!(archive|date|nolive|nobackup))[^}\n]*?)(\|.*?)?}}","\\1\\6}}", before)
    if "SWGTCG" in before:
        before = re.sub("(\{\{SWGTCG\|.*?)}} {{C\|(.*?scenario.*?)}}", "\\1|scenario=\\2}}", before)
    if "Rebelscum.com" in before or "TheForce.net" in before:
        before = re.sub("\*'*?\[(http.*?) (.*?)]'*? (on|at|-).*?\[\[(Rebelscum\.com|TheForce\.net).*]].*?\n","{{WebCite|url=\\1|text=\\2|work=\\4}}", before)
    return before
