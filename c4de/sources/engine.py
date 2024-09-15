import re
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from xmlrpc.client import Boolean

from pywikibot import Page, Category
from c4de.sources.domain import Item, ItemId, FullListData
from c4de.common import build_redirects, fix_redirects


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets", "Soundtracks"
]

IGNORE_TEMPLATES = ["BookCite", "=", "Subtitles", "PAGENAME"]


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
    "FalconCite": ("Star Wars: Millennium Falcon", ""),
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

EP1 = {
    "1": "Episode I Adventures 1: Search for the Lost Jedi",
    "2": "Episode I Adventures 2: The Bartokk Assassins",
    "3": "Episode I Adventures 3: The Fury of Darth Maul",
    "4": "Episode I Adventures 4: Jedi Emergency",
    "5": "Episode I Adventures 5: The Ghostling Children",
    "6": "Episode I Adventures 6: The Hunt for Anakin Skywalker",
    "7": "Episode I Adventures 7: Capture Arawynne",
    "8": "Episode I Adventures 8: Trouble on Tatooine",
    "9": "Episode I Adventures 9: Rescue in the Core",
    "10": "Episode I Adventures 10: Festival of Warriors",
    "11": "Episode I Adventures 11: Pirates from Beyond the Sea",
    "12": "Episode I Adventures 12: The Bongo Rally",
    "13": "Episode I Adventures 13: Danger on Naboo",
    "14": "Episode I Adventures 14: Podrace to Freedom",
    "15": "Episode I Adventures 15: The Final Battle"
}

SCH = {
    "1": "Star Wars Adventures 1: Hunt the Sun Runner",
    "2": "Star Wars Adventures 2: The Cavern of Screaming Skulls",
    "3": "Star Wars Adventures 3: The Hostage Princess",
    "4": "Star Wars Adventures 4: Jango Fett vs. the Razor Eaters",
    "5": "Star Wars Adventures 5: The Shape-Shifter Strikes",
    "6": "Star Wars Adventures 6: The Warlords of Balmorra",
    "7": "Star Wars Adventures 7: The Ghostling Children",
    "8": "Star Wars Adventures 8: The Hunt for Anakin Skywalker",
    "9": "Star Wars Adventures 9: Capture Arawynne",
    "10": "Star Wars Adventures 10: Trouble on Tatooine",
    "11": "Star Wars Adventures 11: Danger on Naboo",
    "12": "Star Wars Adventures 12: Podrace to Freedom",
    "13": "Star Wars Adventures 13: The Final Battle",
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
    "CW": "Clone Wars Chapter"
}

TEMPLATES = {
    "BanthaCite": "Bantha Tracks",
    "CWACite": "Star Wars: Clone Wars Adventures Volume",
    "InQuestCite": "InQuest Gamer",
    "StarWarsKidsCite": "Star Wars Kids (1997)",
    "StarWarsKidsCite|year=1997": "Star Wars Kids (1997)",
    "StarWarsKidsCite|year=1998": "Star Wars Kids (1998)",
    "StarWarsKidsCite|year=1999": "Star Wars Kids (1999)",
    "TCWUKCite|vol=4": "Star Wars Comic UK",
    "TCWUKCite|vol=6": "Star Wars: The Clone Wars Comic",
    "TCWUKCite|vol=7": "Star Wars Comic",
}


def list_templates(site, cat, data, template_type, recurse=False):
    for p in Category(site, cat).articles(recurse=recurse):
        if "/" not in p.title() and p.title(with_ns=False).lower() not in data:
            data[p.title(with_ns=False).lower()] = template_type


def build_template_types(site):
    results = {"db": "DB", "databank": "DB", "swe": "DB", "External": []}

    list_templates(site, "Category:StarWars.com citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates for use in External Links", results, "External", recurse=True)
    list_templates(site, "Category:Social media citation templates", results, "External")

    list_templates(site, "Category:YouTube citation templates", results, "YT")
    list_templates(site, "Category:Card game citation templates", results, "Cards")
    list_templates(site, "Category:Miniature game citation templates", results, "Cards")
    list_templates(site, "Category:Toy citation templates", results, "Toys")
    list_templates(site, "Category:TV citation templates", results, "TV")

    list_templates(site, "Category:Dating citation templates", results, "Dates")
    list_templates(site, "Category:Canon dating citation templates", results, "Dates", recurse=True)
    list_templates(site, "Category:Legends dating citation templates", results, "Dates", recurse=True)

    results["Magazine"] = {}
    for p in Category(site, "Category:Magazine citation templates").articles(recurse=True):
        txt = p.get()
        if "BaseCitation/Magazine" in txt:
            x = re.search("\|series=([A-z0-9:()\-&/ ]+)[|\n]", txt)
            if x:
                results["Magazine"][p.title(with_ns=False)] = x.group(1)
    results["Magazine"]["InsiderCite"] = "Star Wars Insider"

    return results


def convert_issue_to_template(s):
    m = re.search("(\[\[(.*?) ([0-9]+)(\|.*?)?]]'* ?{{C\|(.*?)}})", s)
    if m:
        for template, v in REFERENCE_MAGAZINES.items():
            if m.group(2) == v[0]:
                t = f"{{{{{template}|{m.group(3)}|{m.group(5)}}}}}"
                return s.replace(m.group(1), t.replace("\\|", "|"))
    return re.sub("<!--.*?-->", "", s)


