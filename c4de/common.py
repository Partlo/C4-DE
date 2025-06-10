import re
import time

import requests
import traceback
from json import JSONDecodeError
from pywikibot import Page, Category, pagegenerators
from datetime import datetime
from typing import Dict, List, Union

import urllib3.exceptions
import waybackpy
from waybackpy.exceptions import WaybackError, TooManyRequestsError


from c4de.sources.domain import Item
from c4de.data.nom_data import NOM_TYPES

USER_AGENT = 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36'


class ArchiveException(Exception):
    def __init__(self, message):
        self.message = message


def log(text, *args):
    print(f"[{datetime.now().isoformat()}] {text}", *args)


ERROR_SKIP = ["RemoteDisconnected", "ConnectionError", "ReadTimeout"]


def error_log(text, *args, tb=True):
    text = str(text) if not isinstance(text, str) else text
    if any((e if isinstance(e, str) else str(e)) in text for e in ERROR_SKIP):
        log(f"ERROR: {text}")
        return

    log(f"ERROR: {text}", *args)
    if tb:
        traceback.print_exc()


def to_duration(now):
    return (datetime.now() - now).total_seconds()


def report_duration(msg, now, start):
    print(f"{datetime.now()} {msg}: {to_duration(now)} seconds ({to_duration(start)} total)")
    return datetime.now()


def clean_text(text):
    return (text or '').replace('\t', '').replace('\n', '').replace('\u200e', '').strip()


def extract_err_msg(e):
    try:
        return str(e.args[0] if str(e.args).startswith('(') else e.args)
    except Exception as _:
        return str(e.args)


def prepare_title(t):
    for i in ['(', ')', '?', '!']:
        t = t.replace(i, '\\' + i)
    if t[0].capitalize().isnumeric():
        return t
    return "[" + t[0].capitalize() + t[0].lower() + "]" + t[1:]


def is_redirect(page, title=None):
    if title and "w:c:" in title.lower():
        return False
    try:
        return page.exists() and page.full_url() and page.isRedirectPage()
    except JSONDecodeError:
        print(f"JSONDecodeError, likely an interwiki link")
        return False
    except Exception as e:
        try:
            print(page.title(), e)
        except Exception:
            print(f"Unable to parse link: {title}")
        return False


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


def prep_title_parameter(repl, val, p=""):
    if val.count("''") == 2 and val.startswith("''") and val.endswith("''"):
        repl[f"italics{p}"] = "1"
    elif "''" in val:
        repl[f"title{p}"] = val


def handle_title_format(actual, fmt):
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


def sort_top_template(title, t, add_ref=False, fmt=None):
    if t and add_ref and "|ref" not in t:
        t = t.replace("{{Top|", "{{Top|ref|")
    px = re.search("^(.*?\{\{Top\|)(.*?)(}}.*?)$", t)
    replacement = handle_title_format(title, fmt)
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


def build_redirects(page: Page, manual: str = None):
    results = {}
    pages, pagenames = [], []
    for r in page.linkedPages(follow_redirects=False, namespaces=0):
        pages.append(r)
        pagenames.append(r.title())
    for r in page.templates():
        pages.append(r)
        pagenames.append(r.title())
    for r in page.imagelinks():
        pages.append(r)
        pagenames.append(r.title())
    if manual and isinstance(manual, str):
        for _, x, _ in re.findall("\[\[(?!(Category:))(.*?)(\|.*?)?]]", manual):
            if x not in pagenames:
                pages.append(Page(page.site, x))
                pagenames.append(x)
        for _, x in re.findall("\{\{([Tt]emplate)?:?([^\n|{}[\]]+)", manual):
            if f"Template:{x}" not in pagenames:
                pages.append(Page(page.site, f"Template:{x}"))
                pagenames.append(x)
        # for _, x, _ in re.findall("\|(title=|set=)(.*?)(\|.*?)?}}", manual):
        #     if x not in pagenames:
        #         pages.append(Page(page.site, x))
        #         pagenames.append(x)
        # for _, x, _ in re.findall("\{\{(?!(Quote))[A-z0-9]+\|([^=|\n]+?)(\|.*?)?}}", manual):
        #     if x not in pagenames:
        #         pages.append(Page(page.site, x))
        #         pagenames.append(x)

    for i, r in enumerate(pages):
        if is_redirect(r, pagenames[i]):
            t = r.getRedirectTarget().title()
            if t.startswith("File:"):
                results[r.title().replace(" ", "_")] = t.replace(" ", "_")
            elif not t.startswith("Category:"):
                results[r.title()] = f":{t}" if t.startswith("Category:") else t
    return results


