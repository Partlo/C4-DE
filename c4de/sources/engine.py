import re
import traceback
from datetime import datetime
from typing import List, Dict

from pywikibot import Page, Category


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets"
]

IGNORE_TEMPLATES = ["BookCite", "=", ]


COLLAPSE = {
    "FindtheForce": "Find the Force",
    "CSWECite": "The Complete Star Wars Encyclopedia",
    "TFU": "The Force Unleashed (video game)",
    "TCWA": "Star Wars: Clone Wars Adventures (video game)",  # "[[Star Wars: Clone Wars Adventures (video game)|''Star Wars: Clone Wars Adventures'' video game]]",
    "GEAttr": "Star Wars: Galaxy's Edge",  #"[[Star Wars: Galaxy's Edge|''Star Wars'': Galaxy's Edge]] (template)",
    "GSAttr": "Star Wars: Galactic Starcruiser",  # "[[Star Wars: Galactic Starcruiser|''Star Wars'': Galactic Starcruiser]] (template)",
    "DatapadCite": "Star Wars: Datapad",  # "[[Star Wars: Datapad|''Star Wars'': Datapad]]"
}

REFERENCE_MAGAZINES = {
    "BuildFalconCite": ("Star Wars: Build the Millennium Falcon", ""),
    "BuildR2Cite": ("Star Wars: Build Your Own R2-D2", ""),
    "BuildXWingCite": ("Star Wars: Build Your Own X-Wing", ""),
    "BustCollectionCite": ("Star Wars Bust Collection", ""),
    "FFCite": ("The Official Star Wars Fact File", ""),
    "FFCite\|y=2013": ("The Official Star Wars Fact File Part", "2013"),
    "FFCite\|y=2014": ("The Official Star Wars Fact File Part", "2014"),
    "FigurineCite": ("Star Wars: The Official Figurine Collection", ""),
    "HelmetCollectionCite": ("Star Wars Helmet Collection", ""),
    "ShipsandVehiclesCite": ("Star Wars Starships & Vehicles", ""),
    "StarshipsVehiclesCite": ("Star Wars: The Official Starships & Vehicles Collection", "")
}

