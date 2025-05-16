from typing import List, Dict, Tuple
import re
import copy


SORT_MODES = {
    "General": 0,
    "Web": 1,
    "YT": 1,
    "DB": 2,
    "Toys": 3,
    "Cards": 4,
    "Minis": 4
}


class Item:
    """
    :type date: str
    :type target: str
    :type text: str
    """
    def __init__(self, original: str, mode: str, is_app: bool, *, invalid=False, target: str = None, text: str = None,
                 parent: str = None, template: str = None, url: str = None, issue: str = None, subset: str=None,
                 card: str = None, special=None, collapsed=False, format_text: str = None, no_issue=False, ref_magazine=False,
                 full_url: str=None, publisher_listing=False, check_both=False, date="", archivedate="",
                 alternate_url=None):
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
        self.ref_magazine = ref_magazine
        self.ff_data = {}

        if self.card:
            self.text = None

        self.format_text = format_text
        self.set_format_text = None
        self.no_issue = no_issue
        self.old_version = self.original and ("oldversion" in self.original or "|old=true" in self.original)

        self.is_exception = False
        self.unknown = False
        self.from_extra = None
        self.canon = None
        self.non_canon = False
        self.both_continuities = False
        self.external = False
        self.unlicensed = False
        self.abridged = False
        self.is_audiobook = False
        self.german_ad = False
        self.is_true_appearance = False
        self.reprint = False
        self.has_content = False
        self.publisher_listing = publisher_listing
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
        self.alternate_url = alternate_url
        self.date_ref = None
        self.extra_date = None
        self.ab = ''
        self.repr = ''
        self.crp = False
        self.extra = ''
        self.bold = False
        self.master_text = ''
        self.others = {}

    def copy(self):
        return copy.copy(self)

    def title_format_text(self):
        return self.set_format_text or self.format_text

    def timeline_index(self, canon):
        return self.canon_index if canon else self.legends_index

    def sort_index(self, canon):
        return ((self.canon_index if canon else self.legends_index) or self.index) or 100000

    def card_sort_text(self):
        if self.card and "#" in self.card:
            return re.sub("#([0-9])([):])", "#0\\1\\2", self.card.replace("''", "").replace('"', ''))
        elif self.card:
            return self.card.replace("''", "").replace('"', '')
        else:
            print(f"no card? {self.card}, {self.original}")
            return self.original.replace("''", "").replace('"', '')

    def is_internal_mode(self):
        return self.mode == "Web" or self.mode == "YT" or self.mode == "Toys" or self.mode == "Cards"

    def is_card_or_mini(self):
        return self.mode == "Cards" or self.mode == "Minis"

    def is_card_or_toy(self):
        return self.is_card_or_mini() or self.mode == "Toys"

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
        t = (t or '').lower()
        x = f"i-{self.issue}" if "issue1" in self.original else self.issue
        i = f"{self.mode}|{self.template}|{self.target}|{self.url}|{self.parent}|{x}|{s}|{t}"
        return f"{i}|True" if self.old_version else i

    def can_self_cite(self):
        return self.mode == "YT" or self.template == "Web" or self.self_cite

    def mark_as_publisher(self):
        self.mode = "Publisher"
        self.publisher_listing = True


REF_MAGAZINE_ORDERING = {
    "BuildFalconCite": ["Starship Fact File", "Secrets of Spaceflight", "Guide to the Galaxy", "Build the Falcon"],
    "BuildR2Cite": ["Building the Galaxy", "Droid Directory", "Understanding Robotics", "Build R2-D2"],
    "BuildXWingCite": ["Creating a Starship Fleet", "Starfighter Aces", "Rocket Science", "Build the X-Wing"],
    "BustCollectionCite": ["Character", "Star Wars Universe", "Behind the Cameras"],
    "DarthVaderCite": ["The Dark Side", "Planets (department)", "Villains of the Galaxy"],
    "FalconCite": ["Starship Fact File", "Secrets of Spaceflight", "Build the Falcon"],
    "HelmetCollectionCite": ["Databank A-Z", "Helmets", "Weapons & Uniforms", "Highlights of the Saga"],
    "ShipsandVehiclesCite": ["History of the Ship", "Pilots and Crew Members", "Starships and Vehicles"],
    "StarshipsVehiclesCite": ["Legendary Craft", "Action Stations", "Welcome On Board", "Starship & Vehicle Directory",
                              "In Command", "Droids, Aliens & Creatures", "In A Galaxy Far, Far Away",
                              "A Revolution In Film", "Movie Magic", "Did You Know?", "Star Wars A&ndash;Z",
                              "Star Wars Planet Index"]
}


