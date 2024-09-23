import re
import traceback
from datetime import datetime

from pywikibot import Page, Category
from c4de.sources.domain import Item, FullListData
from c4de.sources.determine import extract_item, KOTOR, FILMS
from c4de.common import build_redirects, fix_redirects


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets", "Soundtracks"
]


def list_templates(site, cat, data, template_type, recurse=False):
    for p in Category(site, cat).articles(recurse=recurse):
        if "/" not in p.title() and p.title(with_ns=False).lower() not in data:
            data[p.title(with_ns=False).lower()] = template_type


def build_template_types(site):
    results = {"db": "DB", "databank": "DB", "swe": "DB", "External": []}

    list_templates(site, "Category:StarWars.com citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates for use in External Links", results, "External")
    list_templates(site, "Category:Social media citation templates", results, "Social")
    list_templates(site, "Category:Commercial and product listing internet citation templates", results, "Commercial")

    list_templates(site, "Category:YouTube citation templates", results, "YT")
    list_templates(site, "Category:Card game citation templates", results, "Cards")
    list_templates(site, "Category:Miniature game citation templates", results, "Cards")
    list_templates(site, "Category:Toy citation templates", results, "Toys")
    list_templates(site, "Category:TV citation templates", results, "TV")

    list_templates(site, "Category:Interwiki link templates", results, "Interwiki")

    results["Magazine"] = {}
    for p in Category(site, "Category:Magazine citation templates").articles(recurse=True):
        txt = p.get()
        if "BaseCitation/Magazine" in txt:
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

    return results


# TODO: Split Appearances category by type

def load_appearances(site, log, canon_only=False, legends_only=False):
    data = []
    pages = ["Appearances/Legends", "Appearances/Canon", "Appearances/Audiobook", "Appearances/Unlicensed"]
    other = ["Appearances/Extra", "Appearances/Collections"]
    if canon_only:
        pages = ["Appearances/Canon", "Appearances/Audiobook"]
    elif legends_only:
        pages = ["Appearances/Legends", "Appearances/Audiobook"]
    for sp in [*pages, *other]:
        i = 0
        p = Page(site, f"Wookieepedia:{sp}")
        for line in p.get().splitlines():
            if line and not line.startswith("=="):
                if "/Header}}" in line:
                    continue
                x = re.search("[*#](.*?)( \(.*?\))?:(<!--.*?-->)? (.*?)$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group(1), "item": x.group(4),
                                 "canon": "/Canon" in sp, "extra": sp in other, "audiobook": "/Audiobook" in sp})
                else:
                    print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} appearances from Wookieepedia:{sp}")

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
            if line and not line.startswith("==") and not "/Header}}" in line:
                # if line.count("{{") > line.count("}}"):
                #     if o + 1 != len(lines) and lines[o + 1].count("}}") > lines[o + 1].count("{{"):
                #         line = f"{line}{lines[o + 1]}"
                #         skip = True
                #         bad.append(o)

                x = re.search("[*#](?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (D: )?(?P<t>.*?)( {{C\|d: .*?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group("d"), "item": x.group("t"),
                                 "canon": None if "/" not in sp else "Canon" in sp, "ref": x.group("r")})
                else:
                    print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/{sp}")

    for y in range(1990, datetime.now().year + 1):
        i = 0
        p = Page(site, f"Wookieepedia:Sources/Web/{y}")
        if p.exists():
            skip = False
            lines = p.get().splitlines()
            bad = []
            for o, line in enumerate(lines):
                if "/Header}}" in line:
                    continue
                # elif skip:
                #     skip = False
                #     continue
                # if line.count("{{") > line.count("}}"):
                #     if o + 1 != len(lines) and lines[o + 1].count("}}") > lines[o + 1].count("{{"):
                #         line = f"{line}{lines[o + 1]}"
                #         skip = True
                #         bad.append(o)
                x = re.search("\*(?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?) ?†?( {{C\|(original|alternate): (?P<a>.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": f"Web/{y}", "date": x.group("d"), "item": x.group("t"),
                                 "alternate": x.group("a"), "ref": x.group("r")})
                else:
                    print(f"Cannot parse line: {line}")
            if log:
                print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{y}")

    p = Page(site, f"Wookieepedia:Sources/Web/Current")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line:
            continue
        x = re.search("\*Current:(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?)( †)?( {{C\|(original|alternate): (?P<a>.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Current", "date": "Current", "item": x.group("t"),
                         "alternate": x.group("a"), "ref": x.group("r")})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Current")

    p = Page(site, f"Wookieepedia:Sources/Web/Unknown")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line:
            continue
        x = re.search("\*.*?:( [0-9:-]+)? (.*?)( †)?( {{C\|(original|alternate): (.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Unknown", "date": "Unknown", "item": x.group(2), "alternate": x.group(6)})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Unknown")

    p = Page(site, f"Wookieepedia:Sources/Web/External")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line:
            continue
        x = re.search("[#*](?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?) ?†?( {{C\|(original|alternate): (?P<a>.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/External", "date": x.groupdict()['d'], "item": x.groupdict()['t'], "alternate": x.groupdict()['a']})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/External")

    db_pages = {"DB": "2011-09-13", "SWE": "2014-07-01", "Databank": "Current"}
    for template, date in db_pages.items():
        p = Page(site, f"Wookieepedia:Sources/Web/{template}")
        i = 0
        for line in p.get().splitlines():
            if "/Header}}" in line:
                continue
            x = re.search("\*((?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? )?(?P<t>{{.*?)$", line)
            if x:
                i += 1
                data.append({"index": 0, "page": f"Web/{template}", "date": date, "item": x.group("t"),
                             "extraDate": x.group("d"), "ref": x.group("r")})
            else:
                print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{template}")

    return data