PARAN = {
    "SWMiniCite": ("Star Wars Miniatures", True),
    "SWPM": ("PocketModels", True)
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

TEMPLATES = {
    "AdventurerCite": "The Adventurer",
    "AdvUnCite": "Adventures Unlimited",
    "Avalonmag": "Avalon",
    "BanthaCite": "Bantha Tracks",
    "CasusBelliCite": "Casus Belli",
    "CollectorCite": "Star Wars Galaxy Collector",
    "CWACite": "Star Wars: Clone Wars Adventures Volume",
    "CWMCite": "Star Wars: The Clone Wars Magazine",
    "DragonCite": "Dragon Magazine",
    "InQuestCite": "InQuest Gamer",
    "GalaxyCite": "Star Wars Galaxy Magazine",
    "GameTradeCite": "Game Trade Magazine",
    "GamerCite": "Star Wars Gamer",
    "InsiderCite": "Star Wars Insider",
    "Journal": "Star Wars Adventure Journal",
    "StarWarsKidsCite": "Star Wars Kids (1997)",
    "StarWarsKidsCite|year=1997": "Star Wars Kids (1997)",
    "StarWarsKidsCite|year=1998": "Star Wars Kids (1998)",
    "StarWarsKidsCite|year=1999": "Star Wars Kids (1999)",
    "SWAdventuresCite": "Star Wars Adventures Magazine",
    "SWMCite": "Star Wars Magazine",
    "SWMUKCite": "Star Wars: The Official Magazine",
    "SWRACite": "Star Wars Rebels Animation",
    "SWResACite": "Star Wars Resistance Animation",
    "SWRMCite": "Star Wars Rebels Magazine",
    "TOMCite": "Star Wars - The Official Magazine",
    "TCWUKCite": "Star Wars Comic UK",
    "TCWUKCite|vol=4": "Star Wars Comic UK",
    "TCWUKCite|vol=6": "Star Wars: The Clone Wars Comic",
    "TCWUKCite|vol=7": "Star Wars Comic",
    "VoyagesCite": "Voyages SF"
}

SELF_CITE = ["torweb", "twitter", "sonycite", "hunters", "ilm", "ilmxlab", "ffgweb", "facebookcite", "ea", "disney",
             "darkhorse", "d23", "dpb", "cite web", "blog", "blogspot", "amgweb", "asmodee", "marvel", "lucasfilm",
             "swkids", "dhboards", "dailyswcite", "disneynow", "disneyplus", "endorexpress", "faraway", "gamespot",
             "holonetnews", "jcfcite", "lucasartscite", "mobygames", "swkids", "sonyforumscite", "suvudu", "wizardscite"]


def list_templates(site, cat, data, template_type, recurse=False):
    for p in Category(site, cat).articles(recurse=recurse):
        if "/" not in p.title() and p.title(with_ns=False).lower() not in data:
            data[p.title(with_ns=False).lower()] = template_type


def build_template_types(site):
    results = {"db": "DB", "databank": "DB", "swe": "DB"}

    list_templates(site, "Category:StarWars.com citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates", results, "Web")
    list_templates(site, "Category:Commercial and product listing internet citation templates", results, "Web")
    list_templates(site, "Category:Social media citation templates", results, "Web")

    list_templates(site, "Category:YouTube citation templates", results, "YT")
    list_templates(site, "Category:Card game citation templates", results, "Cards")
    list_templates(site, "Category:Miniature game citation templates", results, "Cards")
    list_templates(site, "Category:Toy citation templates", results, "Toys")

    return results


def convert_issue_to_template(s):
    m = re.search("(\[\[(.*?) ([0-9]+)(\|.*?)?\]\]'* ?{{C\|(.*?)\}\})", s)
    if m:
        for template, v in REFERENCE_MAGAZINES.items():
            if m.group(2) == v[0]:
                t = f"{{{{{template}|{m.group(3)}|{m.group(5)}}}}}"
                return s.replace(m.group(1), t.replace("\\|", "|"))
    return re.sub("<\!--.*?-->", "", s)


class Item:
    """
    :type date: str
    """
    def __init__(self, original: str, mode: str, is_app: bool, *, invalid=False, target: str = None, text: str = None,
                 parent: str = None, template: str = None, url: str = None, issue: str = None, subset: str=None,
                 card: str = None, special=None, collapsed=False, format_text: str = None, no_issue=False):
        self.is_appearance = is_app
        self.mode = mode
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
        self.old_version = self.original and "oldversion" in self.original
        self.index = None
        self.canon_index = None
        self.legends_index = None
        self.date = ''
        self.canon = None
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
        self.from_other_data = from_other_data
        self.wrong_continuity = wrong_continuity
        self.by_parent = by_parent

        self.replace_references = master.original and "]]'' ([[" not in master.original

    def sort_text(self):
        return (self.current.text if self.current.mode == "DB" else self.current.original).replace("''", "")\
            .replace('"', '').replace("|", " |").replace("}}", " }}").lower()


def extract_item(z: str, a: bool, page, types, master=False) -> Item:
    """ Extracts an Item object from the given source/appearance line, parsing out the target article and all other
    relevant information.

    :rtype: Item
    """
    z = z.replace("|1=", "|").replace("|s=y", "").replace("{{'s}}", "'s").replace("{{'}}", "'").replace("{{!}}", "|").replace("…", "&hellip;")
    z = re.sub("{{([A-z]+)\]\]", "{{\\1}}", re.sub("\|[a-z ]+=\|", "|", z)).replace(" ", " ").replace("<!-- Unknown -->", "")
    while re.search("\[\[([^\]\|\n]+)_", z):
        z = re.sub("\[\[([^\]\|\n]+)_", "[[\\1 ", z)

    s = re.sub("\|volume=([0-9])\|([0-9]+)\|", "|\\1.\\2|", z)
    s = re.sub("^(.*?\[\[.*?[^ ])#(.*?)(\|.*?\]\].*?)$", "\\1\\3", s).replace("|d=y", "").replace("Star Wars Ships and Vehicles", "Star Wars Starships & Vehicles")
    if s.count("{") == 2 and s.count("}") == 1:
        s += "}"
    if s.count("{{") > s.count("}}"):
        print(f"Cannot parse invalid line on {page.title()}: {s}")
        return Item(z, "General", a, invalid=True)
    elif s.count("{{") == 0 and s.count("[[") == 0:
        print(f"Cannot parse invalid line on {page.title()}: {s}")
        return Item(z, "General", a, invalid=True)

    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            x = re.search("\[\[(.*?)(\|(.*?))?$", s)
        else:
            x = re.search("\[\[(.*?)(\|(.*?))?\]+", s)
        return Item(z, "General", a, target=x.group(1), format_text=x.group(3))

    o = f"{s}"
    s = re.sub("(\]+'*?) \(.*?\)", "\\1", s)
    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            r = re.sub("^.*\[\[(.*?)(\|.*?)*?$", '\\1', s)
        else:
            r = re.sub("^.*\[\[(.*?)(\|.*?)?\]+.*$", '\\1', s)
        return Item(o if master else s, "General", a, target=r)

    for i, j in COLLAPSE.items():
        if "{{" + i + "|" in s or "{{" + i + "}}" in s:
            return Item(z, "General", a, target=COLLAPSE[i], template=i, collapsed=True)
    for i, (k, o) in REFERENCE_MAGAZINES.items():
        m = re.search("\{\{" + i + "\|([0-9]+)(\|(multiple=\[*?)?(.*?))?(\|(.*?))?(\|.*?)?}}", s)
        mode = types.get(i.split("\|")[0], "General")
        if m and ((o == "2014" and m.group(1) in ['1', '2', '3', '4', '5']) or (o and o != "2014")):
            return Item(z, mode, a, target=f"{k} {m.group(1)} ({o})", template=i.split("\|")[0], issue=m.group(1),
                        text=m.group(4) or m.group(6), collapsed=True)
        elif m:
            return Item(z, mode, a, target=f"{k} {m.group(1)}", template=i.split("\|")[0], issue=m.group(1),
                        text=m.group(4) or m.group(6), collapsed=True)

    m = re.search('{{([^\|\[\}\n]+)[\|\}]', s)
    template = m.group(1) if m else ''
    mode = types.get(template.lower(), "General")

    if template in IGNORE_TEMPLATES:
        return None

    # # # Template-specific logic
    # IDWAdventures annual= parameter
    if template.startswith("IDWAdventures") and "annual=" in s:
        m = re.search("\|annual=(.*?)\|(.*?\|)?story=(.*?)[\|\}]", s)
        return Item(z, mode, a, target=m.group(3), template=template, parent=f"Star Wars Adventures Annual {m.group(1)}")
    # HoloNet News
    elif template == "Hnn":
        m = re.search("\{\{Hnn\|([0-9]+)(\|(.*?)\|(.*?))?}", s)
        if m:
            return Item(z, mode, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(1)}", template="Hnn",
                        issue=m.group(1), url=m.group(3), text=m.group(4))
    elif template == "Holonet":
        m = re.search("\{\{Holonet\|((both|old)=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Holonet", url=m.group(3).replace("|", "/"),
                        text=m.group(5))
    elif template == "HBCite":
        m = re.search("\{\{HBCite\|([0-9]+)", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Homing Beacon (newsletter)", issue=m.group(1))
    # Blog template - first two parameters combined are the URL
    elif template == "Blog":
        m = re.search("{{[^\|\[\}\n]+\|(official=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, url=m.group(2).replace("|", "/"), text=m.group(2))
    elif template == "LEGOCite":
        m = re.search("{{LEGOCite\|(theme=)?(.*?)\|(num=)?(.*?)\|(name=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent=m.group(2), text=f"{m.group(4)} {m.group(6)}", special=m.group(4))
    # YouTube templates
    elif mode == "YT":
        m = re.search("{{[^\|\[\}\n]+\|((subdomain|parameter)=.*?\|)?(video=)?(?P<video>.*?)(&.*?)?\|(text=)?(?P<text>.*?)(\|.*?)?}}", s)
        if m:
            u = re.search("\|sw_url=(.*?)(\|.*?)?}}", s)
            i = re.search("\|int=(.*?)(\|.*?)?}}", s)
            return Item(z, mode, a, target=i.group(1) if i else None, template=template, url=m.group('video'), text=m.groupdict()['text'],
                        special=u.group(1) if u else None)
    elif template == "Databank":
        m = re.search("{{Databank\|(url=)?(.*?)\|(title=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, url=m.group(2), text=m.group(4))
    elif mode == "DB" or template == "SWE":
        m = re.search("{{[^\|\[\}\n]+\|(.*?)\|(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, url=m.group(1) + "/" + m.group(2), text=m.group(3))
    elif template == "ForceCollection":
        m = re.search("{{[^\|\[\}\n]+\|(.*?)(\|star=([0-9S]))?(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Star Wars: Force Collection",
                        card=m.group(1), special=m.group(3))
        return Item(z, mode, a, target="Star Wars: Force Collection", template=template)
    elif mode == "Cards" or mode == "Toys" or "|card" in s:
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
                return Item(z, mode, a, target=None, template=template, parent="Star Wars: Card Trader", card=m.group(2), text=m.group(3))
        elif template == "FFGXW" and card_set == "Core Set":
            card_set = "Star Wars: X-Wing Miniatures Game Core Set"
        elif card_set and template == "SWPM":
            if card_set == "Base Set":
                card_set = "Star Wars PocketModel TCG: Base Set"
            elif card_set not in ["Clone Wars Conquest", "Clone Wars Tactics", "Scum & Villainy"]:
                card_set = f"{card_set} (PocketModels)"
        elif card_set and template == "SWMiniCite":
            if card_set not in ["Alliance and Empire", "Clone Strike", "The Dark Times", "Rebel Storm",
                                "Starship Battles", "Rebels and Imperials", "Battle of Hoth Scenario Pack",
                                "AT-AT Imperial Walker Colossal Pack"] and "Star Wars Miniatures" not in card_set:
                card_set = f"{card_set} (Star Wars Miniatures)"

        if card_set and "cardname=" in card_set:
            card = card_set.replace("cardname=", "")
            card_set = None
        else:
            m = re.search("{[^\|\[\}\n]+\|.*?(cardname|pack|card|scenario)=(?P<card>.*?)?[\|\}]", s)
            card = m.group(2) if m else None
        u = re.search("(url|link)=(.*?)[\|\}]", s)
        t = re.search("{[^\|\[\}\n]+\|.*?text=(?P<text>.*?)[\|\}]", s)
        ss = re.search("subset=(.*?)(\|.*?)?}}", s)
        subset = ss.group(1) if ss else None
        if not t:
            t = re.search("{[^\|\[\}\n]+\|.*?\|(?P<text>.*?)(\|.*?)?}}", s)
            if t and t.group('text') and re.search("^[a-z]+=", t.group('text')):
                t = None
        if card and "|scenario=" in s:
            return Item(z, mode, a, target=None, template=template, parent=card_set, special=card,
                        url=u.group(2) if u else None, text=t.group('text') if t else None)
        elif card:
            return Item(z, mode, a, target=None, template=template, parent=card_set, card=card, subset=subset,
                        url=u.group(2) if u else None, text=t.group('text') if t else None)
        elif card_set:
            return Item(z, mode, a, target=card_set, template=template, parent=None, subset=subset, text=t.group('text') if t else None)
        else:
            print(s)

    # InsiderCite - link= parameter
    m = re.search("{{[^\|\[\}\n]+\|link=(.*?)\|.*?\|(.*?)(\|(.*?))?}}", s)
    if m:
        return Item(z, mode, a, target=m.group(2), template=template, parent=m.group(1), issue=m.group(1), format_text=m.group(4))

    # HomeVideoCite
    m = re.search("\{+HomeVideoCite.*?\|(set=)?(.*?)(\|.*?)?(episode|featurette|scene)=\[*?(.*?)\]*?(\|.*?)?\}+", s)
    if m:
        target = m.group(5) if "featurette=" in s and "nolink=1" not in s else None
        return Item(z, mode, a, target=target, template=template, parent=m.group(2), issue=m.group(5), collapsed=True)

    # Miniatures, toys or cards with set= parameter
    m = re.search("\{\{[^\|\[\}\n]+\|(.*?\|)?set=(?P<set>.*?)\|(.*?\|)?((scenario|pack)=(?P<scenario>.*?)\|?)?(.*?)}}", s)
    if m:
        return Item(z, mode, a, target=m.group('set'), template=template, text=m.group('scenario'))

    # Magazine articles with issue as second parameter
    m = re.search("{{[^\|\[\}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(issue[0-9]?=)?(?P<issue>(Special Edition |Souvenir Special)?H?S? ?[0-9\.]*)(\|issue[0-9]=.*?)?\|(story=|article=)?(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?(\|.*?)?}}", s.replace("&#61;", "="))
    if m:
        if m.group('year'):
            p = TEMPLATES.get(f"{template}|{m.group('year')}")
        elif m.group('vol'):
            p = TEMPLATES.get(f"{template}|{m.group('vol')}")
        else:
            p = TEMPLATES.get(template)
        p = p or template.replace('Cite', '')
        parent = f"{p} {m.group('issue')}" if p and m.group('issue') else None
        return Item(z, mode, a, target=m.group('article'), template=template, issue=m.group('issue'),
                    special=m.group('year') or m.group('vol'), format_text=m.group('text'),
                    no_issue=m.group('issue') is None, parent=parent)

    # Second parameter is formatted version of the target article
    m = re.search("\{\{[^\|\]\n]+\|([^\|\n=\}\]]+)\|([^\|\n=\}\]]+)\}\}", s)
    if m:
        if template == "Microfighters" or m.group(1).startswith("Star Wars: Visions Filmmaker Focus"):
            return Item(z, mode, a, target=m.group(1), template=template, text=m.group(2))
        simple = re.sub("''", "", m.group(2))
        if m.group(1) == simple or m.group(1).startswith(f"{simple} (") or m.group(1).endswith(simple):
            return Item(z, mode, a, target=m.group(1), template=template)

    # Template-based use cases: collapse down to single value, or convert to identifiable target
    m = re.search("\{\{[^\|\]\n]+\|(\[\[.*?\|)?([^\|\n\}\]]+)\]*?\}\}", s)
    if m:
        i = m.group(2).strip()
        if template == "SWG" and i == "An Empire Divided":
            return Item(z, mode, a, target="Star Wars Galaxies: An Empire Divided", template="SWG")
        elif template and template in PREFIXES:
            return Item(z, mode, a, target=f"{PREFIXES[template]} {i}", template=template)
        elif template == "Film" and i in FILMS:
            return Item(z, mode, a, target=FILMS[i], template="Film")
        elif template == "KOTORbackups" and i in KOTOR:
            return Item(z, mode, a, target=KOTOR[i], template="KOTORbackups")
        elif template and i:
            return Item(z, mode, a, target=i, template=template)

    m = re.search("{{(?P<template>.*?)\|(.*?\|)?series=(?P<series>.*?)\|(.*?\|)?issue1=(?P<issue>[0-9]+)\|(.*?\|)?(adventure|story)=(?P<story>.*?)(\|.*?)?}", s)
    if not m:
        m = re.search("{{(?P<template>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)\|(.*?\|)?issue1=(?P<issue>[0-9]+)\|(.*?\|)?series=(?P<series>.*?)(\|.*?)?}", s)
    if m:
        return Item(z, mode, a, target=m.group('story'), template=template, parent=f"{m.group('series')} {m.group('issue')}")

    # Extract book & adventure or story
    m = re.search("{{(?P<template>.*?)\|(.*?\|)?book[0-9]?=(?P<book>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)(\|.*?)?}", s)
    if not m:
        m = re.search("{{(?P<template>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)\|(.*?\|)?book[0-9]?=(?P<book>.*?)(\|.*?)?}", s)
    if m:
        return Item(z, mode, a, target=m.group('story'), template=template, parent=m.group('book'))

    # Web article with int= parameter
    m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?url=(?P<url>.*?)\|.*?(text=(?P<t1>.*?)\|)?(.*?\|)?int=(?P<int>.*?)(\|.*?text=(?P<t2>.*?))?(\|.*?)?}}", s)
    if m:
        text = m.group('t1') or m.group('t2')
        return Item(z, mode, a, target=m.group('int'), template=template, url=m.group('url'), text=text)

    # Web articles without int= parameter
    m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(.*?\|)?text=(?P<text>.*?)(\|.*?)?}}", s)
    if not m:
        m = re.search("{{[^\|\[\}\n]+\|(.*?\|)?text=(?P<text>.*?)\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)(\|.*?)?}}", s)
    if m:
        return Item(z, mode, a, target=None, template=template, url=m.group('url'), text=m.group('text'))

    # Web templates without named parameters
    if mode == "Web":
        m = re.search("{{[^\|\[\}\n]+\|(subdomain=.*?\|)?(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            y = re.search("\|int=(.*?)[\|\}]", s)
            return Item(z, mode, a, template=template, url=m.group(2), text=m.group(3), target=y.group(1) if y else None)

    m = re.search("['\"]*\[\[(.*?)(\|.*?)?\]\]['\"]* ?[-—] ?['\"]*\[\[(.*?) ?([0-9]*?)(\|.*?)?\]\]", s)
    if m and m.group(4):
        return Item(z, mode, a, target=m.group(1), template="", parent=m.group(3), issue=m.group(4))
    elif m:
        return Item(z, mode, a, target=m.group(3), template="", parent=m.group(1))

    # Second parameter is formatted version of the target article (retry)
    m = re.search("\{\{[^\|\]\n]+\|([A-Z][^\|\n=\}\]]+)\|([^\|\n=\}\]]+)\}\}", s)
    if m:
        return Item(z, mode, a, target=m.group(1), template=template)

    print(f"Unknown: {mode}, {template}, {z}")
    return None


PARANTHETICALS = {
    "TCW": ["episode"],
    "Journal": ["short story", "Adventure Journal", "article series"]
}


def follow_redirect(o: Item, site, log):
    try:
        if o.target:
            p = Page(site, o.target)
            if p.exists() and p.isRedirectPage():
                if log:
                    print(f"Followed redirect {o.target} to {p.getRedirectTarget().title()}")
                o.target = p.getRedirectTarget().title().split('#', 1)[0]
                return True
    except Exception as e:
        print(o.target, e)
    return False


def determine_id_for_item(o: Item, site, data: Dict[str, Item], by_target: Dict[str, List[Item]], other_data: Dict[str, Item],
                          other_targets: Dict[str, List[Item]], remap: dict, log: bool):
    """ :rtype: ItemId """

    followed_redirect = False
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
            if x.template == o.template and x.target and (x.target.startswith(set_name) or set_name in x.target):
                return ItemId(o, x, True, False)

    # Find a match by URL
    if o.url and 'starwars/article/dodcampaign' not in o.url:
        u = o.url.replace("/#!/about", "").lower()
        m = match_url(o, u, data, False)
        if not m:
            m = match_url(o, u, other_data, False)
        if not m and "indexp" in o.url:
            m = match_url(o, u, data, True)
        if not m and "index.html?page=" in o.url:
            m = match_url(o, u, data, True)
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

    if o.issue or o.no_issue:
        t = f"{o.mode}|None|{o.target}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed, False)
        elif o.parent and "Special Edition" in o.parent and by_target.get(o.parent):
            return ItemId(o, by_target[o.parent][0], True, False)
        x = match_issue_target(o, by_target, other_targets, True)
        if not x and o.target and not followed_redirect:
            if follow_redirect(o, site, True):
                followed_redirect = True
                x = match_issue_target(o, by_target, other_targets, False)
                if x:
                    print(o.target, x.current.original, x.master.original, x.use_original_text)
                else:
                    print(o.target, None)
        if x:
            return x

    if o.parent and o.target:
        x = match_parent_target(o, by_target, other_targets)
        if not x and o.target and not followed_redirect:
            if follow_redirect(o, site, True):
                followed_redirect = True
                x = match_parent_target(o, by_target, other_targets)
        if x:
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
    if not x and o.target and not followed_redirect:
        if follow_redirect(o, site, log):
            x = match_target(o, by_target, other_targets, log)
    return x


def find_matching_issue(items, issue):
    for t in items:
        if t.issue == issue:
            return t
    return items[0]


def match_issue_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], use_original):
    if o.target and by_target and o.target in by_target:
        # print(f"Finding {o.full_id()} by target: {o.target} --> {by_target[o.target][0]}")
        return ItemId(o, find_matching_issue(by_target[o.target], o.issue), use_original, False)
    elif o.target and "&hellip;" in o.target and by_target and o.target.replace("&hellip;", "...") in by_target:
        return ItemId(o, find_matching_issue(by_target[o.target.replace("&hellip;", "...")], o.issue), use_original, False)
    elif o.target and other_targets and o.target in other_targets:
        # print(f"Finding {o.full_id()} by target: {o.target} --> {other_targets[o.target][0]}")
        return ItemId(o, find_matching_issue(other_targets[o.target], o.issue), use_original, True)
    elif o.target and "&hellip;" in o.target and by_target and o.target.replace("&hellip;", "...") in other_targets:
        return ItemId(o, find_matching_issue(other_targets[o.target.replace("&hellip;", "...")], o.issue), use_original, False)
    return None