def fix_disambigs(r, t, text):
    if "{{otheruses" in text.lower() or "{{youmay" in text.lower():
        lowercase = re.search("\|title=[a-z]", text)
        tx = t.replace(' (disambiguation)', '')
        if lowercase:
            tx = tx[0].lower() + tx[1:]
        text = re.sub("(\{\{[Oo]theruses(.*?)\|)title=" + prepare_title(r) + "((\|.*?)?}})",
                      f"\\1 {tx}\\3", text)
        text = re.sub("(\{\{[Oo]theruses(.*?)\|) ", "\\1", text)
        text = re.sub("(\{\{[Oo]theruses(.*?)\|)\[\[" + prepare_title(r) + "((\|.*?)?]].*?}})", f"\\1[[{t}\\3", text)
        text = re.sub("(\{\{[Yy]oumay\|.*?)\[\[" + prepare_title(r) + "(\|.*?)?]](.*?}})", f"\\1[[{t}\\2]]\\3", text)
    elif f"[[{r}" in text or f"|{r}|" in text or f"|{r}}}}}" in text:
        log(f"Skipping disambiguation redirect {t}")
    return text


CONSOLES = ["32X", "3DO", "Android (operating system)", "Atari 2600", "Atari 5200", "Atari 8-bit", "ColecoVision",
            "Commodore 64", "Dreamcast", "Google Stadia", "Intellivision", "iOS", "Linux", "Mac", "Nintendo",
            "Game Boy Advance", "Game Boy Color", "Nintendo 3DS", "Nintendo 64", "Nintendo DS", "Nintendo Entertainment System",
            "Nintendo Game Boy", "Nintendo GameCube", "Nintendo Switch", "Super Nintendo Entertainment System", "Wii", "Wii U",
            "Oculus Quest", "Personal computer", "PlayStation", "PlayStation 2", "PlayStation 3", "PlayStation 4", "PlayStation 5",
            "PlayStation Portable", "PlayStation Vita", "R-Zone", "Sega CD", "Sega Game Gear", "Steam", "Xbox", "Xbox 360",
            "Xbox Cloud Gaming", "Xbox One", "Xbox Series X/S"]


def check_text(r, text):
    return f"[[{r}" in text or f"={r}" in text or f"[[{r.replace('_', ' ')}" in text


MULTIPLE_ISSUE_CONVERSION = {
    "catneeded": "CatNeeded",
    "imageReal": "Image|real",
    "imagePerson": "Image|person",
    "moresources": "MoreSources",
    "npov": "NPOV",
    "stayontarget": "StayOnTarget"
}
COMBINE = ["catneeded", "citation", "cleanup", "confirm", "contradict", "disputed", "expand", "imageReal",
           "imagePerson", "image", "moresources", "npov", "oou", "plot", "redlink", "split", "stayontarget", "tense",
           "tone"]


def should_move_to_multiple_issues(x):
    for i in COMBINE:
        z = MULTIPLE_ISSUE_CONVERSION.get(i, i).lower()
        if x.startswith(f"{{{{{z}|") or x.startswith(f"{{{{{z}}}}}"):
            return i
    return None


