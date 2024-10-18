from pywikibot import Site, Page, Category
from datetime import datetime
from typing import Tuple, List
import codecs
import re

from c4de.sources.domain import Item, ItemId, AnalysisResults
from c4de.sources.updates import extract_release_date


def build_alternate(i: ItemId):
    o = "{{SW|url=" + i.master.special + "|text=" + i.master.text + "}}"
    x = Item(o, "Web", i.master.is_appearance, url=i.master.special, template="SW", text=i.master.text)
    x.date = i.master.date
    x.index = i.master.index + 0.1
    x.canon_index = i.master.canon_index
    x.legends_index = i.master.legends_index
    x.extra = i.current.extra
    return ItemId(x, x, False, False)


def flatten(items: List[ItemId], found: List[ItemId], missing: List[ItemId]):
    for i in items:
        if i.master.has_date():
            found.append(i)
            if i.master.mode == "YT" and i.master.special:
                found.append(build_alternate(i))
        else:
            missing.append(i)
            if i.master.mode == "YT" and i.master.special:
                missing.append(build_alternate(i))


def prepare_results(results: AnalysisResults) -> Tuple[List[ItemId], List[ItemId]]:
    found, missing = [], []
    for x in [results.apps, results.nca, results.src, results.ncs]:
        for i in x:
            if i.master.sort_index(results.canon) is None:
                print(i.master.target, i.master.original)
        flatten(x, found, missing)

    found = sorted(found, key=lambda a: (a.master.date, a.master.mode == "DB", a.master.sort_index(results.canon), a.sort_text()))
    return found, missing


def add_link(d, links: set):
    if d in links:
        return d
    links.add(d)
    return f"[[{d}]]"


def convert_date_str(date, links: set):
    if not (date and date[0].isnumeric()):
        return date, None
    elif date.endswith("-XX-XX"):
        return date[:4], datetime(int(date[:4]), 1, 1)
    elif date.endswith("-XX"):
        try:
            d = datetime.strptime(date, "%Y-%m-XX")
            m = add_link(d.strftime("%B"), links)
            y = add_link(d.strftime("%Y"), links)
            return f"{m}, {y}", d
        except Exception as e:
            print(f"Encountered {type(e)} while parsing {date}: {e}")
        return date, None
    else:
        try:
            d = datetime.strptime(date, "%Y-%m-%d")
            m = add_link(d.strftime("%B %d"), links)
            y = add_link(d.strftime("%Y"), links)
            return f"{m}, {y}", d
        except Exception as e:
            print(f"Encountered {type(e)} while parsing {date}: {e}")
        return date, None


def get_reference_for_release_date(site, target, date, refs: dict, contents: dict):
    try:
        if not date:
            print(f"No release date found for {target}")
            return ''
        t = target.replace('"', '')
        if t in refs:
            return f'<ref name="{t}" />'

        ref_text, other_date = extract_release_date_reference(site, target, date)
        if ref_text and ref_text in contents:
            return f'<ref name="{contents[ref_text]} />'
        elif ref_text:
            if other_date:
                print(f"Could not find exact match for {date}; using closest date match: {other_date}")
            refs[t] = ref_text
            contents[ref_text] = t
            return f'<ref name="{t}">{ref_text}</ref>'
    except Exception as e:
        print(f"Encountered {type(e)} while extracting release date for {target}: {e}")
    return ''


def extract_release_date_reference(site, target, date: datetime):
    page = Page(site, target)
    if page.exists() and page.isRedirectPage():
        page = page.getRedirectTarget()
    if not page.exists():
        return '', None
    text = page.get()
    dates = [d for d in extract_release_date(page.title(), text) if d and d[1]]
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
        m = re.search("<ref name=\".*?\".*?>(.*?)</ref>", line)
        if m:
            return m.group(1)
        m = re.search("<ref name=\"(.*?)\" ?/>", line)
        if m:
            x = re.search("<ref name=\"" + m.group(1) + "\" ?>(.*?)</ref>", text)
            if x:
                return x.group(1)
    return None


def create_index(site, page: Page, results: AnalysisResults, save: bool):
    found, missing = prepare_results(results)

    lines = ["This is the media index page for [[{{PAGENAME}}]].", "", "==Media index=="]
    refs = {}
    contents = {}
    links = set()
    for i in found:
        date_str, parsed_date = convert_date_str(i.master.date, links)
        date_ref = ''
        if date_str:
            date_str = re.sub("XX[A-Z]", "XX", date_str.replace(" 0", " "))

            if i.master.target:
                date_ref = get_reference_for_release_date(site, i.master.target, parsed_date, refs, contents)
            if i.master.parent and not date_ref:
                date_ref = get_reference_for_release_date(site, i.master.parent, parsed_date, refs, contents)
            if not date_ref and i.master.url and i.master.can_self_cite():
                t = f"{i.master.template}: {i.master.text}".replace('"', '')
                if t in refs:
                    date_ref = f'<ref name="{t}" />'
                else:
                    refs[t] = i.master.original
                    date_ref = f'<ref name="{t}">{refs[t]}</ref>'

        zt = i.current.original if i.use_original_text else i.master.original
        xt = f"*{date_str}:{date_ref} {zt} {i.current.extra.strip()}".strip()
        xt = re.sub("\|audiobook=1", "", re.sub(" ?\{\{Ab\|.*?}}", "", xt))
        if xt.count("{{") < xt.count("}}") and xt.endswith("}}}}"):
            xt = xt[:-2]
        lines.append(xt)

    if refs:
        lines.append("\n==Notes and references==")
        if len(refs) > 20:
            lines.append("{{Scroll_box|content=")
        lines.append("{{Reflist}}")
        if len(refs) > 20:
            lines.append("}}")
    if re.search("\{\{Top\|(.*?\|)?(real|rwm|rwp)(\|.*?)?}}", page.get()):
        lines.append("\n[[Category:Real-world index pages]]")
    elif re.search("\{\{Top\|(.*?\|)?nc[cl](\|.*?)?}}", page.get()):
        lines.append("\n[[Category:Non-canon index pages]]")
    elif results.canon:
        lines.append("\n[[Category:Canon index pages]]")
    else:
        lines.append("\n[[Category:Legends index pages]]")

    index = None
    if save:
        index = Page(site, f"Index:{page.title()}")
        index.put("\n".join(lines), "Source Engine: Generating Index page", botflag=False)
    else:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w",
                         encoding="utf-8") as f:
            f.writelines("\n".join(lines))

    return index