def extract_item(z: str, a: bool, page, types, master=False) -> Optional[Item]:
    """ Extracts an Item object from the given source/appearance line, parsing out the target article and all other
    relevant information.

    :rtype: Item
    """
    z = z.replace("|1=", "|").replace("|s=y", "").replace("{{'s}}", "'s").replace("{{'}}", "'").replace("{{!}}", "|").replace("…", "&hellip;")
    if "SeriesListing" in z or "UnknownListing" in z:
        z = re.sub("\{\{(Series|Unknown)Listing.*?}} ?", "", z)
    z = re.sub("{{([A-z]+)]]", "{{\\1}}", re.sub("\|[a-z ]+=\|", "|", z)).replace(" ", " ")
    while re.search("\[\[([^]|\n]+)_", z):
        z = re.sub("\[\[([^]|\n]+)_", "[[\\1 ", z)
    while "  " in z:
        z = z.replace("  ", " ")

    s = re.sub("\|volume=([0-9])\|([0-9]+)\|", "|\\1.\\2|", z).replace("|}}", "}}")
    s = re.sub("<!--.*?-->", "", s).replace("|20211029101753", "").replace("-episode-guidea-friend-in-need", "episode-guide-a-friend-in-need")
    s = re.sub("^(.*?\[\[.*?[^ ])#(.*?)(\|.*?]].*?)$", "\\1\\3", s).replace("|d=y", "").replace("Star Wars Ships and Vehicles", "Star Wars Starships & Vehicles")
    s = re.sub(" ?\{\{Ab\|.*?}}", "", s)
    if s.count("{") == 2 and s.count("}") == 1:
        s += "}"
    if s.count("{{") > s.count("}}"):
        print(f"Cannot parse invalid line on {page}: {s}")
        return Item(z, "General", a, invalid=True)
    elif s.count("{{") == 0 and s.count("[[") == 0:
        print(f"Cannot parse invalid line on {page}: {s}")
        return Item(z, "General", a, invalid=True)

    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            x = re.search("\[\[(.*?)(\|(.*?))?$", s)
        else:
            x = re.search("\[\[(.*?)(\|(.*?))?]+", s)
        return Item(z, "General", a, target=x.group(1), format_text=x.group(3))
    if s.count("[") == 1 and s.count("]") == 1:
        x = re.search("\[https?://(.*?web\.archive.org/web/[0-9]+/)?(.*?\.[a-z]+/(.*?)) .*?]", s)
        if x:
            return Item(z, "External", a, url=x.group(3), full_url=x.group(2))

    m = re.search("[\"']*?\[\[(?P<p>.*?)(\|.*?)?]][\"']*? ?([A-z]*? ?in |,|-|–|—|&mdash;|&ndash;|:) ?['\"]*\[\[(?P<t>.*?)(\|.*?)?]]['\"]*?", s)
    if m:
        return Item(z, "General", a, target=m.groupdict()['t'], parent=m.groupdict()['p'], check_both=True)

    m = re.search("\[\[.*?]]'*?:.*?\[\[(.*?)(\|.*?)?]]", s)
    if m:
        return Item(z, "General", a, target=m.group(1))

    o = f"{s}"
    s = re.sub("(]+'*?) \(.*?\)", "\\1", s)
    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            r = re.sub("^.*\[\[(.*?)(\|.*?)*?$", '\\1', s)
        else:
            r = re.sub("^.*\[\[(.*?)(\|.*?)?]+.*$", '\\1', s)
        return Item(o if master else s, "General", a, target=r)

    for i, j in COLLAPSE.items():
        if "{{" + i + "|" in s or "{{" + i + "}}" in s:
            return Item(z, "General", a, target=COLLAPSE[i], template=i, collapsed=True)
    for i, (k, o) in REFERENCE_MAGAZINES.items():
        if i.split('\\', 1)[0].lower() in s.lower():
            m = re.search("\{\{" + i + "\|([0-9]+)(\|((multiple=)?.*?))?}}", s)
            mode = types.get(i.split("\|")[0], "General")
            if m and ((o == "2014" and m.group(1) in ['1', '2', '3', '4', '5']) or (o and o != "2014")):
                return Item(z, mode, a, target=f"{k} {m.group(1)} ({o})", template=i.split("\|")[0], issue=m.group(1),
                            text=m.group(2), collapsed=True)
            elif m:
                return Item(z, mode, a, target=f"{k} {m.group(1)}", template=i.split("\|")[0], issue=m.group(1),
                            text=m.group(2), collapsed=True)

    m = re.search('{{([^|\[}\n]+)[|}]', s)
    template = m.group(1) if m else ''
    mode = types.get(template.lower(), "General")

    if template in IGNORE_TEMPLATES or mode == "Dates":
        return None

    # # # Template-specific logic
    # IDWAdventures annual= parameter
    if template.startswith("IDWAdventures") and "annual=" in s:
        m = re.search("\|annual=(.*?)\|(.*?\|)?story=\[*?(.*?)[|}]", s)
        return Item(z, mode, a, target=m.group(3), template=template, parent=f"Star Wars Adventures Annual {m.group(1)}")
    # HoloNet News
    elif template == "Hnn":
        m = re.search("\{\{Hnn\|([0-9]+)(\|(.*?)\|(.*?))?}", s)
        if m:
            return Item(z, mode, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(1)}", template="Hnn",
                        issue=m.group(1), url=m.group(3), text=m.group(4))
    elif template == "HnnAd":
        m = re.search("\{\{HnnAd\|url=(.*?)\|issue=([0-9]+)\|text=.*?}}", s)
        if not m:
            m = re.search("\{\{HnnAd\|url=(.*?)\|text=.*?\|issue=([0-9]+)}}", s)
        if m:
            return Item(z, mode, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(1)}", template="HnnAd",
                        issue=m.group(2), url=m.group(1))
    elif template == "Holonet":
        m = re.search("\{\{Holonet\|((both|old)=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Holonet", url=m.group(3).replace("|", "/"),
                        text=m.group(5))
    elif template == "TCW" and "TCW|Destiny" in s:
        return Item(z, mode, a, target="Destiny (Star Wars: The Clone Wars)", template=template)
    elif template == "CelebrationTrailer":
        m = re.search("\{\{CelebrationTrailer\|['\[]*(?P<m>.*?)(\|.*?)?['\]]*\|(?P<c>.*?)}}", s)
        if m:
            return Item(z, mode, a, target=m.groupdict()['c'], issue=m.groupdict()['m'])
    elif template == "HBCite":
        m = re.search("\{\{HBCite\|([0-9]+)", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Homing Beacon (newsletter)", issue=m.group(1))
    elif template == "VisionsCite":
        m = re.search("\{\{VisionsCite\|(?P<f>focus=1\|)?(?P<e>.*?)(\|.*?)?}}", s)
        if not m:
            m = re.search("\{\{VisionsCite\|(?P<e>.*?)(\|.*?(?P<f>focus=1)?.*?)?}}", s)
        if m and m.group('f'):
            return Item(z, mode, a, target=f"Star Wars Visions: Filmmaker Focus#{m.group('e')}", template=template, issue=m.group('f'))
        elif m:
            return Item(z, mode, a, target=m.group('e'), template=template)
    # Blog template - first two parameters combined are the URL
    elif template == "Blog":
        m = re.search("{{[^|\[}\n]+\|(official=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, url=m.group(2).replace("|", "/"), text=m.group(2))
    elif template == "SWMB":
        return Item(z, "Toys", a, target="Star Wars Miniatures Battles", template=template, collapsed=True)
    elif template == "Sphero":
        return Item(z, "Toys", a, target="Star Wars Droids App by Sphero", template=template, collapsed=True, date="2017-08-31")
    elif template == "LEGOCite":
        m = re.search("{{LEGOCite\|(theme=)?(.*?)\|(num=)?(.*?)\|(name=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent=m.group(2), text=f"{m.group(4)} {m.group(6)}", special=m.group(4), card=m.group(6))
    # YouTube templates
    elif mode == "YT":
        m = re.search("{{[^|\[}\n]+\|((subdomain|parameter)=.*?\|)?(video=)?(?P<video>.*?)(&.*?)?\|(text=)?(?P<text>.*?)(\|.*?)?}}", s)
        if m:
            u = re.search("\|sw_url=(.*?)(\|.*?)?}}", s)
            i = re.search("\|int=(.*?)(\|.*?)?}}", s)
            return Item(z, mode, a, target=i.group(1) if i else None, template=template, url=m.group('video'), text=m.groupdict()['text'],
                        special=u.group(1) if u else None)
    elif template == "Databank":
        m = re.search("{{Databank\|(url=|entry=)?(.*?)\|(title=)?(.*?)(\|.*?)?}}", s)
        if m and m.group(1):
            return Item(z, mode, a, target=None, template=template, url=m.group(2), text=m.group(4))
        elif m:
            return Item(z, mode, a, target=None, template=template, url=f"databank/{m.group(2)}", text=m.group(4))
    elif mode == "DB" or template == "SWE":
        m = re.search("{{[^|\[}\n]+\|(.*?)\|(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, url=m.group(1) + "/" + m.group(2), text=m.group(3))
    elif template == "ForceCollection":
        m = re.search("{{[^|\[}\n]+\|(.*?)(\|star=([0-9S]))?(\|.*?)?}}", s)
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
            m = re.search("{[^|\[}\n]+\|(set=)?(?P<set>.*?)[|}]", s)
            card_set = m.group(2) if m else None
        if template == "SWCT":
            m = re.search("{+[^|\[}\n]+\|(set=)?(.*?)(\|.*?)?}}", s)
            if m:
                return Item(z, mode, a, target=None, template=template, parent="Star Wars: Card Trader", card=m.group(2), text=m.group(3))
        elif template == "FFGXW" and card_set == "Core Set":
            card_set = "Star Wars: X-Wing Miniatures Game Core Set"
        elif template == "Topps" and card_set == "Star Wars Topps Now" and "|stext=" in s:
            card_set = re.search("\|stext=(.*?)[|}].*?$", s).group(1).replace("''", "")
        elif card_set and template == "TopTrumps":
            card_set = f"Top Trumps: {card_set}"
        elif card_set and template == "SWU":
            if card_set == "Spark of Rebellion":
                card_set = f"{card_set} (Star Wars: Unlimited)"
        elif card_set and template == "SWPM":
            if card_set == "Base Set":
                card_set = "Star Wars PocketModel TCG: Base Set"
            elif card_set not in ["Clone Wars Conquest", "Clone Wars Tactics", "Scum & Villainy"] and "(PocketModels)" not in card_set:
                card_set = f"{card_set} (PocketModels)"
        elif card_set and template == "SWMiniCite":
            if card_set not in ["Alliance and Empire", "Clone Strike", "The Dark Times", "Rebel Storm", "Galaxy Tiles",
                                "Starship Battles", "Rebels and Imperials"] \
                    and not card_set.endswith("Pack") and "Star Wars Miniatures" not in card_set:
                card_set = f"{card_set} (Star Wars Miniatures)"

        if card_set and "cardname=" in card_set:
            card = card_set.replace("cardname=", "")
            card_set = None
        else:
            m = re.search("{[^|\[}\n]+\|.*?(cardname|pack|card|scenario)=(?P<card>.*?)?[|}]", s)
            card = m.group(2) if m else None
        u = re.search("(url|link)=(.*?)[|}]", s)
        t = re.search("{[^|\[}\n]+\|.*?text=(?P<text>.*?)[|}]", s)
        ss = re.search("subset=(.*?)(\|.*?)?}}", s)
        subset = ss.group(1) if ss else None

        if not t:
            t = re.search("{[^|\[}\n]+\|.*?\|(?P<text>.*?)(\|.*?)?}}", s)
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
    m = re.search("{{[^|\[}\n]+\|link=(.*?)\|.*?\|(.*?)(\|(.*?))?}}", s)
    if m:
        return Item(z, mode, a, target=m.group(2), template=template, parent=m.group(1), issue=m.group(1), format_text=m.group(4))

    # HomeVideoCite
    m = re.search("\{+HomeVideoCite.*?\|(set=)?(.*?)(\|.*?)?(episode|featurette|scene)=\[*?(.*?)]*?(\|.*?)?}+", s)
    if m:
        target = m.group(5) if "featurette=" in s and "nolink=1" not in s else None
        return Item(z, mode, a, target=target, template=template, parent=m.group(2), issue=m.group(5), collapsed=True)

    # Miniatures, toys or cards with set= parameter
    m = re.search("\{\{[^|\[}\n]+\|(.*?\|)?set=(?P<set>.*?)\|(.*?\|)?((scenario|pack)=(?P<scenario>.*?)\|?)?(.*?)}}", s)
    if m:
        return Item(z, mode, a, target=m.group('set'), template=template, text=m.group('scenario'))

    # Magazine articles with issue as second parameter
    m = re.search("{{[^|\[}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(issue[0-9]?=)?(?P<issue>(Special Edition |Souvenir Special|Premiere Issue)?H?S? ?[0-9.]*)(\|issue[0-9]=.*?)?\|(story=|article=)?\[*(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?]*(\|.*?)?}}", s.replace("&#61;", "="))
    if not m:
        m = re.search("{{[^|\[}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(story=|article=)?\[*(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?]*\|(issue[0-9]?=)?(?P<issue>(Special Edition |Souvenir Special|Premiere Issue)?H?S? ?[0-9.]*)(\|issue[0-9]=.*?)?(\|.*?)?}}", s.replace("&#61;", "="))
    if m and template != "StoryCite":
        if m.group('year'):
            p = TEMPLATES.get(f"{template}|{m.group('year')}")
        elif m.group('vol'):
            p = TEMPLATES.get(f"{template}|{m.group('vol')}")
        else:
            p = TEMPLATES.get(template)
        if m.group('issue'):
            if template == "InsiderCite" and m.group('issue').isnumeric() and int(m.group('issue')) <= 23:
                p = "The Lucasfilm Fan Club Magazine"
            elif template == "CalendarCite":
                p = f"Star Wars Day-at-a-Time Calendar 20{m.group('issue')}"
        if not p:
            p = types["Magazine"].get(template)
        p = p or template.replace('Cite', '')
        article = m.group('article')
        parent = f"{p} {m.group('issue')}" if p and m.group('issue') else None
        if parent == article and m.group('text'):
            article = f"{parent}#{m.group('text')}"
        format_text = m.group('text') or ''
        if "nolink=1" in format_text:
            format_text = ""
        return Item(z, mode, a, target=article, template=template, issue=m.group('issue'),
                    special=m.group('year') or m.group('vol'), format_text=format_text,
                    no_issue=m.group('issue') is None, parent=parent)

    # Second parameter is formatted version of the target article
    m = re.search("\{\{[^|\]\n]+\|([^|\n=}\]]+)\|([^|\n=}\]]+)}}", s)
    if m:
        if template == "Microfighters" or m.group(1).startswith("Star Wars: Visions Filmmaker Focus"):
            return Item(z, mode, a, target=m.group(1), template=template, text=m.group(2))
        simple = re.sub("''", "", m.group(2))
        if m.group(1) == simple or m.group(1).startswith(f"{simple} (") or m.group(1).endswith(simple):
            return Item(z, mode, a, target=m.group(1), template=template)

    # Template-based use cases: collapse down to single value, or convert to identifiable target
    m = re.search("\{\{[^|\]\n]+\|(\[\[.*?\|)?([^|\n}\]]+)]*?}}", s)
    if m:
        i = m.group(2).strip()
        if template and template in PREFIXES:
            return Item(z, mode, a, target=f"{PREFIXES[template]} {i}", template=template)
        elif template == "Film" and i in FILMS:
            return Item(z, mode, a, target=FILMS[i], template="Film")
        elif template == "KOTORbackups" and i in KOTOR:
            return Item(z, mode, a, target=KOTOR[i], template="KOTORbackups")
        elif template == "EpIAdv" and i in EP1:
            return Item(z, mode, a, target=EP1[i], template="EpIAdv")
        elif template == "SchAdv" and i in SCH:
            return Item(z, mode, a, target=SCH[i], template="SchAdv")
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
    if not m and "book=" in s:
        m = re.search("{{(?P<template>.*?)\|(.*?\|)?(adventure|story)=(?P<story>.*?)\|(.*?)?book[0-9]?=(?P<book>.*?)(\|.*?)?}", s)
    if m:
        return Item(z, mode, a, target=m.group('story'), template=template, parent=m.group('book'))

    # Web article with int= parameter
    m = re.search("{{[^|\[}\n]+\|(.*?\|)?url=(?P<url>.*?)\|.*?(text=(?P<t1>.*?)\|)?(.*?\|)?int=(?P<int>.*?)(\|.*?text=(?P<t2>.*?))?(\|.*?)?}}", s)
    if m:
        text = m.group('t1') or m.group('t2')
        return Item(z, mode, a, target=m.group('int'), template=template, url=m.group('url'), text=text)

    # Web articles without int= parameter
    m = re.search("{{[^|\[}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(.*?\|)?text=(?P<text>.*?)(\|.*?)?}}", s)
    if not m:
        m = re.search("{{[^|\[}\n]+\|(.*?\|)?text=(?P<text>.*?)\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)(\|.*?)?}}", s)
    if m:
        return Item(z, mode, a, target=None, template=template, url=m.group('url'), text=m.group('text'))

    # Web templates without named parameters
    if mode == "Web" or mode == "External":
        m = re.search("{{[^|\[}\n]+\|(subdomain=.*?\|)?(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            y = re.search("\|int=(.*?)[|}]", s)
            return Item(z, mode, a, template=template, url=m.group(2), text=m.group(3), target=y.group(1) if y else None)

    m = re.search("['\"]*\[\[(.*?)(\|.*?)?]]['\"]* ?[-—] ?['\"]*\[\[(.*?) ?([0-9]*?)(\|.*?)?]]", s)
    if m and m.group(4):
        return Item(z, mode, a, target=m.group(1), template="", parent=m.group(3), issue=m.group(4))
    elif m:
        return Item(z, mode, a, target=m.group(3), template="", parent=m.group(1))

    # Second parameter is formatted version of the target article (retry)
    m = re.search("\{\{[^|\]\n]+\|([A-Z][^|\n=}\]]+)\|([^|\n=}\]]+)}}", s)
    if m:
        return Item(z, mode, a, target=m.group(1), template=template)

    if template not in ["WP", "BookCite"] and not template.endswith("Wiki"):
        print(f"Unknown on {page}: {mode}, {template}, {z}")
    return None


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
                          other_targets: Dict[str, List[Item]], remap: dict, canon: bool, log: bool):
    """ :rtype: ItemId """

    followed_redirect = False
    if o.unique_id() in data:
        m = data[o.unique_id()]
        if m.template == "SWE" and not canon and not o.override:
            o.override_date = "2014-04-25"
        return ItemId(o, m, False, False)
    elif "cargobay" in o.original:
        return ItemId(o, o, True, False)
    elif "HoloNet News" in o.original and re.search("\[https://web.archive.*?\.gif .*?].*?\[\[Holonet News", o.original):
        x = ItemId(o, o, True, False)
        x.master.date = "2002-02-28"
        return x
    elif o.template == "InsiderCite" and (o.target == "The Last Page" or o.target == "From the Editor's Desk"):
        t = f"General|None|Star Wars Insider {o.issue}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], True, False)

    if o.mode == "External":
        if o.url:
            m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
            if m:
                return m
        return None

    if o.check_both:
        x, followed_redirect = match_parent_target(o, o.parent, o.target, by_target, other_targets, followed_redirect, site)
        if x:
            return x

        x, _ = match_parent_target(o, o.target, o.parent, by_target, other_targets, False, site)
        if x:
            return x

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
        alt = []
        for s, x in data.items():
            if x.template == "LEGOCite" and x.special == o.special:
                return ItemId(o, x, False, False)
            elif x.template == "LEGOCite" and x.card and o.card and \
                    (x.card.lower() == o.card.lower() or x.card.lower().replace('starfighter', 'fighter') == o.card.lower().replace('starfighter', 'fighter')):
                alt.append(x)
        if alt:
            return ItemId(o, alt[-1], False, False)

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

        if o.url:
            m = match_by_url(o, o.url, data, False)
            if m:
                return m

        set_match = None
        if set_name is not None:
            for s, x in data.items():
                if x.template == o.template:
                    if (x.target and (x.target.startswith(set_name) or set_name in x.target)) or \
                            (x.parent and (x.parent.startswith(set_name) or set_name in x.parent)):
                        if (x.card and x.card == o.card) or (x.text and x.text == o.text):
                            return ItemId(o, x, False, False)
                        elif not set_match:
                            set_match = x
        if set_match:
            return ItemId(o, set_match, True, False)

    # Find a match by URL
    if o.url and 'starwars/article/dodcampaign' not in o.url:
        m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
        if m:
            return m

    # if Toy/Card isn't matched by the URL, then use the original
    if (o.mode == "Cards" or o.mode == "Toys") and (o.card or o.special):
        return ItemId(o, o, True, False)

    if o.issue or o.no_issue:
        is_ref = o.template in REFERENCE_MAGAZINES
        t = f"{o.mode}|None|{o.target}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed, False, ref_magazine=is_ref)
        elif o.parent and "Special Edition" in o.parent and by_target.get(o.parent):
            return ItemId(o, by_target[o.parent][0], True, False, ref_magazine=is_ref)
        x = match_issue_target(o, by_target, other_targets, True, is_ref)
        if not x and o.target and not followed_redirect:
            if follow_redirect(o, site, True):
                followed_redirect = True
                x = match_issue_target(o, by_target, other_targets, False, is_ref)
        if x and x.master.issue != o.issue and o.parent in by_target:
            print(f"Found unrecognized {o.target} listing for {o.parent}")
            targets = by_target.get(o.target, [])
            numbers = [t for t in targets if t.issue and t.issue.isnumeric()]

            if len(targets) == 1:
                x = ItemId(o, targets[0], False, False, False, ref_magazine=is_ref)
            elif o.issue and o.issue.isnumeric() and len(numbers) == 1:
                x = ItemId(o, numbers[0], False, False, False, ref_magazine=is_ref)
            else:
                parent = by_target[o.parent][0]
                x = ItemId(o, parent, True, False, by_parent=True, ref_magazine=is_ref)
        if x:
            return x

    x, followed_redirect = match_parent_target(o, o.parent, o.target, by_target, other_targets, followed_redirect, site)
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


def match_issue_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], use_original, is_ref):
    if o.target and by_target and o.target in by_target:
        return ItemId(o, find_matching_issue(by_target[o.target], o.issue), use_original, False, ref_magazine=is_ref)
    elif o.target and other_targets and o.target in other_targets:
        return ItemId(o, find_matching_issue(other_targets[o.target], o.issue), use_original, False, ref_magazine=is_ref)

    match = match_target_issue_name(o, o.target, by_target, other_targets, use_original, is_ref)
    if not match and o.target and "&hellip;" in o.target and "dash;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&hellip;", "...").replace("&ndash;", '–').replace('&mdash;', '—'), by_target, other_targets, use_original, is_ref)
    if not match and o.target and "&hellip;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&hellip;", "..."), by_target, other_targets, use_original, is_ref)
    if not match and o.target and "dash;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&ndash;", '–').replace('&mdash;', '—'), by_target, other_targets, use_original, is_ref)
    if match:
        return match

    if o.target and o.parent and o.parent in by_target and o.target.startswith(f"{o.parent}#"):
        return ItemId(o, by_target[o.parent][0], True, False, ref_magazine=is_ref)
    elif o.target and o.parent and o.parent in other_targets and o.target.startswith(f"{o.parent}#"):
        return ItemId(o, other_targets[o.parent][0], True, False, ref_magazine=is_ref)
    return None


