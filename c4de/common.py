import re
import requests
import traceback
from typing import Dict

import urllib3.exceptions
import waybackpy
from waybackpy.exceptions import WaybackError, TooManyRequestsError
from pywikibot import Page, Category
from datetime import datetime

from c4de.data.nom_data import NOM_TYPES

USER_AGENT = 'Mozilla/5.0 (Linux; Android 5.0; SM-G900P Build/LRX21T) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Mobile Safari/537.36'


class ArchiveException(Exception):
    def __init__(self, message):
        self.message = message


def log(text, *args):
    print(f"[{datetime.now().isoformat()}] {text}", *args)


def error_log(text, *args):
    log(f"ERROR: {text}", *args)
    traceback.print_exc()


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
    return "[" + t[0].capitalize() + t[0].lower() + "]" + t[1:]


def is_redirect(page):
    try:
        return page.exists() and page.isRedirectPage()
    except Exception as e:
        print(page.title(), e)
        return False


def build_redirects(page: Page):
    results = {}
    for r in page.linkedPages():
        if is_redirect(r):
            results[r.title()] = r.getRedirectTarget().title()
    return results


def fix_redirects(redirects: Dict[str, str], text, section_name, disambigs, template=False):
    for r, t in redirects.items():
        if t in disambigs:
            log(f"Skipping disambiguation redirect {t}")
            continue
        if f"[[{r.lower()}" in text.lower() or f"={r.lower()}" in text.lower():
            if section_name:
                print(f"Fixing {section_name} redirect {r} to {t}")
            x = prepare_title(r)
            text = re.sub("\[\[" + x + "\|('')?(" + prepare_title(t) + ")('')?]]", f"\\1[[\\2]]\\1", text)
            text = re.sub("\[\[" + x + "(\|.*?)]]", f"[[{t}\\1]]", text)
            text = re.sub("\[\[(" + x + ")]]([A-Za-z']*?)", f"[[{t}|\\1\\2]]", text)
            try:
                text = re.sub("(\{\{[A-Za-z0-9]+\|)" + x + "}}", "\\1" + t + "}}", text)
            except Exception as e:
                print(e, x, t)
            text = text.replace(f"set={r}", f"set={t}")
            text = text.replace(f"book={r}", f"book={t}")
            text = text.replace(f"story={r}", f"story={t}")
    return text


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
    match = re.search("Nominated by.*?(User:|U\|)(.*?)[\]\|\}/]", page_text or nom_page.get())
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
                for r in re.findall("\[\[(.*?)[\|\]]", line):
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


def archive_url(url, force_new=False, timeout=30):
    if not force_new:
        try:
            r = requests.get(f"https://web.archive.org/web/{url}", timeout=30)
            if re.search("/web/([0-9]+)/", r.url):
                log(f"URL is archived already: {url}")
                return True, r.url.split("/web/", 1)[1].split("/", 1)[0]
        except (TimeoutError, ConnectionError, requests.exceptions.ConnectionError, urllib3.exceptions.MaxRetryError):
            log(f"ERROR: Timeout/connection error while attempting to archive {url}")
        except Exception as e:
            error_log(url, type(e), e)

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
