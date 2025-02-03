from c4de.common import fix_redirects, build_redirects
from pywikibot import Site, Page, Category, showDiff
from datetime import datetime
from typing import Tuple, List
import codecs
import re

from c4de.sources.domain import Item, ItemId, AnalysisResults
from c4de.sources.updates import extract_release_date, parse_date_string, build_date


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
    for x in results.reprints.values():
        for i in x:
            if i.has_date():
                found.append(ItemId(i, i, False))
            else:
                missing.append(ItemId(i, i, False))

    return found, missing


def add_link(d, links: set):
    if d in links:
        return d
    links.add(d)
    return f"[[{d}]]"


def convert_date_str(date, links: set):
    if date and date.endswith("E"):
        date = date[:-1]

    if not (date and date[0].isnumeric()):
        return date, None
    elif date.endswith("-XX-XX"):
        return date[:4], datetime(int(date[:4]), 1, 1)
    elif date.endswith("-XX"):
        try:
            d = datetime.strptime(date, "%Y-%m-XX")
            m = add_link(d.strftime("%B"), links)
            y = add_link(d.strftime("%Y"), links)
            return f"{m} {y}", d
        except Exception as e:
            print(f"Encountered {type(e)} while parsing {date}: {e}")
        return date, None
    else:
        try:
            d = datetime.strptime(re.sub("[A-Z]", "", date), "%Y-%m-%d")
            m = add_link(d.strftime("%B %d").replace(" 0", " "), links)
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


def build_date_and_ref(i: Item, site, links: set, refs: dict, contents: dict, ref_name=None, existing: dict=None):
    date_str, parsed_date = convert_date_str(re.sub("XX[A-Z]", "XX", i.date), links)
    date_ref = ''
    if date_str:
        if i.target:
            date_ref = get_reference_for_release_date(site, i.target, parsed_date, refs, contents)
        if i.parent and not date_ref:
            date_ref = get_reference_for_release_date(site, i.parent, parsed_date, refs, contents)
        if not date_ref and existing and i.original in existing:
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
    return date_str, date_ref


def create_index(site, page: Page, results: AnalysisResults, appearances: dict, sources: dict, save: bool):
    found, missing = prepare_results(results)

    current_page = Page(site, f"Index:{page.title()}")
    current = {}
    references = {}
    if current_page.exists():
        text = current_page.get().split("==Media index==")[-1].split("==Notes")[0].strip() + "\n"
        if "(Star Wars Encyclopedia)" in text:
            text = re.sub("\(Star Wars Encyclopedia\)(\|.*?)?}}", "(booklet)}}", text)
        if re.search("\*([\[\]A-z 0-9,]*\[*[12][0-9]{3}]*.*?):(<ref name.*?( />|</ref>)) (.*?[]}]+'*)( \{\{[A-z0-9]+.*?}})?( (–|—|&.dash;).*?)\n", text):
            redirects = build_redirects(current_page, manual=text)
            text = fix_redirects(redirects, text, "Index", {}, {}, appearances, sources)
            for x in re.findall("\*([\[\]A-z 0-9,]*\[*[12][0-9]{3}]*.*?):(<ref name.*?( />|</ref>)) (.*?[]}]+'*)( \{\{[A-z0-9]+.*?}})?( (–|—|&.dash;).*?)\n", text):
                current[x[3]] = (x[0], x[1], x[5])

    add_by = []
    for t, (date, ref, nt) in current.items():
        u = re.search("(\|(video|url)=|(You[Tt]ube|StarWarsShow|ThisWeek|HighRepublicShow)\|)(?P<u>.*?)\|", t)
        match = False
        for i in found:
            if i.master.original == t:
                match = True
            elif t.count("|") > 1 and t.rsplit("|", 1)[0] + "}}" == i.master.original:
                match = True
            elif i.master.original.replace("}}", "").split(" \(")[0].startswith(t.replace("}}", "").split(" \(")[0]):
                match = True
            elif u and i.master.url and u.group('u').replace("video=", "") == i.master.url.replace("video=", ""):
                match = True
            if match:
                i.current.extra += nt
                references[i.master.original] = (date, ref)
                if i.master.date == "Current" and "20" in date:
                    x, y = parse_date_string(date.replace("By ", "").replace("[", "").replace("]", "").replace(",", ""), "Index")
                    if x:
                        d = build_date([(x, y)])
                        if d:
                            i.master.date = d
                if date.startswith("By ") and date.replace("By ", "") == i.master.date:
                    add_by.append(i.master.original)
                break
        if not match:
            print(t, nt)

    found = sorted(found, key=lambda a: (a.master.date, a.master.mode == "DB", a.master.sort_index(results.canon), a.sort_text()))

    lines = ["This is the media index page for [[{{PAGENAME}}]].", "", "==Media index=="]
    refs = {}
    contents = {}
    links = set()
    for i in found:
        date_str, date_ref = build_date_and_ref(i.master, site, links, refs, contents, existing=references)
        if i.master.original in add_by:
            date_str = f"By: {date_str}"
        zt = i.current.original if i.use_original_text else i.master.original
        xt = f"*{date_str}:{date_ref} {zt} {i.current.extra.strip()}".strip().replace("|reprint=1", "")
        xt = re.sub(" ?\{\{Ab\|.*?}}", "", xt).replace("|audiobook=1", "")
        if xt.count("{{") < xt.count("}}") and xt.endswith("}}}}"):
            xt = xt[:-2]
        lines.append(xt)

    if refs:
        lines.append("\n==Notes and references==")
        if len(refs) > 20:
            lines.append("{{ScrollBox|content=")
        lines.append("{{Reflist}}")
        if len(refs) > 20:
            lines.append("}}")
    if re.search("\{\{Top\|(.*?\|)?(real|rwm|rwp)(\|.*?)?}}", page.get()):
        lines.append("\n[[Category:Real-world index pages]]")
    elif re.search("\{\{Top\|(.*?\|)?ncl(\|.*?)?}}", page.get()):
        lines.append("\n[[Category:Non-canon Legends index pages]]")
    elif re.search("\{\{Top\|(.*?\|)?ncc(\|.*?)?}}", page.get()):
        lines.append("\n[[Category:Non-canon index pages]]")
    elif results.canon:
        lines.append("\n[[Category:Canon index pages]]")
    else:
        lines.append("\n[[Category:Legends index pages]]")

    index = Page(site, f"Index:{page.title()}")
    if save:
        index.put("\n".join(lines), "Source Engine: Generating Index page", botflag=False)
    else:
        t1 = re.sub(">.*?</ref>", " />", re.sub("name=\".*?\"", "name=\"name\"", index.get()))
        t2 = re.sub(">.*?</ref>", " />", re.sub("name=\".*?\"", "name=\"name\"", "\n".join(lines)))

        showDiff(clean_date_strings(t1), clean_date_strings(t2))
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w",
                         encoding="utf-8") as f:
            f.writelines("\n".join(lines))

    return index


def clean_date_strings(t):
    for x in re.findall("\*([^\n:{]*?\[[^\n:{]*):", t):
        t = t.replace(x, x.replace("[", "").replace("]", ""))
    return t