def load_remap(site) -> dict:
    p = Page(site, "Wookieepedia:Appearances/Remap")
    results = {}
    for line in p.get().splitlines():
        x = re.search("\[\[(.*?)(\|.*?)?]].*?\[\[(.*?)(\|.*?)?]]", line)
        if x:
            results[x.group(1)] = x.group(3)
    print(f"Loaded {len(results)} remap names")
    return results


def load_full_sources(site, types, log) -> FullListData:
    sources = load_source_lists(site, log)
    count = 0
    unique_sources = {}
    full_sources = {}
    target_sources = {}
    both_continuities = set()
    today = datetime.now().strftime("%Y-%m-%d")
    for i in sources:
        try:
            unlicensed = "{{c|unlicensed" in i['item'].lower()
            non_canon = ("{{c|non-canon" in i['item'].lower() or "{{nc" in i['item'].lower())
            reprint = "{{c|republish" in i['item'].lower()
            c = ''
            if "{{C|" in i['item']:
                cr = re.search("({{C\|([Aa]bridged|[Rr]epublished|[Uu]nlicensed|[Nn]on[ -]?canon)}})", i['item'])
                if cr:
                    c = ' ' + cr.group(1)
                    i['item'] = i['item'].replace(cr.group(1), '').strip()
            x = extract_item(i['item'], False, i['page'], types, master=True)
            if x and not x.invalid:
                if x.template == "SWCT" and not x.target:
                    x.target = x.card
                if i['page'] == "Web/External":
                    x.external = True
                x.master_page = f"Sources/{i['page']}"
                x.canon = i.get('canon')
                x.date = i['date']
                x.future = x.date and (x.date == 'Future' or x.date > today)
                x.index = i['index']
                x.extra = c
                x.unlicensed = unlicensed
                x.non_canon = non_canon
                x.reprint = reprint
                x.alternate_url = i.get('alternate')
                x.date_ref = i.get('ref')
                x.extra_date = i.get('extraDate')
                full_sources[x.full_id()] = x
                unique_sources[x.unique_id()] = x
                if x.target:
                    if x.target not in target_sources:
                        target_sources[x.target] = []

                    target_sources[x.target].append(x)
                    if len(target_sources[x.target]) > 1:
                        d = set(i.canon for i in target_sources[x.target])
                        if True in d and False in d:
                            both_continuities.add(x.target)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            print(f"{e}: {i['item']}")
    print(f"{count} out of {len(sources)} unmatched: {count / len(sources) * 100}")
    return FullListData(unique_sources, full_sources, target_sources, set(), both_continuities)


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
    for i in appearances:
        try:
            non_canon = ("{{c|non-canon" in i['item'].lower() or "{{nc" in i['item'].lower())
            reprint = "{{c|republish" in i['item'].lower()
            c = ''
            alternate = ''
            ab = ''
            if "{{C|" in i['item']:
                cr = re.search("({{C\|([Aa]bridged|[Rr]epublished|[Uu]nlicensed|[Nn]on[ -]?canon)}})", i['item'])
                if cr:
                    c = ' ' + cr.group(1)
                    i['item'] = i['item'].replace(cr.group(1), '').strip()
                a = re.search("( {{C\|(original|alternate): (?P<a>.*?)}})", i['item'])
                if a:
                    alternate = a.groupdict()['a']
                    i['item'] = i['item'].replace(a.group(1), '').strip()
            x2 = re.search("\{\{[Aa]b\|.*?}}", i['item'])
            if x2:
                ab = x2.group(0)
                i['item'] = i['item'].replace(ab, '').strip()

            x3 = re.search(" ?\{\{[Cc]rp}}", i['item'])
            crp = False
            if x3:
                crp = True
                i['item'] = i['item'].replace(x3.group(0), '').strip()

            x = extract_item(i['item'], True, i['page'], types, master=True)
            if x and (x.template == "Film" or x.template == "TCW") and x.unique_id() in unique_appearances:
                both_continuities.add(x.target)
                continue

            if x:
                x.master_page = f"Appearances/{i['page']}"
                x.canon = None if i.get('extra') else i.get('canon')
                x.from_extra = i.get('extra')
                x.date = i['date']
                x.future = x.date and (x.date == 'Future' or x.date > today)
                x.extra = c
                x.alternate_url = alternate
                x.unlicensed = "Unlicensed" in i['page']
                x.non_canon = non_canon
                x.reprint = reprint
                x.ab = ab
                x.crp = crp
                x.abridged = "abridged audiobook" in x.original and "unabridged" not in x.original
                x.audiobook = not ab and ("audiobook)" in x.original or x.target in AUDIOBOOK_MAPPING.values() or i['audiobook'])
                full_appearances[x.full_id()] = x
                unique_appearances[x.unique_id()] = x
                if x.target:
                    canon_index_expected = x.canon and x.match_expected() and not i['audiobook'] and x.target not in AUDIOBOOK_MAPPING.values() and x.target not in c_unknown
                    legends_index_expected = not x.canon and x.match_expected() and not i['audiobook'] and x.target not in AUDIOBOOK_MAPPING.values() and x.target not in l_unknown

                    o = increment(x)
                    canon_index = match_audiobook(x.target, canon, canon_index_expected, log_match)
                    if canon_index is not None:
                        x.canon_index = canon_index + o
                    elif canon_index_expected:
                        no_canon_index.append(x)

                    legends_index = match_audiobook(x.target, legends, False, log_match)
                    if legends_index is not None:
                        x.legends_index = legends_index + o
                    elif legends_index_expected:
                        no_legends_index.append(x)

                    if x.target in cx:
                        x.timeline = cx[x.target]
                    elif x.target in lx:
                        x.timeline = lx[x.target]

                    if x.target.endswith(")") and not x.target.endswith("webcomic)"):
                        parentheticals.add(x.target.rsplit(" (", 1)[0])
                    if x.parent and x.parent.endswith(")") and not x.parent.endswith("webcomic)"):
                        parentheticals.add(x.parent.rsplit(" (", 1)[0])

                    if x.target not in target_appearances:
                        target_appearances[x.target] = []
                    target_appearances[x.target].append(x)
                    if len(target_appearances[x.target]) > 1:
                        d = set(i.canon for i in target_appearances[x.target])
                        if True in d and False in d:
                            both_continuities.add(x.target)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            traceback.print_exc()
            print(f"{type(e)}: {e}: {i['item']}")

    print(f"{count} out of {len(appearances)} unmatched: {count / len(appearances) * 100}")
    print(f"{len(no_canon_index)} canon items found without index")
    print(f"{len(no_legends_index)} Legends items found without index")
    return FullListData(unique_appearances, full_appearances, target_appearances, parentheticals, both_continuities,
                        no_canon_index, no_legends_index)