def handle_multiple_issues(text: Union[List[str], str]):
    if isinstance(text, list):
        lines = text
    elif isinstance(text, str):
        lines = text.splitlines()
    else:
        return text
    to_remove = []
    params = []
    current = None
    for ln in lines:
        if "{{multiple" in ln.lower():
            current = ln
            to_remove.append(ln)
        elif ln.startswith("{{"):
            param = should_move_to_multiple_issues(ln.lower())
            if param:
                to_remove.append(ln)
                params.append(param)

    if len(params) > 1:
        new_lines = []
        current = current or "{{MultipleIssues}}"
        if "{{MultipleIssues" not in current:
            current = re.sub("{{[Mm]ultiple.?[Ii]ssues", "{{MultipleIssues", current)
        for x in params:
            current = current.replace("MultipleIssues", f"MultipleIssues|{x}")
        for ln in lines:
            if not ("{{Top|" in ln or "{{Top}}" in ln or "{{Otheruses" in ln or "{{Youmay" in ln):
                if current not in new_lines:
                    new_lines.append(current)
            if ln not in to_remove:
                new_lines.append(ln)
        return new_lines
    return lines


def fix_redirects(redirects: Dict[str, str], text, section_name, disambigs, remap, file=False, overwrite=False,
                  appearances: Dict[str, List[Item]] = None, sources: Dict[str, List[Item]] = None, canon=False) -> str:
    for r, t in redirects.items():
        if t in disambigs or "(disambiguation)" in t:
            fix_disambigs(r, t, text)
            continue
        elif t in remap and "Free Comic Book" not in t:
            log(f"Skipping remap redirect {t}")
            continue
        if r in CONSOLES:
            text = text.replace(f"[[{r}]]", f"[[Wikipedia:{r}|{r}]]").replace(f"[[{r}|", f"[[Wikipedia:{r}|")

        elif r.startswith("Template:"):
            if r.replace("Template:", "{{").lower() not in text.lower().replace("_", " "):
                continue
            if section_name:
                print(f"Fixing {section_name} redirect {r} to {t}")
            x = prepare_title(r.replace("Template:", "")).replace(" ", "[ _]")
            tx = t.replace("Template:", "").replace(" ", "_")
            text = re.sub("\{\{" + x + " *([\n|}])", f"{{{{{tx}\\1", text)

        elif canon and "/Legends" in t and "/Legends" not in r:
            continue

        elif check_text(r.lower(), text.lower()):
            if r.lower() == t.lower() and not (check_text(r, text) or check_text(f"{r[0].lower()}{r[1:].lower()}", text)):
                continue
            if section_name:
                print(f"Fixing {section_name} redirect {r} to {t}")
            if section_name and "Appearances" in section_name and "Star Wars Galaxies" in r:
                continue
            x = prepare_title(r)
            y = appearances.get(t) if appearances else (sources.get(t) if sources else None)
            if r == "Star Wars Galaxies: An Empire Divided":
                y = appearances.get(r) if appearances else (sources.get(r) if sources else y)

            if y and y[0].template and not y[0].tv and y[0].template != "SWIA" and y[0].template != "StoryCite" and "set=" not in y[0].original and "(comic" not in y[0].target and "story)" not in y[0].target:
                rep = f"''[[{y[0].target}]]''"
                if y[0].format_text:
                    rep = f"[[{y[0].target}|{y[0].format_text}]]"
                elif "(" in y[0].target:
                    rep = f"[[{y[0].target}|''{y[0].target.split(' (')[0]}'']]"
                text = re.sub("'?'?\[\[" + x + "(\|.*?)?]]'?'?", rep, text)
            elif y and not y[0].template:
                text = re.sub("'?'?\[\[" + x + "(\|.*?)?]]'?'?", y[0].original, text)
            else:
                if "Ltd" in r or "Limited" in r or " Inc" in r or " LLC" in r or " Co" in r:
                    if re.sub(",? (Ltd|Limited|Inc|LLC)\.?", "", r) == t:
                        text = re.sub("\[\[" + x + "(\|" + prepare_title(t) + ")?]]", f"[[{t}]]", text)

                text = re.sub("(''')?('')?\[\[" + x + "\|('')?(" + prepare_title(t) + ")('')?]](s)?(''')?('')?", f"\\1\\2\\3[[\\4]]\\6\\2\\3", text)
                if file or r.replace("Star Wars: Republic: ", "Star Wars: ") == t \
                        or r.startswith("File:") or (overwrite and "/Legends" not in t and "/Canon" not in t):
                    text = re.sub("\[\[(" + x + ")(s)?]]", f"[[{t}]]\\2", text)
                    text = re.sub("\[\[" + x + "(\|.*?)]](s)?", f"[[{t}]]\\2", text)
                else:
                    text = re.sub("(''')?('')?\[\[(" + x + ")]]([A-Za-z']*)", f"\\1[[{t}|\\2\\3\\4]]\\1", text)
                    text = re.sub("\[\[" + x + "(\|.*?)]](s)?", f"[[{t}\\1\\2]]", text)
            if "/" not in r:
                try:
                    text = re.sub("(\{\{(?!(WP|1stID))[A-Za-z0-9]+\|)" + x + "}}", "\\1    " + t + "}}", text).replace("    ", "")
                except Exception as e:
                    print(e, x, t)
            if r.split(" (")[0] != t.split(" (")[0]:
                text = text.replace(f"set={r}|", f"set={t}|").replace(f"set={r}}}", f"set={t}}}")
            if t.startswith(f"{r} ("):
                text = re.sub("book=" + x + "([|}])", f"book={r}\\1", text)
            else:
                text = text.replace(f"book={r}", f"book={t}")
            text = text.replace(f"story={r}|", f"story={t}|")
            text = text.replace(f"story={r}" + "}", f"story={t}|" + "}")
    return text