def match_target_issue_name(o, target, by_target, other_targets, use_original, is_ref):
    if target and by_target and target in by_target:
        return ItemId(o, find_matching_issue(by_target[o.target.replace("&hellip;", "...")], o.issue), use_original, False, ref_magazine=is_ref)
    elif target and other_targets and target in other_targets:
        return ItemId(o, find_matching_issue(other_targets[o.target.replace("&hellip;", "...")], o.issue), use_original, False, ref_magazine=is_ref)
    return None


def match_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], followed_redirect, site) -> Tuple[Optional[ItemId], Boolean]:
    if parent and target:
        x = match_by_parent_target(o, parent, target, by_target, other_targets)
        if not x and target and not followed_redirect:
            if follow_redirect(o, site, True):
                followed_redirect = True
                x = match_by_parent_target(o, parent, target, by_target, other_targets)
        if not x and o.template == "StoryCite" and "(short story)" not in o.target:
            x = match_by_parent_target(o, parent,f"{target} (short story)", by_target, other_targets)
        if x:
            return x, followed_redirect
    return None, followed_redirect


def match_by_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]]):
    if by_target and target in by_target and len(by_target[target]) > 1:
        for t in by_target[target]:
            if t.parent == parent:
                return ItemId(o, t, False, False, by_parent=True)
    elif other_targets and target in other_targets and len(other_targets[target]) > 1:
        for t in other_targets[target]:
            if t.parent == parent:
                return ItemId(o, t, False, True, by_parent=True)
    elif parent and "Star Wars Legends Epic Collection" in parent and o.template == "StoryCite":
        if by_target and target in by_target:
            return ItemId(o, by_target[target][0], True, False, by_parent=True)
        elif other_targets and target in other_targets:
            return ItemId(o, other_targets[target][0], True, True, by_parent=True)

    if target and target[0].upper() != target[0]:
        return match_by_parent_target(o, o.parent, target[0].capitalize() + target[1:], by_target, other_targets)
    return None


