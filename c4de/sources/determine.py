import re
from typing import List, Dict, Optional

from pywikibot import Page
from c4de.sources.domain import Item, ItemId
from c4de.sources.extract import GAME_TEMPLATES


def compare_cleaned(x, y, r1, s1="", r2=None, s2=""):
    if x and y and r1 and r2:
        return x and y and x.replace(r1, s1).replace(r2, s2) == y.replace(r1, s1).replace(r2, s2)
    elif x and y and r1:
        return x and y and x.replace(r1, s1) == y.replace(r1, s1)
    return False


def follow_redirect(o: Item, site, log):
    try:
        if o.target:
            p = Page(site, o.target)
            if p.exists() and p.isRedirectPage():
                if log:
                    print(f"Followed redirect {o.target} to {p.getRedirectTarget().title()}")
                o.original_target = o.target
                o.target = p.getRedirectTarget().title().split('#', 1)[0]
                return True
    except Exception as e:
        print(o.target, e)
    return False


def do_card_templates_match(set_name, o: Item, x: Item):
    if o.template == x.template:
        return True
    if set_name == "Star Wars: The Power of the Force (1995 toy line)":
        return (o.template == "KennerCite" and x.template == "HasbroCite") or (o.template == "HasbroCite" and x.template == "KennerCite")
    return False


def check_targets(o: Item, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]],
                  use_original_text=False, by_parent=False):
    if by_target and by_target.get(target):
        return ItemId(o, by_target[target][0], use_original_text, False, by_parent=by_parent)
    elif other_targets and other_targets.get(target):
        return ItemId(o, other_targets[target][0], use_original_text, True, by_parent=by_parent)
    return None


SPECIAL_REMAP = ["Star Wars Kids Answer Quest"]


