from typing import List, Dict, Tuple
import re

SELF_CITE = ["torweb", "twitter", "sonycite", "hunters", "ilm", "ilmxlab", "ffgweb", "facebookcite", "ea", "disney",
             "darkhorse", "d23", "dpb", "cite web", "blog", "blogspot", "amgweb", "asmodee", "marvel", "lucasfilm",
             "swkids", "dhboards", "dailyswcite", "disneynow", "disneyplus", "endorexpress", "faraway", "gamespot",
             "holonetnews", "jcfcite", "lucasartscite", "mobygames", "swkids", "sonyforumscite", "suvudu", "wizardscite"]


SORT_MODES = {
    "General": 0,
    "Web": 1,
    "YT": 1,
    "DB": 2,
    "Toys": 3,
    "Cards": 4,
}


class Item:
    """
    :type date: str
    """
    def __init__(self, original: str, mode: str, is_app: bool, *, invalid=False, target: str = None, text: str = None,
                 parent: str = None, template: str = None, url: str = None, issue: str = None, subset: str=None,
                 card: str = None, special=None, collapsed=False, format_text: str = None, no_issue=False, date=''):
        self.is_appearance = is_app
        self.mode = mode
        self.sort_mode = SORT_MODES.get(mode, 5)
        self.invalid = invalid
        self.original = self.strip(original)
        self.target = self.strip(target)
        self.text = self.strip(text)
        self.parent = self.strip(parent)
        self.issue = self.strip(issue)
        self.card = self.strip(card)
        self.template = self.strip(template)
        self.url = self.strip(url)
        self.special = self.strip(special)
        self.subset = self.strip(subset)
        self.collapsed = collapsed

        if self.card:
            self.text = None

        self.format_text = format_text
        self.no_issue = no_issue
        self.old_version = self.original and ("oldversion" in self.original or "|old=true" in self.original)
        self.index = None
        self.canon_index = None
        self.legends_index = None
        self.override = None
        self.override_date = None
        self.date = ''
        self.canon = None
        self.from_extra = None
        self.unlicensed = False
        self.abridged = False
        self.reprint = False
        self.department = ''
        self.non_canon = False
        self.alternate_url = None
        self.date_ref = None
        self.extra_date = None
        self.self_cite = False
        self.extra = ''

    def sort_index(self, canon):
        return (self.canon_index if canon else self.legends_index) or self.index

    def __str__(self):
        return f"Item[{self.full_id()}]"

    def __repr__(self):
        return f"Item[{self.full_id()}]"

    @staticmethod
    def strip(s: str) -> str:
        return s.strip() if s is not None else None

    def has_date(self):
        return self.date is not None and (self.date.startswith("1") or self.date.startswith("2") or self.date == "Current")

    def full_id(self):
        x = self.unique_id()
        return x if self.canon is None else f"{self.canon}|{x}"

    def unique_id(self):
        s = ((self.card or '') + (self.special or '')) if (self.card or self.special) else None
        i = f"{self.mode}|{self.template}|{self.target}|{self.url}|{self.parent}|{self.issue}|{s}|{self.text}"
        return f"{i}|True" if self.old_version else i

    def can_self_cite(self):
        if self.mode == "YT":
            return True
        elif self.template.lower() in SELF_CITE:
            return True
        elif self.template == "SW" and self.url.startswith("news/"):
            return True
        return self.self_cite


class ItemId:
    def __init__(self, current: Item, master: Item, use_original_text: bool,
                 from_other_data=False, wrong_continuity=False, by_parent=False):
        self.current = current
        self.master = master
        self.use_original_text = use_original_text or current.old_version
        if " edition" in self.current.original:
            if re.search("''Star Wars: (Complete Locations|The Complete Visual Dictionary)'', [0-9]+ edition", self.current.original):
                self.use_original_text = True
        self.from_other_data = from_other_data
        self.wrong_continuity = wrong_continuity
        self.by_parent = by_parent

        self.replace_references = master.original and "]]'' ([[" not in master.original

    def sort_date(self):
        return self.current.override_date if self.current.override_date else self.master.date

    def sort_text(self):
        return (self.current.text if self.current.mode == "DB" else self.current.original).replace("''", "")\
            .replace('"', '').replace("|", " |").replace("}}", " }}").lower()


class FullListData:
    def __init__(self, unique: Dict[str, Item], full: Dict[str, Item], target: Dict[str, List[Item]], parantheticals: set):
        self.unique = unique
        self.full = full
        self.target = target
        self.parantheticals = parantheticals


class PageComponents:
    def __init__(self, before):
        self.before = before
        self.final = ""
        self.original = before

        self.ncs = SectionComponents([], [], [], '')
        self.src = SectionComponents([], [], [], '')
        self.nca = SectionComponents([], [], [], '')
        self.apps = SectionComponents([], [], [], '')


class AnalysisResults:
    def __init__(self, apps: List[ItemId], nca: List[ItemId], src: List[ItemId], ncs: List[ItemId], canon: bool, abridged: list, mismatch: List[ItemId]):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.canon = canon
        self.abridged = abridged
        self.mismatch = mismatch


class SectionItemIds:
    def __init__(self, name, found: List[ItemId], wrong: List[ItemId], non_canon: List[ItemId],
                 cards: Dict[str, List[ItemId]], sets: Dict[str, str]):
        self.name = name
        self.found = found
        self.wrong = wrong
        self.non_canon = non_canon
        self.cards = cards
        self.sets = sets


class SectionComponents:
    def __init__(self, items: list[Item], pre: list[str], suf: list[str], after: str):
        self.items = items
        self.preceding = pre
        self.trailing = suf
        self.after = after


class FinishedSection:
    def __init__(self, name, rows: int, text: str):
        self.name = name
        self.rows = rows
        self.text = text
