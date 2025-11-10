import traceback

import time
import json
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

from pywikibot import Site, Page, Category, showDiff
from get_chrome_driver import GetChromeDriver

from selenium.common.exceptions import WebDriverException, SessionNotCreatedException, ElementNotInteractableException
from selenium.webdriver import Remote as WebDriver, Chrome, ChromeService, Firefox, FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from c4de.common import log, error_log, archive_url
from c4de.data.filenames import MISSING_IMAGES_FILE


def build_driver(headless=True, firefox=True):
    if firefox:
        options = FirefoxOptions()
        s = FirefoxService("C:/Users/cadec/Documents/Drivers/geckodriver.exe")
        if headless:
            options.headless = True
            # options.add_argument("no-sandbox")
            # options.add_argument('window-size=1024,768')
            # --start-maximized does not work, headless thinks the maximized size is 800*600, making the element not visible;
            # options.add_experimental_option("prefs", {"credentials_enable_service": False})
        return Firefox(options=options, service=s)
    else:
        options = ChromeOptions()
        s = Chrome("C:/Users/cadec/Documents/Drivers/chromedriver.exe")
        if headless:
            options.add_argument("headless")
            options.add_argument("no-sandbox")
            options.add_argument('window-size=1024,768')
            # --start-maximized does not work, headless thinks the maximized size is 800*600, making the element not visible;
            options.add_experimental_option("prefs", {"credentials_enable_service": False})
        try:
            return Chrome(options=options, service=s)
        except SessionNotCreatedException as e:
            gd = GetChromeDriver()
            gd.auto_download(extract=True, output_path="C:/Users/cadec/Documents/Drivers")
            return Chrome(options=options, service=s)


def extract_isbns(title, text, data):
    if re.search(r"\[\[Category:.*?authors[|\]]", text):
        return
    isbns = []
    for i in re.findall(r"\n\|isbn=([- 0-9A-Z]+?)\n", text):
        x = i.replace("-", "").replace(" ", "").strip()
        if x:
            isbns.append(x)
    for i in re.findall(r"\*{{ISBN\|([0-9]+)}}", text):
        if i:
            isbns.append(i)
    if isbns:
        data[title] = set(isbns)


def calculate_isbns_for_all_pages(site):
    """ Scans the entire wiki for all usages of the ISBN template and the ISBN infobox parameter, recording them in a
      dict that is saved to Template:ISBN/data in JSON form. """

    isbns_by_page = {}
    log("ISBN Protocol: Checking media category")
    for p in Category(site, "Media with defined ISBN").articles():
        if p.title().startswith("List of") or p.title().startswith("Timeline of "):
            continue
        elif p.title() in isbns_by_page:
            continue
        elif p.isRedirectPage():
            p = p.getRedirectTarget()
        extract_isbns(p.title(), p.get(), isbns_by_page)

    log("ISBN Protocol: Checking template usages")
    for p in Page(site, "Template:ISBN").getReferences(namespaces=0, only_template_inclusion=True):
        if p.title().startswith("List of") or p.title().startswith("Timeline of "):
            continue
        elif p.title() in isbns_by_page:
            continue
        extract_isbns(p.title(), p.get(), isbns_by_page)

    page = Page(site, "Template:ISBN/data")
    text = []
    for k in sorted(isbns_by_page):
        text.append('    ' + json.dumps(k) + ": " + json.dumps(sorted(list(isbns_by_page[k]))))
    page_text = "{" + ",\n".join(text) + "}"
    page.put(page_text, "Updating sitewide ISBN records", botflag=False)
    return isbns_by_page


def load_pages_by_isbn(site):
    page = Page(site, "Template:ISBN/data")
    results = {}
    for k, v in json.loads(page.get()).items():
        for i in v:
            results[i] = k
    return results


def load_false_positives(site):
    page = Page(site, "User:C4-DE Bot/Products")
    if page.exists():
        return json.loads(page.get())
    return []