def match_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], log):
    targets = []
    if o.target:
        targets.append(o.target.replace("_", " ").replace("Game Book ", ""))
        if "&hellip;" in o.target:
            targets.append(o.target.replace("&hellip;", "..."))
        if "..." in o.target:
            targets.append(o.target.replace("...", "&hellip;"))
        if "(" not in o.target and o.tv:
            targets.append(f"{o.target} (episode)")
            targets.append(f"{o.target} (short film)")
        if "(" not in o.target and o.template == "EncyclopediaCite":
            targets.append(f"{o.target} (Star Wars Encyclopedia)")
        if "(" not in o.target and o.template == "StoryCite":
            targets.append(f"{o.target} (short story)")
        if "(" not in o.target and o.template == "CWACite":
            targets.append(f"{o.target} (comic)")
        if "(" not in o.target and o.template == "InsiderCite":
            targets.append(f"{o.target} (Star Wars Insider)")
            targets.append(f"{o.target} (article)")
        if "ikipedia:" in o.target:
            targets.append(o.target.split("ikipedia:", 1)[-1])
        if o.template in ["Tales", "TCWUKCite", "IDWAdventuresCite-2017"] and "(" not in o.target and o.target not in by_target:
            targets.append(f"{o.target} (comic)")

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
        m = re.search("\{\{([A-z_ ]+)\|([0-9]+)\|}}", o.original)
        if m and m.group(1) in TEMPLATES:
            targets.append(f"{TEMPLATES[m.group(1)]} {m.group(2)}")

    for t in targets:
        x = match_by_target(t, o, by_target, other_targets, log)
        if x:
            return x

    for par in ["episode", "TPB"]:
        if o.target and f"({par})" in o.target:
            x = match_by_target(o.target.replace(f" ({par})", ""), o, by_target, other_targets, log)
            if x:
                return x
    if o.format_text and o.parent and o.parent.startswith(o.format_text):
        x = match_by_target(o.format_text, o, by_target, other_targets, log)
        if x:
            log(f"Matched {o.original} --> {x.master.original} via format text {o.format_text}")
            return x

    return None