def match_parent_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]]):
    if by_target and o.target in by_target and len(by_target[o.target]) > 1:
        for t in by_target[o.target]:
            if t.parent == o.parent:
                return ItemId(o, t, False, False, True)
    elif other_targets and o.target in other_targets and len(other_targets[o.target]) > 1:
        for t in other_targets[o.target]:
            if t.parent == o.parent:
                return ItemId(o, t, False, False, True)
    return None


def match_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], log):
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
            for x in by_target[t]:
                if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''",
                                                                                                                ""):
                    return ItemId(o, x, o.collapsed, False)
            return ItemId(o, by_target[t][0], o.collapsed, False)
        elif other_targets and t in other_targets:
            # print(f"Other Target: {o.full_id()}")
            if len(other_targets[t]) == 1:
                return ItemId(o, other_targets[t][0], o.collapsed, True)
            if log:
                print(f"Multiple matches found for {t}")
            for x in other_targets[t]:
                if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''",
                                                                                                                ""):
                    return ItemId(o, x, o.collapsed, False)
            return ItemId(o, other_targets[t][0], o.collapsed, False)
    return None


def prep_url(url):
    u = url or ''
    if u.startswith("/"):
        u = u[1:]
    if u.endswith("/"):
        u = u[:-1]
    return u.lower()


