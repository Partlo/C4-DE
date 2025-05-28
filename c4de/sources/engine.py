import json
import re
import traceback
from datetime import datetime
from typing import Tuple, Optional, List, Dict

from pywikibot import Page, Category
from c4de.sources.domain import Item, FullListData
from c4de.sources.extract import extract_item, TEMPLATE_MAPPING
from c4de.common import build_redirects, fix_redirects, log as _log


SUBPAGES = [
    # "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s",
    "Canon/General", "Legends/General",
    "Canon/Toys", "Legends/Toys", "Canon/RefMagazine", "Legends/RefMagazine", "Canon/CardSets", "Legends/CardSets",
    "Canon/Miniatures", "Legends/Miniatures", "Reprint", "Soundtracks", "CardTrader"
]

LIST_AT_START = ["Star Wars: Galactic Defense", "Star Wars: Force Arena", "Star Wars: Starfighter Missions"]
LIST_AT_END = ["Star Wars: Galaxy of Heroes"]

MANGA = {
    "Star Wars Rebels (webcomic)": {
        "Star Wars Rebels, Vol. 1": ["Star Wars Rebels: Spark of Rebellion"],
        "Star Wars Rebels, Vol. 2": ["Rise of the Old Masters", "Empire Day (episode)", "Gathering Forces"],
        "Star Wars Rebels, Vol. 3": ["Path of the Jedi", "Call to Action", "Rebel Resolve", "Fire Across the Galaxy"]
    },
    "Star Wars: The Mandalorian: The Manga": {
        "The Mandalorian: The Manga, Vol. 1": ["Chapter 1: The Mandalorian"],
        "The Mandalorian: The Manga, Vol. 2": ["Chapter 2: The Child", "Chapter 3: The Sin"],
        "The Mandalorian: The Manga, Vol. 3": ["Chapter 4: Sanctuary", "Chapter 5: The Gunslinger", "Chapter 6: The Prisoner"],
        "The Mandalorian: The Manga, Vol. 4": ["Chapter 6: The Prisoner", "Chapter 7: The Reckoning", "Chapter 8: Redemption"],
    }
}


def list_templates(site, cat, data, template_type, recurse=False, web=False):
    for p in Category(site, cat).articles(recurse=recurse):
        if "/" not in p.title() and p.title(with_ns=False).lower() not in data:
            data[p.title(with_ns=False).lower()] = template_type
            # if web:
            #     x = re.search("on \[\[(.*?)(\|.*?)?]].*?\[.*?official w?e?b?site",  p.get())
            #     if x:
            #         data["WebsiteNames"][p.title(with_ns=False).lower()] = x.group(1)


def build_template_types(site):
    now = datetime.now()
    results = {"db": "DB", "databank": "DB", "swe": "DB", "swboards": "External", "WebsiteNames": {}}

    list_templates(site, "Category:StarWars.com citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates", results, "Web", web=True)
    list_templates(site, "Category:Publisher internet citation templates", results, "Publisher", web=True)
    list_templates(site, "Category:Commercial and product listing internet citation templates", results, "Commercial")
    list_templates(site, "Category:Internet citation templates for use in External Links", results, "External")
    list_templates(site, "Category:Social media citation templates", results, "Social")

    list_templates(site, "Category:YouTube citation templates", results, "YT", recurse=True)
    list_templates(site, "Category:Card game citation templates", results, "Cards")
    list_templates(site, "Category:Miniature game citation templates", results, "Minis")
    list_templates(site, "Category:Toy citation templates", results, "Toys")
    list_templates(site, "Category:TV citation templates", results, "TV")

    list_templates(site, "Category:Interwiki link templates", results, "Interwiki")

    results["Magazine"] = {}
    for p in Category(site, "Category:Magazine citation templates").articles(recurse=True):
        txt = p.get()
        if "BaseCitation" in txt and ("mode=magazine" in txt or "mode=ref" in txt):
            x = re.search("\|series=([A-z0-9:()\-&/ ]+)[|\n]", txt)
            if x:
                results["Magazine"][p.title(with_ns=False)] = x.group(1)
    results["Magazine"]["InsiderCite"] = "Star Wars Insider"

    for k, cat in {"Nav": "Navigation templates", "Dates": "Dating citation templates"}.items():
        results[k] = []
        for p in Category(site, f"Category:{cat}").articles(recurse=True):
            if p.title(with_ns=False).lower() in results:
                print(f"ERROR: Duplicate template name: {p.title(with_ns=False).lower()}")
            results[k].append(p.title(with_ns=False).lower())

    duration = datetime.now() - now
    print(f"Loaded {len(results)} templates in {duration.seconds} seconds")
    return results


