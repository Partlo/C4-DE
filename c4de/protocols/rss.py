from typing import Dict, List
import xml.etree.ElementTree as ET
import feedparser
import json
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

ANNOUNCEMENTS = "announcements"
ADMIN_REQUESTS = "admin-requests"


def fix_title(title: str):
    if title.count(":") >= 2 and (title.startswith("Wookieepedia") or title.startswith("Forum")):
        return title.split(":", 2)[-1]
    return title


def check_new_pages_rss_feed(site, url, cache: Dict[str, List[str]]):
    d = feedparser.parse(url)
    is_new = "NewPages" in url

    entries_to_report = []
    for e in d.entries:
        try:
            pt, ch, message, d = None, None, None, None
            if is_new:
                if e.title.startswith("Forum:SH:"):
                    pt, ch, message = "Senate Hall", ANNOUNCEMENTS, f"📣 **New Senate Hall thread**: [{fix_title(e.title)}](<{e.link}>)"
                elif e.title.startswith("Forum:NB:"):
                    pt, ch, message = "Administrator's Noticeboard", ANNOUNCEMENTS, f"📢 **New Administrators' noticeboard thread**: [{fix_title(e.title)}](<{e.link}>)"
                elif e.title.startswith("Forum:CT:"):
                    pt, ch, message = "Consensus Track", ANNOUNCEMENTS, f"📢 **New Consensus track vote**: [{fix_title(e.title)}](<{e.link}>)"
                elif e.title.startswith("Forum:TC:") or e.title.startswith("Wookieepedia:Trash compactor"):
                    pt, ch, message = "Trash Compactor", ANNOUNCEMENTS, f"🗑️ **New Trash Compactor thread**: [{fix_title(e.title)}](<{e.link}>)"
                elif e.title.startswith("User blog:"):
                    if "Category:Staff blogs" in e.description or "Category:Technical Updates" in e.description or "{{blog_footer}}" in e.description.lower() or "{{blog footer}}" in e.description.lower():
                        pt, ch, message = "Fandom Blog", ANNOUNCEMENTS, f"<:fandom:872166055693393940>**New Fandom Staff blog post**\n<{e.link}>"
            elif re.match("^<p>.*? deleted page.*?</p>", e.description):
                continue
            elif e.title.startswith("Wookieepedia:Trash compactor") and re.match("^<p>.*?delete.*?</p>", e.description.lower()):
                continue
            elif e.title.startswith("Forum:TC:") and re.match("^<p>.*?delete.*?</p>", e.description.lower()):
                continue
            elif did_edit_add_deletion_template(site, e.title, e.description) or "<p>CSD</p>" in e.description or "<p>delete</p>" in e.description.lower():
                pt, ch, message = "CSD", ADMIN_REQUESTS, f"❗ **{e.author}** requested deletion of [**{e.title}**](<{e.link}>)"
                d = e.title
            elif re.match("^<p>.*?CSD.*?</p>", e.description) or re.match("^<p>.*?delete[^d].*?</p>", e.description.lower()):
                pt, ch, message = "CSD", ADMIN_REQUESTS, f"❓ **{e.author}** used 'delete' or 'CSD' in edit summary on [**{e.title}**](<{e.link}>); may be false positive"
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
        try:
            entries = check_new_pages_rss_feed(site, url, cache)
            for cm in entries:
                if cm[2] in to_delete:
                    to_delete.pop(cm[2])
                messages.append(cm)
        except Exception as e:
            error_log(type(e), e.args)

    for p, u in to_delete.items():
        cache["CSD"] += [p, u]

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Bot_requests?action=history&feed=rss", cache, "Bot Requests")
    for e in entries:
        diff = parse_bot_request_diff(e.description)
        diff_text = f"\n{diff}" if diff else ""
        messages.append(("bot-requests", f"🔧 **WP:BR** was edited by **{e.author}**: [view change](<{e.link}>)\n{diff_text}", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Forum:SH:General_bug_thread?action=history&feed=rss", cache, "Bug Thread")
    for e in entries:
        diff = parse_bot_request_diff(e.description)
        diff_text = f"\n{diff}" if diff else ""
        messages.append((ADMIN_REQUESTS, f"🔧 **Forum:SH:General bug thread** was edited by **{e.author}**: [view change](<{e.link}>)\n{diff_text}", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Vandalism_in_progress?action=history&feed=rss", cache, "Vandalism")
    for e in entries:
        messages.append((ADMIN_REQUESTS, f"❗ **WP:VIP** was edited by **{e.author}**: [view change](<{e.link}>)", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Spamfilter_problems?action=history&feed=rss", cache, "Spamfilter")
    for e in entries:
        messages.append((ADMIN_REQUESTS, f"⚠️ **WP:SF** was edited by **{e.author}**: [view change](<{e.link}>)", None))

    entries = parse_history_rss_feed("https://starwars.fandom.com/wiki/Wookieepedia:Image_requests?action=history&feed=rss", cache, "Image")
    for e in entries:
        messages.append(("images-and-audio", f"📷  **Wookieepedia:Image requests** was edited by **{e.author}**: [view change](<{e.link}>)", None))

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

    return "\n".join([f"```{r.strip()}```" for r in results if r])


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

    site = "StarWars.com"
    site_cache = cache.get(site)
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
                cache[site].append(e["url"])

            d = datetime.now().strftime("%Y-%m-%d")
            try:
                if e.get('date'):
                    x = datetime.strptime(e['date'], "%B %d, %Y")
                    if (datetime.now() - x).days >= 30:
                        continue
                    d = x.strftime("%Y-%m-%d")
                else:
                    d = None
            except Exception:
                pass
            content = get_content_from_sw_article(r_text)
            final_entries.append({"site": site, "title": title, "url": e["url"], "content": content, "date": d})
        except Exception as e:
            error_log(type(e), e)

    # cache["StarWars.com"] = cache["StarWars.com"][-100:]
    return final_entries


def check_ubisoft_news(site, url, feed_url, cache: Dict[str, List[str]]):
    page_html = requests.get(feed_url).content
    soup = BeautifulSoup(page_html, "html.parser")

    initial_entries = []
    for item in soup.find_all("a", class_="updatesFeed__item"):
        try:
            link = item.get("href")
            title = item.find("h2", class_="updatesFeed__item__wrapper__content__title").text.strip()
            pub_date = item.find("span", class_="date").text.strip()
            initial_entries.append({"title": title, "url": link, "date": pub_date})
        except Exception as e:
            error_log(type(e), e)

    final_entries = []
    for e in initial_entries:
        try:
            u = url + e["url"]
            if site not in cache:
                cache[site] = []
            if cache[site] and u in cache[site]:
                continue

            d = datetime.now().strftime("%Y-%m-%d")
            try:
                d = datetime.strptime(e['date'], "%B %d, %Y").strftime("%Y-%m-%d") if e.get('date') else None
            except Exception:
                pass
            final_entries.append({"site": site, "title": e["title"], "url": u, "content": "", "date": d})
            cache[site].append(u)
        except Exception as e:
            error_log(type(e), e)

    return final_entries


def check_blog_list(site, url, feed_url, cache: Dict[str, List[str]]):
    x = None
    try:
        x = requests.get(feed_url, timeout=15).text
    except Exception as e:
        error_log(e)
    if not x:
        return []

    soup = BeautifulSoup(x, "html.parser")
    results = []

    for article in reversed(soup.find_all(class_="transmission-wrapper")):
        link = article.find("a", class_="btn")
        if not link:
            continue
        u = link.get('href')
        if site not in cache:
            cache[site] = []
        if cache[site] and u in cache[site]:
            continue

        title = article.find("h2", class_="allblog-title")
        d = article.find("h3", class_="dateski")
        date = d.text.strip() if d else None
        try:
            date = datetime.strptime(date, "%m/%d/%Y").strftime("%Y-%m-%d")
        except Exception:
            pass
        results.append({"site": site, "title": title.text if title else None, "url": u, "content": "", "date": date})
        cache[site].append(u)

    return results


def check_unlimited(site, url, feed_url, cache: Dict[str, List[str]]):
    x = None
    try:
        x = requests.get(feed_url, timeout=15).text
    except Exception as e:
        error_log(e)
    if not x:
        return []

    soup = BeautifulSoup(x, "html.parser")
    results = []
    if site not in cache:
        cache[site] = []

    script = soup.find("script", id="__NEXT_DATA__")
    if script and any(s and "dehydratedState" in s for s in script.contents):
        target = next(s for s in script.contents if s and "dehydratedState" in s)
        data = json.loads(target)
        articles = data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"]["data"]["data"]
        for a in articles:
            u = f"{url}/articles/{a['attributes']['slug']}"
            if cache[site] and u in cache[site]:
                continue
            d = None
            if a["attributes"]["publishedAt"]:
                d = a["attributes"]["publishedAt"].split("T")[0]
            t = re.sub("'*Star Wars'*", "''Star Wars''", a["attributes"]["title"])

            results.append({"site": site, "title": t, "url": u, "content": "", "date": d})
            cache[site].append(u)

    return results


def check_ea_news(site, url, feed_url, cache: Dict[str, List[str]]):
    x = None
    try:
        x = requests.get(feed_url, timeout=15).text
    except Exception as e:
        error_log(e)
    if not x:
        return []

    soup = BeautifulSoup(x, "html.parser")
    results = []

    for article in reversed(soup.find_all("ea-tile")):
        link = article.find("ea-cta")
        if not link:
            continue
        link = link.find("a")
        if not link:
            continue
        u = url + link.get('href')
        if site not in cache:
            cache[site] = []
        if cache[site] and u in cache[site]:
            continue

        d = article['eyebrow-secondary-text']
        try:
            d = datetime.strptime(d, "%b %d, %Y").strftime("%Y-%m-%d")
        except Exception:
            pass

        results.append({"site": site, "title": article['title-text'], "url": u, "content": "", "date": d})
        cache[site].append(u)

    return results


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

        if site == "*Star Wars: The Old Republic*":
            if any(x in e.title.lower() for x in ["mise à jour", "de l'histoire", "spieleupdate", "spiel-update", "teaser-clip"]):
                continue
            elif any(f" {x} " in f" {e.title.lower()} " for x in ["de", "la", "zu", "der", "des", "sur"]):
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
            cache[site].append(e.link)
            continue
        template = None
        if (content and ("this week in" in content.lower() or "this week!" in content.lower())) or \
                (title and ("this week in" in title.lower() or "this week!" in title.lower())):
            template = "ThisWeek"
            if "Dispatch" in title:
                title = f"Dispatch: {title.replace('Dispatch', '')}"
            title = title.replace(" &#124; This Week! in Star Wars", "").replace(" | This Week! in Star Wars", "")
        elif content and "the high republic show" in content.lower():
            template = "HighRepublicShow"

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

    if match_terms(title.lower()):
        return [{"site": site, "title": title, "url": response.url, "content": ""}]
    elif match_terms(response.url.lower()):
        return [{"site": site, "title": title, "url": response.url, "content": ""}]
    elif title:
        log(f"Skipping notification for non-SW article {title}")
    else:
        log(f"Skipping notification for non-SW article {response.url}")
    return []


def match_terms(val):
    return any(x in val or x.replace(" ", "-") in val for x in ["star wars", "ahsoka", "ewoks", "mandalorian"])


def check_title_formatting(text, title_regex, title):
    m = re.search(title_regex, text)
    if m:
        title = m.group(1)
    title = re.sub(r"<em>(.*?)( )?</em>", r"''\1''\2", title)
    title = re.sub(r"<i( .*?)?>(.*?)( )?</i>", r"''\2''\3", title)
    title = re.sub(r"<span[^>]*?italic.*?>(.*?)( )?</span>", r"''\1''\2", title)
    title = re.sub(r"<span[^>]*?>(.*?)( )?</span>", r"\1\2", title)
    title = title.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    title = title.replace("|", "&#124;")
    title = re.sub(" &#124; ?D[Ii][Ss][Nn][Ee][Yy] ?(\+|Plus)[ ]*(& Disney Junior)?[ ]*$", "", title)
    title = re.sub(" (&#124; )?@?StarWarsKids *?x *?@?disneyjunior", "", title)
    if title.strip().endswith("&#124;"):
        title = title.strip()[:-6]
    return html.unescape(title).replace("’", "'").strip()


def check_review_board_nominations(site: Site):
    page = Page(site, "Wookieepedia:Review board membership nominations")
    text = page.get()

    noms = {"EduCorps": [], "AgriCorps": [], "Inquisitorius": []}
    for section in text.split("==[[Wookieepedia:"):
        board = section.split("|", 1)[0]
        if board not in noms:
            continue

        for u in re.findall("====\{\{U\|(.*?)\}\}.*?====", section):
            if u != "USERNAME":
                noms[board].append(u)

    page = Page(site, "Wookieepedia:Review board recruitment")
    text = page.get()
    interested = {"EduCorps": {}, "AgriCorps": {}, "Inquisitorius": {}}
    for section in text.split("===Expression")[1:]:
        board = section.split("|", 1)[0].split("Wookieepedia:")[-1]
        if board not in interested:
            continue

        for u in re.findall("(\[\[User:|{{U\|)(?P<user>.*?)(\|.*?)?(\]\]|\}\})", section):
            if u[1] != "USERNAME":
                interested[board][u[1]] = datetime.now().strftime("%Y-%m-%d")

    return noms, interested


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
    for u in re.findall("\n{{/(.*?)}}", text2):
        if u != "USERNAME":
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


SKIPS = ["audio", "activities", "behind-the-scenes", "community", "databank", "disneyplus", "films", "force-for-change",
         "fuel-your-force", "games-apps", "halloween", "interactive", "life-day", "news", "science-and-star-wars",
         "search", "series", "the-high-republic", "the-star-wars-show", "video", "databank/the-rise-of-skywalker",
         "empire-40th", "esbuncut", "mando-mania", "much-to-learn", "rebels-recon", "return-of-the-jedi-40th",
         "star-wars-40th", "star-wars-celebration", "star-wars-day", "star-wars-galaxy-of-adventures", "tarkin",
         "this-is-madness", "this-week-in-star-wars", "the-star-wars-show-book-club", "the-high-republic-show",
         "obi-wan-wednesdays", "our-star-wars-stories"]
PREFIXES = ["/news/contributor/", "/news/category/", "/news/tag/", "/games-apps/", "/star-wars-fan-awards/", "/interactive/", "/audio/", "fan-awards", "fan-film"]
GALLERIES = ["-history-gallery", "-biography-gallery", "-biography-slideshow", "the-force-gallery", "-details-gallery",
             "-poster-gallery", "-posters-gallery", "-stills-gallery", "/poster-gallery", "/posters-gallery",
             "/stills-gallery", "poster-and-promo-gallery", "-character-posters"]

FULL_SKIP = ["jazwares-micro-galaxy", "jazwares-micro-galaxy-series-v", "news/colin-trevorrow-dirigira-star-wars-episodio-ix",
             "the-high-republic-claudia-gray", "the-high-republic-concept-art-gallery",
             "the-high-republic-daniel-cavan-scott", "the-high-republic-daniel-charles-soule",
             "the-high-republic-daniel-jose-older", "the-high-republic-george-mann",
             "the-high-republic-justina-ireland", "the-high-republic-lydia-kang",
             "the-high-republic-tessa-gratton", "the-high-republic-zoraida-cordova",]


def build_site_map(full: bool):
    t = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    directory = ET.fromstring(requests.get("https://www.starwars.com/sitemap.xml").text)
    results = set()
    for e in directory:
        for i in e.findall(f'{t}loc'):
            part = ET.fromstring(requests.get(i.text).text)
            for u in part.findall(f"{t}url"):
                for loc in u.findall(f"{t}loc"):
                    if full:
                        results.add(loc.text.split("starwars.com/", 1)[-1])
                        continue

                    if any(loc.text.endswith(f".com/{s}") for s in SKIPS):
                        continue
                    elif any(loc.text.endswith(f".com/{s}") for s in FULL_SKIP):
                        continue
                    elif any(s in loc.text for s in PREFIXES):
                        continue
                    elif any(s in loc.text for s in GALLERIES):
                        continue
                    elif "/series/" in loc.text and re.match(".*?/series/[a-z0-9-]+$", loc.text):
                        continue
                    elif "/archived-201" in loc.text or "/archived-202" in loc.text:
                        continue
                    elif "/databank/" in loc.text and re.search("/databank/[a-z0-9-]+-all", loc.text):
                        continue
                    elif loc.text.endswith("-gallery"):
                        continue
                    results.add(loc.text.split("starwars.com/", 1)[-1])
    return results


def compile_tracked_urls(site):
    urls = []
    for y in range(1990, datetime.now().year + 1):
        p = Page(site, f"Wookieepedia:Sources/Web/{y}")
        if p.exists():
            for line in p.get().splitlines():
                if "|sw_url=" in line:
                    urls.append(line.split("|sw_url=")[-1].split("|")[0].split("}", 1)[0])
                elif "{{SW|" in line:
                    urls.append(line.split("|url=", 1)[-1].split("|")[0].split("}", 1)[0])
                    if "{{C|alternate: " in line:
                        urls.append(line.split("alternate: ", 1)[-1].split("}", 1)[0])

    for line in Page(site, "Wookieepedia:Sources/Web/Databank").get().splitlines():
        if "{{Databank|url=" in line:
            urls.append(line.split("|url=", 1)[-1].split("|")[0].split("}", 1)[0])
        elif "{{Databank|" in line:
            urls.append("databank/" + line.split("{{Databank|", 1)[-1].split("|")[0].split("}", 1)[0])
    return urls


IGNORE = """
ahsoka-props-costumes-sdcc-2023
art-inspired-by-the-mandalorian
badge-art-swce23
character-posters-ahsoka
community/force-for-change-at-the-force-awakens-world-premiere
community/star-wars-fans
community/star-wars-legion-gallery-part-1
community/star-wars-legion-gallery-part-2
community/star-wars-legion-gallery-part-3
covers-the-high-republic
dark-horse-the-high-republic-phase-iii-artwork-reveal
disneyplus/lego-star-wars
fashion-illustrator-marilee-heyer-sketches
films/star-wars-episode-ix-the-rise-of-skywalker
first-look-the-mandalorian-season-two
gift-the-galaxy-good-morning-america
heroes-concept-art-the-high-republic
lego-star-wars-holiday-special-concept-art
lego-star-wars-the-force-awakens-screenshots
lego-star-wars-the-skywalker-saga
mandalorian-mayhem-rocket-league-screenshots
marvel-star-wars-rebels-variant-covers
news/20-favorite-quotes-the-mandalorian-season-one
news/the-recruit-episode-guide-star-wars-resistance
rebels-season-two-fan-art-contest-winners
screenshots-minecraft-star-wars-path-of-the-jedi-dlc
shag-beeline-creative-return-of-the-jedi-collection
star-wars-battlefront-screenshots
star-wars-celebration-live-backstage
star-wars-eclipse-screenshots
star-wars-force-arena-mobile-screenshots
star-wars-frames-a-new-hope
star-wars-frames-the-empire-strikes-back
star-wars-heroes-path-screenshots
star-wars-hunters-screenshots
star-wars-insider-the-mighty-walt-marvel-covers
star-wars-jedi-fallen-order-journey-screenshots
star-wars-jedi-survivor-screenshots
star-wars-journey-to-batuu-gameplay-screenshots
star-wars-the-high-republic-character-encyclopedia-nycc-2023
star-wars-uprising-screenshots
stellan-gios-lightsaber-the-high-republic
swce-2023-online-store-products
tales-from-the-death-star-nycc-2023
the-bad-batch-mobile-wallpaper
the-empire-strikes-back-ralph-mcquarrie
thra-6-preview
thra-7-preview
thra-8-preview
villains-concept-art-the-high-republic

art-awakens-official-rules
eras
go-rogue-contest
news/star-wars-celebration-europe-2023-tickets-retire
projectlegion
series/star-wars-resistance/shorts-collection
series/the-mandalorian/bounty-hunting-highlights
star-wars-rebels-season-2-fan-art-contest
the-high-republic-cavan-scott"""


def compare_site_map(site, series, already_tracked, cache):
    skip = [m['url'] for m in (already_tracked or [])]
    urls = compile_tracked_urls(site)
    sitemap = build_site_map(False)

    guides, db, series_db = augment_site_map(site, series, urls)
    sitemap = sitemap.union(list(guides) + list(db.keys()) + list(series_db.keys()))
    updated_db_entries = {u: t for u, t in db.items() if u in urls}

    return handle_site_map(sitemap, urls, skip, updated_db_entries, guides)


def handle_site_map(sitemap: set, urls, skip, updated_db_entries, guides):
    diff = []
    ignore = IGNORE.splitlines()
    for x in sorted(sitemap):
        if x in urls or x in ignore or x == "https://www.starwars.com":
            continue
        # elif "-concept-art-gallery" in x or "-episode-stills" in x or "-trivia-gallery" in x or x.startswith("video/"):
        elif x.startswith("video/"):
            continue

        u = f"https://www.starwars.com/{x}"
        if x in skip or u in skip:
            continue
        r = requests.get(u)
        if r.url != u:
            continue
        elif '<section class="module image_gallery' in r.text and x not in guides:
            continue
        title = re.search("<title>(.*?)</title>", r.text)
        if title:
            title = title.group(1).replace(" | StarWars.com", "").strip()
        else:
            title = "Unable to Determine Title"
        title = title.replace("’", "'").replace('&#39;', "'").replace('&quot;', '"')
        s = "Databank" if x.startswith("databank/") else "StarWars.com"
        if s == "Databank" and ("- " in title or "|" in title):
            title = re.sub(" ?[-\|] (The Acolyte|Star Wars Databank|Databank)", "", title)
        if u in updated_db_entries:
            updated_db_entries.pop(u)
        diff.append({"site": s, "url": u, "title": title, "date": datetime.now().strftime('%Y-%m-%d')})
    return diff, updated_db_entries


def convert_to_url(s):
    return s.lower().split("(")[0].strip().replace("/", "").replace("  ", " ").replace(" ", "-")


def augment_site_map(site, series, urls):
    urls_to_check = set()
    db_entries = {}
    series_db_entries = {}
    for s in series:
        st = convert_to_url(s.replace("Star Wars: ", ""))
        _, series_urls, series_db = check_series_page(f"https://starwars.com/series/{st}")
        urls_to_check.update(series_urls)
        series_db_entries.update(series_db)

        data = requests.get(f"https://www.starwars.com/_grill/filter/series/{st}?filter=All&mod=8&slug=all").json()
        for a in data['data']:
            series_db_entries[a['href'].split('.com/')[-1]] = re.sub(" ?- ?The Acolyte", "", a['title'])
        while data.get('next'):
            data = requests.get(f"https://www.starwars.com/_grill/filter/series/{st}{data['next']}").json()
            for a in data['data']:
                series_db_entries[a['href'].split('.com/')[-1]] = re.sub(" ?- ?The Acolyte", "", a['title'])

        cat = Category(site, f"Category:{s} episodes")
        if not cat.exists():
            continue
        for p in cat.articles():
            if p.title().startswith("Episode "):
                continue
            episode = convert_to_url(p.title())
            if "'" in p.title():
                if check_episode(st, episode.replace("'", ""), urls, urls_to_check, db_entries):
                    continue
            check_episode(st, episode, urls, urls_to_check, db_entries)
        check_episode(st, "season-1-episode-8-the-acolyte", urls, urls_to_check, db_entries)

    return urls_to_check, db_entries, series_db_entries


def check_target_url(url, urls):
    x, u = url.split(".com/", 1)
    if u in urls:
        return True, None, None
    exists, ep_urls, ep_db = check_series_page(f"https://www.starwars.com/{u}")
    if exists:
        ep_urls.add(u)
        log(f"Found {len(list(ep_db))} entries and {len(ep_urls)} pages on {u}")
    return exists, ep_urls, ep_db


def check_episode(st, episode, urls, urls_to_check, db_entries):
    u = f"series/{st}/{episode}-episode-guide"
    if u in urls:
        return True

    exists, ep_urls, ep_db = check_series_page(f"https://www.starwars.com/{u}")
    if exists:
        urls_to_check.add(u)
        urls_to_check.update(ep_urls)
        log(f"Found {len(list(ep_db))} entries and {len(ep_urls)} pages on {u}")
        db_entries.update(ep_db)
    return exists


def check_series_page(url):
    urls_to_check, db_entries = set(), {}
    r = requests.get(url)
    if r.status_code == 200 and r.url == url:
        soup = BeautifulSoup(r.content, "html.parser")
        for l in [*soup.find_all("ol", class_="slider-list"), *soup.find_all("section", class_="incredibles_slider"), *soup.find_all("div", "display_filters")]:
            if 'data-title' in l.attrs and "Galleries" in l['data-title']:
                for a in l.find_all("a", class_="entity-link"):
                    urls_to_check.add(a['href'].split('.com/')[-1])
            elif 'data-title' in l.attrs and "Databank" in l['data-title']:
                for a in l.find_all("a", class_="title-link"):
                    db_entries[a['href'].split('.com/')[-1]] = re.sub(" ?- ?The Acolyte", "", a['data-title'])

    return r.status_code == 200, urls_to_check, db_entries