def do_final_replacements(new_txt, replace):
    for x in re.findall("((\{\{[Qq]uote\|[^{}\[\]|\n]*)(\[\[([^{}\[\]\n]*?\|)?[^{}\[\]\n]*?]][^{}\n]*?)(\|audio=[^|{}\[\]]*?)?\|<ref.*?}})", new_txt):
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

    while replace:
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+)&mdash;", "\\1—", new_txt))
        new_txt2 = re.sub("(\[\[(?!File:)[^\[\]|\r\n]+–[^\[\]|\r\n]+\|[^\[\]|\r\n]+)&ndash;", "\\1–",
                          re.sub("(\[\[(?!File:)[^\[\]|\n]+—[^\[\]|\r\n]+\|[^\[\]|\r1\n]+)&mdash;", "\\1—", new_txt2))
        new_txt2 = re.sub("\[\[(.*?)\|\\1((?!(Bestoon)[^\n \[\]}{])*?)]]", "[[\\1]]\\2", new_txt2)
        new_txt2 = re.sub("(\|set=(.*?) \(.*?\))\|(s?text|sformatt?e?d?)=\\2([|}])", "\\1\\4", new_txt2)
        new_txt2 = re.sub("([^']''[^' ][^']+?'')'s ", "\\1{{'s}} ", new_txt2)
        new_txt2 = re.sub("([^']''((?!-class)[^' ])+?[^']+?s'')' ", "\\1{{'}} ", new_txt2)
        new_txt2 = new_txt2.replace("{{'}}s", "{{'s}}")
        new_txt2 = new_txt2.replace("{{'}}\n", "{{'}}")
        if "'''s " in new_txt2:
            new_txt2 = re.sub("( ''[^'\n]+'')'s ", "\\1{{'s}} ", new_txt2)

        new_txt2 = re.sub("(\|url=[^\n|{}]+?)/\|", "\\1|", new_txt2)
        new_txt2 = new_txt2.replace("\n\n*{{ISBN", "\n*{{ISBN")
        if "stext=" in new_txt2:
            new_txt2 = re.sub("(\|set=[^|{}\n]*?)(\|stext=[^|{}\n]*?)}}", "\\1}}", new_txt2)

        new_txt2 = re.sub("(\[\[((.*?) \((.*?)\)).*?]].*?)(\{\{Ab\|.*?)\[\[\\2\|''\\3'' \\4]]", "\\1\\5[[\\2|\\4]]", new_txt2)
        new_txt2 = re.sub("(\{\{[^\n{}]+?)(\|nolive=1)([^\n{}]*?(\|nobackup=1)?[^\n{}]*?)}}", "\\1\\3\\2}}", new_txt2)
        new_txt2 = re.sub("(\{\{[^\n{}]+?)(\|nobackup=1)([^\n{}]+?)}}", "\\1\\3\\2}}", new_txt2)
        new_txt2 = re.sub("([\n[]File:[^ \n|\]\[]+) ", "\\1_", new_txt2)

        x = re.search("\[\[([A-Z])(.*?)\|(.\\2)(.*?)]]", new_txt2)
        if x and x.group(3).lower().startswith(x.group(1).lower()) and x.group(3).lower() != "ochi of bestoon":
            new_txt2 = new_txt2.replace(x.group(0), f"[[{x.group(3)}]]{x.group(4)}")

        new_txt2 = re.sub("(\|[a-z]+=[^|{}\n]*)\\1+", "\\1", new_txt2)

        if "''{{Film|" in new_txt2:
            new_txt2 = re.sub("(?<!')''(\{\{Film\|.*?}})'*", "\\1", new_txt2)

        # TODO: remove
        for ix in re.findall(
                "((\{\{(BuildFalconCite|BuildR2Cite|BuildXWingCite|BustCollectionCite|DarthVaderCite|FalconCite|FigurineCite|HelmetCollectionCite|ShipsandVehiclesCite|StarshipsVehiclesCite)\|[0-9]+\|[^|\[{}]+?)(\|((?!reprint).)*?)}})",
                new_txt2):
            new_txt2 = new_txt2.replace(ix[0], ix[1] + "}}")

        # new_txt2 = re.sub("}} \{\{C\|Reissued in (\[\[.*?)}}", "reissued=\\1}}", new_txt2)
        # new_txt2 = re.sub("(reissus?ed?=.*?\[\[.*?\|)''(.*?)'']]", "\\1\\2]]", new_txt2)
        new_txt2 = re.sub("2012 edition}} \{\{C\|\[*2012]* edition}}", "2012 edition}}", new_txt2)
        new_txt2 = re.sub("(\{\{SWMiniCite\|set=[^\n}]+?\|)cardname=", "\\1pack=", new_txt2)
        new_txt2 = new_txt2.replace(" (SWGTCG)|scenario=", "|scenario=")
        new_txt2 = new_txt2.replace("[[Ochi]] of Bestoon", "[[Ochi|Ochi of Bestoon]]")
        new_txt2 = new_txt2.replace("[[Battle station/Legends|battlestation", "[[Battle station/Legends|battle station")
        new_txt2 = re.sub("\*.*?\{\{FactFile\|1\|Gala.*? [Mm]ap.*?}}", "*<!-- 2001-12-27 -->{{FactFile|1|[[:File:Galaxymap3.jpg|Galaxy Map poster]]}}", new_txt2)
        if "{{more" in new_txt2.lower():
            new_txt2 = re.sub("\{\{[Mm]ore[ _]?[Ss]ources}}\n+}}", "}}\n{{MoreSources}}", new_txt2)
        replace = new_txt != new_txt2
        new_txt = new_txt2
    return new_txt