def handle_entry(item: WebElement, sku_list, search_term):
    body = item.find_element(By.CSS_SELECTOR, "div[class^='productRowBody']")
    publisher_line = item.find_element(By.CSS_SELECTOR, "div[class^='itemHeader']")
    publisher = re.sub(r"^[0-9]+ \([0-9]+\)\.? (.*?)$", "\\1", publisher_line.text.strip().splitlines()[0])
    no_image = bool(body.find_elements(By.CSS_SELECTOR, "div[class^='noJacketImage']"))

    info = body.find_element(By.CSS_SELECTOR, "div[class^='biblioOneAndTwo']")
    if not info:
        log("Error: cannot find biblio")
        return None

    data = info.find_elements(By.CSS_SELECTOR, "div.dotDot")
    status, date, _ = re.split(r" ?\| ?", data[0].text, 2)
    isbn, sku = data[1].text.split(",", 1)
    fmt = data[2].text
    if sku in sku_list:
        return None
    else:
        sku_list.append(sku)

    title_link = body.find_element(By.ID, "title-actions-button")
    title = title_link.text
    sn = title_link.find_elements(By.CSS_SELECTOR, "span[class^='subTitleName']")
    subtitle = sn[0].text if sn else ""
    if subtitle:
        title = re.sub(r"^(.*?):$", "\\1", title.splitlines()[0].strip())

    if search_term.lower() not in body.get_attribute("innerHTML").lower():
        log(f"{search_term} not mentioned in {title}; skipping")
        return None

    print(title, no_image)

    categories = ""
    for c in info.find_element(By.TAG_NAME, "div").find_elements(By.TAG_NAME, "div"):
        if "BISAC" in c.text:
            categories = c.text.replace("BISAC: ", "")
            break

    if "CANCELED" in status or "CANCELLED" in status:
        print(f"Skipping canceled product: {title}")
        return None
    elif "BACKLIST" in status:
        return None
    elif "Thomas Kinkade Studios" in title:
        return None
    elif "Non-Classifiable" in categories:
        return None

    return {
        "title": title.replace("[", "(").replace("]", ")"),
        "subTitle": subtitle,
        "publicationDate": date.strip(),
        "hasImage": not no_image,
        "isbn": isbn.strip(),
        "sku": sku.strip(),
        "status": status,
        "publisher": publisher,
        "format": fmt,
        "categories": categories
    }


def extract_items_from_edelweiss(driver: WebDriver, search_term, sku_list: List[str]) -> List[dict]:
    """ Loads the product listings from the Edelweiss website, using Selenium to traverse and parse the webpage. """

    driver.get(f"https://www.edelweiss.plus/#keywordSearch&q={search_term.replace(' ', '+')}")
    time.sleep(15)

    try:
        # wait for "Not Yet Published" button
        log("Waiting for Not Yet Published button")

        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CLASS_NAME, "ListView__filterButton")))
        button = driver.find_element(By.CLASS_NAME, "ListView__filterButton")
        try:
            button.click()
        except WebDriverException:
            driver.execute_script("arguments[0].scrollIntoView()", button)
            button.click()

        WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.ID, "filterDrawerId")))
        WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CLASS_NAME, "MuiListItem-root")))

        found = None
        for x in driver.find_elements(By.CLASS_NAME, "MuiListItem-root"):
            b = x.find_element(By.CSS_SELECTOR, "button.MuiButtonBase-root")
            if b and b.text == "Publishing Status":
                found = x
                b.click()
                time.sleep(1)
                for s in x.find_elements(By.CSS_SELECTOR, "span.MuiFormControlLabel-label"):
                    if "Forthcoming" in s.text:
                        s.click()

        if not found:
            raise Exception

        close = driver.find_element(By.CSS_SELECTOR, "#filterDrawerId button[aria-label='Close Modal']")
        try:
            close.click()
        except WebDriverException:
            driver.execute_script("arguments[0].scrollIntoView()", button)
            close.click()

    except Exception as e:
        print(f"Encountered {type(e)} while looking for Not Yet Published button")

    time.sleep(3)
    log("Waiting for results")
    try:
        WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div[class^='listViewItemsCount']")))
    except Exception:
        driver.get(f"https://www.edelweiss.plus/#keywordSearch&q={search_term.replace(' ', '+')}")
        WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div[class^='listViewItemsCount']")))

    x = driver.find_elements(By.CSS_SELECTOR, "div[class^='listViewItemsCount']")
    if not x:
        x = driver.find_elements(By.CSS_SELECTOR, "div[class^='listViewItemsCount']")
    total = re.sub("^.*?filtered to ([0-9]+).*?$", "\\1", x[0].text.replace("\n", ""))
    total = int(total) if total else 500

    i, j = 0, 1
    results = []
    while i < total:
        log(f"Processing page {j}")

        for item in driver.find_elements(By.CSS_SELECTOR, "div[class^='productRow_']"):
            try:
                ix = handle_entry(item, sku_list, search_term)
                if ix:
                    results.append(ix)
            except Exception as e:
                error_log(type(e), e.args)

        i += 50
        j += 1
        buttons = driver.find_elements(By.CSS_SELECTOR, "button.MuiButton-root.MuiButton-contained")
        for b in buttons:
            if b.text.lower() == "next page":
                b.click()
                time.sleep(3)

    return results


