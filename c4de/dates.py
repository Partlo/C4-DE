from pywikibot import Page
from datetime import datetime
from typing import Tuple, Optional, List
import re

from c4de.sources.domain import Item


def parse_date_string(d, title) -> Tuple[str, datetime]:
    if d and d.lower() != "none" and d.lower() != "future" and d.lower() != "canceled":
        t, z = None, None
        for x, df in {"day": "%B %d %Y", "month": "%B %Y", "year": "%Y"}.items():
            try:
                z = datetime.strptime(d.strip(), df)
                t = x
                return t, z
            except Exception:
                pass
        if not z:
            print(f"Unrecognized date string on {title}: [{d}]")
    return None, None


def convert_date_str(date: str, links: set, add_links=True) -> Tuple[str, Optional[datetime]]:
    if date and date.endswith("E"):
        date = date[:-1]

    if not (date and date[0].isnumeric()):
        return date, None
    elif date.endswith("-XX-XX"):
        return date[:4], datetime(int(date[:4]), 1, 1)
    elif date.endswith("-XX"):
        try:
            d = datetime.strptime(date, "%Y-%m-XX")
            m = add_link(d.strftime("%B"), links, add_links)
            y = add_link(d.strftime("%Y"), links, add_links)
            return f"{m} {y}", d
        except Exception as e:
            print(f"Encountered {type(e)} while parsing {date}: {e}")
        return date, None
    else:
        try:
            d = datetime.strptime(re.sub("[A-Z]", "", date), "%Y-%m-%d")
            m = add_link(d.strftime("%B %d").replace(" 0", " "), links, add_links)
            y = add_link(d.strftime("%Y"), links, add_links)
            return f"{m}, {y}", d
        except Exception as e:
            print(f"Encountered {type(e)} while parsing {date}: {e}")
        return date, None


def add_link(d, links: set, add_links):
    if d in links or not add_links:
        return d
    links.add(d)
    return f"[[{d}]]"


def prep_date(d):
    return re.sub("-([0-9])$", "-0\\1", re.sub("-([0-9])([:-])", "-0\\1\\2", d))


def build_date(dates):
    if dates and dates[0][0] == "day":
        return dates[0][1].strftime('%Y-%m-%d')
    elif dates and dates[0][0] == "month":
        return f"{dates[0][1].strftime('%Y-%m')}-XX"
    elif dates and dates[0][0] == "year":
        return f"{dates[0][1].strftime('%Y')}-XX-XX"
    return "Future"


def build_date_and_ref(i: Item, site, links: set, refs: dict, contents: dict, ref_name=None, existing: dict=None):
    date_str, parsed_date = convert_date_str(re.sub("XX[A-Z]", "XX", i.date), links)
    date_ref = ''
    if date_str and not i.mode == "Toys":
        if i.target:
            date_ref = get_reference_for_release_date(site, i.target, i.original, parsed_date, refs, contents)
        if i.parent and not date_ref:
            date_ref = get_reference_for_release_date(site, i.parent, i.original, parsed_date, refs, contents)
        if not date_ref and existing and existing.get(i.original):
            _, date_ref = existing[i.original]
        if not date_ref and i.url and i.can_self_cite():
            if not ref_name:
                ref_name = f"{i.template}: {i.text}".replace('"', '')
            if ref_name in refs:
                date_ref = f'<ref name="{ref_name}" />'
            else:
                refs[ref_name] = i.original
                date_ref = f'<ref name="{ref_name}">{refs[ref_name]}</ref>'
    if not (date_str and date_ref) and existing and i.original in existing:
        exd, exr = existing[i.original]
        date_str = date_str if date_str else exd
        date_ref = date_ref if date_ref else exr
    return date_str, date_ref or ''