def increment(x: Item):
    if x.abridged:
        return 0.2
    elif "audio drama)" in x.target:
        return 0.3
    elif "audiobook" in x.target or "script" in x.target or " demo" in x.target:
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
    "The Phantom Menace (German audio drama)": FILMS["1"],
    "Attack of the Clones (German audio drama)": FILMS["2"],
    "Revenge of the Sith (German audio drama)": FILMS["3"],
    "A New Hope (German audio drama)": FILMS["4"],
    "The Empire Strikes Back (German audio drama)": FILMS["5"],
    "Return of the Jedi (German audio drama)": FILMS["6"],
    "The Force Awakens (German audio drama)": FILMS["7"],
    "The Last Jedi (German audio drama)": FILMS["8"],
    "The Rise of Skywalker (German audio drama)": FILMS["9"],
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

    "Ambush": "The Clone Wars Episode 1 - Ambush / Rising Malevolence",
    "Rising Malevolence": "The Clone Wars Episode 1 - Ambush / Rising Malevolence",
    "Shadow of Malevolence": "The Clone Wars Episode 2 - Shadow of Malevolence / Destroy Malevolence",
    "Destroy Malevolence": "The Clone Wars Episode 2 - Shadow of Malevolence / Destroy Malevolence",
    "Rookies": "The Clone Wars Episode 3 - Rookies / Downfall of a Droid",
    "Downfall of a Droid": "The Clone Wars Episode 3 - Rookies / Downfall of a Droid",
    "Duel of the Droids": "The Clone Wars Episode 4 - Duel of the Droids / Bombad Jedi",
    "Bombad Jedi": "The Clone Wars Episode 4 - Duel of the Droids / Bombad Jedi",
    "Cloak of Darkness": "The Clone Wars Episode 5 - Cloak of Darkness / Lair of Grievous",
    "Lair of Grievous": "The Clone Wars Episode 5 - Cloak of Darkness / Lair of Grievous",
    "Dooku Captured": "The Clone Wars Episode 6 - Dooku Captured / The Gungan General",
    "The Gungan General": "The Clone Wars Episode 6 - Dooku Captured / The Gungan General",
    "Jedi Crash": "The Clone Wars Episode 7 - Jedi Crash / Defenders of Peace",
    "Defenders of Peace": "The Clone Wars Episode 7 - Jedi Crash / Defenders of Peace",
    "Trespass": "The Clone Wars Episode 8 - Trespass / The Hidden Enemy",
    "The Hidden Enemy": "The Clone Wars Episode 8 - Trespass / The Hidden Enemy",
    "Blue Shadow Virus (episode)": "The Clone Wars Episode 9 - Blue Shadow Virus / Mystery of a Thousand Moons",
    "Mystery of a Thousand Moons": "The Clone Wars Episode 9 - Blue Shadow Virus / Mystery of a Thousand Moons",
    "Storm Over Ryloth": "The Clone Wars Episode 10 - Storm Over Ryloth / Innocents of Ryloth",
    "Innocents of Ryloth": "The Clone Wars Episode 10 - Storm Over Ryloth / Innocents of Ryloth",
    "Liberty on Ryloth": "The Clone Wars Episode 11 - Liberty on Ryloth / Hostage Crisis",
    "Hostage Crisis": "The Clone Wars Episode 11 - Liberty on Ryloth / Hostage Crisis",
    "Holocron Heist": "The Clone Wars Episode 12 - Holocron Heist / Cargo of Doom",
    "Cargo of Doom": "The Clone Wars Episode 12 - Holocron Heist / Cargo of Doom",
    "Children of the Force": "The Clone Wars Episode 13 - Children of the Force / Senate Spy",
    "Senate Spy": "The Clone Wars Episode 13 - Children of the Force / Senate Spy",
    "Landing at Point Rain": "The Clone Wars Episode 14 - Landing at Point Rain / Weapons Factory",
    "Weapons Factory": "The Clone Wars Episode 14 - Landing at Point Rain / Weapons Factory",
    "Legacy of Terror": "The Clone Wars Episode 15 - Legacy of Terror / Brain Invaders",
    "Brain Invaders": "The Clone Wars Episode 15 - Legacy of Terror / Brain Invaders",
    "Grievous Intrigue": "The Clone Wars Episode 16 - Grievous Intrigue / The Deserter",
    "The Deserter": "The Clone Wars Episode 16 - Grievous Intrigue / The Deserter",
    "Lightsaber Lost": "The Clone Wars Episode 17 - Lightsaber Lost / The Mandalore Plot",
    "The Mandalore Plot": "The Clone Wars Episode 17 - Lightsaber Lost / The Mandalore Plot",
    "Voyage of Temptation": "The Clone Wars Episode 18 - Voyage of Temptation / Duchess of Mandalore",
    "Duchess of Mandalore": "The Clone Wars Episode 18 - Voyage of Temptation / Duchess of Mandalore",
    "Senate Murders": "The Clone Wars Episode 19 - Senate Murders / Cat and Mouse",
    "Cat and Mouse": "The Clone Wars Episode 19 - Senate Murders / Cat and Mouse",
    "Bounty Hunters (episode)": "The Clone Wars Episode 20 - Bounty Hunters / The Zillo Beast",
    "The Zillo Beast": "The Clone Wars Episode 20 - Bounty Hunters / The Zillo Beast",
    "The Zillo Beast Strikes Back": "The Clone Wars Episode 21 - The Zillo Beast Strikes Back / Death Trap",
    "Death Trap": "The Clone Wars Episode 21 - The Zillo Beast Strikes Back / Death Trap",
    "R2 Come Home": "The Clone Wars Episode 22 - R2 Come Home / Lethal Trackdown",
    "Lethal Trackdown": "The Clone Wars Episode 22 - R2 Come Home / Lethal Trackdown"
}