def match_by_target(t, o, by_target, other_targets, log):
    if t in by_target:
        if len(by_target[t]) == 1:
            return ItemId(o, by_target[t][0], o.collapsed, False)
        if log:
            print(f"Multiple matches found for {t}")
        for x in by_target[t]:
            if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''", ""):
                return ItemId(o, x, o.collapsed, False)
            elif x.url and o.url and do_urls_match(o.url, o.template, x, True, True):
                return ItemId(o, x, o.collapsed, False)
        return ItemId(o, by_target[t][0], o.collapsed, False)
    elif other_targets and t in other_targets:
        if len(other_targets[t]) == 1:
            return ItemId(o, other_targets[t][0], o.collapsed, True)
        if log:
            print(f"Multiple matches found for {t}")
        for x in other_targets[t]:
            if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''", ""):
                return ItemId(o, x, o.collapsed, False)
            elif x.url and o.url and do_urls_match(o.url, o.template, x, True, True):
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


def do_urls_match(url, template, d: Item, replace_page, log=False):
    d_url = prep_url(d.url)
    alternate_url = prep_url(d.alternate_url)
    if "youtube" in template.lower() and not alternate_url and d_url and d_url.startswith("-"):
        alternate_url = d_url[1:]
    if not alternate_url and template == "Hyperspace" and d_url.startswith("fans/"):
        alternate_url = d_url.replace("fans/", "")
    if d_url and d_url == url:
        return 2
    elif d_url and d_url.lower() == url.lower():
        return 2
    elif alternate_url and alternate_url == url:
        return 2
    elif alternate_url and alternate_url.lower() == url.lower():
        return 2
    elif d_url and "&month=" in d_url and "&month=" in url and d_url.split("&month=", 1)[0] == url.split("&month=", 1)[0]:
        return 2
    elif d_url and "index.html" in d_url and re.search("indexp[0-9]\.html", url):
        if replace_page and d_url == re.sub("indexp[0-9]+\.html", "index.html", url):
            return 2
        elif d_url == re.sub("indexp([0-9]+)\.html", "index.html?page=\\1", url):
            return 2
    elif d_url and ("index.html" in d_url or "index.html" in url) and url.split("/index.html", 1)[0] == d_url.split("/index.html", 1)[0]:
        return 1
    elif d_url and template == "SW" and d.template == "SW" and url.startswith("tv-shows/") and \
            d_url.startswith("series") and d_url == url.replace("tv-shows/", "series/"):
        return 2
    elif d_url and "?page=" in url and d_url == url.split("?page=", 1)[0]:
        return 2
    elif template == "SonyCite" and d.template == "SonyCite" and url.startswith("en_US/players/"):
        if d_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("&resource=features", ""):
            return 2
        elif alternate_url and alternate_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("&resource=features", ""):
            return 2
    return 0

