import re
from datetime import datetime
from typing import List, Dict

from pywikibot import Page


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets"
]


COLLAPSE = {
    "FindtheForce": "Find the Force",
    "CSWECite": "The Complete Star Wars Encyclopedia",
    "TFU": "The Force Unleashed (video game)",
    "TCWA": "Star Wars: Clone Wars Adventures (video game)",  # "[[Star Wars: Clone Wars Adventures (video game)|''Star Wars: Clone Wars Adventures'' video game]]",
    "GEAttr": "Star Wars: Galaxy's Edge",  #"[[Star Wars: Galaxy's Edge|''Star Wars'': Galaxy's Edge]] (template)",
    "GSAttr": "Star Wars: Galactic Starcruiser",  # "[[Star Wars: Galactic Starcruiser|''Star Wars'': Galactic Starcruiser]] (template)",
    "DatapadCite": "Star Wars: Datapad",  # "[[Star Wars: Datapad|''Star Wars'': Datapad]]"
}

ISSUES = {
    "BuildFalconCite": ("Star Wars: Build the Millennium Falcon", ""),
    "BuildR2Cite": ("Star Wars: Build Your Own R2-D2", ""),
    "BuildXWingCite": ("Star Wars: Build Your Own X-Wing", ""),
    "BustCollectionCite": ("Star Wars Bust Collection", ""),
    "FFCite": ("The Official Star Wars Fact File", ""),
    "FFCite\|y=2013": ("The Official Star Wars Fact File Part", "2013"),
    "FFCite\|y=2014": ("The Official Star Wars Fact File Part", "2014"),
    "HelmetCollectionCite": ("Star Wars Helmet Collection", ""),
    "ShipsandVehiclesCite": ("Star Wars Starships & Vehicles", ""),
    "StarshipsVehiclesCite": ("Star Wars: The Official Starships & Vehicles Collection", "")
}

PARAN = {
    "SWMiniCite": ("Star Wars Miniatures", True),
    "SWPM": ("PocketModels", False)
}

KOTOR = {
    "0": "The Taris Holofeed: Prime Edition",
    "13": "The Admiral's List: Jimas Veltraa Memorial Edition",
    "14": "The Adjudicator Special Report: The Outer Rim",
    "15": "The Taris Holofeed: Siege Edition",
    "16": "The Admiral's List: Remember Serroco! Edition",
    "17": "Adascorp Fiscal Period Financial Report and Outlook: Message from the Chief Executive",
    "18": "The Taris Holofeed: Invasion Edition",
    "19": "Adascorp Fiscal Period Financial Report and Outlook: Field Report: Project Black Harvest",
    "20": "The Adjudicator Special Report: Tools of the Trade",
    "21": "The Taris Holofeed Special Proclamation",
    "22": "The Admiral's List: Karath Home Safely",
    "23": "The Adjudicator Special Report: The Colonies",
    "24": "Galactic Republic Defense Ministry Daily Brief KD0092",
}

FILMS = {
    "I": "Star Wars: Episode I The Phantom Menace",
    "1": "Star Wars: Episode I The Phantom Menace",
    "II": "Star Wars: Episode II Attack of the Clones",
    "2": "Star Wars: Episode II Attack of the Clones",
    "III": "Star Wars: Episode III Revenge of the Sith",
    "3": "Star Wars: Episode III Revenge of the Sith",
    "IV": "Star Wars: Episode IV A New Hope",
    "4": "Star Wars: Episode IV A New Hope",
    "V": "Star Wars: Episode V The Empire Strikes Back",
    "5": "Star Wars: Episode V The Empire Strikes Back",
    "VI": "Star Wars: Episode VI Return of the Jedi",
    "6": "Star Wars: Episode VI Return of the Jedi",
    "VII": "Star Wars: Episode VII The Force Awakens",
    "7": "Star Wars: Episode VII The Force Awakens",
    "VIII": "Star Wars: Episode VIII The Last Jedi",
    "8": "Star Wars: Episode VIII The Last Jedi",
    "IX": "Star Wars: Episode IX The Rise of Skywalker",
    "9": "Star Wars: Episode IX The Rise of Skywalker"
}

PREFIXES = {
    "Jedi Temple Challenge": "Star Wars: Jedi Temple Challenge - Episode",
    "CW": "Clone Wars Chapter",
    "SWG": "Star Wars Galaxies:"
}

TOYS = ["disneytoycite", "gentlegiantcite", "galoob", "hasbrocite", "kennercite", "legocite", "sideshowcite",
        "kotocite", "tomycite", "bandaicite", "swminicite"]