class ItemId:
    def __init__(self, current: Item, master: Item, use_original_text: bool,
                 from_other_data=False, wrong_continuity=False, by_parent=False):
        self.current = current
        self.master = master
        self.use_original_text = use_original_text or current.old_version
        if " edition" in self.current.original:
            if re.search("''Star Wars: (Complete Locations|The Complete Visual Dictionary|Complete Vehicles)'', [0-9]+ edition", self.current.original):
                self.use_original_text = True
        self.from_other_data = from_other_data
        self.wrong_continuity = wrong_continuity
        self.by_parent = by_parent

        self.replace_references = master.original and "]]'' ([[" not in master.original
        if master.template == "Film" and "[[" in current.original and "]]" in current.original:
            if "|" not in current.original:
                self.replace_references = True
            else:
                z = current.original.split("|", 1)[-1].replace("]]", "").replace("''", "")
                if z.replace(":", "") == master.target.replace(":", ""):
                    self.replace_references = True

    def sort_date(self):
        if self.current.override_date:
            return self.current.override_date
        elif self.current.unknown and self.current.original_date:
            return self.current.original_date
        return self.master.date

    def sort_text(self):
        if self.current.template == "ForceCollection":
            return self.current.original

        if self.current.ref_magazine or self.current.template in REF_MAGAZINE_ORDERING:
            z = REF_MAGAZINE_ORDERING.get(self.current.template) or []
            x = z.index(self.current.target) if self.current.target in z else 9
            return f"{self.current.index} {x} {self.current.original}"
        return (self.current.text if self.current.mode == "DB" else self.current.original).replace("''", "")\
            .replace('"', '').replace("|", " |").replace("}}", " }}").lower().split(" (novel")[0]


class AnalysisConfig:
    def __init__(self):
        pass


class FullListData:
    def __init__(self, unique: Dict[str, Item], full: Dict[str, Item], target: Dict[str, List[Item]],
                 parantheticals: set, both_continuities: set, reprints: Dict[str, List[Item]], no_canon_index: List[Item]=None, no_legends_index: List[Item]=None):
        self.unique = unique
        self.full = full
        self.target = target
        self.parentheticals = parantheticals
        self.reprints = reprints
        self.both_continuities = both_continuities
        self.no_canon_index = no_canon_index
        self.no_legends_index = no_legends_index
        self.archive_data = {}


class PageComponents:
    """
    :type collections: SectionComponents
    :type sections: dict[str, SectionLeaf]
    :type links: SectionComponents
    """
    def __init__(self, original: str, canon: bool, non_canon: bool, unlicensed: bool, real: bool, mode, media, infobox,
                 original_infobox, flag: list, page_name):
        self.before = ""
        self.final = ""
        self.original = original
        self.canon = canon
        self.non_canon = non_canon
        self.unlicensed = unlicensed
        self.real = real
        self.app_mode = mode
        self.media = media
        self.infobox = infobox
        self.original_infobox = original_infobox
        self.flag = flag
        self.page_name = page_name

        self.ncs = SectionComponents([], [], [], '')
        self.src = SectionComponents([], [], [], '')
        self.nca = SectionComponents([], [], [], '')
        self.apps = SectionComponents([], [], [], '')
        self.links = SectionComponents([], [], [], '')

        self.collections = SectionComponents([], [], [], '')
        self.sections = {}
        self.nav_templates = []
        self.redirects_fixed = set()

    def get_navs(self):
        return [*self.nav_templates, *self.apps.nav, *self.nca.nav, *self.src.nav, *self.ncs.nav, *self.links.nav]