DATABANK_OVERWRITE = {
    "Batcher": "batcher",
    "marrok": "marrok-inquisitor",
    "tarkin": "grand-moff-tarkin",
    "ezra-bridger-biography-gallery": "ezra-bridger",
    "kanan-jarrus-biography-gallery": "kanan-jarrus",
    "nightsisters-history-gallery": "nightsisters",
    "the-grand-inquisitor-biography-gallery": "the-grand-inquisitor",
    "tatooine-history-gallery": "tatooine"
}


def match_url(o: Item, u: str, data, other_data):
    m = match_by_url(o, u, data, False)
    if not m:
        m = match_by_url(o, u, other_data, False)
    if not m and "indexp" in o.url:
        m = match_by_url(o, u, data, True)
    if not m and "index.html?page=" in o.url:
        m = match_by_url(o, u, data, True)
    # if not m and "/#/" in o.url:
    #     m = match_by_url(o, u.split("/#/")[0], data, False)
    if not m and o.template == "WebCite":
        m = match_by_url(o, u.split("//", 1)[-1].split("/", 1)[-1], data, True)
    if not m and o.template == "Databank" and o.url.startswith("databank/"):
        m = match_by_url(o, u.replace("databank/", ""), data, True)
    if not m and o.template == "Databank" and not o.url.startswith("databank/"):
        m = match_by_url(o, f"databank/{u}", data, True)
    if not m and o.template == "SonyCite" and "&month=" in o.url:
        m = match_by_url(o, u.split("&month=")[0], data, False)
    if not m and o.template == "Faraway" and "starwarsknightsoftheoldrepublic" in o.url:
        x = re.sub("kotor([0-9]+)\|", "kotor0\\1|", re.sub("starwarsknightsoftheoldrepublic/starwarsknightsoftheoldrepublic([0-9]+)(\.html)?/?", "swknights/swkotor\\1.html", u))
        m = match_by_url(o, x.replace("starwarsknightsoftheoldrepublicwar", "swkotorwar"), data, False)
    if not m and "%20" in o.url:
        m = match_by_url(o, u.replace("%20", "-"), data, False)
    if not m and o.template in ["SW", "Databank"] and o.url in DATABANK_OVERWRITE:
        m = match_by_url(o, DATABANK_OVERWRITE[o.url], data, False)
        if not m:
            m = match_by_url(o, "databank/" + DATABANK_OVERWRITE[o.url], data, False)
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
    return None


