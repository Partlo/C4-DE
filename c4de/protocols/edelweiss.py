import time
import json
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from pywikibot import Site, Page, Category, showDiff
from get_chrome_driver import GetChromeDriver

from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from selenium.webdriver import Remote as WebDriver, Chrome
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from c4de.common import log, error_log, archive_url
from c4de.data.filenames import MISSING_IMAGES_FILE


def build_driver(headless=True):
    options = ChromeOptions()
    if headless:
        options.add_argument("headless")
        options.add_argument("no-sandbox")
        options.add_argument('window-size=1024,768')
        # --start-maximized does not work, headless thinks the maximized size is 800*600, making the element not visible;
        options.add_experimental_option("prefs", {"credentials_enable_service": False})
    try:
        return Chrome(chrome_options=options, executable_path="C:/Users/Michael/Documents/Drivers/chromedriver")
    except SessionNotCreatedException as e:
        gd = GetChromeDriver()
        gd.auto_download(extract=True, output_path="C:/Users/Michael/Documents/Drivers")
        return Chrome(chrome_options=options, executable_path="C:/Users/Michael/Documents/Drivers/chromedriver")


def extract_isbns(title, text, data):
    if re.search("\[\[Category:.*?authors[|\]]", text):
        return
    isbns = []
    for i in re.findall("\n\|isbn=([- 0-9A-Z]+?)\n", text):
        x = i.replace("-", "").replace(" ", "").strip()
        if x:
            isbns.append(x)
    for i in re.findall("\*{{ISBN\|([0-9]+)}}", text):
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
    page.put(page_text, "Updating sitewide ISBN records")
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


def extract_items_from_edelweiss(driver: WebDriver, search_term, sku_list: List[str]) -> List[dict]:
    """ Loads the product listings from the Edelweiss website, using Selenium to traverse and parse the webpage. """

    driver.get(f"https://www.edelweiss.plus/#keywordSearch&q={search_term.replace(' ', '+')}")
    time.sleep(10)

    # open the left nav if it's closed
    chevron = driver.find_elements_by_class_name("leftNavContracted")
    if chevron:
        chevron[0].click()

    # wait for "Not Yet Published" button
    log("Waiting for Not Yet Published button")
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "f_4_2")))
    button = driver.find_element_by_id("f_4_2")
    driver.execute_script("arguments[0].scrollIntoView()", button)
    try:
        button.click()
    except WebDriverException:
        driver.execute_script("arguments[0].scrollIntoView()", button)
        button.click()

    if not driver.find_elements_by_css_selector("#f_4_2.box_checked"):
        button = driver.find_element_by_id("f_4_2")
        driver.execute_script("arguments[0].scrollIntoView()", button)
        try:
            button.click()
        except WebDriverException:
            driver.execute_script("arguments[0].scrollIntoView()", button)
            button.click()

    log("Waiting for results")
    WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, "results")))
    total = int(driver.find_element_by_id("results").text.replace("of", "").strip())

    i, j = 0, 1
    results = []
    while i < total:
        log(f"Processing page {j}")
        toggle = driver.find_elements_by_css_selector(".visibility-toggle-anchor.visible")
        if toggle:
            toggle[0].click()
        time.sleep(5)

        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CLASS_NAME, "ltRow")))

        container_ids = [c.get_attribute('id') for c in driver.find_elements_by_class_name("tempListContainer")]
        for cid in container_ids:
            k = 0
            num_items = len(driver.find_elements_by_xpath(f".//div[@id='{cid}']//div[@class='ltRow']"))
            while k < num_items:
                k += 1
                item = driver.find_element_by_xpath(f".//div[@id='{cid}']//div[contains(@class, 'ltRow')][{k}]")
                isbn, sku = item.find_element_by_css_selector(".pve_sku").text.split(",", 1)
                if sku in sku_list:
                    continue
                else:
                    sku_list.append(sku)
                title = item.find_element_by_css_selector(".pve_title span.textLarge").text
                if search_term.lower() not in item.get_attribute("innerHTML").lower():
                    log(f"{search_term} not mentioned in {title}; skipping")
                    continue

                date = item.find_elements_by_css_selector(".pve_shipDate span")
                if not date:
                    date = item.find_elements_by_css_selector(".pve_shipDate")
                publication_date = date[0].get_attribute("innerHTML").replace("On Sale Date:", "").strip()

                fmt = item.find_elements_by_class_name("pve_format")
                sub_names = item.find_elements_by_class_name("pve_subName")
                page_fields = item.find_elements_by_class_name("pve_numberOfPages")
                item = driver.find_element_by_xpath(f".//div[@id='{cid}']//div[contains(@class, 'ltRow')][{k}]")
                imprint = item.find_element_by_class_name("headerImprint").text
                no_image = bool(item.find_elements_by_class_name("noThumbImageScroll"))
                categories = [c.text for c in item.find_elements_by_css_selector(".pve_categories ul.categories li")]

                results.append({
                    "title": title,
                    "subTitle": sub_names[0].text if sub_names else "",
                    "publicationDate": publication_date,
                    "author": item.find_element_by_css_selector(".title_Author").text,
                    "hasImage": not no_image,
                    "isbn": isbn.strip(),
                    "sku": sku.strip(),
                    "publisher": imprint.split(".")[-1].strip(),
                    "format": fmt[0].text if fmt else "",
                    "categories": categories,
                    "pageCount": page_fields[0].text if page_fields else ""
                })

        i += 50
        j += 1
        page_buttons = driver.find_elements_by_id(f"pageOption{j}")
        if page_buttons:
            page_buttons[0].click()
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

    m = re.search("(.*?): Star Wars Legends( \((.*?)\))?$", title)
    if m:
        titles = [f"{m.group(3)}: {m.group(1)}", m.group(1)]
        if subtitle:
            titles += [f"{m.group(3)}: {m.group(1)}: {subtitle}", f"{m.group(3)}: {m.group(1)} — {subtitle}"]
        for t in titles:
            page = page_exists(site, t, media_type)
            if page:
                return page, False
        return None, False

    m = re.search("Star Wars: (.*?) \((.*?)\)", title)
    if m:
        titles = [f"{m.group(2)}: {m.group(1)}", f"Star Wars: {m.group(2)}: {m.group(1)}"]
        if subtitle:
            titles += [f"{m.group(2)}: {m.group(1)}: {subtitle}", f"{m.group(2)}: {m.group(1)} — {subtitle}"]
        for t in titles:
            page = page_exists(site, t, media_type)
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