def page_exists(site: Site, title: str, media_type: str):
    for t in [f"{title} ({media_type})", title]:
        page = Page(site, t)
        if page.exists() and page.isRedirectPage():
            return page.getRedirectTarget()
        elif page.exists():
            return page
    return None


def determine_page(site: Site, title: str, item: dict, pages_by_isbn: Dict[str, str]) -> Tuple[Optional[Page], bool]:
    title = title.replace(" [NEW PRINTING]", "")
    if item['isbn'] in pages_by_isbn:
        return Page(site, pages_by_isbn[item['isbn']]), True

    if "(Star Wars)" in title:
        title = title.replace(" (Star Wars)", "")

    subtitle = item.get("subtitle", "")
    if subtitle.startswith(": "):
        subtitle = subtitle[:2]
    if "(Unabridged)" in subtitle:
        subtitle = subtitle.replace("(Unabridged)", "").strip()

    media_type = "novel"
    if "audio" in item["format"].lower():
        media_type = "audiobook"
    elif any("Graphic Novels" in c for c in item["categories"]):
        media_type = "TPB"

    titles = [title]
    if subtitle:
        titles += [f"{title}: {subtitle}", f"{title} — {subtitle}"]

    for t in titles:
        page = page_exists(site, t, media_type)
        if page:
            return page, False

    m = re.search(r"(.*?): Star Wars Legends( \((.*?)\))?$", title)
    if m:
        titles = [f"{m.group(3)}: {m.group(1)}", m.group(1)]
        if subtitle:
            titles += [f"{m.group(3)}: {m.group(1)}: {subtitle}", f"{m.group(3)}: {m.group(1)} — {subtitle}"]
        for t in titles:
            page = page_exists(site, t, media_type)
            if page:
                return page, False
        return None, False

    m = re.search(r"Star Wars: (.*?) \((.*?)\)", title.replace("World of Reading: ", ""))
    if m:
        titles = [f"{m.group(2)}: {m.group(1)}", f"Star Wars: {m.group(2)}: {m.group(1)}"]
        if re.search(r".*?: .*?", m.group(1)):
            titles.append(m.group(1))
        if subtitle:
            titles += [f"{m.group(2)}: {m.group(1)}: {subtitle}", f"{m.group(2)}: {m.group(1)} — {subtitle}"]
        for t in titles:
            page = page_exists(site, t.strip(), media_type)
            if page:
                return page, False
        return None, False

    return None, False


def load_products_missing_images():
    with open(MISSING_IMAGES_FILE, "r") as f:
        data = json.load(f)
    return data


def save_products_missing_images(skus):
    with open(MISSING_IMAGES_FILE, "w") as f:
        f.write(json.dumps(skus))


def archive_sku(sku):
    try:
        success, archive_date = archive_url(f"https://www.edelweiss.plus/#sku={sku}")
        return f" (Archive Date: {archive_date})" if success else ""
    except Exception as e:
        error_log(type(e), e)


