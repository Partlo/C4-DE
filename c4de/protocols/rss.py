from typing import Dict, List
import xml.etree.ElementTree as ET
import feedparser
import re
import requests
import html
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from pywikibot import Site, Page, Category

from c4de.common import error_log, log


FEED_URLS = [
    "https://starwars.fandom.com/wiki/Special:NewPages?feed=rss&namespace=4",
    "https://starwars.fandom.com/wiki/Special:NewPages?feed=rss&namespace=100",
    "https://community.fandom.com/wiki/Special:NewPages?feed=rss&namespace=500",
    "https://starwars.fandom.com/wiki/Special:RecentChanges?feed=rss"
]


def check_new_pages_rss_feed(site, url, cache: Dict[str, List[str]]):
    d = feedparser.parse(url)
    is_new = "NewPages" in url

    entries_to_report = []
    for e in d.entries:
        try:
            pt, ch, message, d = None, None, None, None
            if is_new:
                if e.title.startswith("Forum:SH:"):
                    pt, ch, message = "Senate Hall", "announcements", f"📣 **New Senate Hall thread**\n<{e.link}>"
                elif e.title.startswith("Forum:NB:"):
                    pt, ch, message = "Administrator's Noticeboard", "announcements", f"📢 **New Administrators' noticeboard thread**\n<{e.link}>"
                elif e.title.startswith("Forum:CT:"):
                    pt, ch, message = "Consensus Track", "announcements", f"📢 **New Consensus track vote**\n<{e.link}>"
                elif e.title.startswith("Forum:TC:") or e.title.startswith("Wookieepedia:Trash compactor"):
                    pt, ch, message = "Trash Compactor", "announcements", f"🗑️ **New Trash Compactor thread**\n<{e.link}>"
                elif e.title.startswith("User blog:"):
                    pt, ch, message = "Fandom Blog", "announcements", f"<:fandom:872166055693393940>**New Fandom Staff blog post**\n<{e.link}>"
            elif re.match("^<p>.*? deleted page.*?</p>", e.description):
                continue
            elif e.title.startswith("Wookieepedia:Trash compactor") and re.match("^<p>.*?delete.*?</p>", e.description.lower()):
                continue
            elif e.title.startswith("Forum:TC:") and re.match("^<p>.*?delete.*?</p>", e.description.lower()):
                continue
            elif did_edit_add_deletion_template(site, e.title, e.description) or "<p>CSD</p>" in e.description or "<p>delete</p>" in e.description.lower():
                pt, ch, message = "CSD", "admin-help", f"❗ **{e.author}** requested deletion of **{e.title}**\n<{e.link}>"
                d = e.title
            elif re.match("^<p>.*?CSD.*?</p>", e.description) or re.match("^<p>.*?delete[^d].*?</p>", e.description.lower()):
                pt, ch, message = "CSD", "admin-help", f"❓ **{e.author}** used 'delete' or 'CSD' in edit summary on **{e.title}**; may be false positive.\n<{e.link}>"
                d = e.title
            else:
                continue

            if pt:
                if pt not in cache:
                    cache[pt] = []
                if e.link in cache[pt]:
                    continue
                entries_to_report.append((ch, message, d))
                cache[pt].append(e.link)
                if d:
                    cache[pt].append(d)
        except Exception as x:
            error_log(f"Encountered {type(x)} while parsing RSS feed entry for {e.title}", e)

    return entries_to_report


def parse_diff_description(text):
    table_content = []
    for row in re.findall("<tr.*?>((.*?\n)*?.*?)</tr>", text):
        row_content = []
        for line in re.findall("<td(.*?)>(.*?)</td>", row[0]):
            if "colspan=2" in line[0]:
                row_content.append(line[1])
            row_content.append(line[1])
        table_content.append(row_content)

    return table_content


def did_edit_add_deletion_template(site, title, description):
    page = Page(site, title)
    if page.title().startswith("Special:") or not page.exists() or page.isRedirectPage():
        return False
    table_content = parse_diff_description(description)
    return any("{{csd" in row[-1].lower() or "{{delete|" in row[-1].lower() for row in table_content if row)