def determine_id_for_item(o: Item, page: Page, data: Dict[str, Item], by_target: Dict[str, List[Item]], other_data: Dict[str, Item],
                          other_targets: Dict[str, List[Item]], remap: dict, canon: bool, log: bool, ref=False):
    """ :rtype: ItemId """

    # Remapping common mistakes in naming
    if remap and o.target and o.target in remap:
        m = check_targets(o, remap[o.target], by_target, other_targets, use_original_text=False)
        if m:
            return m
    elif o.target and o.target in SPECIAL_REMAP and o.parent:
        m = check_targets(o, o.parent, by_target, other_targets, use_original_text=False)
        if m:
            return m
    if o.template in GAME_TEMPLATES and o.card:
        return ItemId(o, o, True, False)

    data_sets = {True: other_data, False: data} if ref else {False: data, True: other_data}

    if (o.unique_id() in data or o.unique_id() in other_data) and not o.card:
        m = data.get(o.unique_id(), other_data.get(o.unique_id()))
        if m.template == "SWE" and not canon and not o.override:
            o.override_date = "2014-04-25"
        return ItemId(o, m, False, o.unique_id() in other_data)
    elif "cargobay" in o.original:
        return ItemId(o, o, True, False)
    elif "HoloNet News" in o.original and re.search("\[https://web.archive.*?\.gif .*?].*?\[\[Holonet News", o.original):
        x = ItemId(o, o, True, False)
        x.master.date = "2002-02-28"
        return x
    elif o.template == "InsiderCite" and (o.target == "The Last Page" or o.target == "From the Editor's Desk"):
        if o.parent and (o.parent in by_target or o.parent in other_targets):
            return ItemId(o, by_target[o.parent][0] if o.parent in by_target else other_targets[o.parent], True, False)
        print(f"Unexpected state: {o.target} fell through Insider parent logic")
        t = f"General|None|Star Wars Insider {o.issue}|None|None|None|None|None"
        if t in data or t in other_data:
            return ItemId(o, data[t] if t in data else other_data[t], True, False)

    if o.mode == "External" or o.mode == "Basic":
        if o.url:
            m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
            if m:
                return m
        return None

    if o.template and o.template.startswith("FactFile"):
        x = match_fact_file(o, by_target, other_targets)
        if x:
            return x

    if not o.template and o.target and "(radio)" in o.target:
        m = check_targets(o, o.target, by_target, other_targets, use_original_text=True)
        if m:
            return m

    if o.check_both:
        x = match_parent_target(o, o.parent, o.target, by_target, other_targets, page.site)
        y = match_parent_target(o, o.target, o.parent, by_target, other_targets, page.site, False)
        if x and y:
            if x.master.parent and y.master.target and x.master.parent == y.master.target:
                return x
            elif x.master.target and y.master.parent and x.master.target == y.master.target:
                return y
        elif x:
            return x
        elif y:
            return x

    # Template-specific matching
    for other, d in data_sets.items():
        if o.template == "LEGOCite" and o.special:
            alt = []
            for s, x in d.items():
                if x.template == "LEGOCite" and x.special == o.special:
                    return ItemId(o, x, False, other)
                elif x.template == "LEGOCite" and compare_cleaned(x.card, o.card, r1="starfighter", s1="fighter"):
                    alt.append(x)
            if alt:
                return ItemId(o, alt[-1], False, other)
        elif o.template == "CalendarCite":
            for s, x in d.items():
                if x.target == o.target:
                    return ItemId(o, x, True, other)

    is_tracked_mini = o.template == "SWIA" or (o.mode == "Minis" and o.template not in ["Shatterpoint"])
    if o.mode == "Minis":
        set_name = o.parent or o.target
        m = match_miniatures(o, set_name, data_sets, canon, ref, is_tracked_mini)
        if m:
            return m

    if o.is_card_or_toy() and (o.card or o.special):
        set_name = o.parent or o.target
        if o.url and o.mode != "Minis":
            m = match_by_url(o, o.url, data, False)
            if not m:
                m = match_by_url(o, o.url, other_data, False)
            if m:
                return m

        exact, start, other_set = [], [], []
        if set_name is not None:
            for other, d in data_sets.items():
                for s, x in d.items():
                    if do_card_templates_match(set_name, o, x) and x.canon == canon:
                        m = match_cards(o, x, set_name, other, exact, start)
                        if m:
                            return m
        if is_tracked_mini and exact:
            return ItemId(o, exact[0], True, False)
        elif is_tracked_mini and other_set:
            print(f"Converting {o.parent} card {o.card} to correct set {other_set[0].parent}")
            xz = [i for i in other_set if i.canon == canon]
            return ItemId(o, xz[0] if xz else other_set[0], False, False)
        elif exact or start:
            if o.mode == "Toys" or o.mode == "Minis":
                print(f"Unknown {o.template} set: {o.card}/{o.special}/{o.parent}")
                o.unknown = True
            return ItemId(o, exact[0] if exact else start[0], True, False)

    if o.is_card_or_toy():
        set_name = o.parent or o.target
        if o.card or o.special:
            if o.mode == "Toys":
                print(f"{o.mode} {o.template} with {o.card}/{o.special} card/special fell through specific logic")
                o.unknown = True
        m = match_by_set_name(o, o.mode, o.template, set_name, data, other_data)
        if not m:
            m = match_by_set_name(o, o.mode, None, set_name, data, other_data)
        if m:
            return m

    # Find a match by URL
    if o.url and 'starwars/article/dodcampaign' not in o.url:
        m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
        if m and not (o.mode == "Toys" and m.master.mode == "Found-External"):
            return m

    # if Toy/Card isn't matched by the URL, then use the original
    if o.is_card_or_mini() and (o.card or o.special):
        return ItemId(o, o, True, False)
    elif o.mode == "Toys" and (o.card or o.special):
        o.unknown = True
        return ItemId(o, o, True, False)

    if o.issue or o.no_issue:
        t = f"{o.mode}|None|{o.target}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed, False)
        elif o.parent and "Special Edition" in o.parent and by_target.get(o.parent):
            return ItemId(o, by_target[o.parent][0], True, False)
        x = match_issue_target(o, by_target, other_targets, True)
        if not x and o.target and not o.followed_redirect:
            if follow_redirect(o, page.site, True):
                o.followed_redirect = True
                x = match_issue_target(o, by_target, other_targets, False)
        if not x or (x and x.master.issue != o.issue and o.parent in by_target):
            targets = [(t, False) for t in get_possible_targets(o, by_target)]
            targets += [(t, True) for t in get_possible_targets(o, other_targets)]
            print(f"Found unrecognized {o.target} listing for {o.parent} --> {len(targets)} possible matches")

            exact = [(t, c) for (t, c) in targets if t.template == o.template and t.issue == o.issue]
            magazine = [(t, c) for (t, c) in targets if t.template == o.template]
            numbers = [(t, c) for (t, c) in targets if t.issue and t.issue.isnumeric()]

            if len(exact) == 1:
                x = ItemId(o, exact[0][0], False, exact[0][1], False)
            elif len(targets) == 1:
                x = ItemId(o, targets[0][0], False, targets[0][1], False)
            elif len(magazine) == 1:
                x = ItemId(o, magazine[0][0], False, magazine[0][1], False)
            elif o.issue and o.issue.isnumeric() and len(numbers) == 1:
                x = ItemId(o, numbers[0][0], False, numbers[0][1], False)
            elif by_target.get(o.parent):
                parent = by_target[o.parent][0]
                x = ItemId(o, parent, True, False, by_parent=True)
        if x:
            return x
        if o.target == o.parent and by_target.get(o.parent) and o.text and o.text.replace("'", "") != o.target:
            return ItemId(o, by_target[o.parent][0], True, False, by_parent=True)

    x = match_parent_target(o, o.parent, o.target, by_target, other_targets, page.site)
    if x:
        if o.target in ["The Last Page", "From the Editor's Desk"]:
            x.by_parent = False
        return x

    if o.parent and "|story=" not in o.original and "|adventure=" not in o.original:
        # print(f"Parent: {o.full_id()}")
        t = f"{o.mode}|None|{o.parent}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed or o.card is not None, False)
        elif other_data and t in other_data:
            return ItemId(o, other_data[t], o.collapsed or o.card is not None, True)
        elif o.card:
            return ItemId(o, o, True, False)

    x = match_target(o, by_target, other_targets, log)
    if not x and o.target and not o.followed_redirect:
        if follow_redirect(o, page.site, log):
            o.followed_redirect = True
            x = match_target(o, by_target, other_targets, log)
    if x and o.template == "GermanFanCite" and x.master.template == "InsiderCite" and "|reprint=1" not in x.master.original:
        x.use_original_text = True
        x.current.unknown = True

    if o.template == "HomeVideoCite":
        x = None
        if "episode=" in o.original:
            x = match_specific_target(o, o.parent, by_target, other_targets, log)
            if x:
                x.use_original_text = True
                return x
        for is_other, ids in data_sets.items():
            for k, v in ids.items():
                if k.startswith(f"General|HomeVideoCite|None|None|{o.parent}|"):
                    if "scene=" in o.original and "scene=" in v.original:
                        return ItemId(o, v, True, is_other)
                    elif "featurette=" in o.original and "featurette=<FEATURETTE>" in v.original:
                        return ItemId(o, v, True, is_other)
    return x