def analyze_products(site, products: List[dict], search_terms):
    false_positives = load_false_positives(site)
    pages_by_isbn = load_pages_by_isbn(site)
    missing_images = load_products_missing_images()
    processed = set()

    results = {"newItems": [], "newDates": [], "newImages": [], "reprints": [], "unknown": []}
    reprints = {}
    new_missing_images = []
    for item in products:
        try:
            url = f"<https://www.edelweiss.plus/#sku={item['sku']}>"
            page, by_isbn = determine_page(site, item["title"], item, pages_by_isbn)
            if not item["hasImage"]:
                new_missing_images.append(item["sku"])

            if not page and item["title"] in false_positives:
                continue
            elif not page and not any(s.lower() in item["title"].lower() for s in search_terms):
                results["newItems"].append(f"(Potential False Positive): {item['title']} - {url}{archive_sku(item['sku'])}")
                continue
            elif not (page and page.exists()):
                results["newItems"].append(f"{item['title']} - {url}{archive_sku(item['sku'])}")
                continue
            dupe = page.title() in processed
            processed.add(page.title())

            if "(" in page.title():
                t, p = page.title().split("(", 1)
                title = f"*{t.strip()}* ({p}"
            else:
                title = f"*{page.title()}*"

            text = page.get()
            date_strs = []
            m = re.search("\|(publish date|publication date|release date|released|published)=(.*?)(<.*?)?\n(\*(.*?)(<.*?)?\n)*", text)
            if m:
                date1 = m.group(2).replace("[", "").replace("]", "").replace("*", "").strip()
                date_strs.append(re.sub("([A-z]+ [0-9]+) ([0-9]+)", "\\1, \\2", date1))
                if m.group(5):
                    date2 = m.group(5).replace("[", "").replace("]", "").replace("*", "").strip()
                    date_strs.append(re.sub("([A-z]+ [0-9]+) ([0-9]+)", "\\1, \\2", date2))

            if not date_strs and " 202" not in item.get("publicationDate", ""):
                log(f"{page.title()} has a release date of {item.get('publicationDate')}")
                continue
            elif not date_strs:
                log(f"No release date found in {page.title()}")
                continue
            elif not item.get("publicationDate"):
                log(f"No publication date found for {item['title']}")
                continue
            page_dates = []
            for d in date_strs:
                page_dates.append(datetime.strptime(d, "%B %d, %Y"))
            item_date = datetime.strptime(item["publicationDate"], "%B %d, %Y")

            past = any([d < datetime.now() for d in page_dates])
            if item["sku"] in missing_images and item["hasImage"]:
                results["newImages"].append(f"{title} - {url}{archive_sku(item['sku'])}")
            elif any([d == item_date for d in page_dates]):
                log(f"No date changes found for {page.title()}")
            elif past and by_isbn:
                log(f"Reprint {item['isbn']} already recorded on {page.title()}")
            else:
                arc = archive_sku(item['sku'])
                if past:
                    results["reprints"].append(f"{title}: {item['isbn']} - {url}{arc}")
                    if page.title() not in reprints:
                        reprints[page.title()] = []
                    reprints[page.title()].append(item)
                elif by_isbn and dupe:
                    log(f"{title}: Duplicate listing {item['isbn']} has publication date {item['publicationDate']}")
                elif by_isbn:
                    results["newDates"].append(f"{title}: {item['publicationDate']} (formerly {date_strs[0]}){arc}")
                else:
                    results["unknown"].append(f"Different publication dates found for {title}, but no ISBN - {url}{arc}")
        except Exception as e:
            error_log(item['title'], type(e), e)

    save_products_missing_images(new_missing_images)
    reprint_messages = save_reprints(site, reprints)
    return results, reprint_messages