CARDS = ["forcecollection", "armada", "ccg", "destiny", "ffgtcg", "ffgxw", "ffgxw2", "jktcg", "legion", "metallicimpressions", "sote",
         "soteemcc", "swct", "swgtcg", "swia", "swor", "swpm", "smith's", "tcg", "topps", "toptrumps", "yjccg", "swr", "swu"]
DB = ["db", "databank", "swe"]
VIDEO = ["youtube", "youtube", "swyoutube", "swkidsyoutube", "ilmvfxyoutube", "ilmxlabyoutube", "legoyoutube", "easwyoutube",
         "disneyplusyoutube", "disneyxdyoutube", "disneyyoutube", "starwarsshow", "thisweek", "toryoutube"]
WEB = ["torweb", "twitter", "sonycite", "swarchive", "sw", "holonet", "hunters", "ilm", "ilmxlab",
       "legowebcite", "ffgweb", "facebookcite", "ea", "disney", "darkhorse", "d23", "dpb", "cite web", "cn", "blog",
       "blogspot", "amgweb", "asmodee", "marvel", "lucasfilm", "swkids", "bficite", "cardcon", "celebration",
       "dhboards", "dailyswcite", "disneycompany", "disneynow", "disneyplus", "endorexpress", "faraway", "gamespot",
       "holonetnews", "imdb", "jcfcite", "kobo", "lccn", "lucasartscite", "mobygames", "swkids", "sonyforumscite",
       "spotify", "suvudu", "tvcom", "unbound", "wizardscite", "wookcite", "hbcite"]


def grouping_type(t):
    if t.lower() in TOYS:
        return "Toys"
    elif t.lower() in CARDS:
        return "Cards"
    elif t.lower() in DB:
        return "DB"
    elif t.lower() in WEB:
        return "Web"
    elif t.lower() in VIDEO:
        return "YT"
    return "General"


class Item:
    def __init__(self, original: str, is_app: bool, *, invalid=False, target: str = None, text: str = None,
                 parent: str = None, mode: str = None, template: str = None, url: str = None, issue: str = None,
                 card: str = None, special=None, collapsed=False):
        self.is_appearance = is_app
        self.mode = mode or grouping_type(template or '')
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
        self.collapsed = collapsed

        if self.card:
            self.text = None

        self.old_version = self.original and "oldversion" in self.original
        self.index = None
        self.date = None
        self.canon = None
        self.alternate_url = None
        self.extra = ''
        self.is_card_set = False

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


class ItemId:
    def __init__(self, current: Item, master: Item, use_original_text: bool,
                 from_other_data=False, wrong_continuity=False):
        self.current = current
        self.master = master
        self.use_original_text = use_original_text
        self.from_other_data = from_other_data
        self.wrong_continuity = wrong_continuity

    def sort_text(self):
        return (self.current.text if self.current.mode == "DB" else self.current.original).replace("''", "").replace('"', '').replace("|", " |").replace("}}", " }}").lower()