def prepare_title(x: str):
    return (x.title() if x.isupper() else x).replace("Lego", "LEGO")


def analyze_products(site, products: List[dict], search_terms):
    false_positives = load_false_positives(site)
    pages_by_isbn = load_pages_by_isbn(site)
    missing_images = load_products_missing_images()
    processed = set()

    results = {"newItems": [], "newDates": [], "newImages": [], "reprints": [], "unknown": [], "newTPBs": []}
    reprints = {}
    new_missing_images = []
    for item in products:
        try:
            url = f"<https://www.edelweiss.plus/#sku={item['sku']}>"
            page, by_isbn = determine_page(site, item["title"], item, pages_by_isbn)
            if not item["hasImage"]:
                new_missing_images.append(item["sku"])

            if not page and any(s.lower() in item["title"].lower() for s in false_positives):
                continue
            elif not page and not any(s.lower() in item["title"].lower() for s in search_terms):
                results["newItems"].append((item['sku'], f"(Potential False Positive): {item['title']} - {url}{archive_sku(item['sku'])}"))
                continue
            elif not (page and page.exists()):
                if any("Graphic Novels" in c for c in item["categories"]):
                    results["newTPBs"].append((item['sku'], f"{item['title']} - {url}"))
                else:
                    title = prepare_title(item['title'])
                    results["newItems"].append((item['sku'], f"[{title}](https://starwars.fandom.com/{title.replace(' ', '_')}) - {url}{archive_sku(item['sku'])}"))
                continue
            if page.title() == "Hyperspace Stories: Qui-Gon":
                continue
            dupe = page.title() in processed
            processed.add(page.title())

            if "(" in page.title():
                t, p = page.title().split("(", 1)
                title = f"*{t.strip()}* ({p}"
            else:
                title = f"*{page.title()}*"

            page_url = page.full_url().replace(" ", "_")
            text = page.get()
            date_strs = []
            m = re.search(r"\|(publish date|publication date|release date|released|published)=(.*?)(<.*?)?\n(\*(.*?)(<.*?)?\n)*", text)
            if m:
                date1 = re.sub(r"\([A-Z]+\)", "", m.group(2).replace("[", "").replace("]", "").replace("*", "").replace(" ,", ",").strip())
                date_strs.append(re.sub(r"([A-z]+ [0-9]+) ([0-9]+)", "\\1, \\2", date1))
                if m.group(5):
                    date2 = m.group(5).replace("[", "").replace("]", "").replace("*", "").strip()
                    date_strs.append(re.sub(r"([A-z]+ [0-9]+) ([0-9]+)", "\\1, \\2", date2))

            if "isbn=none" in text:
                print(f"Saving new ISBN {item['isbn']} for {page.title()}")
                text = text.replace("isbn=none", f"isbn={item['isbn']}")
                page.put(text, f"Saving new ISBN {item['isbn']} from Edelweiss", botflag=False)
                if page.title() not in pages_by_isbn:
                    pages_by_isbn[page.title()] = []
                pages_by_isbn[page.title()].append(item['isbn'])

            if not date_strs and " 202" not in item.get("publicationDate", ""):
                log(f"{page.title()} has a release date of {item.get('publicationDate')}")
                continue
            elif not date_strs:
                log(f"No release date found in {page.title()}")
                continue
            elif not item.get("publicationDate"):
                log(f"No publication date found for {item['title']}")
                continue
            if item["status"] and any(s in item["status"].lower() for s in ["canceled", "cancelled", "postponed"]):
                if any("Canceled" in d or "Cancelled" in d for d in date_strs) or "{{Canceled" in text:
                    log(f"Skipping canceled product {item['title']}")
                    continue
                else:
                    arc = archive_sku(item['sku'])
                    log(f"{title} has been listed as canceled")
                    results["canceled"].append((item['sku'], f"[{title}]({page_url}) has been listed as canceled: {url}{arc}"))
                    continue

            page_dates = []
            for d in date_strs:
                c = re.sub(r"\([A-Z]+\)", "", d.split("{{C|")[0].strip()).replace(",", "")
                if c:
                    try:
                        page_dates.append(datetime.strptime(c, "%B %d %Y"))
                    except Exception as e:
                        try:
                            page_dates.append(datetime.strptime(c.replace(',', ''), "%B %Y"))
                        except Exception as e2:
                            print(e2)
            item_date = datetime.strptime(item["publicationDate"], "%b %d, %Y")

            past = any([d < datetime.now() for d in page_dates])
            if item["sku"] in missing_images and item["hasImage"]:
                results["newImages"].append((item['sku'], f"{title} - {url}{archive_sku(item['sku'])}"))
            elif any([d == item_date for d in page_dates]):
                log(f"No date changes found for {page.title()}")
            elif past and by_isbn:
                log(f"Reprint {item['isbn']} already recorded on {page.title()}")
            elif by_isbn and different_isbn_and_already_listed(text, item['isbn']):
                log(f"{title} already recorded with a different ISBN")
            else:
                arc = archive_sku(item['sku'])
                if past:
                    results["reprints"].append((item['sku'], f"[{title}]({page_url}): {item['isbn']} - {url}{arc}"))
                    if page.title() not in reprints:
                        reprints[page.title()] = []
                    reprints[page.title()].append(item)
                elif by_isbn and dupe:
                    log(f"[{title}]({page.full_url()}): Duplicate listing {item['isbn']} has publication date {item['publicationDate']}")
                elif by_isbn:
                    results["newDates"].append((item['sku'], f"[{title}]({page_url}): {item['publicationDate']} (formerly {date_strs[0]}){arc}"))
                else:
                    results["unknown"].append((item['sku'], f"Different publication dates found for [{title}]({page_url}), but no ISBN - {url}{arc}"))
        except Exception as e:
            error_log(item['title'], type(e), e)

    save_products_missing_images(new_missing_images)
    reprint_messages = save_reprints(site, reprints)
    return results, reprint_messages