def determine_title_format(page_title, text) -> str:
    """ Examines the target article's usage of {{Top}} and extracts the title= and title2= parameters, in order to
      generate a properly-formatted pipelink to the target. """

    if page_title.startswith("en:"):
        page_title = page_title[3:]

    pagename = re.match("{{[Tt]op\|[^\n]+\|title=''{{PAGENAME}}''", text)
    if pagename:
        return f"''[[{page_title}]]''"

    title1 = None
    title_match = re.match("{{[Tt]op\|[^\n]+\|title=(?P<title>.*?)[|}]", text)
    if title_match:
        title1 = title_match.groupdict()['title']
        if title1 == f"''{page_title}''":
            return f"''[[{page_title}]]''"

    match = re.match("^(?P<title>.+?) \((?P<paren>.*?)\)$", page_title)
    if match:
        title2 = None
        title2_match = re.match("{{[Tt]op\|[^\n]+\|title2=(?P<title>.*?)[|}]", text)
        if title2_match:
            title2 = title2_match.groupdict()['title']

        if title1 or title2:
            title1 = title1 or match.groupdict()['title']
            title2 = title2 or match.groupdict()['paren']
            return f"[[{page_title}|{title1} ({title2})]]"
        else:
            return f"[[{page_title}]]"
    elif title1 and title1 != page_title:
        return f"[[{page_title}|{title1}]]"
    else:
        return f"[[{page_title}]]"