def reload_templates(site):
    templates = build_template_types(site)
    with open("c4de/data/templates.json", "w") as f:
        f.writelines(json.dumps(templates, indent=4))
    print(f"Loaded {len(templates)} templates from cache")
    return templates


def load_template_types(site):
    try:
        with open("c4de/data/templates.json", "r") as f:
            results = json.loads("\n".join(f.readlines()))
        if not results:
            results = reload_templates(site)
        return results
    except Exception as e:
        print(f"Encountered {type(e)} while loading infobox JSON", e)
        return reload_templates(site)


def build_auto_categories(site):
    cats = []
    for c in Category(site, "Auto-generated category roots").subcategories():
        if c.title() not in cats:
            cats.append(c.title())
        for x in c.subcategories():
            if x.title() not in cats:
                cats.append(x.title())
    return cats


def reload_auto_categories(site):
    cats = build_auto_categories(site)
    with open("c4de/data/categories.json", "w") as f:
        f.writelines(json.dumps(cats))
    print(f"Loaded {len(cats)} categories from cache")
    return cats


def load_auto_categories(site):
    try:
        with open("c4de/data/categories.json", "r") as f:
            results = json.loads("\n".join(f.readlines()))
        if not results:
            results = build_auto_categories(site)
        return results
    except Exception as e:
        print(f"Encountered {type(e)} while loading categories JSON", e)
        return reload_auto_categories(site)


# TODO: Split Appearances category by type

def load_appearances(site, log, canon_only=False, legends_only=False):
    data = []
    pages = ["Legends", "Canon", "Audiobook", "Unlicensed", "Audiobook/German"]
    other = ["Extra", "Series", "Collections", "Reprint"]
    if canon_only:
        pages = ["Canon", "Audiobook"]
    elif legends_only:
        pages = ["Legends", "Audiobook"]
    for sp in [*pages, *other]:
        i = 0
        collection_type = None
        p = Page(site, f"Wookieepedia:Appearances/{sp}")
        for line in p.get().splitlines():
            if line and sp in ("Extra", "Series") and line.startswith("=="):
                if "anthologies" in line:
                    collection_type = "anthology"
                elif "Toy lines" in line:
                    collection_type = "toy"
                elif "reprint" in line.lower():
                    collection_type = "reprint"
                else:
                    collection_type = None
            elif line and not line.startswith("=="):
                if "/Header}}" in line or line.startswith("----"):
                    continue
                x = re.search("[*#](.*?)( \(.*?\))?:(<!--.*?-->)? (.*?)$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": f"Appearances/{sp}", "date": x.group(1), "item": x.group(4),
                                 "canon": "Canon" in sp, "extra": sp in other, "audiobook": "Audiobook" in sp,
                                 "collectionType": collection_type, "master": sp == "Legends" or sp == "Canon"})
                else:
                    print(f"{p.title()}: Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} appearances from Wookieepedia:Appearances/{sp}")

    return data