def match_url(o: Item, url: str, data: Dict[str, Item], replace_page: bool):
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
        elif d_url and "index.html" in d_url and re.search("indexp[0-9]\.html", url):
            if replace_page and d_url == re.sub("indexp[0-9]+\.html", "index.html", url):
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


def load_appearances(site, log, canon_only=False, legends_only=False):
    data = []
    pages = ["Appearances/Legends", "Appearances/Canon", "Appearances/Extra"]
    if canon_only:
        pages = ["Appearances/Canon"]
    elif legends_only:
        pages = ["Appearances/Legends"]
    for sp in pages:
        i = 0
        p = Page(site, f"Wookieepedia:{sp}")
        for line in p.get().splitlines():
            if line and not line.startswith("=="):
                if "/Header}}" in line:
                    continue
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
                x = re.search("[\*#](?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (D: )?(?P<t>.*?)( {{C\|d: .*?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": sp, "date": x.group("d"), "item": x.group("t"),
                                 "canon": None if sp == "CardSets" else "Canon" in sp, "ref": x.group("r")})
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


class FullListData:
    def __init__(self, unique: Dict[str, Item], full: Dict[str, Item], target: Dict[str, List[Item]], parantheticals: set):
        self.unique = unique
        self.full = full
        self.target = target
        self.parantheticals = parantheticals