def get_reference_for_release_date(site, target, formatted, date, refs: dict, contents: dict):
    try:
        if not date:
            print(f"No release date found for {target}")
            return ''
        t = target.replace('"', '')
        if t in refs:
            return f'<ref name="{t}" />'

        ref_text, other_date = extract_release_date_reference(site, target, date)
        if ref_text and ref_text.count("[[") == 0 and ref_text.count("{{") == 0:
            tx = t.split(" (")[0]
            if ref_text.replace("''", "").startswith(tx):
                ref_text = formatted

        if ref_text and ref_text in contents:
            return f'<ref name="{contents[ref_text]}" />'
        elif ref_text:
            if other_date:
                print(f"Could not find exact match for {date}; using closest date match: {other_date}")
            refs[t] = ref_text
            contents[ref_text] = t
            return f'<ref name="{t}">{ref_text}</ref>'
    except Exception as e:
        print(f"Encountered {type(e)} while extracting release date for {target}: {e}")
    return ''


def extract_release_date(title, text) -> Tuple[List[Tuple[str, datetime, str]], List[Tuple[str, str]]]:
    date_strs = []
    m = re.search("\|(publish date|publication date|first aired|airdate|start date|first date|release date|released|published)=(?P<d1>.*?)(?P<r1><ref.*?)?\n(\*(?P<d2>.*?)(?P<r2><ref.*?)?\n)?(\*(?P<d3>.*?)(?P<r3><ref.*?)?\n)?", text)
    if m:
        for i in range(1, 4):
            if m.groupdict()[f"d{i}"]:
                d = m.groupdict()[f"d{i}"]
                d = re.sub("\[\[([A-z]+)( [0-9]+)?\|[A-z]+\.?( [0-9]+)?]]", "\\1\\2", d).replace("c. ", "")
                d = d.replace("[", "").replace("]", "").replace("*", "").strip().replace(',', '')
                if "{{c|reprint" in d.lower() or "(reprint" in d.lower() or d.lower().startswith("cancel") or d.lower().startswith("future"):
                    continue
                d = re.sub("\{\{C\|.*?}}", "", d)
                d = re.sub("([A-z]+ ?[0-9]*)(-|&[mn]dash;)([A-z]+ ?[0-9]*) ", "\\1 ", d)
                d = re.sub("&[mn]dash; ?[A-z]+ [0-9|]+", "", d)
                d = re.sub("\([A-Z]+\)", "", d)
                d = re.sub("([A-z]+ ?[0-9]*) ([0-9]{4})( .*?)$", "\\1 \\2", d)
                d = d.replace("Late ", "").replace("Early ", "")
                d = re.sub("  +", " ", d)
                d = d.split("<br")[0]
                date_strs.append((d.split("-")[0], m.groupdict().get(f"r{i}")))

    page_dates = []
    for d, r in date_strs:
        if d and d.lower() != "none" and d.lower() != "future" and d.lower() != "canceled":
            t, z = parse_date_string(d, title)
            if t and z:
                page_dates.append((t, z, r))
    return page_dates, date_strs


def extract_release_date_reference(site, target, date: datetime) -> Tuple[Optional[str], Optional[str]]:
    page = Page(site, target)
    if page.exists() and page.isRedirectPage():
        page = page.getRedirectTarget()
    if not page.exists():
        return '', None
    text = page.get()
    dates, date_strs = extract_release_date(page.title(), text)
    dates = [d for d in dates if d and d[1]]
    if not dates:
        return '', None
    elif len(dates) == 1:
        return extract_reference(dates[0][2], text), None
    else:
        y1, y2, d1, d2 = None, None, None, None
        for t, d, r in dates:
            if d == date:
                return extract_reference(r, text), None
            if d.year == date.year:
                y1 = r
                d1 = d
                if d.month == date.month:
                    y2 = r
                    d2 = r
        if y1:
            return extract_reference(y1, text), d1
        if y2:
            return extract_reference(y2, text), d2
        return None, None


def extract_reference(line, text):
    if line:
        m = re.search("<ref name=\".*?\" *?>(.*?)</ref>", line)
        if m:
            return m.group(1)
        m = re.search("<ref name=\"(.*?)\" ?/>", line)
        if m:
            x = re.search("<ref name=\"" + m.group(1) + "\" ?>(.*?)</ref>", text)
            if x:
                return x.group(1)
    return None