def load_source_lists(site, log):
    data = []
    for sp in SUBPAGES:
        i = 0
        skip = False
        p = Page(site, f"Wookieepedia:Sources/{sp}")
        lines = p.get().splitlines()
        bad = []
        for o, line in enumerate(lines):
            # if skip:
            #     skip = False
            #     continue
            if line and not line.startswith("==") and "/Header}}" not in line and not line.startswith("----"):
                line = line.replace(" |reprint=", "|reprint=")
                if "Miniatures" in sp or "RefMagazine" in sp or "CardSets" in sp or "CardTrader" in sp:
                    line = re.sub("(\{\{SWMiniCite.*?)\|num=[0-9-]+", "\\1", line)
                    line = re.sub("(\{\{SWIA.*?)\|page=[0-9]+", "\\1", line)
                    line = re.sub("<!-- .*? -->", "", line)
                    line = re.sub("}}<[0-9 A-z-]+>", "}}", line)

                if "Toys" in sp:
                    line = re.sub("(\|text=.*?)(\|set=.*?)\|", "\\2\\1|", line)
                    line = re.sub("(\|a?l?t?link=.*?) ?(\|pack=.*?)(\|.*?)?}}", "\\2\\1\\3}}", line)
                x = re.search("[*#](?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (D: )?(?P<t>.*?)( {{C\|d: .*?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group("d"), "item": x.group("t"),
                                 "canon": None if "/" not in sp else "Canon" in sp, "ref": x.group("r")})
                else:
                    print(f"{p.title()}: Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/{sp}")

    for y in [*range(1990, datetime.now().year + 1), "Special", "Repost"]:
        i = 0
        p = Page(site, f"Wookieepedia:Sources/Web/{y}")
        if p.exists():
            lines = p.get().splitlines()
            for o, line in enumerate(lines):
                if "/Header}}" in line or line.startswith("----"):
                    continue
                x = re.search("\*(R: )?(?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? *(?P<t>.*?) ?†?( {{C\|1?=?(original|alternate): (?P<a>.*?)}})?( {{C\|int: (?P<i>.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": "Web/Repost" if y == "Special" else f"Web/{y}", "date": x.group("d"), "item": x.group("t"),
                                 "alternate": x.group("a"), "int": x.group("i"), "ref": x.group("r")})
                else:
                    print(f"{p.title()}: Cannot parse line: {line}")
            if log:
                print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{y}")

    p = Page(site, f"Wookieepedia:Sources/Web/Current")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line or line.startswith("----"):
            continue
        x = re.search("\*Current:(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?)( †)?( {{C\|1?=?(original|alternate): (?P<a>.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Current", "date": "Current", "item": x.group("t"),
                         "alternate": x.group("a"), "ref": x.group("r")})
        else:
            print(f"{p.title()}: Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Current")

    p = Page(site, f"Wookieepedia:Sources/Web/Unknown")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line or line.startswith("----"):
            continue
        x = re.search("\*(.*?):( [0-9:-]+)? (.*?)( †)?( {{C\|1?=?(original|alternate): (.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Unknown", "date": "Unknown", "item": x.group(3), "alternate": x.group(7), "official": x.group(1) == "OfficialSite"})
        else:
            print(f"{p.title()}: Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Unknown")

    for sp in ["External", "Target", "Publisher"]:
        p = Page(site, f"Wookieepedia:Sources/Web/{sp}")
        i = 0
        for line in p.get().splitlines():
            if "/Header}}" in line or not line.strip():
                continue
            x = re.search("[#*](?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?) ?†?( {{C\|1?=?(original|alternate): (?P<a>.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
            if x:
                i += 1
                data.append({"index": i, "page": f"Web/{sp}", "date": x.group('d'), "item": x.group('t'), "alternate": x.group('a')})
            else:
                print(f"{p.title()}: Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/{sp}")

    db_pages = {"DB": "2011-09-13", "SWE": "2014-07-01", "Databank": "Current"}
    for template, date in db_pages.items():
        p = Page(site, f"Wookieepedia:Sources/Web/{template}")
        i = 0
        for line in p.get().splitlines():
            if "/Header}}" in line or not line.strip():
                continue
            x = re.search("\*((?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? )?(?P<t>{{.*?)( {{C\|1?=?(original|alternate): (?P<a>.*?)}})?$", line)
            if x:
                i += 1
                data.append({"index": 0, "page": f"Web/{template}", "date": date, "item": x.group("t"),
                             "extraDate": x.group("d"), "ref": x.group("r"), "alternate": x.group('a')})
            else:
                print(f"{p.title()}: Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{template}")

    return data


def load_remap(site) -> dict:
    p = Page(site, "Wookieepedia:Appearances/Remap")
    results = {}
    for line in p.get().splitlines():
        x = re.search("\[\[(.*?)(\|.*?)?]].*?[\[{]+(.*?)(\|.*?)?[]}]+", line)
        if x:
            results[x.group(1)] = "Star Wars Galaxies" if x.group(3) == "GalaxiesNGE" else x.group(3)
    print(f"Loaded {len(results)} remap names")
    return results


ISSUE_REPRINTS = ["A Certain Point of View (department)", "Classic Moment", "Behind the Magic",
                  "In the Star Wars Universe", "Interrogation Droid!", "Jedi Toy Box", "Legendary Authors",
                  "My Star Wars", "Retro", "Red Five (department)", "Rogues Gallery (department)",
                  "Set Piece", "Second Trooper", "The Star Wars Archive", "The Wonder Column"]


def remove_templates(s):
    if s.count("{{") > 0:
        s = re.sub(" ?\{+[Cc]rp}}", "", s)
        y = re.sub(
            '( ?\{+ ?(1st[A-z]*|V?[A-z][od]|[Ff]act|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]cm?|[Aa]mbig|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}].*?$)',
            "", s)
        if y != s:
            print(f"Unexpected template found: {s}")
        return y
    return s


def remove_capture(item: str, pattern: re.Pattern, n, n2=None) -> Tuple[str, Optional[str]]:
    match = re.search(pattern, item)
    if match:
        return item.replace(match.group(n), '').strip(), match.group(n if n2 is None else n2)
    return item, None


def remove_flag(item: str, replacement: str):
    if replacement and replacement in item:
        return item.replace(replacement, '').strip(), True
    return item, False


def store_data(x: Item, i: dict, old: str, extra: str, parenthetical: str, alternate: str, is_reprint: bool, today: str):
    x.master_page = i['page']
    x.canon = None if i.get('extra') else i.get('canon')
    x.from_extra = i.get('extra')
    if i['page'] == "Web/Target":
        x.original_date = i['date']
        x.date = "Target"
    else:
        x.date = i['date']
    x.future = x.date and (x.date == 'Future' or x.date > today)
    x.extra = extra or ''
    x.parenthetical = parenthetical
    x.is_reprint = is_reprint
    x.alternate_url = x.alternate_url or alternate
    x.unlicensed = "Unlicensed" in i['page'] or "{{c|unlicensed" in old.lower() or "{{un}}" in old.lower()
    x.non_canon = "{{c|non-canon" in old.lower() or "{{nc" in old.lower()

    if i.get("int"):
        x.target = f"{i['int']}"
    elif x.target and parenthetical and f"({parenthetical})" not in x.target:
        x.target = f"{x.target} ({parenthetical})"


def check_for_both_continuities(x: Item, targets: Dict[str, List[Item]], both_continuities: set):
    if x.target not in targets:
        targets[x.target] = []
    targets[x.target].append(x)
    if len(targets[x.target]) > 1:
        d = set(i.canon for i in targets[x.target])
        if True in d and False in d:
            both_continuities.add(x.target)
            x.both_continuities = True
            # TODO: is this still necessary?


def record_reprints(reprints, x):
    if x.target in ISSUE_REPRINTS:
        if f"{x.target}|{x.issue}" not in reprints:
            reprints[f"{x.target}|{x.issue}"] = []
        reprints[f"{x.target}|{x.issue}"].append(x)
    elif x.target and x.target not in reprints:
        reprints[x.target] = [x]
    elif x.target:
        reprints[x.target].append(x)
    else:
        print(f"Unexpected state: reprint with no target: {x.original}")


def load_full_sources(site, types, log) -> FullListData:
    sources = load_source_lists(site, log)
    set_formatting = {}
    for ln in Page(site, "Module:FormattedTextLookup/Cards").get().splitlines():
        x = re.search("\[['\"](.*?)['\"]] ?= ?\"(.*?)\"", ln)
        if x:
            set_formatting[x.group(1)] = x.group(2)
    for ln in Page(site, "Module:CardMiniDB/shared").get().splitlines():
        x = re.search("\[['\"](.*?)['\"]] ?= ?\"('*)?\[\[(.*?)]]('*)?\"", ln)
        if x and "|Core Set" not in ln:
            link, _, fmt = x.group(3).partition("|")
            if fmt:
                set_formatting[link] = fmt
            else:
                set_formatting[link] = x.group(2) + link + x.group(4)

    italic_templates = []
    for z in re.findall("([ \t]+([A-z]+) = \{[ \t]*((\n.*?)+?)\n[ \t]+},)",  Page(site, "Module:CardGameCite/data").get()):
        if "noItalics" not in z[0]:
            italic_templates.append(z[1])

    print(f"Loaded formatting text for {len(set_formatting)} sets")

    count = 0
    unique_sources = {}
    full_sources = {}
    target_sources = {}
    both_continuities = set()
    today = datetime.now().strftime("%Y-%m-%d")
    ff_data = {}
    reprints = {}
    card_suffixes = {}
    by_parent = {}
    for i in sources:
        item = i['item']
        old = f"{i['item']}"
        try:
            is_reprint = "{{c|republish" in old.lower() or i["page"].endswith("Reprint")
            item = re.sub("{{C\|([Uu]nlicensed|[Nn]on[ -]?canon)}}", "", item)
            item, parenthetical = remove_capture(item, re.compile("(\|p=(.*?))(?=(\|.*?)?}})"), 1, 2)
            item, extra = remove_capture(item, re.compile("{{[Uu]n}}|{{[Nn]cm?}}|{{[Cc]rp}}"), 0)
            x = extract_item(remove_templates(item), False, i['page'], types, master=True)
            if x and not x.invalid:
                store_data(x, i, old, extra, parenthetical, i.get('alternate'), is_reprint, today)

                if i['page'] == "Web/External" or i["page"] == "Web/Target":
                    x.external = True
                elif i["page"] == "Web/Publisher":
                    x.mode = "Publisher"
                    x.publisher_listing = True
                elif i.get("official"):
                    x.publisher_listing = True
                elif i["page"].startswith("Web/1") or i["page"].startswith("Web/2"):
                    if x.mode == "Publisher" or x.mode == "Commercial":
                        x.mode = "Web"
                x.index = i['index']
                x.date_ref = i.get('ref')
                x.extra_date = i.get('extraDate')

                if x.parent:
                    if x.parent not in by_parent:
                        by_parent[x.parent] = []
                    by_parent[x.parent].append(x)

                if x.target in set_formatting:
                    x.set_format_text = set_formatting[x.target]
                elif x.template in italic_templates:
                    x.set_format_text = "''" + x.target.split(" (")[0] + "''"

                if x.master_page.endswith("CardSets") and x.parenthetical:
                    if x.template not in card_suffixes:
                        card_suffixes[x.template] = {}
                    card_suffixes[x.template][x.target.replace(f" ({parenthetical})", "")] = x.target
                elif x.is_card_or_mini() and x.card:
                    if x.template in card_suffixes and x.parent in card_suffixes[x.template]:
                        x.parent = card_suffixes[x.template][x.parent]

                full_sources[x.full_id()] = x
                unique_sources[x.unique_id()] = x
                if x.target:
                    check_for_both_continuities(x, target_sources, both_continuities)

                if x.ff_data:
                    if x.issue not in ff_data:
                        ff_data[x.issue] = []
                    ff_data[x.issue].append(x)
                if is_reprint:
                    record_reprints(reprints, x)
            else:
                print(f"Unrecognized: {item}")
                count += 1
        except Exception as e:
            print(f"{e}: {item}")
    for k, v in ff_data.items():
        target_sources[f"FFData|{k}"] = v
    for k, v in reprints.items():
        if k is None:
            print(k, v)
        elif "|" in k:
            k, _, s = k.partition("|")
            if k in target_sources:
                y = [i for i in target_sources[k] if s == str(i.issue)]
                if y:
                    for i in v:
                        i.original_printing = y[0]
        else:
            if k in target_sources:
                x = target_sources[k][0]
                for i in v:
                    i.original_printing = x
    _log(f"{count} out of {len(sources)} unmatched: {count / len(sources) * 100}")
    return FullListData(unique_sources, full_sources, target_sources, by_parent, set(), both_continuities, reprints)


def load_full_appearances(site, types, log, canon_only=False, legends_only=False, log_match=True) -> FullListData:
    appearances = load_appearances(site, log, canon_only=canon_only, legends_only=legends_only)
    cx, canon, c_unknown = parse_new_timeline(Page(site, "Timeline of canon media"), types)
    lx, legends, l_unknown = parse_new_timeline(Page(site, "Timeline of Legends media"), types)
    count = 0
    unique_appearances = {}
    full_appearances = {}
    target_appearances = {}
    parentheticals = set()
    both_continuities = set()
    today = datetime.now().strftime("%Y-%m-%d")
    no_canon_index = []
    no_legends_index = []
    reprints = {}
    by_parent = {}
    for i in appearances:
        item = i['item']
        old = f"{i['item']}"
        try:
            is_reprint = "{{c|republish" in item.lower() or i["page"] == "Reprint"
            item = re.sub("{{C\|([Uu]nlicensed|[Nn]on[ -]?canon)}}", "", item)
            item, reprint = remove_capture(item, re.compile("{{[Rr]eprint\|.*?}}"), 0)
            item, ab = remove_capture(item, re.compile("\{\{[Aa]b\|.*?}}"), 0)
            item, parenthetical = remove_capture(item, re.compile("(\|p=(.*?))(?=(\|.*?)?}})"), 1, 2)
            item, extra = remove_capture(item, re.compile("{{[Uu]n}}|{{[Nn]cm?}}|{{[Cc]rp}}"), 0)
            item, alternate = remove_capture(item, re.compile("{{C\|1?=?(original|alternate): (.*?)}}"), 0, 2)
            item, has_content = remove_flag(item, '(content)')
            item, is_extra = remove_flag(item, '(extra)')
            if is_extra:
                i['extra'] = True
            x = extract_item(remove_templates(item), True, i['page'], types, master=True)
            if x and x.unique_id() in unique_appearances:
                if x.template == "Film" or x.template == "TCW" or x.target == "Star Wars: The Clone Wars (film)":
                    x.both_continuities = True
                    both_continuities.add(x.target)
                    continue
                elif x.canon != unique_appearances[x.unique_id()].canon:
                    x.both_continuities = True
                    both_continuities.add(x.target)
                    continue

            if x:
                store_data(x, i, old, extra, parenthetical, alternate, is_reprint, today)

                x.is_appearance = "{{c|source}}" not in old.lower()
                x.has_content = has_content and any(s in i['page'] for s in ["Collections", "Series", "Extra", "Reprint"])
                x.ab = ab
                x.repr = reprint
                x.crp = "{{crp}}" in old.lower()
                x.collection_type = i.get("collectionType")
                x.is_abridged = "abridged audiobook" in x.original and "unabridged" not in x.original
                x.is_audiobook = not ab and ("audiobook)" in x.original or x.target in AUDIOBOOK_MAPPING.values() or i['audiobook'])
                x.german_ad = x.target and "German audio drama" in x.target
                x.is_true_appearance = i["master"]
                if x.template == "SchAdv" or x.template == "EpIAdv":
                    x.original = f"''[[{x.target}]]''"

                full_appearances[x.full_id()] = x
                unique_appearances[x.unique_id()] = x
                if x.parent:
                    if x.parent not in by_parent:
                        by_parent[x.parent] = []
                    by_parent[x.parent].append(x)

                if x.target:
                    x.is_adaptation = (lx.get(x.target, {}) or cx.get(x.target, {})).get("adaptation", False)
                    c, l = determine_index(x, f"{x.issue}-{x.target}" if x.target == "Galaxywide NewsNets" else x.target, i, canon, legends, c_unknown, l_unknown, log_match)
                    if c or l:
                        y = Page(site, x.target)
                        if y.exists() and y.isRedirectPage():
                            x.target = y.getRedirectTarget().title()
                            c, l = determine_index(x, x.target, i, canon, legends, c_unknown, l_unknown, log_match)
                            if not c or not l:
                                print(f"Reconnected {y.title()} redirect to {x.target}")
                    if c:
                        no_canon_index.append(x)
                    if l:
                        no_legends_index.append(x)

                    if x.target.endswith(")") and not x.target.endswith("webcomic)"):
                        parentheticals.add(x.target.rsplit(" (", 1)[0])
                    if x.parent and x.parent.endswith(")") and not x.parent.endswith("webcomic)"):
                        parentheticals.add(x.parent.rsplit(" (", 1)[0])

                    check_for_both_continuities(x, target_appearances, both_continuities)
                elif x.parent and "scenario=" not in x.original:
                    c, l = determine_index(x, x.parent, i, canon, legends, c_unknown, l_unknown, log_match)
                    if c:
                        no_canon_index.append(x)
                    if l:
                        no_legends_index.append(x)

                if is_reprint:
                    record_reprints(reprints, x)
            else:
                print(f"Unrecognized: {item}")
                count += 1
        except Exception as e:
            traceback.print_exc()
            print(f"{type(e)}: {e}: {item}")

    for k, v in reprints.items():
        if k in target_appearances:
            x = target_appearances[k][0]
            for i in v:
                i.original_printing = x

    _log(f"{count} out of {len(appearances)} unmatched: {count / len(appearances) * 100}")
    _log(f"{len(no_canon_index)} canon items found without index")
    _log(f"{len(no_legends_index)} Legends items found without index")
    return FullListData(unique_appearances, full_appearances, target_appearances, by_parent, parentheticals,
                        both_continuities, reprints, no_canon_index, no_legends_index)


def determine_index(x: Item, target, i: dict, canon: Dict[str, int], legends: Dict[str, int], c_unknown, l_unknown, log_match):
    c, l = False, False
    o = increment(x)
    canon_index_expected = x.canon and x.match_expected() and not i['audiobook'] and target not in AUDIOBOOK_MAPPING.values() and not x.german_ad and target not in c_unknown
    legends_index_expected = not x.canon and x.match_expected() and not i['audiobook'] and target not in AUDIOBOOK_MAPPING.values() and not x.german_ad and target not in l_unknown

    canon_index = match_audiobook(x, target, canon, log_match and canon_index_expected, x.master_page)
    if canon_index is not None:
        x.canon_index = canon_index + o
    elif canon_index_expected and target not in LIST_AT_START and target not in LIST_AT_END:
        c = True

    legends_index = match_audiobook(x, target, legends, log_match and legends_index_expected, x.master_page)
    if legends_index is not None:
        x.legends_index = legends_index + o
    elif legends_index_expected and target not in LIST_AT_START and target not in LIST_AT_END:
        l = True

    return c, l


def increment(x: Item):
    if x.is_abridged:
        return 0.2
    elif x.target and "audio drama)" in x.target:
        return 0.3
    elif x.target and ("audiobook" in x.target or "script" in x.target or " demo" in x.target):
        return 0.1
    elif x.parent and ("audiobook" in x.parent or "script" in x.parent or " demo" in x.parent):
        return 0.1
    return 0


SPECIAL_INDEX_MAPPING = {
    "Doctor Aphra (script)": "Doctor Aphra: An Audiobook Original",
    "Hammertong (audiobook)": 'Hammertong: The Tale of the "Tonnika Sisters"',
    "The Siege of Lothal, Part 1 (German audio drama)": "Star Wars Rebels: The Siege of Lothal",
    "The Siege of Lothal, Part 2 (German audio drama)": "Star Wars Rebels: The Siege of Lothal",
    "Forces of Destiny: The Leia Chronicles & The Rey Chronicles": "Forces of Destiny: The Leia Chronicles",
    "Forces of Destiny: Daring Adventures: Volumes 1 & 2": "Forces of Destiny: Daring Adventures: Volume 1",
    "The Rise of Skywalker Adaptation 1": "Star Wars: The Rise of Skywalker Graphic Novel Adaptation",
    "Dark Lord (German audio drama)": "Dark Lord: The Rise of Darth Vader",
    "The Phantom Menace (German audio drama)": TEMPLATE_MAPPING["Film"]["1"],
    "Attack of the Clones (German audio drama)": TEMPLATE_MAPPING["Film"]["2"],
    "Revenge of the Sith (German audio drama)": TEMPLATE_MAPPING["Film"]["3"],
    "A New Hope (German audio drama)": TEMPLATE_MAPPING["Film"]["4"],
    "The Empire Strikes Back (German audio drama)": TEMPLATE_MAPPING["Film"]["5"],
    "Return of the Jedi (German audio drama)": TEMPLATE_MAPPING["Film"]["6"],
    "The Force Awakens (German audio drama)": TEMPLATE_MAPPING["Film"]["7"],
    "The Last Jedi (German audio drama)": TEMPLATE_MAPPING["Film"]["8"],
    "The Rise of Skywalker (German audio drama)": TEMPLATE_MAPPING["Film"]["9"],
    "The High Republic – Attack of the Hutts 1": "The High Republic (2021) 5",
    "Cartel Market": "Star Wars: The Old Republic",
    "Heir to the Empire: The 20th Anniversary Edition": "Heir to the Empire",
    "Star Wars: Dark Forces Consumer Electronics Show demo": "Star Wars: Dark Forces",
    "Star Wars: Dark Forces Remaster": "Star Wars: Dark Forces"
}


AUDIOBOOK_MAPPING = {
    "Adventures in Wild Space: The Escape": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Snare": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Nest": "Adventures in Wild Space: Books 1–3",
    "Adventures in Wild Space: The Dark": "Adventures in Wild Space: Books 4–6",
    "Adventures in Wild Space: The Cold": "Adventures in Wild Space: Books 4–6",
    "Adventures in Wild Space: The Rescue": "Adventures in Wild Space: Books 4–6",
    "Join the Resistance": "Join the Resistance: Books 1-3",
    "Join the Resistance: Escape from Vodran": "Join the Resistance: Books 1-3",
    "Join the Resistance: Attack on Starkiller Base": "Join the Resistance: Books 1-3",
    "The Prequel Trilogy Stories": "Star Wars Storybook Collection",
    "The Original Trilogy Stories": "Star Wars Storybook Collection",
    "Star Wars: Episode II Attack of the Clones (junior novelization)": "Star Wars: Episode II Attack of the Clones (junior novelization audiobook)",
}


def match_audiobook(x: Item, target, data: Dict[str, int], log, page):
    if target in data:
        return data[target]
    elif target in SPECIAL_INDEX_MAPPING and SPECIAL_INDEX_MAPPING[target] in data:
        return data[SPECIAL_INDEX_MAPPING[target]]
    elif "Star Wars: Jedi Temple Challenge" in target and "Star Wars: Jedi Temple Challenge" in data:
        return data["Star Wars: Jedi Temple Challenge"] + int(target.replace("Episode ", "").split("(")[0]) / 100
    elif target in TEMPLATE_MAPPING["KOTORbackups"].values():
        issue = next(f"Knights of the Old Republic {k}" for k, v in TEMPLATE_MAPPING["KOTORbackups"].items() if v == target)
        if issue in data:
            return data[issue]
    elif x.parenthetical and target.replace(f" ({x.parenthetical})", "") in data:
        return data[target.replace(f" ({x.parenthetical})", "")]

    for x in ["audiobook", "unabridged audiobook", "abridged audiobook", "audio", "script", "audio drama", "German audio drama"]:
        if target.replace(f"({x})", "(novelization)") in data:
            return data[target.replace(f"({x})", "(novelization)")]
        elif target.replace(f"({x})", "(novel)") in data:
            return data[target.replace(f"({x})", "(novel)")]
        elif target.replace(f"({x})", "(episode)") in data:
            return data[target.replace(f"({x})", "(episode)")]
        elif target.replace(f" ({x})", "") in data:
            return data[target.replace(f" ({x})", "")]
        elif target.replace(f" {x}", "") in data:
            return data[target.replace(f" {x}", "")]
    if target.replace(" audiobook)", ")") in data:
        return data[target.replace(" audiobook)", ")")]
    elif target.replace(" demo", "") in data:
        return data[target.replace(" demo", "")]
    if log:
        print(f"{page} No match found: {target}")
    return None


def parse_new_timeline(page: Page, types):
    text = page.get()
    redirects = build_redirects(page)
    text = fix_redirects(redirects, text, "Timeline", [], {})
    results = {}
    unique = {}
    is_adaptation = False
    index = 0
    unknown = None
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text).replace("|simple=1", "").replace("(comic)", "(comic story)")
    for line in text.splitlines():
        if "==Unknown placement==" in line:
            unknown = {}
            continue
        line = re.sub("<!--.*?-->", "", line).replace("†", "").strip()

        m = re.search("^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\||\|- ?class.*?\|)?[ ]*?[A-Z]+[ ]*?\n?\|.*?\|+[* ]*?(?P<full>['\"]*[\[{]+.*?[]}]+['\"]*)( *?(†|‡|Ω|&dagger;))*?$", line)
        if m:
            x = extract_item(m.group('full'), True, "Timeline", types, master=False)
            if x and x.target:
                timeline = None
                # target = Page(page.site, x.target)
                # if target.exists() and not target.isRedirectPage():
                #     dt = re.search("\|timeline=[ \[]+(.*?)(\|.*?)?]+(.*?)\n", target.get())
                #     if dt:
                #         timeline = dt.group(1)
                t = f"{x.issue}-{x.target}" if x.target == "Galaxywide NewsNets" else x.target
                results[t] = {"index": index, "date": m.group("date"), "timeline": timeline, "adaptation": is_adaptation}
                if unknown is not None:
                    unknown[t] = index
                elif x.target not in unique:
                    unique[t] = index
                index += 1
        elif "Star Wars (LINE Webtoon)" not in unique and "Star Wars (LINE Webtoon)" in line:
            unique["Star Wars (LINE Webtoon)"] = index
            index += 1
        elif re.match("^\|- ?class ?= ?\".*?\"[ \t]*$", line):
            is_adaptation = "adaptation" in line

    return results, unique, unknown or {}

# TODO: handle dupes between Legends/Canon