def load_remap(site) -> dict:
    p = Page(site, "Wookieepedia:Appearances/Remap")
    results = {}
    for line in p.get().splitlines():
        x = re.search("\[\[(.*?)(\|.*?)?\]\].*?\[\[(.*?)(\|.*?)?\]\]", line)
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
                x.canon = i.get('canon')
                x.date = i['date']
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
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            print(f"{e}: {i['item']}")
    print(f"{count} out of {len(sources)} unmatched: {count / len(sources) * 100}")
    return FullListData(unique_sources, full_sources, target_sources, set())


def load_full_appearances(site, types, log, canon_only=False, legends_only=False) -> FullListData:
    appearances = load_appearances(site, log, canon_only=canon_only, legends_only=legends_only)
    _, canon = parse_timeline(Page(site, "Timeline of canon media").get())
    _, legends = parse_timeline(Page(site, "Timeline of Legends media").get())
    count = 0
    unique_appearances = {}
    full_appearances = {}
    target_appearances = {}
    parantheticals = set()
    for i in appearances:
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
            x = extract_item(i['item'], True, i['page'], types, master=True)
            if x:
                x.canon = None if i.get('extra') else i.get('canon')
                x.date = i['date']
                x.extra = c
                x.unlicensed = unlicensed
                x.non_canon = non_canon
                x.reprint = reprint
                x.abridged = "abridged audiobook" in x.original and "unabridged" not in x.original
                full_appearances[x.full_id()] = x
                unique_appearances[x.unique_id()] = x
                if x.target:
                    if x.target in canon:
                        x.canon_index = canon[x.target]
                    elif x.target.replace(" (audiobook)", "") in canon:
                        x.canon_index = canon[x.target.replace(" (audiobook)", "")] + 0.1
                    elif x.target.replace("(audiobook)", "(novel)") in canon:
                        x.canon_index = canon[x.target.replace("(audiobook)", "(novel)")] + 0.1
                    elif x.target.replace("(script)", "(novel)") in canon:
                        x.canon_index = canon[x.target.replace("(script)", "(novel)")] + 0.1

                    if x.target in legends:
                        x.legends_index = legends[x.target]
                    elif x.target.replace(" (audiobook)", "") in legends:
                        x.legends_index = legends[x.target.replace(" (audiobook)", "")] + 0.1
                    elif x.target.replace("(audiobook)", "(novel)") in legends:
                        x.legends_index = legends[x.target.replace("(audiobook)", "(novel)")] + 0.1
                    elif x.target.replace("(script)", "(novel)") in legends:
                        x.legends_index = legends[x.target.replace("(script)", "(novel)")] + 0.1

                    if x.target.endswith(")"):
                        parantheticals.add(x.target.rsplit(" (", 1)[0])
                    if x.parent and x.parent.endswith(")"):
                        parantheticals.add(x.parent.rsplit(" (", 1)[0])

                    if x.target not in target_appearances:
                        target_appearances[x.target] = []
                    target_appearances[x.target].append(x)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            traceback.print_exc()
            print(f"{type(e)}: {e}: {i['item']}")
    print(f"{count} out of {len(appearances)} unmatched: {count / len(appearances) * 100}")
    return FullListData(unique_appearances, full_appearances, target_appearances, parantheticals)


def parse_timeline(text):
    results = []
    unique = {}
    index = 0
    repl = True
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text)
    for line in text.splitlines():
        if "==page.get() placement==" in line:
            break
        line = re.sub("<\!--.*?-->", "", line).strip()
        m = re.search(
            "^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\|)? ?[A-Z]+ ?\n?\|.*?\|+[\* ]*?(['\"]*\[\[(?P<target>.*?)(\|.*?)?\]\]['\"]*) ?†?$",
            line)
        if m:
            t = m.group('target').replace("&ndash;", '–').replace('&mdash;', '—').strip()
            results.append({"index": index, "target": t, "date": m.group("date")})
            if t not in unique:
                unique[t] = index
            index += 1

    return results, unique

# TODO: handle dupes between Legends/Canon