def extract_item(z: str, a: bool, page, master=False):
    """ Extracts an Item object from the given source/appearance line, parsing out the target article and all other
    relevant information.

    :rtype: Item
    """
    z = z.replace("|1=", "|").replace("|d=y", "").replace("|s=y", "").replace("{{'s}}", "'s").replace("{{'}}", "'").replace("{{!}}", "|")
    z = re.sub("{{([A-z]+)\]\]", "{{\\1}}", re.sub("\|[a-z ]+=\|", "|", z)).replace("|official=true|", "|").replace(" ", " ")
    while re.search("\[\[([^\]\|\n]+)_", z):
        z = re.sub("\[\[([^\]\|\n]+)_", "[[\\1 ", z)

    s = re.sub("^(.*?\[\[.*?[^ ])#(.*?)(\|.*?\]\].*?)$", "\\1\\3", z)
    if s.count("{") == 2 and s.count("}") == 1:
        s += "}"
    if s.count("{{") > s.count("}}"):
        print(f"Cannot parse invalid line on {page.title()}: {s}")
        return Item(z, a, invalid=True)
    elif s.count("{{") == 0 and s.count("[[") == 0:
        print(f"Cannot parse invalid line on {page.title()}: {s}")
        return Item(z, a, invalid=True)

    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            r = re.sub("^.*\[\[(.*?)(\|.*?)*?$", '\\1', s)
        else:
            r = re.sub("^.*\[\[(.*?)(\|.*?)?\]+.*$", '\\1', s)
        return Item(z, a, target=r, mode="General")

    o = f"{s}"
    s = re.sub("(\]+'*?) \(.*?\)", "\\1", s)
    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            r = re.sub("^.*\[\[(.*?)(\|.*?)*?$", '\\1', s)
        else:
            r = re.sub("^.*\[\[(.*?)(\|.*?)?\]+.*$", '\\1', s)
        return Item(o if master else s, a, target=r, mode="General")

    if "{{SWG}}" in s or "{{SWG|An Empire" in s:
        return Item(z, a, target="Star Wars Galaxies", template="SWG")
    for i, j in COLLAPSE.items():
        if "{{" + i + "|" in s or "{{" + i + "}}" in s:
            return Item(z, a, target=COLLAPSE[i], template=i, collapsed=True)
    for i, (k, o) in ISSUES.items():
        m = re.search("\{\{" + i + "\|([0-9]+)(\|(multiple=\[*?)?(.*?))?(\|(.*?))?(\|.*?)?}}", s)
        if m and ((o == "2014" and m.group(1) in ['1', '2', '3', '4', '5']) or (o and o != "2014")):
            return Item(z, a, target=f"{k} {m.group(1)} ({o})", template=i.split("\|")[0], issue=m.group(1), text=m.group(4) or m.group(6), collapsed=True)
        elif m:
            return Item(z, a, target=f"{k} {m.group(1)}", template=i.split("\|")[0], issue=m.group(1), text=m.group(4) or m.group(6), collapsed=True)

    m = re.search('{{([^\|\[\}\n]+)[\|\}]', s)
    template = m.group(1) if m else ''
    template_type = grouping_type(template)

    # # # Template-specific logic
    # IDWAdventures annual= parameter
    if template.startswith("IDWAdventures") and "annual=" in s:
        m = re.search("\|annual=(.*?)\|(.*?\|)?story=(.*?)[\|\}]", s)
        return Item(z, a, target=m.group(3), template=template, parent=f"Star Wars Adventures Annual {m.group(1)}")
    # HoloNet News
    elif template == "Hnn":
        m = re.search("\{\{Hnn\|([0-9]+)(\|(.*?)\|(.*?))?}", s)
        if m:
            return Item(z, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(1)}", template="Hnn",
                        issue=m.group(1), url=m.group(3), text=m.group(4))
    elif template == "Holonet":
        m = re.search("\{\{Holonet\|((both|old)=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, parent="Holonet", url=m.group(3).replace("|", "/"),
                        text=m.group(5))
    elif template == "HBCite":
        m = re.search("\{\{HBCite\|([0-9]+)", s)
        if m:
            return Item(z, a, target=None, template=template, parent="Homing Beacon (newsletter)", issue=m.group(1))
    # Blog template - first two parameters combined are the URL
    elif template == "Blog":
        m = re.search("{{[^\|\[\}\n]+\|(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, url=m.group(1).replace("|", "/"), text=m.group(2))
    elif template == "LEGOCite":
        m = re.search("{{LEGOCite\|(theme=)?(.*?)\|(num=)?(.*?)\|(name=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, parent=m.group(2), text=f"{m.group(4)} {m.group(6)}", special=m.group(4))
    # YouTube templates
    elif template_type == "YT":
        m = re.search("{{[^\|\[\}\n]+\|((subdomain|parameter)=.*?\|)?(video=)?(?P<video>.*?)(&.*?)?\|(text=)?(?P<text>.*?)(\|.*?)?}}", s)
        if m:
            u = re.search("\|sw_url=(.*?)(\|.*?)?}}", s)
            return Item(z, a, target=None, template=template, url=m.groupdict()['video'], text=m.groupdict()['text'],
                        special=u.group(1) if u else None)
    elif template == "Databank":
        m = re.search("{{Databank\|(url=)?(.*?)\|(title=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, url=m.group(2), text=m.group(4))
    elif template_type == "DB" or template == "SWE":
        m = re.search("{{[^\|\[\}\n]+\|(.*?)\|(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, url=m.group(1) + "/" + m.group(2), text=m.group(3))
    elif template == "ForceCollection":
        m = re.search("{{[^\|\[\}\n]+\|(.*?)(\|star=([0-9S]))?(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, parent="Star Wars: Force Collection", card=m.group(1),
                        special=m.group(3))
        return Item(z, a, target="Star Wars: Force Collection", template=template)
    elif template_type == "Cards" or template_type == "Toys" or "|card" in s:
        if "{{SOTEEMCC" in s:
            card_set = "Star Wars: Shadows of the Empire Embossed Metal Collector Cards"
        elif "{{SOTE" in s:
            card_set = "1996 Topps Star Wars: Shadows of the Empire"
        else:
            m = re.search("{[^\|\[\}\n]+\|(set=)?(?P<set>.*?)[\|\}]", s)
            card_set = m.group(2) if m else None
        if template == "SWCT":
            m = re.search("{+[^\|\[\}\n]+\|(set=)?(.*?)(\|.*?)?}}", s)
            if m:
                return Item(z, a, target=None, template=template, parent="Star Wars: Card Trader", card=m.group(2), text=m.group(3))
        elif template == "SWPM" and card_set == "Base Set":
            card_set = "Star Wars PocketModel TCG: Base Set"
        if card_set and PARAN.get(template) and PARAN[template][1]:
            card_set = f"{card_set} ({PARAN[template][0]})"
        if card_set and "cardname=" in card_set:
            card = card_set.replace("cardname=", "")
            card_set = None
        else:
            m = re.search("{[^\|\[\}\n]+\|.*?(cardname|pack|card|scenario)=(?P<card>.*?)?[\|\}]", s)
            card = m.group(2) if m else None
        u = re.search("(url|link)=(.*?)[\|\}]", s)
        t = re.search("{[^\|\[\}\n]+\|.*?text=(?P<text>.*?)[\|\}]", s)
        if not t:
            t = re.search("{[^\|\[\}\n]+\|.*?\|(?P<text>.*?)(\|.*?)?}}", s)
            if t and t.groupdict()['text'] and re.search("^[a-z]+=", t.groupdict()['text']):
                t = None
        if card and "|scenario=" in s:
            return Item(z, a, target=None, template=template, parent=card_set, special=card,
                        url=u.group(2) if u else None, text=t.groupdict()['text'] if t else None)
        elif card:
            return Item(z, a, target=None, template=template, parent=card_set, card=card,
                        url=u.group(2) if u else None, text=t.groupdict()['text'] if t else None)
        elif card_set:
            return Item(z, a, target=card_set, template=template, parent=None, text=t.groupdict()['text'] if t else None)
        else:
            print(s)

    # InsiderCite - link= parameter
    m = re.search("{{[^\|\[\}\n]+\|link=(.*?)\|.*?\|(.*?)(\|.*?)?}}", s)
    if m:
        return Item(z, a, target=m.group(2), template=template, issue=m.group(1))

    # Episode/Featurette parameter
    m = re.search("\{+[^\|\}\]]+?\|(set=)?(.*?)(\|.*?)?(episode|featurette)=\[*?(.*?)\]*?(\|.*?)?\}+", s)
    if m:
        return Item(z, a, target=None, template=template, parent=m.group(2), issue=m.group(5))

    # Miniatures, toys or cards with set= parameter
    m = re.search("\{\{[^\|\[\}\n]+\|(.*?\|)?set=(?P<set>.*?)\|(.*?\|)?(scenario=(?P<scenario>.*?)\|?)?(.*?)}}", s)
    if m:
        return Item(z, a, target=m.groupdict()['set'], template=template, text=m.groupdict()['scenario'])

    # Magazine articles with issue as second parameter
    m = re.search("{{[^\|\[\}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(issue[0-9]?=)?(?P<issue>(Special Edition )?H?S? ?[0-9\.]+)(\|issue[0-9]=.*?)?\|(story=)?(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?(\|.*?)?}}", s)
    if m:
        return Item(z, a, target=m.groupdict()['article'], template=template, issue=m.groupdict()['issue'],
                    special=m.group('year') or m.group('vol'))

    # Second parameter is formatted version of the target article
    m = re.search("\{\{[^\|\]\n]+\|([^\|\n=\}\]]+)\|([^\|\n=\}\]]+)\}\}", s)
    if m:
        if template == "Microfighters" or m.group(1).startswith("Star Wars: Visions Filmmaker Focus"):
            return Item(z, a, target=m.group(1), template=template, text=m.group(2))
        simple = re.sub("''", "", m.group(2))
        if m.group(1) == simple or m.group(1).startswith(f"{simple} (") or m.group(1).endswith(simple):
            return Item(z, a, target=m.group(1), template=template)

    # Template-based use cases: collapse down to single value, or convert to identifiable target
    m = re.search("\{\{[^\|\]\n]+\|(\[\[.*?\|)?([^\|\n\}\]]+)\]*?\}\}", s)
    if m:
        i = m.group(2).strip()
        if template == "SWG" and i == "An Empire Divided":
            return Item(z, a, target="Star Wars Galaxies: An Empire Divided", template="SWG")
        elif template and template in PREFIXES:
            return Item(z, a, target=f"{PREFIXES[template]} {i}", template=template)
        elif template == "Film" and i in FILMS:
            return Item(z, a, target=FILMS[i], template="Film")
        elif template == "KOTORbackups" and i in KOTOR:
            return Item(z, a, target=KOTOR[i], template="KOTORbackups")
        elif template and i:
            return Item(z, a, target=i, template=template)

    m = re.search("{{(?P<template>.*?)\|(.*?\|)?series=(?P<series>.*?)\|(.*?\|)?issue1=(?P<issue>[0-9]+)\|(.*?\|)?(adventure|story)=(?P<story>.*?)(\|.*?)?}", s)
    if not m:
        m = re.search("{{(?P<template>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)\|(.*?\|)?issue1=(?P<issue>[0-9]+)\|(.*?\|)?series=(?P<series>.*?)(\|.*?)?}", s)
    if m:
        return Item(z, a, target=m.groupdict()['story'], template=template, parent=f"{m.groupdict()['series']} {m.groupdict()['issue']}")

    # Extract book & adventure or story
    m = re.search("{{(?P<template>.*?)\|(.*?\|)?book[0-9]?=(?P<book>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)(\|.*?)?}", s)
    if not m:
        m = re.search("{{(?P<template>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)\|(.*?\|)?book[0-9]?=(?P<book>.*?)(\|.*?)?}", s)
    if m:
        return Item(z, a, target=m.groupdict()['story'], template=template, parent=m.groupdict()['book'])

    # Web article with int= parameter
    m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?url=(?P<url>.*?)\|(.*?\|)?(text=(?P<t1>.*?)\|)?(.*?\|)?int=(?P<int>.*?)(\|.*?)?(text=(?P<t2>.*?)\|)?(.*?\|)?}}", s)
    if m:
        text = m.groupdict()['t1'] or m.groupdict()['t2']
        return Item(z, a, target=m.groupdict()['int'], template=template, url=m.groupdict()['url'], text=text)

    # Web articles without int= parameter
    m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(.*?\|)?text=(?P<text>.*?)(\|.*?)?}}", s)
    if not m:
        m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?text=(?P<text>.*?)\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)(\|.*?)?}}", s)
    if m:
        return Item(z, a, target=None, template=template, url=m.groupdict()['url'], text=m.groupdict()['text'])

    # Web templates without named parameters
    if template_type == "Web":
        m = re.search("{{[^\|\[\}\n]+\|(subdomain=.*?\|)?(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, a, target=None, template=template, url=m.group(2), text=m.group(3))

    m = re.search("['\"]*\[\[(.*?)(\|.*?)?\]\]['\"]* ?[-—] ?['\"]*\[\[(.*?) ?([0-9]*?)(\|.*?)?\]\]", s)
    if m and m.group(4):
        return Item(z, a, target=m.group(1), template="", parent=m.group(3), issue=m.group(4))
    elif m:
        return Item(z, a, target=m.group(3), template="", parent=m.group(1))

    return None


PARANTHETICALS = {
    "TCW": ["episode"],
    "Journal": ["short story", "Adventure Journal", "article series"]
}


def determine_id_for_item(o: Item, data: Dict[str, Item], by_target: Dict[str, List[Item]], other_data: Dict[str, Item],
                          other_targets: Dict[str, List[Item]], remap: dict, log: bool):
    """ :rtype: ItemId """

    if o.unique_id() in data:
        return ItemId(o, data[o.unique_id()], False, False)
    elif "cargobay" in o.original:
        return ItemId(o, o, True, False)
    elif "HoloNet News" in o.original and re.search("\[https://web.archive.*?\.gif .*?\].*?\[\[Holonet News", o.original):
        x = ItemId(o, o, True, False)
        x.master.date = "2002-02-28"
        return x
    elif o.template == "InsiderCite" and (o.target == "The Last Page" or o.target == "From the Editor's Desk"):
        t = f"General|None|Star Wars Insider {o.issue}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], True, False)

    # Remapping common mistakes in naming
    if remap and o.target and o.target in remap:
        if remap[o.target] in by_target:
            return ItemId(o, by_target[remap[o.target]][0], False, False)
        if other_targets and remap[o.target] in other_targets:
            return ItemId(o, other_targets[remap[o.target]][0], False, False)

    # Template-specific matching
    if o.template == "SWCT" and o.card:
        matches = []
        for s, x in data.items():
            if x.template == "SWCT" and x.card and x.card in o.card:
                matches.append(x)
        if matches:
            x = sorted(matches, key=lambda a: len(a.card))[-1]
            return ItemId(o, x, True, False)
    elif o.template == "LEGOCite" and o.special:
        for s, x in data.items():
            if o.template == "LEGOCite" and x.special == o.special:
                return ItemId(o, x, False, False)

    if (o.mode == "Cards" or o.mode == "Toys") and (o.card or o.special):
        set_name = o.parent or o.target
        t = f"{o.mode}|{o.template}|{set_name}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], True, False)
        elif other_data and t in other_data:
            return ItemId(o, other_data[t], True, True)
        if o.template == "SWMiniCite":
            t = f"General|None|{set_name}|None|None|None|None|None"
            if t in data:
                return ItemId(o, data[t], True, False)
            elif other_data and t in other_data:
                return ItemId(o, other_data[t], True, True)

        for s, x in data.items():
            if x.template == o.template and x.is_card_set and x.target and (x.target.startswith(set_name) or set_name in x.target):
                return ItemId(o, x, True, False)

    # Find a match by URL
    if o.url:
        m = match_url(o, o.url.replace("/#!/about", "").lower(), data)
        if not m:
            m = match_url(o, o.url.replace("/#!/about", "").lower(), other_data)
        if m:
            return m

        mx = None
        if o.text and "Homing Beacon" in o.text:
            mx = re.search("Homing Beacon #([0-9]+)", o.text)
        elif "/beacon" in o.url:
            mx = re.search("/beacon([0-9]+)\.html", o.url)
        if mx:
            t = f"Web|HBCite|None|None|Homing Beacon (newsletter)|{mx.group(1)}|None|None"
            if t in data:
                return ItemId(o, data[t], False, False)
            elif t in other_data:
                return ItemId(o, other_data[t], False, True)

    # if Toy/Card isn't matched by the URL, then use the original
    if (o.mode == "Cards" or o.mode == "Toys") and (o.card or o.special):
        return ItemId(o, o, True, False)

    if o.issue:
        t = f"{o.mode}|None|{o.target}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed, False)
        elif other_data and t in other_data:
            return ItemId(o, other_data[t], o.collapsed, False)
        elif o.target and by_target and o.target in by_target:
            # print(f"Finding {o.full_id()} by target: {o.target} --> {by_target[o.target][0]}")
            return ItemId(o, by_target[o.target][0], True, False)
        elif o.target and "&hellip;" in o.target and by_target and o.target.replace("&hellip;", "...") in by_target:
            return ItemId(o, by_target[o.target.replace("&hellip;", "...")][0], True, False)
        elif o.target and other_targets and o.target in other_targets:
            # print(f"Finding {o.full_id()} by target: {o.target} --> {other_targets[o.target][0]}")
            return ItemId(o, other_targets[o.target][0], True, True)
        elif o.target and "&hellip;" in o.target and by_target and o.target.replace("&hellip;", "...") in other_targets:
            return ItemId(o, other_targets[o.target.replace("&hellip;", "...")][0], True, False)

    if o.parent and o.target:
        if by_target and o.target in by_target and len(by_target[o.target]) > 1:
            for t in by_target[o.target]:
                if t.parent == o.target:
                    return ItemId(o, t, False, False)
        elif other_targets and o.target in other_targets and len(other_targets[o.target]) > 1:
            for t in other_targets[o.target]:
                if t.parent == o.target:
                    return ItemId(o, t, False, False)

    if o.parent and "|story=" not in o.original and "|adventure=" not in o.original:
        # print(f"Parent: {o.full_id()}")
        t = f"{o.mode}|None|{o.parent}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed or o.card is not None, False)
        elif other_data and t in other_data:
            return ItemId(o, other_data[t], o.collapsed or o.card is not None, True)
        elif o.card:
            return ItemId(o, o, True, False)

    targets = []
    if o.target:
        targets.append(o.target.replace("_", " ").replace("Game Book ", ""))
        if "&hellip;" in o.target:
            targets.append(o.target.replace("&hellip;", "..."))
        if "(" not in o.target and o.template == "TCW":
            targets.append(f"{o.target} (episode)")

        m = re.search("^(Polyhedron|Challenge|Casus Belli|Valkyrie|Inphobia) ([0-9]+)$", o.target)
        if m:
            x = m.group(1).replace(" ", "") + "Cite"
            for dct in [by_target, other_targets or {}]:
                for t, d in dct.items():
                    for i in d:
                        if i.parent == o.target:
                            return ItemId(o, i, False, False)
                        elif i.template == x and i.issue == m.group(2):
                            return ItemId(o, i, False, False)
    if "|}}" in o.original:
        m = re.search("\{\{(Journal|GamerCite|InsiderCite)\|([0-9]+)\|}}", o.original)
        if m and m.group(1) == "Journal":
            targets.append(f"Star Wars Adventure Journal {m.group(2)}")
        elif m and m.group(2) == "GamerCite":
            targets.append(f"Star Wars Gamer {m.group(2)}")
        elif m and m.group(2) == "InsiderCite":
            targets.append(f"Star Wars Insider {m.group(2)}")

    for t in targets:
        if t in by_target:
            # print(f"Target: {o.full_id()}")
            if len(by_target[t]) == 1:
                return ItemId(o, by_target[t][0], o.collapsed, False)
            if log:
                print(f"Multiple matches found for {t}")
            return ItemId(o, by_target[t][0], o.collapsed, False)
        elif other_targets and t in other_targets:
            # print(f"Other Target: {o.full_id()}")
            if len(other_targets[t]) == 1:
                return ItemId(o, other_targets[t][0], o.collapsed, True)
            if log:
                print(f"Multiple matches found for {t}")
            return ItemId(o, other_targets[t][0], o.collapsed, False)

    return None


def prep_url(url):
    u = url or ''
    if u.startswith("/"):
        u = u[1:]
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def match_url(o: Item, url: str, data: Dict[str, Item]):
    check_sw = o.template == "SW" and url.startswith("video/")
    url = prep_url(url)
    for k, d in data.items():
        url_match = False
        d_url = prep_url(d.url)
        alternate_url = prep_url(d.alternate_url)
        if d_url and d_url == url:
            url_match = True
        elif alternate_url and alternate_url == url:
            url_match = True
        elif d_url and "&month=" in d_url and "&month=" in url and d_url.split("&month=", 1)[0] == url.split("&month=", 1)[0]:
            url_match = True
        elif d_url and "index.html" in d_url and re.match("indexp[0-9]\.html", url):
            if d_url == re.sub("indexp[0-9]+\.html", "index.html", url):
                url_match = True
            elif d_url == re.sub("indexp([0-9]+)\.html", "index.html?page=\\1", url):
                url_match = True
        elif d_url and o.template == "SW" and d.template == "SW" and url.startswith("tv-shows/") and \
                d_url.startswith("series") and d_url == url.replace("tv-shows/", "series/"):
            url_match = True
        elif d_url and "?page=" in url and d_url == url.split("?page=", 1)[0]:
            url_match = True
        elif o.template == "SonyCite" and d.template == "SonyCite" and url.startswith("en_US/players/"):
            if d_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("&resource=features", ""):
                url_match = True
            elif alternate_url and alternate_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("&resource=features", ""):
                url_match = True

        if url_match:
            if d.template == o.template:
                return ItemId(o, d, False, False)
            elif d.template == "SWArchive" and o.template == "SW":
                return ItemId(o, d, False, False)
            elif d.template == "SW" and o.template == "SWArchive":
                return ItemId(o, d, False, False)
            elif d.mode == "YT" and o.mode == "YT":
                return ItemId(o, d, False, False)
        if check_sw and d.mode == "YT" and d.special and prep_url(d.special) == url:
            return ItemId(o, d, False, False)


def load_appearances(site, log):
    data = []
    for sp in ["Appearances/Legends", "Appearances/Canon", "Appearances/Extra"]:
        i = 0
        p = Page(site, f"Wookieepedia:{sp}")
        for line in p.get().splitlines():
            if line and not line.startswith("=="):
                x = re.search("[\*#](.*?): (.*?)$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group(1), "item": x.group(2), "canon": "/Canon" in sp, "extra": "/Extra" in sp})
                else:
                    print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} appearances from Wookieepedia:{sp}")

    return data


def load_source_lists(site, log):
    data = []
    for sp in SUBPAGES:
        i = 0
        p = Page(site, f"Wookieepedia:Sources/{sp}")
        for line in p.get().splitlines():
            if line and not line.startswith("==") and not "/Header}}" in line:
                x = re.search("[\*#](.*?): (D: )?(.*?)( {{C\|d: .*?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group(1), "item": x.group(3), "canon": None if sp == "CardSets" else "Canon" in sp})
                else:
                    print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/{sp}")

    for y in range(1990, datetime.now().year + 1):
        i = 0
        p = Page(site, f"Wookieepedia:Sources/Web/{y}")
        if p.exists():
            for line in p.get().splitlines():
                if "/Header}}" in line:
                    continue
                x = re.search("\*(.*?): (.*?)( †)?( {{C\|alternate: (.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": f"Web/{y}", "date": x.group(1), "item": x.group(2), "alternate": x.group(5)})
                else:
                    print(f"Cannot parse line: {line}")
            if log:
                print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{y}")

    p = Page(site, f"Wookieepedia:Sources/Web/Current")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line:
            continue
        x = re.search("\*Current: (.*?)( †)?( {{C\|alternate: (.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Current", "date": "Current", "item": x.group(1), "alternate": x.group(4)})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Current")

    p = Page(site, f"Wookieepedia:Sources/Web/Unknown")
    i = 0
    for line in p.get().splitlines():
        if "/Header}}" in line:
            continue
        x = re.search("\*.*?:( [0-9:-]+)? (.*?)( †)?( {{C\|alternate: (.*?)}})?$", line)
        if x:
            i += 1
            data.append({"index": i, "page": "Web/Unknown", "date": "Unknown", "item": x.group(2), "alternate": x.group(5)})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/Unknown")

    db_pages = {"DB": "2011-09-13", "SWE": "2014-07-01", "Databank": "Current"}
    for template, date in db_pages.items():
        p = Page(site, f"Wookieepedia:Sources/Web/{template}")
        i = 0
        for line in p.get().splitlines():
            if "/Header}}" in line:
                continue
            if line.startswith("*{{"):
                x = line.strip()[1:]
                i += 1
                data.append({"index": 0, "page": f"Web/{template}", "date": date, "item": x})
            else:
                print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{template}")

    return data