def different_isbn_and_already_listed(text, isbn):
    infobox = re.search(r"\|isbn=([0-9X-]+)", text)
    if infobox and infobox.group(1) and infobox.group(1) != isbn:
        s = "{{ISBN|" + isbn + "}}"
        return s in text and text.count("{{ISBN|") > 1
    return False


def run_edelweiss_protocol(site, cache, scheduled=False):
    search_terms = ["Star Wars", "Mandalorian"]
    sku_list = []
    products = []
    for term in search_terms:
        driver = build_driver(headless=False, firefox=True)
        try:
            products += extract_items_from_edelweiss(driver, term, sku_list)
        except ElementNotInteractableException as e:
            error_log(type(e), e, tb=False)
            return [f"Error encountered during Edelweiss protocol; cannot complete scan."], []
        except Exception as e:
            error_log(type(e), e)
            return [f"Error encountered during Edelweiss protocol: {type(e)} - {e}"], []
        finally:
            driver.close()

    log(f"Processing {len(products)} products")

    try:
        analysis_results, reprints = analyze_products(site, products, search_terms)
    except ElementNotInteractableException as e:
        error_log(type(e), e, tb=False)
        return [f"Error encountered during Edelweiss protocol; cannot complete scan."], []
    except Exception as e:
        error_log(type(e), e)
        return [f"Error encountered during Edelweiss protocol: {type(e)} - {e}"], []

    messages = []
    headers = {"newItems": "New Listings:", "newDates": "New Publication Dates:", "newImages": "New Cover Images:",
               "reprints": "New Reprints:", "newTPBs": "New Trade Paperbacks", "canceled": "Canceled Products"}
    for key, header in headers.items():
        if not analysis_results.get(key):
            continue
        m = [[header]]
        has_items = False
        for sku, item in analysis_results[key]:
            if key == "newItems" and sku in cache:
                d = datetime.strptime(cache[sku], "%Y-%m-%d")
                if (datetime.now() - d).days % 3 != 0:
                    continue
            elif key == "newItems":
                cache[sku] = datetime.now().strftime("%Y-%m-%d")

            if sum(len(x) for x in m[-1]) + len(item) + 2 >= 2000:
                m.append([])
            m[-1].append(f"- {item}")
            log(f"{header} {item}")
            has_items = True
        if has_items:
            messages += ["\n".join(x) for x in m]

    if messages:
        messages.insert(0, ":book: Edelweiss Catalog Report:")
    elif scheduled:
        messages.append(f"No updates found in Edelweiss catalog during scheduled run for {datetime.now().strftime('%B %d, %Y')}")

    return messages, reprints