class AnalysisResults:
    def __init__(self, apps: List[ItemId], nca: List[ItemId], src: List[ItemId], ncs: List[ItemId], canon: bool, abridged: list, mismatch: List[ItemId], reprints: Dict[str, List[Item]]):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.canon = canon
        self.abridged = abridged
        self.mismatch = mismatch
        self.reprints = reprints


class SectionItemIds:
    def __init__(self, name, found: List[ItemId], wrong: List[ItemId], non_canon: List[ItemId],
                 group_items: Dict[str, List[ItemId]], group_ids: Dict[str, str], links: List[Item], expanded):
        self.name = name
        self.found = found
        self.wrong = wrong
        self.non_canon = non_canon
        self.group_items = group_items
        self.group_ids = group_ids
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
        for k, v in other.group_items.items():
            if k in self.group_items:
                self.group_items[k] += v
            else:
                self.group_items[k] = v
        other.group_items = {}
        for k, v in other.group_ids.items():
            if k not in self.group_ids:
                self.group_ids[k] = v
        other.group_ids = {}
        self.links += other.links
        other.links = []


class SectionLeaf:
    """
    :type lines: list[str]
    :type subsections: dict[str, SectionLeaf]
    :type other: list[SectionLeaf]
    """
    def __init__(self, name, header: str, num: int, level: int, lines=None, duplicate=False):
        self.name = name
        self.header_line = header
        self.num = num
        self.master_num = 100
        self.level = level
        self.lines = lines or []
        self.subsections = {}
        self.invalid = False
        self.remove = False
        self.flag = False
        self.duplicate = duplicate
        self.other = []

    def has_subsections(self, *terms):
        return any(s in self.subsections for s in terms)

    def is_empty_section(self):
        return len(self.lines) == 0 and not self.subsections

    def build_text(self, header=None, image=None, media_cat=None):
        header_line = header or self.name
        added_media_cat = False
        if "=" not in header_line:
            header_line = f"{'='*self.level}{header_line}{'='*self.level}"
        if self.flag:
            header_line = re.sub("(===?.*?)(===?)", "\\1 {{SectionFlag}}\\2", header_line)
        if not any(ln.strip() for ln in self.lines):
            return [header_line], added_media_cat

        lines = [header_line]
        if media_cat:
            lines.append(media_cat)
            added_media_cat = True
        if "cover gallery" in header_line.lower():
            lines += self.build_gallery(image)
        else:
            lines += self.lines
        lines.append("")
        return lines, added_media_cat

    def build_gallery(self, image=None):
        before, images, filenames, after = [], [], [], []
        gallery_start = False
        add_image = image is not None
        for ln in self.lines:
            if "<gallery" in ln:
                before.append(ln)
                gallery_start = True
            elif "file:" in ln.lower():
                fx = ln.split("|")[0].replace(" ", "_")
                if fx in filenames:
                    continue
                filenames.append(fx)
                images.append(ln)
                if image and image.lower() in ln.lower().replace(" ", "_"):
                    add_image = False
            elif gallery_start:
                after.append(ln)
            else:
                before.append(ln)
        if add_image:
            images.insert(0, f"{image}|Cover")
        return [*before, *images, *after]


class SectionComponents:
    """
    :type items: list[Item]
    """
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
                 links: FinishedSection, collections: FinishedSection, navs: list):
        self.apps = apps
        self.nca = nca
        self.src = src
        self.ncs = ncs
        self.links = links
        self.collections = collections
        self.navs = navs


class UnknownItems:
    def __init__(self, apps: list, src: list, final_items: list, links: list):
        self.apps = apps
        self.src = src
        self.final_items = final_items
        self.links = links

    def found(self):
        return len(self.apps) + len(self.src) + len(self.final_items) + len(self.links)