class FullListData:
    def __init__(self, unique: Dict[str, Item], full: Dict[str, Item], target: Dict[str, List[Item]]):
        self.unique = unique
        self.full = full
        self.target = target


def load_remap(site) -> dict:
    p = Page(site, "Wookieepedia:Appearances/Remap")
    results = {}
    for line in p.get().splitlines():
        x = re.search("\[\[(.*?)(\|.*?)?\]\].*?\[\[(.*?)(\|.*?)?\]\]", line)
        if x:
            results[x.group(1)] = x.group(3)
    print(f"Loaded {len(results)} remap names")
    return results


def load_full_sources(site, log) -> FullListData:
    sources = load_source_lists(site, log)
    count = 0
    unique_sources = {}
    full_sources = {}
    target_sources = {}
    for i in sources:
        try:
            c = ''
            if "{{C|" in i['item']:
                cr = re.search("({{C\|([Rr]epublished|[Uu]nlicensed)}})", i['item'])
                if cr:
                    c = ' ' + cr.group(1)
                    i['item'] = i['item'].replace(cr.group(1), '').strip()
            x = extract_item(i['item'], False, i['page'], master=True)
            if x:
                if x.template == "SWCT" and not x.target:
                    x.target = x.card
                x.canon = i.get('canon')
                x.date = i['date']
                x.index = i['index']
                x.extra = c
                x.alternate_url = i.get('alternate')
                full_sources[x.full_id()] = x
                unique_sources[x.unique_id()] = x
                if x.target:
                    if x.target not in target_sources:
                        target_sources[x.target] = []
                    target_sources[x.target].append(x)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            print(f"{e}: {i['item']}")
    print(f"{count} out of {len(sources)} unmatched: {count / len(sources) * 100}")
    return FullListData(unique_sources, full_sources, target_sources)


def load_full_appearances(site, log) -> FullListData:
    appearances = load_appearances(site, log)
    count = 0
    unique_appearances = {}
    full_appearances = {}
    target_appearances = {}
    for i in appearances:
        try:
            c = ''
            if "{{C|" in i['item']:
                cr = re.search("({{C\|([Rr]epublished|[Uu]nlicensed)}})", i['item'])
                if cr:
                    c = ' ' + cr.group(1)
                    i['item'] = i['item'].replace(cr.group(1), '').strip()
            x = extract_item(i['item'], True, i['page'], master=True)
            if x:
                x.canon = i.get('canon')
                x.date = i['date']
                x.index = i['index']
                x.extra = c
                full_appearances[x.full_id()] = x
                unique_appearances[x.unique_id()] = x
                if x.target:
                    if x.target not in target_appearances:
                        target_appearances[x.target] = []
                    target_appearances[x.target].append(x)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            print(f"{e}: {i['item']}")
    print(f"{count} out of {len(appearances)} unmatched: {count / len(appearances) * 100}")
    return FullListData(unique_appearances, full_appearances, target_appearances)

# TODO: handle dupes between Legends/Canon