def match_by_url(o: Item, url: str, data: Dict[str, Item], replace_page: bool):
    check_sw = o.template == "SW" and url.startswith("video/")
    url = prep_url(url)
    merge = {"SW", "SWArchive", "Hyperspace"}
    partial_matches = []
    for k, d in data.items():
        x = do_urls_match(url, o.template, d, replace_page)
        if x == 2:
            if d.template == o.template:
                return ItemId(o, d, False, False)
            elif {d.template, o.template}.issubset(merge):
                return ItemId(o, d, False, False)
            elif d.mode == "YT" and o.mode == "YT":
                return ItemId(o, d, False, False)
        elif x == 1:
            partial_matches.append(d)
        if check_sw and d.mode == "YT" and d.special and prep_url(d.special) == url:
            return ItemId(o, d, False, False)
    if partial_matches:
        return ItemId(o, partial_matches[0], False, False)
    return None


def load_appearances(site, log, canon_only=False, legends_only=False):
    data = []
    pages = ["Appearances/Legends", "Appearances/Canon", "Appearances/Audiobook"]
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
            #     if line.count("{{") > line.count("}}"):
            #         if o + 1 != len(lines) and lines[o + 1].count("}}") > lines[o + 1].count("{{"):
            #             line = f"{line}{lines[o + 1]}"
            #             skip = True
            #             bad.append(o)

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
            unlicensed = "{{c|unlicensed" in i['item'].lower()
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

            x = extract_item(i['item'], True, i['page'], types, master=True)
            if x:
                x.canon = None if i.get('extra') else i.get('canon')
                x.from_extra = i.get('extra')
                x.date = i['date']
                x.future = x.date and (x.date == 'Future' or x.date > today)
                x.extra = c
                x.alternate_url = alternate
                x.unlicensed = unlicensed
                x.non_canon = non_canon
                x.reprint = reprint
                x.ab = ab
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

    for x in ["audiobook", "unabridged audiobook", "abridged audiobook", "script", "audio drama", "German audio drama"]:
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
    text = fix_redirects(redirects, text, "Timeline", [])
    results = {}
    unique = {}
    index = 0
    unknown = None
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text).replace("|simple=1", "")
    for line in text.splitlines():
        if "==Unknown placement==" in line:
            unknown = {}
            continue
        line = re.sub("<!--.*?-->", "", line).strip()

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


