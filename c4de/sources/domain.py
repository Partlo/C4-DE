from typing import List, Dict, Tuple
import re
import copy

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
    :type target: str
    """
    def __init__(self, original: str, mode: str, is_app: bool, *, invalid=False, target: str = None, text: str = None,
                 parent: str = None, template: str = None, url: str = None, issue: str = None, subset: str=None,
                 card: str = None, special=None, collapsed=False, format_text: str = None, no_issue=False,
                 full_url: str=None, check_both=False, date="", archivedate=""):
        self.master_page = None
        self.is_appearance = is_app
        self.tv = mode == "TV"
        self.mode = "General" if mode == "TV" else mode
        self.sort_mode = SORT_MODES.get(self.mode, 5)
        self.invalid = invalid
        self.original = self.strip(original)
        self.target = self.strip(target)
        if self.target:
            self.target = self.target.replace("&ndash;", '–').replace('&mdash;', '—')
        if self.target and self.target[0].islower():
            self.target = f"{self.target[0].upper()}{self.target[1:]}"
        self.text = self.strip(text)
        self.parent = self.strip(parent)
        self.issue = self.strip(issue)
        self.card = self.strip(card)
        self.template = self.strip(template)
        self.url = self.strip(url)
        self.special = self.strip(special)
        self.subset = self.strip(subset)
        self.collapsed = collapsed
        self.ff_data = {}

        if self.card:
            self.text = None

        self.format_text = format_text
        self.no_issue = no_issue
        self.old_version = self.original and ("oldversion" in self.original or "|old=true" in self.original)

        self.unknown = False
        self.from_extra = None
        self.canon = None
        self.non_canon = False
        self.both_continuities = False
        self.external = False
        self.unlicensed = False
        self.abridged = False
        self.audiobook = False
        self.german_ad = False
        self.reprint = False
        self.has_content = False
        self.collection_type = None
        self.expanded = False
        self.original_printing = None

        self.index = None
        self.canon_index = None
        self.legends_index = None
        self.timeline = None

        self.date = date
        self.override = None
        self.override_date = None
        self.original_date = None
        self.future = False
        self.archivedate = archivedate

        self.parenthetical = ''
        self.department = ''
        self.check_both = check_both
        self.self_cite = False
        self.followed_redirect = False
        self.original_target = None
        self.full_url = full_url
        self.alternate_url = None
        self.date_ref = None
        self.extra_date = None
        self.ab = ''
        self.repr = ''
        self.crp = False
        self.extra = ''
        self.bold = False
        self.master_text = ''

    def copy(self):
        return copy.copy(self)

    def timeline_index(self, canon):
        return self.canon_index if canon else self.legends_index

    def sort_index(self, canon):
        return ((self.canon_index if canon else self.legends_index) or self.index) or 100000

    def is_internal_mode(self):
        return self.mode == "Web" or self.mode == "YT" or self.mode == "Toys" or self.mode == "Cards"

    def __str__(self):
        return f"Item[{self.full_id()}]"

    def __repr__(self):
        return f"Item[{self.full_id()}]"

    @staticmethod
    def strip(s: str) -> str:
        return s.strip() if s is not None else None

    def has_date(self):
        return self.date is not None and (self.date.startswith("1") or self.date.startswith("2") or self.date == "Current" or self.date.startswith("Cancel"))

    def match_expected(self):
        return (not self.non_canon and not self.unlicensed and not self.from_extra and not self.reprint
                and self.has_date() and not self.future and "Jedi Temple Challenge" not in self.original and "{{JTC|" not in self.original)

    def full_id(self):
        x = self.unique_id()
        return x if self.canon is None else f"{self.canon}|{x}"

    def unique_id(self):
        s = ((self.card or '') + (self.special or '')) if (self.card or self.special) else None
        t = (self.format_text or self.text) if (self.target == "Database" or self.target == "Puzzle") else self.text
        x = f"i-{self.issue}" if "issue1" in self.original else self.issue
        i = f"{self.mode}|{self.template}|{self.target}|{self.url}|{self.parent}|{x}|{s}|{t or ''}"
        return f"{i}|True" if self.old_version else i

    def can_self_cite(self):
        if self.mode == "YT":
            return True
        elif self.template.lower() in SELF_CITE:
            return True
        elif self.template == "SW" and self.url.startswith("news/"):
            return True
        return self.self_cite


REF_MAGAZINE_ORDERING = {
    "BuildFalconCite": ["Starship Fact File", "Secrets of Spaceflight", "Guide to the Galaxy", "Build the Falcon"],
    "BuildR2Cite": ["Building the Galaxy", "Droid Directory", "Understanding Robotics", "Build R2-D2"],
    "BuildXWingCite": ["Creating a Starship Fleet", "Starfighter Aces", "Rocket Science", "Build the X-Wing"],
    "BustCollectionCite": ["Star Wars Universe", "Behind the Cameras"],
    "FalconCite": ["Starship Fact File", "Secrets of Spaceflight", "Guide to the Galaxy", "Build the Falcon"],
    "HelmetCollectionCite": ["Databank A-Z", "Helmets", "Weapons & Uniforms", "Highlights of the Saga"],
    "ShipsandVehiclesCite": ["History of the Ship", "Pilots and Crew Members", "Starships and Vehicles"],
}


class ItemId:
    def __init__(self, current: Item, master: Item, use_original_text: bool,
                 from_other_data=False, wrong_continuity=False, by_parent=False, ref_magazine=False):
        self.current = current
        self.master = master
        self.use_original_text = use_original_text or current.old_version
        if " edition" in self.current.original:
            if re.search("''Star Wars: (Complete Locations|The Complete Visual Dictionary|Complete Vehicles)'', [0-9]+ edition", self.current.original):
                self.use_original_text = True
        self.from_other_data = from_other_data
        self.wrong_continuity = wrong_continuity
        self.by_parent = by_parent
        self.ref_magazine = ref_magazine

        self.replace_references = master.original and "]]'' ([[" not in master.original

    def sort_date(self):
        if self.current.override_date:
            return self.current.override_date
        elif self.current.unknown and self.current.original_date:
            return self.current.original_date
        return self.master.date

    def sort_text(self):
        if self.ref_magazine or self.current.template in REF_MAGAZINE_ORDERING:
            z = REF_MAGAZINE_ORDERING.get(self.current.template) or []
            x = z.index(self.current.target) if self.current.target in z else 9
            return f"{self.current.index} {x} {self.current.original}"
        return (self.current.text if self.current.mode == "DB" else self.current.original).replace("''", "")\
            .replace('"', '').replace("|", " |").replace("}}", " }}").lower()


class AnalysisConfig:
    def __init__(self):
        pass


class FullListData:
    def __init__(self, unique: Dict[str, Item], full: Dict[str, Item], target: Dict[str, List[Item]],
                 parantheticals: set, both_continuities: set, reprints: Dict[str, List[Item]], no_canon_index: List[Item]=None, no_legends_index: List[Item]=None):
        self.unique = unique
        self.full = full
        self.target = target
        self.parantheticals = parantheticals
        self.reprints = reprints
        self.both_continuities = both_continuities
        self.no_canon_index = no_canon_index
        self.no_legends_index = no_legends_index


class PageComponents:
    def __init__(self, before, canon, non_canon, unlicensed, real, mode):
        self.before = before
        self.final = ""
        self.original = before
        self.canon = canon
        self.non_canon = non_canon
        self.unlicensed = unlicensed
        self.real = real
        self.app_mode = mode

        self.ncs = SectionComponents([], [], [], '')
        self.src = SectionComponents([], [], [], '')
        self.nca = SectionComponents([], [], [], '')
        self.apps = SectionComponents([], [], [], '')
        self.links = SectionComponents([], [], [], '')

    def get_navs(self):
        return [*self.apps.nav, *self.nca.nav, *self.src.nav, *self.ncs.nav, *self.links.nav]


class AnalysisResults:
    def __init__(self, apps: List[ItemId], nca: List[ItemId], src: List[ItemId], ncs: List[ItemId], canon: bool, abridged: list, mismatch: List[ItemId], disambig_links: list, reprints: Dict[str, List[Item]]):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.canon = canon
        self.abridged = abridged
        self.mismatch = mismatch
        self.disambig_links = disambig_links
        self.reprints = reprints


class SectionItemIds:
    def __init__(self, name, found: List[ItemId], wrong: List[ItemId], non_canon: List[ItemId],
                 cards: Dict[str, List[ItemId]], sets: Dict[str, str], links: List[Item], expanded):
        self.name = name
        self.found = found
        self.wrong = wrong
        self.non_canon = non_canon
        self.cards = cards
        self.sets = sets
        self.links = links
        self.is_appearances = name and "appearances" in name.lower()
        self.expanded = expanded
        self.mark_as_non_canon = ""

    def merge(self, other):
        """:type other: SectionItemIds """
        self.found += other.found
        other.found = []
        self.wrong += other.wrong
        other.wrong = []
        self.found += other.non_canon
        other.non_canon = []
        for k, v in other.cards.items():
            if k in self.cards:
                self.cards[k] += v
            else:
                self.cards[k] = v
        other.cards = {}
        for k, v in other.sets.items():
            if k not in self.sets:
                self.sets[k] = v
        other.sets = {}
        self.links += other.links
        other.links = []


class SectionComponents:
    def __init__(self, items: list[Item], pre: list[str], suf: list[str], after: str, nav=None):
        self.items = items
        self.preceding = pre
        self.trailing = suf
        self.after = after
        self.before = ""
        self.nav = nav or []

    def has_text(self):
        return self.preceding or self.trailing or self.after or self.before


class FinishedSection:
    def __init__(self, name, rows: int, text: str):
        self.name = name
        self.rows = rows
        self.text = text


class NewComponents:
    def __init__(self, apps: FinishedSection, nca: FinishedSection, src: FinishedSection, ncs: FinishedSection,
                 links: FinishedSection, navs: list):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.links = links
        self.navs = navs


class UnknownItems:
    def __init__(self, apps: list, src: list, final_items: list, links: list):
        self.apps = apps
        self.src = src
        self.final_items = final_items
        self.links = links

    def found(self):
        return len(self.apps) + len(self.src) + len(self.final_items) + len(self.links)