def flatten_card(s, x=False):
    return (s.split("&mdash;")[0].split("—")[0] if x else s).replace("''", "").replace('"', "").replace("The ", "").replace("0", "O").replace("1", "I").lower()


def match_individual_miniature(o: Item, oc: str, x: Item):
    close = []
    if x.url and o.url and x.url == o.url:
        return True, []
    elif x.card and oc:
        if flatten_card(x.card) == oc:
            if flatten_card(x.special or '') == flatten_card(o.special or ''):
                return True, []
            elif (x.special and not o.special) or (o.special and not x.special):
                close.append(x)
        elif o.template == "SWMiniCite" and oc in flatten(x.card):
            return True, []
    return False, close


def match_miniatures(o: Item, set_name, data_sets: Dict[bool, dict], canon, ref, is_tracked_mini):
    oc = flatten_card(o.card or '', True)
    exact, other_set, close = [], [], []
    for other, d in data_sets.items():
        for s, x in d.items():
            if do_card_templates_match(set_name, o, x) and x.card:
                # if x.canon != canon:
                #     continue
                for t in [x.target, x.parent]:
                    if t and (t == set_name or t.replace(" - ", " ") == set_name.replace(" - ", " ") or t.startswith(set_name)):
                        m, c = match_individual_miniature(o, oc, x)
                        exact += c
                        if m:
                            return ItemId(o, x, False, other)
                if "bypass" not in o.original:
                    m, c = match_individual_miniature(o, oc, x)
                    close += c
                    if m:
                        other_set.append(x)

    if exact:
        if not o.card:
            o.card = exact[0].card
        return ItemId(o, exact[0], False, False)
    elif other_set and o.template != "SWMiniCite":
        print(f"Converting {o.parent} card {o.card} to correct set {other_set[0].parent}")
        if not o.card:
            o.card = other_set[0].card
        return ItemId(o, other_set[0], False, False)
    elif close and o.template != "SWMiniCite":
        print(f"Unknown {o.template} set: {o.card}/{o.special}/{o.parent}")
        o.unknown = True
        return ItemId(o, close[0], True, False)
    if is_tracked_mini:
        print(f"{'Ref: ' if ref else ''}{o.template} [{set_name}] [{oc}] [{o.special}] [{o.url}] (canon={canon}) fell through miniatures logic: {o.original}")
    return None