def parse_timeline(text):
    results = []
    unique = {}
    index = 0
    unknown = None
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text)
    for line in text.splitlines():
        if "==Unknown placement==" in line:
            unknown = {}
            continue
        line = re.sub("<!--.*?-->", "", line).strip()
        if "{{Film|" in line:
            f = re.search(
                "^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\|)? ?[A-Z]+ ?\n?\|.*?\|+[* ]*?(['\"]*\{\{Film\|(?P<target>.*?)(\|.*?)?}}['\"]*) ?†?$",
                line)
            if f:
                t = f.group('target').replace("&ndash;", '–').replace('&mdash;', '—').strip()
                if t in FILMS:
                    results.append({"index": index, "target": FILMS[t], "date": f.group("date")})
                    if FILMS[t] not in unique:
                        unique[FILMS[t]] = index
                    index += 1
                    continue

        m = re.search(
            "^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\|)? ?[A-Z]+ ?\n?\|.*?\|+[* ]*?(['\"]*\[\[(?P<target>.*?)(\|.*?)?]]['\"]*) ?†?$",
            line)
        if m:
            t = m.group('target').replace("&ndash;", '–').replace('&mdash;', '—').strip()
            results.append({"index": index, "target": t, "date": m.group("date")})
            if unknown is not None:
                unknown[t] = index
            elif t not in unique:
                unique[t] = index
            index += 1
        elif "Star Wars (LINE Webtoon)" not in unique and "Star Wars (LINE Webtoon)" in line:
            results.append({"index": index, "target": "Star Wars (LINE Webtoon)", "date": ''})
            unique["Star Wars (LINE Webtoon)"] = index
            index += 1

    return results, unique, unknown or {}

# TODO: handle dupes between Legends/Canon