def determine_nominator(page: Page, nom_type: str, nom_page: Page) -> str:
    revision = calculate_nominated_revision(page=page, nom_type=nom_type, raise_error=False)
    if revision and revision.get("user"):
        return revision["user"]
    return extract_nominator(nom_page=nom_page)


def extract_nominator(nom_page: Page, page_text: str = None):
    match = re.search("Nominated by.*?(User:|U\|)(.*?)[]|}/]", page_text or nom_page.get())
    if match:
        return match.group(2).replace("_", " ").strip()
    else:
        return list(nom_page.revisions(reverse=True, total=1))[0]["user"]


def calculate_nominated_revision(*, page: Page, nom_type, raise_error=True):
    nominated_revision = None
    for revision in page.revisions():
        if f"Added {nom_type}nom" in revision['tags'] or revision['comment'] == f"Added {nom_type}nom":
            nominated_revision = revision
            break

    if nominated_revision is None and raise_error:
        raise ArchiveException("Could not find nomination revision")
    return nominated_revision


def calculate_revisions(*, page, nom_type, comment):
    """ Examines the target article's revision history to identify the revisions where the nomination template was
     added and removed. """

    nominated_revision = None
    completed_revision = None
    for revision in page.revisions():
        if revision['comment'] == comment:
            completed_revision = revision
        if f"Added {nom_type}nom" in revision['tags'] or revision['comment'] == f"Added {nom_type}nom":
            nominated_revision = revision
            break

    if completed_revision is None:
        raise ArchiveException("Could not find completed revision")
    elif nominated_revision is None:
        raise ArchiveException("Could not find nomination revision")
    return completed_revision, nominated_revision


def compare_category_and_page(site, nom_type):
    page = Page(site, NOM_TYPES[nom_type].page)

    page_articles = []
    dupes = []
    start_found = False
    for line in page.get().splitlines():
        if start_found and "<!--End-->" in line:
            break
        elif start_found:
            if line.count("[[") > 1:
                for r in re.findall("\[\[(.*?)[|\]]", line):
                    if r.replace("\u200e", "") in page_articles:
                        dupes.append(r.replace("\u200e", ""))
                    else:
                        page_articles.append(r.replace("\u200e", ""))
            elif "[[" in line:
                target = line.split("[[")[1].split("]]")[0].split("|")[0].replace("\u200e", "")
                if target in page_articles:
                    dupes.append(target)
                else:
                    page_articles.append(target)
        elif "<!--Start-->" in line:
            start_found = True

    category = Category(site, NOM_TYPES[nom_type].category)
    missing_from_page = []
    for p in category.articles(content=False):
        if p.namespace().id != 0:
            continue
        elif p.title() in page_articles:
            page_articles.remove(p.title())
        elif p.title()[0].lower() + p.title()[1:] in page_articles:
            page_articles.remove(p.title()[0].lower() + p.title()[1:])
        else:
            missing_from_page.append(p.title())

    return dupes, page_articles, missing_from_page


