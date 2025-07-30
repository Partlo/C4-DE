from pywikibot import Page, showDiff
from typing import Tuple, List
import codecs
import re

from c4de.common import fix_redirects, build_redirects
from c4de.dates import parse_date_string, build_date, build_date_and_ref
from c4de.sources.archive import clean_archive_usages
from c4de.sources.domain import Item, ItemId, AnalysisResults


def build_alternate(i: ItemId):
    o = "{{SW|url=" + i.master.special + "|text=" + i.master.text + "}}"
    x = Item(o, "Web", i.master.is_appearance, url=i.master.special, template="SW", text=i.master.text)
    x.date = i.master.date
    x.index = (i.master.index or 0) + 0.1
    x.canon_index = i.master.canon_index
    x.legends_index = i.master.legends_index
    x.extra = i.current.extra
    i.current.original = i.master.original.replace(f"|site_url={i.master.special}", "").replace(f"|sw_url={i.master.special}", "")
    i.use_original_text = True
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
                print("No index?", i.master.target, i.master.original)
        flatten(x, found, missing)
    for x in results.reprints.values():
        for i in x:
            if i.has_date():
                found.append(ItemId(i, i, False))
            else:
                missing.append(ItemId(i, i, False))

    return found, missing


def prepare_ordered_list(results: AnalysisResults):
    found, missing = prepare_results(results)
    found = sorted(found, key=lambda a: (a.master.date, a.master.mode == "DB", a.master.sort_index(results.canon), a.sort_text()))
    found += missing

    by_date = []
    for item in found:
        by_date.append(f"#{item.master.date}: {item.master.original} {item.current.extra}".strip())
    return by_date


def clean(x):
    return re.sub("(\{\{(BuildR2Cite|BuildXWingCite|BuildFalconCite|FalconCite|HelmetCollectionCite|BustCollectionCite)\|[0-9]+\|[^{}\n]*?)\|[^{}\n]*?}}", "\\1}}", x)