def match_cards(o: Item, x: Item, set_name, other: bool, exact: list, start: list):
    check = True
    m = None
    if any(t and (t == set_name or t.replace(" - ", " ") == set_name.replace(" - ", " ")) for t in
           (x.target, x.parent)):
        check = False
        m = match_card(o, x, other, exact)
    if not m and any(t and (t.startswith(set_name) or set_name in t) for t in (x.target, x.parent)):
        check = False
        m = match_card(o, x, other, start)
    if not m and o.mode == "Minis" and check and "bypass" not in o.original:
        m = match_card(o, x, other, [])
    return m


def match_card(o: Item, x: Item, other: bool, matches: list):
    if (x.card and x.card == o.card) or (x.text and x.text == o.text):
        return ItemId(o, x, False, other)
    elif o.mode == "Minis" and x.card and o.card and flatten_card(x.card) == flatten_card(o.card, True):
        return ItemId(o, x, False, other)
    elif o.mode == "Minis" and x.card and x.url and o.url and x.url == o.url:
        return ItemId(o, x, False, other)
    elif o.mode != "Minis":
        matches.append(x)


def match_fact_file(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]]):
    if f"FFData|{o.issue}" in by_target:
        x = match_fact_file_issue(o, by_target[f"FFData|{o.issue}"], False)
        if x:
            return x
    if f"FFData|{o.issue}" in other_targets:
        x = match_fact_file_issue(o, other_targets[f"FFData|{o.issue}"], True)
        if x:
            return x

    for i in range(1, 141):
        if str(i) != o.issue and f"FFData|{i}" in by_target:
            x = match_fact_file_issue(o, by_target[f"FFData|{i}"], False, False)
            if x:
                return x
        if str(i) != o.issue and f"FFData|{i}" in other_targets:
            x = match_fact_file_issue(o, other_targets[f"FFData|{i}"], True, False)
            if x:
                return x
    print(o.issue, o.original, f"FFData|{o.issue}" in by_target, f"FFData|{o.issue}" in other_targets)
    o.unknown = True
    return ItemId(o, o, True, False)


def flatten(s):
    return s.replace("&", "and").replace("-", "").replace("–", "").replace("—", "").replace("&mdash;", "").replace("&ndash;", "").replace("'", "").replace("German Edition - ", "").replace("(German Edition)", "").replace("  ", " ").lower().strip()


def match_fact_file_issue(o: Item, entries: list[Item], other: bool, log_missing=True):
    if not o.ff_data:
        return None
    a = (o.ff_data.get("abbr") or "").replace(" ", "")
    a = "0ABY" if a == "0BBY" else a
    if o.issue == "Part 8" and a == "22BBY":
        a = "21BBY"
    if a == "ANA" and o.issue and o.issue.startswith("Part") and o.issue != "Part 55":
        a = "SKY"
    abbr = [x for x in entries if a and x.ff_data.get("abbr") and x.ff_data["abbr"].replace(" ", "") == a]
    if len(abbr) == 1:
        # if o.ff_data['legacy']:
        #     print(f"Match: {o.ff_data}, {abbr[0].ff_data}")
        return ItemId(o, abbr[0], False, other)
    elif len(abbr) > 1:
        for i in [1, 2]:
            if o.ff_data[f"num{i}"]:
                x1, x2 = to_int(o.ff_data[f"num{i}"]), to_int(o.ff_data[f"num{i + 1}"])
                for x in abbr:
                    n1, n2 = to_int(x.ff_data[f"num{i}"]), to_int(x.ff_data[f"num{i + 1}"])
                    if x1 and x2 and n1 <= x1 and x2 <= n2:
                        return ItemId(o, x, False, other)
                    elif x1 and x2 is None and n1 <= x1 <= n2:
                        return ItemId(o, x, False, other)
        print(f"Unable to exact-match {o.ff_data['page']}, using {abbr[0].ff_data}: {o.original}")
        return ItemId(o, abbr[0], False, other)

    if o.ff_data["text"]:
        t1, _, _ = flatten(o.ff_data["text"]).lower().partition("}}")
        for i in entries:
            if i.issue != o.issue:
                continue
            t2, _, _ = flatten(i.ff_data["text"]).lower().partition("}}")
            if i.ff_data["text"] and (t1 == t2 or t2 in t1 or t2[:-1] in t1 or t1 in t2):
                return ItemId(o, i, False, other)
    if log_missing:
        print(f"Unable to find {o.ff_data['page']} for issue {o.issue}: {o.ff_data}")
    return None