def save_reprints(site, reprints: Dict[str, List[dict]]):
    results = []
    for title, entries in reprints.items():
        try:
            r = save_reprint(site, title, entries)
            if r:
                results.append(r)
        except Exception as e:
            error_log(type(e), e)
    return results


def save_reprint(site, title, entries: List[dict]):
    try:
        page = Page(site, title)
        text = page.get()
        if "==Editions==" in text:
            i_header, international = "", ""
            before, split1, after = re.split(r"(=+Editions=+\n)", text)
            if re.search(r"=+[A-z]* ?[Gg]allery=+", after):
                section, split2, after = re.split(r"(\n=+[A-z]* ?gallery=+)", after, 1)
            elif re.search(r"\n==[A-Z]", after):
                section, split2, after = re.split(r"(\n==[A-z].*?==)", after, 1)
            else:
                return f"- Cannot add {len(entries)} new reprints to {page.title()} due to malformed Editions section"

            if "===" in section:
                section, i_header, international = re.split(r"(\n=+.*?=+)", section, 1)

            lines = [section.rstrip()]
            build_editions(lines, entries)

            new_text = "".join([before, split1, "\n".join(lines), i_header, international, split2, after])
            page.put(new_text, f"Adding {len(entries)} new reprints to Editions", botflag=False)

        elif re.search(r"=+[A-z]* ?[Gg]allery=+", text):
            before, split, after = re.split(r"(=+[A-z]* ?[Gg]allery=+\n)", text, 1)
            lines = []
            if "==Media==" in before:
                pass
            else:
                build_new_media_section(text, lines, entries)
                lines.append("===Cover gallery===")
            new_text = "".join([before, "\n".join(lines), after])
            page.put(new_text, f"Creating Editions section and adding {len(entries)} new reprints", botflag=False)

        elif re.search(r"=+Appearances=+", text):
            before, split, after = re.split(r"(=+Appearances=+)", text, 1)
            lines = []
            if "==Media==" in before:
                pass
            else:
                build_new_media_section(text, lines, entries)
                lines.append("==Appearances==")
            new_text = "".join([before, "\n".join(lines), after])
            page.put(new_text, f"Creating Editions section and adding {len(entries)} new reprints", botflag=False)

        else:
            return f"- Cannot add {len(entries)} new reprints to {page.title()} due to lack of Editions and/or Media subsection"
    except Exception as e:
        traceback.print_exc()
        log(f"Encountered {type(e)} while adding reprint to {title}: {e}")


def build_editions(lines: list, entries: list):
    for e in entries:
        template = "{{" + f"Edelweiss|url=#sku={e['sku']}|text={e['title']}|nobackup=1" + "}}"
        x = "; ".join(e for e in [f"{{{{ISBN|{e['isbn']}}}}}", e.get("publicationDate"), e.get("publisher"), e.get("format")] if e and e.strip())
        lines.append(f"\n*{x}<ref name=\"Edelweiss-{e['sku']}\">{template}</ref>")
    lines.append("")


def build_new_media_section(text, lines: list, entries: list):
    lines.append("==Media==")
    lines.append("===Editions===")
    d = re.search(r"\|release date ?= ?\*?([\[\]A-Za-z, 0-9/]+)", text)
    date = ("; " + d.group(1)) if d else ""
    p = re.search(r"\|publisher ?= ?\*?([\[\]A-Za-z., 0-9/]+)", text)
    pub = ("; " + p.group(1)) if p else ""
    for i in re.findall(r"\|isbn[23]? ?= ?([0-9-]+)", text):
        lines.append(f"\n*{{{{ISBN|{i}}}}}{date}{pub}")

    build_editions(lines, entries)