def parse_history_rss_feed(feed_url, cache: Dict[str, List[str]], feed_type):
    if feed_type not in cache:
        cache[feed_type] = []

    d = feedparser.parse(feed_url)

    entries_to_report = []
    for e in d.entries:
        if e.link in cache[feed_type]:
            continue
        entries_to_report.append(e)
        cache[feed_type].append(e.link)

    return entries_to_report


def check_wookieepedia_feeds(site: Site, cache: Dict[str, List[str]]):
    messages = []

    to_delete = {}
    for p in Category(site, "Candidates for speedy deletion").articles():
        if p.title() not in cache["CSD"] and p.full_url() not in cache["CSD"]:
            to_delete[p.title()] = f"https://starwars.fandom.com/wiki/{p.title().replace(' ', '_')}"
            print(p.title())

    for url in FEED_URLS:
        entries = check_new_pages_rss_feed(site, url, cache)
        for cm in entries:
            if cm[2] in to_delete:
                to_delete.pop(cm[2])
            messages.append(cm)

    for p, u in to_delete.items():
        cache["CSD"] += [p, u]

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Bot_requests?action=history&feed=rss", cache, "Bot Requests")
    for e in entries:
        diff = parse_bot_request_diff(e.description)
        diff_text = f"\n{diff}" if diff else ""
        messages.append(("bot-requests", f"🔧 **WP:BR** was edited by **{e.author}**\n<{e.link}>{diff_text}", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Vandalism_in_progress?action=history&feed=rss", cache, "Vandalism")
    for e in entries:
        messages.append(("admin-help", f"❗ **WP:VIP** was edited by **{e.author}**\n<{e.link}>", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Spamfilter_problems?action=history&feed=rss", cache, "Spamfilter")
    for e in entries:
        messages.append(("admin-help", f"⚠️ **WP:SF** was edited by **{e.author}**\n<{e.link}>", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Image_requests?action=history&feed=rss", cache, "Image")
    for e in entries:
        messages.append(("images-and-audio", f"📷  **Wookieepedia:Image requests** was edited by **{e.author}**\n<{e.link}>", None))

    return messages, to_delete


def parse_bot_request_diff(description):
    results = []
    soup = BeautifulSoup(description, "html.parser")
    section = None
    for row in soup.find_all("tr"):
        if row.find("td", class_="diff-empty"):
            cells = row.find_all("td", class_=lambda c: c is None or 'diff-marker' not in c)
            if len(cells) == 2 and cells[0].get("class") is not None and "diff-empty" in cells[0].get("class"):
                if "==" in cells[1].text:
                    section = cells[1].text
                elif section:
                    results.append(re.sub("(\[\[User:|\{\{U\|).* [0-9]+:[0-9]+, [0-9]+ [A-z]+ 202[0-9] \(UTC\)", "", cells[1].text))
                else:
                    print(f"No new section detected for the following text: {cells[1].text}")

    return "\n".join([f"`{r.strip()}`" for r in results])


def check_entry(*, entries, title_regex, site, link, title, content, check_star_wars, video_id):
    r = requests.get(link).text
    title = check_title_formatting(r, title_regex, title)

    if check_star_wars and "star wars" not in title.lower().replace("-", " ") and \
            "star wars" not in content.lower().replace("-", " "):
        log(f"Skipping non-Star Wars post: {title} --> {link}")
        return

    entries.append({"site": site, "title": title, "url": link, "content": content,
                    "videoId": video_id})


def get_content_from_sw_article(text):
    soup = BeautifulSoup(text, "html.parser")
    content = soup.find("div", class_="content-area")
    if content:
        return content.text
    return ""


def check_sw_news_page(feed_url, cache: Dict[str, List[str]], title_regex):
    page_html = requests.get(feed_url).content
    soup = BeautifulSoup(page_html, "html.parser")

    site_cache = cache.get("StarWars.com")
    today = datetime.now().strftime("%B %d, %Y")

    initial_entries = []
    bumpers = soup.find_all("div", class_="content-bumper")
    for bumper in bumpers:
        try:
            h3 = bumper.find("h3", class_="title")
            link = h3.find("a").get("href")
            title = h3.find("span", class_="long-title").text.strip()
            initial_entries.append({"title": title, "url": link})
        except Exception as e:
            error_log(type(e), e)

    grid_items = soup.find_all("div", class_="text-content")
    for item in grid_items:
        try:
            a = item.find("a")
            link = a.get("href")
            title = a.text.strip()
            pub_date = item.find("p", class_="publish-date").text.strip()
            initial_entries.append({"title": title, "url": link, "date": pub_date})
        except Exception as e:
            error_log(type(e), e)

    final_entries = []
    d = datetime.now().strftime("%Y-%m-%d")
    for e in initial_entries:
        try:
            if site_cache and e["url"] in site_cache:
                continue

            r_text = requests.get(e["url"], timeout=5).text
            title = check_title_formatting(r_text, title_regex, e["title"])
            if not e.get("date"):
                x = re.search('<div class="publish-date">(.*?)</div>', r_text)
                if x:
                    e["date"] = x.group(1)

            if not site_cache:
                if e.get("date") and today not in e["date"]:
                    continue
            else:
                cache["StarWars.com"].append(e["url"])

            content = get_content_from_sw_article(r_text)
            u = e["url"].split("starwars.com/", 1)[1]
            cite = f"*{d}: {{{{SW|url={u}|text={e['title']}}}}}"
            final_entries.append({"site": "StarWars.com", "title": title, "url": e["url"], "content": content,
                                  "cite": cite})
        except Exception as e:
            error_log(type(e), e)

    # cache["StarWars.com"] = cache["StarWars.com"][-100:]
    return final_entries


def check_rss_feed(feed_url, cache: Dict[str, List[str]], site, title_regex, check_star_wars):
    x = None
    try:
        x = requests.get(feed_url, timeout=15).text
    except Exception as e:
        error_log(e)
    if not x:
        return []

    d = feedparser.parse(feed_url)

    site_cache = cache.get(site)
    today1 = datetime.now().strftime("%d %b %Y")
    if today1.startswith("0"):
        today1 = today1[1:]
    today2 = datetime.now().strftime("%Y-%m-%d")
    today3 = datetime.now().strftime("%Y/%m/%d")
    today4 = today3.replace("/0", "/")
    today5 = datetime.now().strftime("%Y%m%d")

    entries_to_report = []
    for e in d.entries:
        if site_cache and e.link in site_cache:
            continue
        elif not site_cache:
            if e.get("published") and today1 not in e.published and today2 not in e.published:
                continue
            elif not any(t in e.link for t in [today2, today3, today4, today5]):
                continue

        r = requests.get(e.link).text
        title = check_title_formatting(r, title_regex, e.title)
        content = ""
        if e.get("content"):
            content = e.content[0]["value"]
        elif e.get("description"):
            content = e.description
        elif e.get("summary"):
            content = e.summary

        if check_star_wars and "star wars" not in title.lower().replace("-", " ") and \
                "star wars" not in content.lower().replace("-", " "):
            log(f"Skipping non-Star Wars post: {title} --> {e.link}")
            continue
        template = None
        if content and "This week in Star Wars" in content:
            template = "ThisWeek"

        entries_to_report.append({"site": site, "title": title, "url": e.link, "content": content,
                                  "videoId": e.get("yt_videoid"), "template": template})
        cache[site].append(e.link)

    if cache.get(site):
        cache[site] = cache[site][-50:]

    return entries_to_report


def check_latest_url(url, cache: dict, site, title_regex):
    last_post_url = cache[site]
    response = requests.get(url, timeout=10)
    if response.url == url:
        error_log("Unexpected state, URL did not redirect")
        return []
    elif response.url == last_post_url:
        # log(f"No new articles found on {site}.")
        return []

    cache[site] = response.url
    title = re.search("<meta name=\"title\" content=\"(.*?)( \| Marvel)?\"", response.text)
    if title:
        title = title.group(1)
    else:
        log(f"Cannot extract title from URL: {response.url}")
        title = ""

    title = check_title_formatting(response.text, title_regex, title)

    if title and "star wars" in title.lower():
        return [{"site": site, "title": title, "url": response.url, "content": ""}]
    elif "star-wars" in response.url.lower():
        return [{"site": site, "title": title, "url": response.url, "content": ""}]
    elif title:
        log(f"Skipping notification for non-SW article {title}")
    else:
        log(f"Skipping notification for non-SW article {response.url}")
    return []


def check_title_formatting(text, title_regex, title):
    m = re.search(title_regex, text)
    if not m:
        return html.unescape(title).replace("’", "'")

    title = m.group(1)
    title = re.sub(r"<em>(.*?)( )?</em>", r"''\1''\2", title)
    title = re.sub(r"<i( .*?)?>(.*?)( )?</i>", r"''\2''\3", title)
    title = re.sub(r"<span[^>]*?italic.*?>(.*?)( )?</span>", r"''\1''\2", title)
    title = re.sub(r"<span[^>]*?italic.*?>(.*?)( )?</span>", r"''\1''\2", title)
    title = title.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")

    return html.unescape(title).replace("’", "'")


def check_review_board_nominations(site: Site):
    page = Page(site, "Wookieepedia:Review board membership nominations")
    text = page.get()

    noms = {"EduCorps": [], "AgriCorps": [], "Inquisitorius": []}
    for section in text.split("==[[Wookieepedia:"):
        board = section.split("|", 1)[0]
        if board not in noms:
            continue

        for u in re.findall("====\{\{U\|(.*?)\}\}====", section):
            if u != "USERNAME":
                noms[board].append(u)

    return noms


def check_user_rights_nominations(site: Site):
    page = Page(site, "Wookieepedia:Requests for user rights")
    text = page.get()

    noms = {"Rollback": [], "Admin": [], "Bureaucrat": []}
    for u in re.findall("\n{{/(.*?)/(.*?)}}", text):
        if u[0] not in noms:
            error_log(f"Unexpected nom type {u[0]}")
            noms[u[0]] = []
        if u[1] != "USERNAME":
            noms[u[0]].append(u[1])

    page2 = Page(site, "Wookieepedia:Requests for removal of user rights")
    text2 = page2.get()
    noms["Removal"] = []
    for u in re.findall("====\{\{U\|(.*?)\}\} \(.*?\)====", text2):
        noms["Removal"].append(u)

    return noms


def check_policy(site: Site):
    page = Page(site, "Wookieepedia:Policy and consensus updates")
    text = page.get()

    year = datetime.today().year
    section = text.split(f"={year}=")[1]
    section = section.split(f"={year - 1}")[0]
    updates = {}
    current = None
    for line in section.splitlines():
        if not line:
            continue
        elif line.startswith("=="):
            current = line.replace("==", "")
        else:
            if current not in updates:
                updates[current] = []
            match = re.search("'''CT:?''':?[ ]+\[\[(?P<link>.*?)\]\][ ]+.*?'''(?P<result>.*?)'''", line)
            if match:
                x = {k: v.replace("‎", "") for k, v in match.groupdict().items()}
                updates[current].append(x)
            else:
                print(f"Cannot identify results from {line}")
    return updates


def check_consensus_track_duration(site: Site, offset):
    category = Category(site, "Consensus track")
    result = {}

    now = datetime.now()
    for page in category.articles():
        created = page.oldest_revision['timestamp']
        result[page.title()] = now - (created - timedelta(hours=offset))

    return result


def build_site_map():
    t = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    directory = ET.fromstring(requests.get("https://www.starwars.com/sitemap.xml").text)
    results = set()
    skip = ["/news/contributor/", "/news/category/", "/news/tag/"]
    for e in directory:
        for i in e.findall(f'{t}loc'):
            part = ET.fromstring(requests.get(i.text).text)
            for u in part.findall(f"{t}url"):
                for loc in u.findall(f"{t}loc"):
                    if not any(s in loc.text for s in skip):
                        results.add(loc.text)
    return results