def to_int(x: str):
    return int(x) if x and x.isnumeric() else None


def get_possible_targets(o: Item, by_target):
    targets = by_target.get(o.target, [])
    if not targets and o.template == "InsiderCite":
        targets = by_target.get(f"{o.target} (Star Wars Insider)", [])
    if not targets and o.template == "InsiderCite":
        targets = by_target.get(f"{o.target} (article)", [])
    return targets


def match_by_set_name(o: Item, mode: str, template: Optional[str], set_name: str, data, other_data):
    m = find_matching_set(mode, template, set_name, data)
    if m:
        return ItemId(o, m, True, False)

    m = find_matching_set(mode, template, set_name, other_data)
    if m:
        return ItemId(o, m, True, True)
    return None


def find_matching_set(mode, template, set_name, data: dict):
    t = f"{'Cards' if template == 'SWIA' else mode}|{template}|{set_name}"
    for x in ["", "None"]:
        if f"{t}|None|None|None|None|{x}" in data:
            return data[f"{t}|None|None|None|None|{x}"]

    partial = []
    for x, y in data.items():
        if (y.template == template or not template) and y.target and set_name:
            if y.target == set_name:
                return y
            elif y.target.startswith(set_name):
                partial.append(y)
    return partial[0] if partial else None


def find_matching_issue(items, issue, text, template):
    if "issue1=" in text:
        for t in items:
            if t.issue == issue and template == t.template and t.original and "issue1=" in t.original:
                return t
    for t in items:
        if t.issue == issue and template == t.template:
            return t
    return items[0]


def match_issue_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], use_original):
    match = match_target_issue_name(o, o.target, by_target, other_targets, use_original)
    if match:
        return match
    elif o.target and ("&hellip;" in o.target or "dash;" in o.target):
        t1 = o.target.replace("&ndash;", '–').replace('&mdash;', '—')
        t2 = o.target.replace("&hellip;", "...")
        targets = {t1, t2, t1.replace("&hellip;", "...")}
        for tx in targets:
            match = match_target_issue_name(o, tx, by_target, other_targets, use_original)
            if match:
                return match

    if o.target and o.parent and o.target.startswith(f"{o.parent}#"):
        m = check_targets(o, o.parent, by_target, other_targets, use_original_text=True)
        if m:
            return m
    return None


def match_target_issue_name(o, target, by_target, other_targets, use_original):
    if o.ref_magazine and target and target == "Star Wars Universe" and o.text:
        for name in ["Star Wars Universe", "Character"]:
            for b, targets in {False: by_target, True: other_targets}.items():
                if not targets:
                    continue
                items = [i for i in (targets.get(name) or []) if i.issue == o.issue and i.text and (o.text.lower() in i.text or i.text.startswith(o.text[:6]))]
                if items:
                    return ItemId(o, items[0], False, b)

    if target and by_target and target in by_target:
        return ItemId(o, find_matching_issue(by_target[target], o.issue, o.original, o.template), use_original, False)
    elif target and other_targets and target in other_targets:
        return ItemId(o, find_matching_issue(other_targets[target], o.issue, o.original, o.template), use_original, False)
    return None


def match_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]],
                        site, save=True) -> Optional[ItemId]:
    if parent and target:
        x = match_by_parent_target(o, parent, target, by_target, other_targets, True)
        if not x and target and not o.followed_redirect:
            if follow_redirect(o, site, True):
                if save:
                    o.followed_redirect = True
                x = match_by_parent_target(o, parent, target, by_target, other_targets)
        if not x and o.template == "StoryCite" and "(short story)" not in o.target:
            x = match_by_parent_target(o, parent, f"{target} (short story)", by_target, other_targets)
        if x:
            return x
    return None