def run_edelweiss_protocol(site, scheduled=False):
    driver = build_driver(False)
    search_terms = ["Star Wars", "Mandalorian"]
    sku_list = []
    products = []
    for term in search_terms:
        try:
            products += extract_items_from_edelweiss(driver, term, sku_list)
        except Exception as e:
            error_log(type(e), e)
            return [f"Error encountered during Edelweiss protocol: {type(e)} - {e}"], []
        driver.get("https://google.com")
    driver.close()

    log(f"Processing {len(products)} products")

    try:
        analysis_results, reprints = analyze_products(site, products, search_terms)
    except Exception as e:
        error_log(type(e), e)
        return [f"Error encountered during Edelweiss protocol: {type(e)} - {e}"], []

    messages = []
    headers = {"newItems": "New Listings:", "newDates": "New Publication Dates:", "newImages": "New Cover Images:",
               "reprints": "New Reprints:"}
    for key, header in headers.items():
        if not analysis_results.get(key):
            continue
        m = [header]
        for item in analysis_results[key]:
            m.append(f"- {item}")
            log(f"{header} {item}")
        messages.append("\n".join(m))

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
    page = Page(site, title)
    text = page.get()
    if "==Editions==" in text:
        i_header, international = "", ""
        before, split1, after = re.split("(=+Editions=+\n)", text)
        if re.search("=+[A-z]* ?[Gg]allery=+", after):
            section, split2, after = re.split("(\n=+[A-z]* ?gallery=+)", after, 1)
        elif re.search("\n==[A-Z]", after):
            section, split2, after = re.split("(\n==[A-z].*?==)", after, 1)
        else:
            return f"- Cannot add {len(entries)} new reprints to {page.title()} due to malformed Editions section"

        if "===" in section:
            section, i_header, international = re.split("(\n=+.*?=+)", section, 1)

        section = section.rstrip()
        for e in entries:
            template = "{{" + f"Edelweiss|url=#sku={e['sku']}|text={e['title']}|nobackup=1" + "}}"
            section += f"\n*{{{{ISBN|{e['isbn']}}}}}; {e['publicationDate']}; {e['publisher']}; {e['format']}<ref name=\"Edelweiss-{e['sku']}\">{template}</ref>"
        section += "\n"

        new_text = "".join([before, split1, section, i_header, international, split2, after])
        page.put(new_text, f"Adding {len(entries)} new reprints to Editions")

    elif re.search("=+[A-z]* ?[Gg]allery=+", text):
        before, split, after = re.split("(=+[A-z]* ?[Gg]allery=+\n)", text)
        lines = []
        if "==Media==" in before:
            pass
        else:
            lines.append("==Media==")
            lines.append("===Editions===")
            d = re.search("\|release date ?= ?\*?([\[\]A-Za-z, 0-9/]+)", text)
            date = ("; " + d.group(1)) if d else ""
            p = re.search("\|publisher ?= ?\*?([\[\]A-Za-z., 0-9/]+)", text)
            pub = ("; " + p.group(1)) if p else ""
            for i in re.findall("\|isbn[23]? ?= ?([0-9-]+)", text):
                lines.append(f"\n*{{{{ISBN|{i}}}}}{date}{pub}")

            for e in entries:
                template = "{{" + f"Edelweiss|url=#sku={e['sku']}|text={e['title']}|nobackup=1" + "}}"
                lines.append(f"\n*{{{{ISBN|{e['isbn']}}}}}; {e['publicationDate']}; {e['publisher']}; {e['format']}<ref name=\"Edelweiss-{e['sku']}\">{template}</ref>")
            lines.append("")
            lines.append("===Cover gallery===")
        new_text = "".join([before, "\n".join(lines), after])
        page.put(new_text, f"Creating Editions section and adding {len(entries)} new reprints")

    else:
        return f"- Cannot add {len(entries)} new reprints to {page.title()} due to lack of Editions and/or Media subsection"