def create_index(site, page: Page, results: AnalysisResults, appearances: dict, sources: dict, save: bool):
    found, missing = prepare_results(results)
    for i in missing:
        print(i)

    current_page = Page(site, f"Index:{page.title()}")
    current = {}
    keep = {}
    current_item = None
    references = {}
    if current_page.exists():
        text = current_page.get().split("==Media index==")[-1].split("==Notes")[0].strip() + "\n"
        if "(Star Wars Encyclopedia)" in text:
            text = re.sub("\(Star Wars Encyclopedia\)(\|.*?)?}}", "(booklet)}}", text)
        redirects = build_redirects(current_page, manual=text)
        text = fix_redirects(redirects, text, "Index", {}, {}, appearances, sources)
        text = re.sub("(<ref name=.*?( />|</ref>))(<ref name=.*?( />|</ref>))*", "\\1", text)
        if "  " in text:
            text = re.sub("  +", " ", text)
        for ln in text.splitlines():
            x = re.search("^\*([\[\]A-z. 0-9,]*\[*[12][0-9]{3}]*.*?|Current|Unknown):(<ref name.*?( />|</ref>))? ?(.*?[]}]+'*)( *\{\{[A-z0-9]+.*?}})?( *(–|—|&.dash;).*?)?$", ln)
            if x:
                current[x.group(4)] = (x.group(1), x.group(2), x.group(6) or '')
                current_item = x.group(4)
            if ln.startswith("**") and current_item:
                keep[current_item] = ln

    add_by = {}
    for t, (date, ref, nt) in current.items():
        u = re.search("(\|(video|url|link)=|(You[Tt]ube|StarWarsShow|ThisWeek|LegoMiniMovie|HighRepublicShow|Databank)\|)(?P<u>.*?)\|", t)
        match = False
        z = clean(t.replace("&ndash;", "–").replace("&mdash;", "—"))
        for i in found:
            match = False
            for o in [i.master, i.current]:
                if clean(o.original.replace("&ndash;", "–").replace("&mdash;", "—")) == z:
                    match = True
                elif z.count("|") > 1 and z.rsplit("|", 1)[0] + "}}" == o.original.replace("&ndash;", "–").replace("&mdash;", "—"):
                    match = True
                elif o.original.replace("}}", "").split(" \(")[0].startswith(z.replace("}}", "").split(" \(")[0]):
                    match = True
                elif o.target and (f"[[{o.target}|" in t or f"[[{o.target}]]" in t):
                    match = True
                elif u and o.url and u.group('u').replace("video=", "") == o.url.replace("video=", ""):
                    match = True
                if match:
                    break
            if match:
                if (i.master.date == "Current" and "20" in date) or "{{DLC}}" in i.current.extra:
                    x, y = parse_date_string(date.replace("By ", "").replace("c. ", "").replace("[", "").replace("]", "").replace(",", ""), "Index")
                    if x:
                        d = build_date([(x, y)])
                        if d:
                            i.master.date = d
                i.current.extra += nt
                references[i.master.original] = (date, ref)
                if date.startswith("By ") and date.replace("By ", "") == i.master.date:
                    add_by[i.master.original] = "By"
                elif date.startswith("c. ") and date.replace("c. ", "") == i.master.date:
                    add_by[i.master.original] = "c."
                break
        if nt and not match:
            print(t, nt)

    # TODO: CardGameSet and SourceContents
    found = sorted(found, key=lambda a: (a.master.date, a.master.mode == "DB", a.master.sort_index(results.canon), a.sort_text()))

    x = page.title()
    title = re.search("(?<!SucessionBox)\n\|(name|title)=(.*?)\n", page.get())
    if title:
        x = re.sub("<br ?/?>\{\{C\|.*?$", "", title.group(2))
        x = re.sub("<br ?/?>", " ", x).replace("  ", "")
    elif x.endswith("/Legends") or x.endswith("/Canon"):
        x = page.title().replace("/Legends", "").replace("/Canon", "")
    if x.startswith("Unidentified"):
        x = x[0].lower() + x[1:]

    if x == f"''{page.title()}''":
        x = f"''[[{page.title()}]]''"
    elif x != page.title():
        x = f"[[{page.title()}|{x}]]"
    else:
        x = f"[[{x}]]"
    lines = [f"This is the media index page for {x}.", "", "==Media index=="]
    refs = {}
    contents = {}
    links = set()
    has_references = False
    for i in found:
        date_str, date_ref = build_date_and_ref(i.master, site, links, refs, contents, existing=references)
        if i.master.original in add_by:
            date_str = f"{add_by[i.master.original]} {date_str}"
        zt = i.current.original if i.use_original_text else i.master.original
        if i.master.mode == "Minis" and i.master.card:
            zt = re.sub("\|link=.*?(\|.*?)?}}", "\\1}}", re.sub(" ?\{\{[Cc]\|[Rr]eissued.*?}}", "", zt))
        xt = f"*{date_str}:{date_ref} {zt} {i.current.extra.strip()}".strip().replace("|reprint=1", "")
        xt = re.sub(" ?\{\{Ab\|.*?}}", "", xt).replace("|audiobook=1", "")
        if xt.count("{{") < xt.count("}}") and xt.endswith("}}}}"):
            xt = xt[:-2]
        has_references = has_references or "<ref" in xt
        lines.append(xt)

    if has_references:
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
    old_id = index.latest_revision_id if index.exists() else None
    new_txt, _ = clean_archive_usages(index, "\n".join(lines), None)
    if save and not index.exists():
        index.put(new_txt, "Source Engine: Generating Index page", botflag=False)
    else:
        t1 = re.sub(">.*?</ref>", " />", re.sub("name=\".*?\"", "name=\"name\"", index.get() if index.exists() else ""))
        t2 = re.sub(">.*?</ref>", " />", re.sub("name=\".*?\"", "name=\"name\"", new_txt))

        showDiff(clean_date_strings(t1), clean_date_strings(t2))
        if save:
            index.put(new_txt, "Source Engine: Generating Index page", botflag=False)
        else:
            with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w",
                             encoding="utf-8") as f:
                f.writelines("\n".join(lines))

    return index, old_id


def clean_date_strings(t):
    for x in re.findall("\*([^\n:{]*?\[[^\n:{]*):", t):
        t = t.replace(x, x.replace("[", "").replace("]", ""))
    return t