def match_by_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], single=False):
    if by_target and target in by_target and len(by_target[target]) > (0 if single else 1):
        for t in by_target[target]:
            if t.parent == parent:
                return ItemId(o, t, False, False)
    if other_targets and target in other_targets and len(other_targets[target]) > (0 if single else 1):
        for t in other_targets[target]:
            if t.parent == parent:
                return ItemId(o, t, False, True)
    if parent and "Star Wars Legends Epic Collection" in parent and o.template == "StoryCite":
        m = check_targets(o, target, by_target, other_targets, use_original_text=True, by_parent=True)
        if m:
            return m

    if target and target[0].upper() != target[0]:
        return match_by_parent_target(o, o.parent, target[0].capitalize() + target[1:], by_target, other_targets)
    return None


TEMPLATE_SUFFIXES = {
    "EncyclopediaCite": ["reference book"],
    "StoryCite": ["short story"],
    "CWACite": ["comic story", "comic"],
    "GoC": ["episode", "Galaxy of Creatures"],
    "GalacticPals": ["episode", "Galactic Pals"],
    "InsiderCite": ["Star Wars Insider", "article"],
}


TV_SUFFIXES = {
    "Acolyte": "The Acolyte",
    "TCW": "The Clone Wars",
    "TBB": "The Bad Batch",
    "DisneyGallery": "Disney Gallery: The Mandalorian"
}


def match_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], log):
    return match_specific_target(o, o.target, by_target, other_targets, log)


def match_specific_target(o: Item, target: str, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], log):
    targets = []
    if target:  # build list of possible target matches; template-specific remaps and simple mistakes
        targets.append(target.replace("_", " ").replace("Game Book ", ""))
        if "&hellip;" in target:
            targets.append(target.replace("&hellip;", "..."))
        if "..." in target:
            targets.append(target.replace("...", "&hellip;"))
        if "(" not in target and o.tv:
            targets.append(f"{target} (episode)")
            targets.append(f"{target} (short film)")
            if o.template in TV_SUFFIXES and TV_SUFFIXES[o.template] not in target:
                targets.append(f"{target} ({TV_SUFFIXES[o.template]})")
        if "(" not in target and o.template in TEMPLATE_SUFFIXES:
            for i in TEMPLATE_SUFFIXES[o.template]:
                targets.append(f"{target} ({i})")
        if "ikipedia:" in target:
            targets.append(target.split("ikipedia:", 1)[-1])
        if o.template in ["Tales", "TCWUKCite", "IDWAdventuresCite-2017"] and "(" not in target and target not in by_target:
            targets.append(f"{target} (comic)")

        m = re.search("^(Polyhedron|Challenge|Casus Belli|Valkyrie|Inphobia) ([0-9]+)$", target)
        if m:
            x = m.group(1).replace(" ", "") + "Cite"
            for dct in [by_target, other_targets or {}]:
                for t, d in dct.items():
                    for i in d:
                        if i.parent == target:
                            return ItemId(o, i, False, False)
                        elif i.template == x and i.issue == m.group(2):
                            return ItemId(o, i, False, False)

    for t in targets:
        x = match_by_target(t, o, by_target, other_targets, log)
        if x:
            return x

    for par in ["episode", "TPB"]:
        if target and f"({par})" in target and target != "Star Wars Rebels (TPB)":
            x = match_by_target(target.replace(f" ({par})", ""), o, by_target, other_targets, log)
            if x:
                return x
    if o.format_text and o.parent and o.parent.startswith(o.format_text):
        x = match_by_target(o.format_text, o, by_target, other_targets, log)
        if x:
            log(f"Matched {o.original} --> {x.master.original} via format text {o.format_text}")
            return x

    return None


def match_by_target(t, o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], log):
    if t in by_target:
        return _match_by_target(o, t, by_target[t], False, log)
    elif other_targets and t in other_targets:
        return _match_by_target(o, t, other_targets[t], True, log)
    return None


def _match_by_target(o: Item, t, targets, from_other, log: bool):
    if len(targets) == 1:
        return ItemId(o, targets[0], o.collapsed, from_other)
    if log and not o.both_continuities:
        print(f"Multiple matches found for {t}")
    for x in targets:
        if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''", ""):
            return ItemId(o, x, o.collapsed, from_other)
        elif not o.template and not x.template and not o.parent and not x.parent:
            return ItemId(o, x, o.collapsed, from_other)
        elif x.url and o.url and do_urls_match(o.url, o.template, x, True, True):
            return ItemId(o, x, o.collapsed, from_other)
    return ItemId(o, targets[0], o.collapsed, False)