def match_audiobook(target, data, canon, log):
    if target in data:
        return data[target]
    elif target in SPECIAL_INDEX_MAPPING and SPECIAL_INDEX_MAPPING[target] in data:
        return data[SPECIAL_INDEX_MAPPING[target]]
    elif target.startswith("Star Wars: Jedi Temple Challenge") and "Star Wars: Jedi Temple Challenge" in data:
        return data["Star Wars: Jedi Temple Challenge"] + int(target.replace("Star Wars: Jedi Temple Challenge - Episode ", "")) / 100
    elif target in KOTOR.values():
        issue = next(f"Knights of the Old Republic {k}" for k, v in KOTOR.items() if v == target)
        if issue in data:
            return data[issue]

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
    if canon and log:
        print(f"No match found: {target}")
    return None


ERAS = {
    "Rise of the Empire era": "32 BBY",
    "Rebellion era": "0 ABY",
    "New Republic era": "10 ABY"
}


def parse_new_timeline(page: Page, types):
    text = page.get()
    redirects = build_redirects(page)
    text = fix_redirects(redirects, text, "Timeline", [], {})
    results = {}
    unique = {}
    index = 0
    unknown = None
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text).replace("|simple=1", "")
    for line in text.splitlines():
        if "==Unknown placement==" in line:
            unknown = {}
            continue
        line = re.sub("<!--.*?-->", "", line).replace("†", "").strip()

        m = re.search("^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\||\|- ?class.*?\|)?[ ]*?[A-Z]+[ ]*?\n?\|.*?\|+[* ]*?(?P<full>['\"]*[\[{]+.*?[]}]+['\"]*) ?†?$", line)
        if m:
            x = extract_item(m.group('full'), True, "Timeline", types, master=False)
            if x and x.target:
                timeline = None
                # target = Page(page.site, x.target)
                # if target.exists() and not target.isRedirectPage():
                #     dt = re.search("\|timeline=[ \[]+(.*?)(\|.*?)?]+(.*?)\n", target.get())
                #     if dt:
                #         timeline = dt.group(1)
                results[x.target] = {"index": index, "date": m.group("date"), "timeline": timeline}
                if unknown is not None:
                    unknown[x.target] = index
                elif x.target not in unique:
                    unique[x.target] = index
                index += 1
        elif "Star Wars (LINE Webtoon)" not in unique and "Star Wars (LINE Webtoon)" in line:
            unique["Star Wars (LINE Webtoon)"] = index
            index += 1

    return results, unique, unknown or {}

# TODO: handle dupes between Legends/Canon