def build_analysis_response(site, nom_type):
    dupes, missing_from_category, missing_from_page = compare_category_and_page(site, nom_type)
    lines = []
    if dupes:
        lines.append(f"Duplicates on {NOM_TYPES[nom_type].page}:")
        for p in dupes:
            lines.append(f"- {p}")
    if missing_from_page:
        lines.append(f"Missing from {NOM_TYPES[nom_type].page}:")
        for p in missing_from_page:
            lines.append(f"- {p}")
    if missing_from_category:
        lines.append(f"Listed on {NOM_TYPES[nom_type].page}, but not in {NOM_TYPES[nom_type].category}:")
        for p in missing_from_category:
            lines.append(f"- {p}")
    return lines


def archive_url(url, force_new=False, timeout=30, enabled=True, skip=False, start=None):
    if not enabled:
        return False, "Wayback Machine is currently read-only"

    if not force_new:
        try:
            x = f"{start}/" if start else ""
            r = requests.get(f"https://web.archive.org/web/{x}{url}", timeout=timeout)
            if re.search("/web/([0-9]+)/", r.url):
                z = r.url.split("/web/", 1)[1].split("/", 1)[0]
                if z != start and not (start and start[:4] == z[:4]):
                    log(f"URL is archived already: {z} -> {url}")
                    return True, r.url.split("/web/", 1)[1].split("/", 1)[0]
            else:
                log(f"No archive has been recorded for {url}")
                if skip:
                    return False, "No archive has been recorded for this site"
        except (TimeoutError, ConnectionError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError, urllib3.exceptions.MaxRetryError) as e:
            log(f"ERROR: {type(e)} while attempting to archive {url}")
            time.sleep(15)
        except Exception as e:
            error_log(url, type(e), e)

    if skip:
        return False, "Skipping archive for initial reporting"

    err_msg = None
    try:
        log(f"Archiving in the wayback: {url}")
        wayback = waybackpy.Url(url, USER_AGENT)
        archive = wayback.save()
        log(f"Successful archive: {archive.archive_url}")
        return True, archive.archive_url.split("/web/", 1)[1].split("/", 1)[0]
    except TooManyRequestsError as e:
        err_msg = "Too many save requests, server is overwhelmed"
    except WaybackError as e:
        print(e)
        err_msg = "URL cannot be archived by wayback machine as it is a redirect"
    except (TimeoutError, ConnectionError, requests.exceptions.ConnectionError, urllib3.exceptions.MaxRetryError):
        log(f"ERROR: Timeout/connection error while attempting to archive {url}")
    except Exception as e:
        error_log(url, type(e), e)
        err_msg = str(e)

    try:
        r = requests.get(f"https://web.archive.org/web/{url}")
        if re.search("/web/([0-9]+)/", r.url):
            log(f"URL is archived already: {url}")
            return True, r.url.split("/web/", 1)[1].split("/", 1)[0]
    except (TimeoutError, ConnectionError, requests.exceptions.ConnectionError, urllib3.exceptions.MaxRetryError):
        log(f"ERROR: Timeout/connection error while attempting to archive {url}")
    except Exception as e:
        error_log(url, type(e), e)
        return False, err_msg or str(e)

    return False, err_msg or ""


def dash_redirects():
    gen_factory = pagegenerators.GeneratorFactory()
    gen_factory.handle_arg("-ns:0")
    gen_factory.handle_arg("-start:*")
    gener = None
    gener = gen_factory.getCombinedGenerator(gener)
    gen = pagegenerators.PreloadingGenerator(gener, groupsize=50)
    found = []
    for page in gen:
        if "-" in page.title() or "–" in page.title() or "—":
            found.append(page.title())