def prep_url(url):
    u = url or ''
    if u.startswith("/"):
        u = u[1:]
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def clean_language_prefix(u):
    return u.replace("en/", "").replace("en-gb/", "").replace("en-us/", "")


def matches_up_to_string(d, u, x, in_both: bool):
    """ Checks if two URLs match up until the given string """
    if not d:
        return False
    elif in_both:
        return x in d and u in d and d.split(x, 1)[0] == u.split(x, 1)[0]
    else:
        return (x in d or u in d) and d.split(x, 1)[0] == u.split(x, 1)[0]


def do_urls_match(url, template, d: Item, replace_page, log=False):
    d_url = prep_url(d.url)
    alternate_url = prep_url(d.alternate_url)
    if template and "youtube" in template.lower() and not alternate_url and d_url and d_url.startswith("-"):
        alternate_url = d_url[1:]
    if not alternate_url and template == "Hyperspace" and d_url.startswith("fans/"):
        alternate_url = d_url.replace("fans/", "")
    if d_url and d_url.lower() == url.lower():
        return 2
    elif alternate_url and alternate_url.lower() == url.lower():
        return 2
    elif d_url and d.template == "EA" and ("/battlefront-2" in url or "starwars/jedi-" in url) and url.replace("/battlefront-2", "/star-wars-battlefront-2").replace("starwars/jedi-", "starwars/jedi/jedi-") == d_url:
        return 2
    elif d_url and clean_language_prefix(d_url) == clean_language_prefix(url):
        return 2
    elif d_url and matches_up_to_string(d_url.lower(), url.lower(), "&month=", True):
        return 2
    elif d_url and "index.html" in d_url and re.search("indexp[0-9]\.html", url):
        if replace_page and d_url == re.sub("indexp[0-9]+\.html", "index.html", url):
            return 2
        elif d_url == re.sub("indexp([0-9]+)\.html", "index.html?page=\\1", url):
            return 2
    elif d_url and matches_up_to_string(d_url.lower(), url.lower(), "/index.html", False):
        return 1
    elif d_url and template == "SW" and d.template == "SW" and url.startswith("tv-shows/") and \
            d_url.startswith("series") and d_url == url.replace("tv-shows/", "series/"):
        return 2
    elif d_url and matches_up_to_string(d_url.lower(), url.lower(), "?page=", False):
        return 2
    elif template == "SonyCite" and d.template == "SonyCite" and (url.startswith("players/") or url.startswith("en_US/players/")):
        nu = url.replace("en_US/players/", "").replace("players/", "")
        if d_url.replace("&resource=features", "") == nu.replace("&resource=features", ""):
            return 2
        elif alternate_url and alternate_url.replace("&resource=features", "") == nu.replace("&resource=features", ""):
            return 2
    return 0


def add_or_remove_piece(u, fx):
    if fx.startswith("/"):
        return u.replace(fx, "") if u.endswith(fx) else f"{u}{fx}"
    elif fx.endswith("/"):
        return u.replace(fx, "") if u.startswith(fx) else f"{fx}{u}"
    return u


def match_url(o: Item, u: str, data: dict, other_data: dict):
    m = match_by_urls(o, u, data, other_data, False)
    if not m and o.url.endswith("?"):
        m = match_by_urls(o, u[:-1], data, other_data, False)
    if not m and ("indexp" in o.url or "index.html?page=" in o.url):  # match old multipage URLs
        m = match_by_urls(o, u, data, other_data, True)
    if not m and o.template == "WebCite":
        simple_url = u.replace("http:", "https:").split("//", 1)[-1]
        m = match_by_urls(o, simple_url.replace("www.", ""), data, other_data, True)
        if not m:
            m = match_by_urls(o, simple_url.split("/", 1)[-1], data, other_data, True)
    if not m and o.template == "Databank":  # check for missing/extra databank and comments
        m = match_by_urls(o, add_or_remove_piece(o.url, "databank/"), data, other_data, True)
    if not m and o.template == "Blog" and not o.url.endswith("/comments"):
        m = match_by_urls(o, add_or_remove_piece(o.url, "/comments"), data, other_data, True)
    if not m and o.template == "SonyCite" and "&month=" in o.url:
        m = match_by_urls(o, u.split("&month=")[0], data, other_data, False)
    if not m and o.template == "Faraway" and "starwarsknightsoftheoldrepublic" in o.url:    # TODO: remove
        x = re.sub("kotor([0-9]+)\|", "kotor0\\1|", re.sub("starwarsknightsoftheoldrepublic/starwarsknightsoftheoldrepublic([0-9]+)(\.html)?/?", "swknights/swkotor\\1.html", u))
        m = match_by_urls(o, x.replace("starwarsknightsoftheoldrepublicwar", "swkotorwar"), data, other_data, False)
    if not m and "%20" in o.url:
        m = match_by_urls(o, u.replace("%20", "-"), data, other_data, False)
    # if not m and o.template in ["SW", "Databank"] and o.url in DATABANK_OVERWRITE:
    #     m = match_by_urls(o, DATABANK_OVERWRITE[o.url], data, other_data, False)
    #     if not m:
    #         m = match_by_urls(o, "databank/" + DATABANK_OVERWRITE[o.url], data, other_data, False)
    if m:
        return m

    mx = None
    if o.original and "Homing Beacon" in o.original:
        mx = re.search("Homing Beacon #([0-9]+)", o.original)
    elif "/beacon" in o.url:
        mx = re.search("/beacon([0-9]+)\.html", o.url)
    if mx:
        for x in ["", "None"]:
            t = f"Web|HBCite|None|None|Homing Beacon (newsletter)|{mx.group(1)}|None|{x}"
            if t in data:
                return ItemId(o, data[t], False, False)
            elif t in other_data:
                return ItemId(o, other_data[t], False, True)
    return None


def match_by_urls(o: Item, u: str, data: dict, other_data: dict, replace_page: bool):
    m = match_by_url(o, u, data, replace_page)
    if not m:
        m = match_by_url(o, u, other_data, replace_page)
        if m:
            m.from_other_data = True
    return m


def match_by_url(o: Item, url: str, data: Dict[str, Item], replace_page: bool):
    check_sw = o.template == "SW" and url.startswith("video/")
    url = prep_url(url)
    merge = {"SW", "SWArchive", "Hyperspace"}
    valid = {"External", "Web"}
    partial_matches = []
    old_versions = []
    new_versions = []
    possible = []
    y = re.search("(archive(date|url)=.*?)(\|.*?)?}}", o.original)
    is_old = "oldversion=" in o.original
    if is_old and not y and "|oldversion=1" not in o.original:
        y = re.search("(oldversion=.*?)(\|.*?)?}}", o.original)
    ad = y.group(1) if y else None
    for k, d in data.items():
        x = do_urls_match(url, o.template, d, replace_page)
        if x == 2:
            if o.mode == "Toys" and o.card and d.card and o.card != d.card:
                possible.append(d)
            elif d.original and "oldversion=" in d.original and ad and ad in d.original:
                return ItemId(o, d, False, False)
            elif d.original and "oldversion=" in d.original and not ad:
                old_versions.append(d)
            elif old_versions and d.original and "oldversion=" not in d.original:
                new_versions.append(d)
            elif ad and is_old and ((o.mode == d.mode and o.mode != "Toys" and o.mode != "Cards") or (o.mode in valid and d.mode in valid)):
                possible.append(d)
            elif d.template == o.template and o.target == d.target and not ad:
                return ItemId(o, d, False, False)
            elif d.template == o.template:
                partial_matches.append(d)
            elif {d.template, o.template}.issubset(merge) and not ad:
                return ItemId(o, d, False, False)
            elif d.mode == "YT" and o.mode == "YT":
                return ItemId(o, d, False, False)

        elif x == 1:
            partial_matches.append(d)
        if check_sw and d.mode == "YT" and d.special and prep_url(d.special) == url:
            return ItemId(o, d, False, False)
    exact = []
    for x in old_versions:
        if o.text and x.text and o.text.replace("'", "") == x.text.replace("'", ""):
            exact.append(x)
    if len(exact) == 1:
        return ItemId(o, exact[0], ad is not None, False)
    elif ad and old_versions:
        return ItemId(o, old_versions[-1], True, False)
    elif new_versions:
        return ItemId(o, new_versions[-1], ad is not None, False)
    elif old_versions:
        return ItemId(o, old_versions[-1], ad is not None, False)
    elif possible:
        return ItemId(o, possible[-1], False, False)
    if partial_matches:
        return ItemId(o, partial_matches[0], False, False)
    return None
