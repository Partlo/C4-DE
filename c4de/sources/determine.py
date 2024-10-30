import re
from re import Match
from typing import List, Dict, Optional

from pywikibot import Page
from c4de.sources.domain import Item, ItemId


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets", "Soundtracks"
]

IGNORE_TEMPLATES = ["BookCite", "=", "Subtitles", "PAGENAME"]


COLLAPSE = {
    "GalaxiesAED": "Star Wars Galaxies: An Empire Divided",
    "GalaxiesNGE": "Star Wars Galaxies",
    "FindtheForce": "Find the Force",
    "CSWECite": "The Complete Star Wars Encyclopedia",
    "TFU": "Star Wars: The Force Unleashed",
    "TCWA": "Star Wars: Clone Wars Adventures (video game)",  # "[[Star Wars: Clone Wars Adventures (video game)|''Star Wars: Clone Wars Adventures'' video game]]",
    "GEAttr": "Star Wars: Galaxy's Edge",  #"[[Star Wars: Galaxy's Edge|''Star Wars'': Galaxy's Edge]] (template)",
    "GSAttr": "Star Wars: Galactic Starcruiser",  # "[[Star Wars: Galactic Starcruiser|''Star Wars'': Galactic Starcruiser]] (template)",
    "DatapadCite": "Star Wars: Datapad",  # "[[Star Wars: Datapad|''Star Wars'': Datapad]]"
}

COLLAPSED_MAGAZINES = {
    "FalconCite": ("Star Wars: Millennium Falcon", ""),
    "FFCite": ("The Official Star Wars Fact File", ""),
    "FFCite\|y=2013": ("The Official Star Wars Fact File Part", "2013"),
    "FFCite\|y=2014": ("The Official Star Wars Fact File Part", "2014"),
    "FigurineCite": ("Star Wars: The Official Figurine Collection", ""),
    "StarshipsVehiclesCite": ("Star Wars: The Official Starships & Vehicles Collection", "")
}

REFERENCE_MAGAZINES = {
    "BuildFalconCite": "Star Wars: Build the Millennium Falcon",
    "BuildR2Cite": "Star Wars: Build Your Own R2-D2",
    "BuildXWingCite": "Star Wars: Build Your Own X-Wing",
    "BustCollectionCite": "Star Wars Bust Collection",
    "HelmetCollectionCite": "Star Wars Helmet Collection",
    "ShipsandVehiclesCite": "Star Wars Starships & Vehicles"
}

TEMPLATE_MAPPING = {
    "KOTORbackups":  {
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
    },
    "EpIAdv": {
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
    },
    "SchAdv": {
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
    },
    "Film": {
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
}

PREFIXES = {
    "Jedi Temple Challenge": "Star Wars: Jedi Temple Challenge - Episode",
    "CW": "Clone Wars Chapter",
    "VaderImmortal": "Vader Immortal – Episode"
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


def convert_issue_to_template(s):
    m = re.search("(\[\[(.*?) ([0-9]+)(\|.*?)?]]'* ?{{C\|(.*?)}})", s)
    if m:
        for template, v in {**REFERENCE_MAGAZINES, **COLLAPSED_MAGAZINES}.items():
            if m.group(2) == v[0]:
                t = f"{{{{{template}|{m.group(3)}|{m.group(5)}}}}}"
                return s.replace(m.group(1), t.replace("\\|", "|"))
    return re.sub("<!--.*?-->", "", s)


def swap_parameters(s: str):
    return re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", s)


def extract_fact_file(z: str, s: str, a: bool):
    x = re.search("\{\{FFCite\|([0-9]+)\|?}}", s)
    if x:
        return Item(z, "General", a, target=f"The Official Star Wars Fact File {x.group(1)}")

    x = re.search("FFCite\|([0-9]+)\|(German Edition - )?(([A-Z]+) ?([0-9]+) ?(-|–|—|&mdash;|&ndash;)? ?\\4?([0-9]*)?)([|,])? ?(.*?)$", s)
    if x:
        issue = x.group(1)
        page = x.group(3)
        abbr = x.group(4)
        num1 = x.group(5)
        num2 = x.group(7)
        text = x.group(9)
        item = Item(z, "General", a, target=f"The Official Star Wars Fact File {issue}", template="FFCite",
                    issue=issue, text=f"{abbr} {num1} {text}")
        item.ff_data = {"page": page, "abbr": abbr, "num1": num1, "num2": num2, "text": text, "legacy": x.group(8) == ","}
        return item

    x = re.search("FFCite\|([0-9]+)\|'*(.*?)'*}}", s)
    if x:
        issue = x.group(1)
        item = Item(z, "General", a, target=f"The Official Star Wars Fact File {issue}", template="FFCite",
                    issue=issue, text=x.group(2))
        item.ff_data = {"page": None, "abbr": None, "num1": None, "num2": None, "text": x.group(2), "legacy": True}
        return item
    return None


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
    s = re.sub("<!--.*?-->", "", s)
    s = re.sub("^(.*?\[\[.*?[^ ])#(.*?)(\|.*?]].*?)$", "\\1\\3", s).replace("|d=y", "")
    s = re.sub(" ?\{\{Ab\|.*?}}", "", s)
    s = re.sub("^(Parent: )*", "", s)
    if "{{youtube" in s.lower():
        s = re.sub("You[tT]ube(\|channel[A-z]*=.*?\|channel[A-z]*=.*?)(\|(video=)?.*?\|(text=)?.*?)(\|.*?)?}}",
                   "YouTube\\2\\1\\5}}", s)
    if s.count("{") == 2 and s.count("}") == 1:
        s += "}"
    for i, j in COLLAPSE.items():
        if "{{" + i + "|" in s or "{{" + i + "}}" in s:
            return Item(z, "General", a, target=COLLAPSE[i], template=i, collapsed=True)

    s = re.sub("''(\[[^\[].*?[^]]])''", "\\1", s)
    # Plaintext links not wrapped in WebCite or OfficialSite
    if s.count("[") == 1 and s.count("]") == 1 and "WebCite" not in s:
        x = re.search("\[(https?://)(.*?web\.archive.org/web/([0-9]+)/)?(.*?\.[a-z]+/(.*?)) (.*?)]", s)
        if x:
            return Item(z, "Basic", a, url=x.group(1) + x.group(5), full_url=x.group(1) + x.group(5), text=x.group(6), archivedate=x.group(3))
        x = re.search("\[(https?://)(.*?web\.archive.org/web/([0-9]+)/)?(.*?) (.*?)]", s)
        if x:
            return Item(z, "Basic", a, url=x.group(1) + x.group(4), full_url=x.group(1) + x.group(4), text=x.group(5), archivedate=x.group(3))

    if s.count("{{") > s.count("}}"):
        print(f"Cannot parse invalid line on {page}: {s}")
        return Item(z, "General", a, invalid=True)
    elif s.count("{{") == 0 and s.count("[[") == 0:
        print(f"Cannot parse invalid line on {page}: {s}")
        return Item(z, "General", a, invalid=True)

    # Parent/child items not listed in StoryCite or appropriate template
    m = re.search("[\"']*?\[\[(?P<t>.*?)(\|.*?)?]],?[\"']*?,? ?([A-z]*? ?(published )?in |via|,[\"']*|-|–|—|&mdash;|&ndash;|:| \() ?(the )?['\"]*\[\[(?P<p>.*?)(\|.*?)?]]['\"]*?\)?", s)
    if m:
        return Item(z, "General", a, target=m.groupdict()['t'], parent=m.groupdict()['p'], check_both=True)
    m = re.search("\[\[.*?]]'*?:.*?\[\[(.*?)(\|.*?)?]]", s)
    if m:
        return Item(z, "General", a, target=m.group(1))

    # Simple wikilinks with no templates (also catches broken links)
    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            x = re.search("\[\[(.*?)(\|(.*?))?$", s)
        else:
            x = re.search("\[\[(.*?)(\|(.*?))?]+", s)
        if x:
            return Item(z, "External" if x.group(1).startswith(":File") else "General", a, target=x.group(1), format_text=x.group(3))

    # TODO: Remove once Episode I Adventures are switched over to template
    o = f"{s}"
    s = re.sub("(]+'*?) \(.*?\)", "\\1", s)
    if s.count("[[") == 1 and s.count("{{") == 0:
        if s.count("]") == 0:
            r = re.sub("^.*\[\[(.*?)(\|.*?)*?$", '\\1', s)
        else:
            r = re.sub("^.*\[\[(.*?)(\|.*?)?]+.*$", '\\1', s)
        return Item(o if master else s, "External" if r.startswith(":File") else "General", a, target=r)

    if "FFCite" in s and "y=" not in s:
        x = extract_fact_file(s, z, a)
        if x:
            return x

    # Handling reference magazines - individual articles aren't tracked, so remove multiple= param and collapse
    for i, (k, o) in COLLAPSED_MAGAZINES.items():
        if i.split('\\', 1)[0].lower() in s.lower():
            m = re.search("\{\{" + i + "\|([0-9]+)(\|((multiple=)?.*?))?}}", s)
            mode = types.get(i.split("\|")[0], "General")
            if m and ((o == "2014" and m.group(1) in ['1', '2', '3', '4', '5']) or (o and o != "2014")):
                return Item(z, mode, a, target=f"{k} {m.group(1)} ({o})", template=i.split("\|")[0], issue=m.group(1),
                            text=m.group(2), collapsed=True)
            elif m:
                return Item(z, mode, a, target=f"{k} {m.group(1)}", template=i.split("\|")[0], issue=m.group(1),
                            text=m.group(2), collapsed=True)

    for i, k in REFERENCE_MAGAZINES.items():
        if i.split('\\', 1)[0].lower() in s.lower():
            m = re.search("\{\{" + i + "\|([0-9]+)(\|(multiple=)?(.*?)(\|(.*?))?(\|(.*?))?)}}", s)
            mode = types.get(i, "General")
            if m and m.group(4):
                return Item(z, mode, a, parent=f"{k} {m.group(1)}", target=m.group(4), template=i, issue=m.group(1), text=m.group(6) if m.group(4) == 'Star Wars Universe' else None)
            elif m:
                return Item(z, mode, a, parent=f"{k} {m.group(1)}", template=i, issue=m.group(1), text=m.group(2), collapsed=True)

    m = re.search('\{\{([^|\[}\n]+)[|}]', s)
    template = m.group(1) if m else ''
    if template and template[0].islower():
        template = template[0].upper() + template[1:]
    tx = template.replace("_", " ").lower()
    mode = types.get(tx, "General")
    if mode == "Interwiki" or (mode == "External" and "url=" not in s):
        return Item(z, mode, a, template=template)
    elif tx in types["Nav"] or tx in types["Dates"]:
        print(f"Skipping {'navigation' if tx in types['Nav'] else 'date'} template: {template}: {z}")
        return None
    elif template in IGNORE_TEMPLATES:
        print(f"Skipping {mode} template: {template}: {z}")
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
            return Item(z, mode, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(2)}", template="HnnAd",
                        issue=m.group(2), url=m.group(1))
    elif template == "Holonet":
        m = re.search("\{\{Holonet\|((both|old)=true\|)?(.*?\|.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Holonet", url=m.group(3).replace("|", "/"),
                        text=m.group(5))
    # elif template == "TCW" and "TCW|Destiny" in s:
    #     return Item(z, mode, a, target="Destiny (Star Wars: The Clone Wars)", template=template)
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
    elif template == "Blog":  # Blog template - first two parameters combined are the URL
        if "listing=" in s:
            m = re.search("\{\{Blog\|(listing=true\|)(.*?)(\|.*?)?}}", s)
        else:
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
    elif template == "CalendarCite":
        m = re.search("\{\{CalendarCite\|([0-9]+)\|(.*?)}}", s)
        if m:
            return Item(z, mode, a, target=f"Star Wars Day-at-a-Time Calendar 20{m.group(1)}", template=template, special=m.group(2), )
    elif template == "HomeVideoCite":
        m = re.search("\{+HomeVideoCite.*?\|(set=)?(.*?)(\|.*?)?\|(episode|featurette|scene)=\[*?(.*?)]*?(\|.*?)?}+", s)
        if m:
            target = m.group(5) if "featurette=" in s and "nolink=1" not in s else None
            return Item(z, mode, a, target=target, template=template, parent=m.group(2), issue=m.group(5), collapsed=True)
    elif mode == "Social":
        m = re.search("\{\{[A-z]+\|([^|\n}]+)\|\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, "Profile", a, target=None, template=template, url=m.group(1), text=m.group(2))
        if "|url=" not in s.replace("|url=|", "|").replace("|url=}}", "}}"):
            m = re.search("\{\{[A-z]+\|(.*?\|)?(name|author|blogspotname|tumblrname)=(?P<t>[^|\n}]+)\|.*?(profile|profilelink|tumblrurl|blogspoturl)=(?P<u>[^|\n}]+)(\|.*?)?}}", s)
            if not m:
                m = re.search("\{\{[A-z]+\|(.*?\|)?(profile|profilelink|tumblrurl|blogspoturl)=(?P<u>[^|\n}]+)\|(.*?\|)?(name|author|blogspotname|tumblrname)=(?P<t>[^|\n}]+)(\|.*?)?}}", s)
            if m:
                return Item(z, "Profile", a, target=None, template=template, url=m.groupdict()['u'], text=m.groupdict()['t'])
        m = re.search("\{\{(Instagram|Twitter)\|([^|\n}]+)\|(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, "Social", a, target=None, template=template, url=m.groups()[3])
    elif template == "OfficialSite":
        m = re.search("\|url=(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, "Official", a, target=None, template=template, url=m.group(1))
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
    elif template == "TOMCite":
        m = re.search("\{\{TOMCite\|([0-9]+?)\|(.*?)\|(.*?)}}", s)
        if m:
            return Item(z, mode, a, target=m.group(2), template="TOMCite", parent=f"Star Wars - Das offizielle Magazin {m.group(1)}", format_text=m.group(3))
    elif template == "LSWCite":
        m = re.search("\{\{LSWCite\|([0-9]+)\|(.*?)(\|(.*?))?}}", s)
        if m:
            return Item(z, mode, a, target=m.group(2), template=template, parent=f"LEGO Star Wars {m.group(1)}", format_text=m.group(4))
    elif template == "ForceCollection":
        m = re.search("{{[^|\[}\n]+\|(.*?)(\|star=([0-9S]))?(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Star Wars: Force Collection",
                        card=m.group(1), special=m.group(3))
        return Item(z, mode, a, target="Star Wars: Force Collection", template=template)
    elif template == "SimpleToyCite":
        m = re.search("\{\{SimpleToyCite\|.*?parent=(?P<p>.*?)(\|.*?)?\|(item|nolink)=(?P<i>.*?)(\|.*?)?}}", s)
        if not m:
            m = re.search("\{\{SimpleToyCite\|.*?(item|nolink)=(?P<i>.*?)(\|.*?)?\|parent=(?P<p>.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent=m.groupdict()['p'], card=m.groupdict()['i'])
    elif mode == "Cards" or mode == "Toys" or "|card" in s:
        x = parse_card_line(s, z, template, mode, a)
        if x:
            return x

    # InsiderCite and similar templates - link= parameter
    m = re.search("{{[^|\[}\n]+\|link=(.*?)\|.*?\|(.*?)(\|(.*?))?}}", s)
    if m:
        return Item(z, mode, a, target=m.group(2), template=template, parent=m.group(1), issue=m.group(1), format_text=m.group(4))

    # Miniatures, toys or cards with set= parameter
    m = re.search("\{\{[^|\[}\n]+\|(.*?\|)?set=(?P<set>.*?)\|(.*?\|)?((scenario|pack)=(?P<scenario>.*?)\|?)?(.*?)}}", s)
    if m:
        return Item(z, mode, a, target=m.group('set'), template=template, text=m.group('scenario'))

    # Magazine articles with issue as second parameter
    m = re.search("{{[^|\[}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(issue[0-9]?=)?(?P<issue>(Special Edition |Souvenir Special|Premiere Issue)?H?S? ?[0-9.]*)(\|issue[0-9]=.*?)?\|(story=|article=)?\[*(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?]*(\|.*?)?}}", s.replace("&#61;", "="))
    if not m:
        m = re.search("{{[^|\[}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(story=|article=)?\[*(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?]*\|(issue[0-9]?=)?(?P<issue>(Special Edition |Souvenir Special|Premiere Issue)?H?S? ?[0-9.]*)(\|issue[0-9]=.*?)?(\|.*?)?}}", s.replace("&#61;", "="))
    if m and template != "StoryCite" and template != "SimpleCite":
        p = determine_parent_magazine(m, template, types)
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
        elif template and template in TEMPLATE_MAPPING and i in TEMPLATE_MAPPING[template]:
            return Item(z, mode, a, target=TEMPLATE_MAPPING[template][i], template=template)
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
    m = re.search("{{[^|\[}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(.*?\|)?(text|postname|thread)=(?P<text>.*?)(\|.*?)?}}", s)
    if not m:
        m = re.search("{{[^|\[}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(blogspotname=.*?\|)?(?P<text>.*?)(\|.*?)?}}", s)
    if not m:
        m = re.search("{{[^|\[}\n]+\|(.*?\|)?(full_url|url|video)=(?P<url>.*?)\|(.*?\|)?(text|postname|thread)=(?P<text>.*?)(\|.*?)?}}", s)
    if m:
        return Item(z, mode, a, target=None, template=template, url=m.group('url'), text=m.group('text'))

    # Web templates without named parameters
    if mode == "Web" or mode == "External" or mode == "Commercial":
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


def determine_parent_magazine(m: Match, template, types: dict):
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
    if not p:
        p = template.replace('Cite', '')
    return p


GAME_TEMPLATES = {
    "SWOR": "Star Wars: Outer Rim",
    "SWR": "Star Wars: Rebellion (board game)"
}

CORE_SETS = {
    "Armada": "Star Wars: Armada Core Set",
    "FFGTCG": "Star Wars: The Card Game Core Set",
    "FFGXW": "Star Wars: X-Wing Miniatures Game Core Set",
    "FFGXW2": "X-Wing Second Edition Core Set",
    "Legion": "Star Wars: Legion Core Set",
    "Shatterpoint": "Star Wars: Shatterpoint Core Set",
    "SWIA": "Star Wars: Imperial Assault Core Set",
    "SWPM": "Star Wars PocketModel TCG: Base Set",
}


def parse_card_line(s: str, z: str, template: str, mode: str, a: bool):
    m = re.search("{[^|\[}\n]+\|(set=)?(?P<set>.*?)[|}]", s)
    card_set = m.group(2) if m else None

    if template in GAME_TEMPLATES and "cardname=" not in s and "set=" not in s:
        return Item(z, mode, a, target=GAME_TEMPLATES[template], template=None)

    if template == "SWCT":
        m = re.search("{+[^|\[}\n]+\|(set=)?(.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Star Wars: Card Trader", card=m.group(2),
                        text=m.group(3))
    elif (card_set == "Core Set" or card_set == "Base Set") and CORE_SETS.get(template):
        card_set = CORE_SETS[template]
    elif template == "Topps" and card_set == "Star Wars Topps Now" and "|stext=" in s:
        card_set = re.search("\|stext=(.*?)[|}].*?$", s).group(1).replace("''", "")
    elif card_set and template == "TopTrumps":
        card_set = f"Top Trumps: {card_set}"
    # elif card_set and template == "SWU":
    #     if card_set == "Spark of Rebellion":
    #         card_set = f"{card_set} (Star Wars: Unlimited)"
    # elif card_set and template == "SWMiniCite":
    #     if card_set not in ["Alliance and Empire", "Clone Strike", "The Dark Times", "Rebel Storm", "Galaxy Tiles",
    #                         "Starship Battles", "Rebels and Imperials"] \
    #             and not card_set.endswith("Pack") and "Star Wars Miniatures" not in card_set:
    #         card_set = f"{card_set} (Star Wars Miniatures)"

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
        return Item(z, mode, a, target=card_set, template=template, parent=None, subset=subset,
                    text=t.group('text') if t else None)
    else:
        print(s)
    return None


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
                  use_original_text=False, ref_magazine=False, by_parent=False):
    if by_target and by_target.get(target):
        return ItemId(o, by_target[target][0], use_original_text, False, ref_magazine=ref_magazine, by_parent=by_parent)
    elif other_targets and other_targets.get(target):
        return ItemId(o, other_targets[target][0], use_original_text, True, ref_magazine=ref_magazine, by_parent=by_parent)
    return None


def determine_id_for_item(o: Item, site, data: Dict[str, Item], by_target: Dict[str, List[Item]], other_data: Dict[str, Item],
                          other_targets: Dict[str, List[Item]], remap: dict, canon: bool, log: bool):
    """ :rtype: ItemId """

    # Remapping common mistakes in naming
    if remap and o.target and o.target in remap:
        m = check_targets(o, remap[o.target], by_target, other_targets, use_original_text=False)
        if m:
            return m

    if o.unique_id() in data or o.unique_id() in other_data:
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
        t = f"General|None|Star Wars Insider {o.issue}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], True, False)

    if o.mode == "External" or o.mode == "Basic":
        if o.url:
            m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
            if m:
                return m
        return None

    if o.template == "FFCite" and "|y=" not in o.original:
        x = match_fact_file(o, by_target, other_targets)
        if x:
            return x

    if not o.template and o.target in ["Star Wars (radio)", "The Empire Strikes Back (radio)", "Return of the Jedi (radio)"]:
        m = check_targets(o, o.target, by_target, other_targets, use_original_text=True)
        if m:
            return m

    if o.check_both:
        x = match_parent_target(o, o.parent, o.target, by_target, other_targets, site)
        y = match_parent_target(o, o.target, o.parent, by_target, other_targets, site, False)
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
    if o.template == "SWCT" and o.card:
        matches = []
        for s, x in data.items():
            if x.template == "SWCT" and x.card and x.card in o.card:
                matches.append(x)
        if matches:
            x = sorted(matches, key=lambda a: len(a.card))[-1]
            return ItemId(o, x, True, False)
        o.unknown = True
        return ItemId(o, o, True, False)
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
    elif o.template == "CalendarCite":
        for s, x in data.items():
            if x.target == o.target:
                return ItemId(o, x, True, False)

    if (o.mode == "Cards" or o.mode == "Toys") and (o.card or o.special):
        set_name = o.parent or o.target
        m = match_by_set_name(o, o.mode, o.template, set_name, data, other_data)
        if m:
            return m

        if set_name == "Star Wars: The Power of the Force (1995 toy line)":
            v = 'HasbroCite' if o.template == 'KennerCite' else 'KennerCite'
            m = match_by_set_name(o, o.mode, v, set_name, data, other_data)
            if m:
                return m

        if o.template == "SWMiniCite":
            m = match_by_set_name(o, "General", "None", set_name, data, other_data)
            if m:
                return m

        if o.url:
            m = match_by_url(o, o.url, data, False)
            if m:
                return m

        set_match = None
        if set_name is not None:
            for s, x in data.items():
                if do_card_templates_match(set_name, o, x):
                    if (x.target and (x.target.startswith(set_name) or set_name in x.target)) or \
                            (x.parent and (x.parent.startswith(set_name) or set_name in x.parent)):
                        if (x.card and x.card == o.card) or (x.text and x.text == o.text):
                            return ItemId(o, x, False, False)
                        elif not set_match:
                            set_match = x
        if set_match:
            return ItemId(o, set_match, True, False)
    elif o.mode == "Cards" or o.mode == "Toys":
        m = match_by_set_name(o, o.mode, o.template, o.parent if o.parent else o.target, data, other_data)
        if m:
            return m

    # Find a match by URL
    if o.url and 'starwars/article/dodcampaign' not in o.url:
        m = match_url(o, o.url.replace("/#!/about", "").replace("news/news/", "news/").lower(), data, other_data)
        if m and not (o.mode == "Toys" and m.master.mode == "Found-External"):
            return m

    # if Toy/Card isn't matched by the URL, then use the original
    if o.mode == "Cards" and (o.card or o.special):
        return ItemId(o, o, True, False)
    elif o.mode == "Toys" and (o.card or o.special):
        o.unknown = True
        return ItemId(o, o, True, False)

    if o.issue or o.no_issue:
        is_ref = o.template in REFERENCE_MAGAZINES
        t = f"{o.mode}|None|{o.target}|None|None|None|None|None"
        if t in data:
            return ItemId(o, data[t], o.collapsed, False, ref_magazine=is_ref)
        elif o.parent and "Special Edition" in o.parent and by_target.get(o.parent):
            return ItemId(o, by_target[o.parent][0], True, False, ref_magazine=is_ref)
        x = match_issue_target(o, by_target, other_targets, True, is_ref)
        if not x and o.target and not o.followed_redirect:
            if follow_redirect(o, site, True):
                o.followed_redirect = True
                x = match_issue_target(o, by_target, other_targets, False, is_ref)
        if not x or (x and x.master.issue != o.issue and o.parent in by_target):
            targets = [(t, False) for t in get_possible_targets(o, by_target)]
            targets += [(t, True) for t in get_possible_targets(o, other_targets)]
            print(f"Found unrecognized {o.target} listing for {o.parent} --> {len(targets)} possible matches")

            exact = [(t, c) for (t, c) in targets if t.template == o.template and t.issue == o.issue]
            magazine = [(t, c) for (t, c) in targets if t.template == o.template]
            numbers = [(t, c) for (t, c) in targets if t.issue and t.issue.isnumeric()]

            if len(exact) == 1:
                x = ItemId(o, exact[0][0], False, exact[0][1], False, ref_magazine=is_ref)
            elif len(targets) == 1:
                x = ItemId(o, targets[0][0], False, targets[0][1], False, ref_magazine=is_ref)
            elif len(magazine) == 1:
                x = ItemId(o, magazine[0][0], False, magazine[0][1], False, ref_magazine=is_ref)
            elif o.issue and o.issue.isnumeric() and len(numbers) == 1:
                x = ItemId(o, numbers[0][0], False, numbers[0][1], False, ref_magazine=is_ref)
            elif by_target.get(o.parent):
                parent = by_target[o.parent][0]
                x = ItemId(o, parent, True, False, by_parent=True, ref_magazine=is_ref)
        if x:
            return x
        if o.target == o.parent and by_target.get(o.parent) and o.text and o.text.replace("'", "") != o.target:
            return ItemId(o, by_target[o.parent][0], True, False, by_parent=True, ref_magazine=is_ref)

    x = match_parent_target(o, o.parent, o.target, by_target, other_targets, site)
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
        if follow_redirect(o, site, log):
            o.followed_redirect = True
            x = match_target(o, by_target, other_targets, log)

    if o.template == "HomeVideoCite":
        x = None
        if "episode=" in o.original:
            x = match_specific_target(o, o.parent, by_target, other_targets, log)
            if x:
                x.use_original_text = True
                return x
        for is_other, ids in {False: data, True: other_data}.items():
            for k, v in ids.items():
                if k.startswith(f"General|HomeVideoCite|None|None|{o.parent}|"):
                    if "scene=" in o.original and "scene=" in v.original:
                        return ItemId(o, v, True, is_other)
                    elif "featurette=" in o.original and "featurette=<FEATURETTE>" in v.original:
                        return ItemId(o, v, True, is_other)
    return x


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
            x = match_fact_file_issue(o, other_targets[f"FFData|{i}"], False, False)
            if x:
                return x
    o.unknown = True
    return ItemId(o, o, True, False)


def match_fact_file_issue(o: Item, entries: list[Item], other: bool, log_missing=True):
    abbr = [x for x in entries if o.ff_data["abbr"] and x.ff_data["abbr"] == o.ff_data["abbr"]]
    if len(abbr) == 1:
        if o.ff_data['legacy']:
            print(f"Match: {o.ff_data}, {abbr[0].ff_data}")
        return ItemId(o, abbr[0], False, other)
    elif len(abbr) > 1:
        if o.ff_data["num1"]:
            x1, x2 = to_int(o.ff_data["num1"]), to_int(o.ff_data["num2"])
            for i in abbr:
                n1, n2 = to_int(i.ff_data["num1"]), to_int(i.ff_data["num2"])
                if x1 and x2 and n1 <= x1 and x2 <= n2:
                    return ItemId(o, i, False, other)
                elif x1 and x2 is None and n1 <= x1 <= n2:
                    return ItemId(o, i, False, other)
        print(f"Unable to exact-match {o.ff_data['page']}, using {abbr[0].ff_data}: {o.original}")
        return ItemId(o, abbr[0], False, other)

    if not o.ff_data["abbr"] and o.ff_data["text"]:
        for i in entries:
            if i.issue != o.issue:
                continue
            t, _, _ = i.ff_data["text"].replace("'", "").partition("}}")
            if i.ff_data["text"] and (t == o.ff_data["text"] or t in o.ff_data["text"] or t[:-1] in o.ff_data["text"]):
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


def match_by_set_name(o: Item, mode: str, template: str, set_name: str, data, other_data):
    m = find_matching_set(mode, template, set_name, data)
    if m:
        return ItemId(o, m, True, False)

    m = find_matching_set(mode, template, set_name, other_data)
    if m:
        return ItemId(o, m, True, True)
    return None


def find_matching_set(mode, template, set_name, data: dict):
    t = f"{mode}|{template}|{set_name}"
    for x in ["", "None"]:
        if f"{t}|None|None|None|None|{x}" in data:
            return data[f"{t}|None|None|None|None|{x}"]

    partial = []
    for x, y in data.items():
        if y.template == template and y.target:
            if y.target == set_name:
                return y
            elif y.target.startswith(set_name):
                partial.append(y)
    return partial[0] if partial else None


def find_matching_issue(items, issue, text):
    if "issue1=" in text:
        for t in items:
            if t.issue == issue and t.original and "issue1=" in t.original:
                return t
    for t in items:
        if t.issue == issue:
            return t
    return items[0]


def match_issue_target(o: Item, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], use_original, is_ref):
    # if o.target and by_target and o.target in by_target:
    #     return ItemId(o, find_matching_issue(by_target[o.target], o.issue, o.original), use_original, False, ref_magazine=is_ref)
    # elif o.target and other_targets and o.target in other_targets:
    #     return ItemId(o, find_matching_issue(other_targets[o.target], o.issue, o.original), use_original, False, ref_magazine=is_ref)
    match = match_target_issue_name(o, o.target, by_target, other_targets, use_original, is_ref)
    if not match and o.target and "&hellip;" in o.target and "dash;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&hellip;", "...").replace("&ndash;", '–').replace('&mdash;', '—'), by_target, other_targets, use_original, is_ref)
    if not match and o.target and "&hellip;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&hellip;", "..."), by_target, other_targets, use_original, is_ref)
    if not match and o.target and "dash;" in o.target:
        match = match_target_issue_name(o, o.target.replace("&ndash;", '–').replace('&mdash;', '—'), by_target, other_targets, use_original, is_ref)
    # if not match and o.template == "InsiderCite":
    #     match = match_target_issue_name(o, f"{o.target} (Star Wars Insider)", by_target, other_targets, use_original, is_ref)
    # if not match and o.template:
    #     match = match_target_issue_name(o, f"{o.target} (article)", by_target, other_targets, use_original, is_ref)
    if match:
        return match

    if o.target and o.parent and o.target.startswith(f"{o.parent}#"):
        m = check_targets(o, o.parent, by_target, other_targets, use_original_text=True, ref_magazine=is_ref)
        if m:
            return m
    return None


def match_target_issue_name(o, target, by_target, other_targets, use_original, is_ref):
    if target and by_target and target in by_target:
        return ItemId(o, find_matching_issue(by_target[target], o.issue, o.original), use_original, False, ref_magazine=is_ref)
    elif target and other_targets and target in other_targets:
        return ItemId(o, find_matching_issue(other_targets[target], o.issue, o.original), use_original, False, ref_magazine=is_ref)
    return None


def match_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], site, save=True) -> Optional[ItemId]:
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
    "EncyclopediaCite": ["Star Wars Encyclopedia"],
    "StoryCite": ["short story"],
    "CWACite": ["comic"],
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
    if target:
        targets.append(target.replace("_", " ").replace("Game Book ", ""))
        if "&hellip;" in target:
            targets.append(target.replace("&hellip;", "..."))
        if "..." in target:
            targets.append(target.replace("...", "&hellip;"))
        if "(" not in target and o.tv:
            targets.append(f"{target} (episode)")
            targets.append(f"{target} (short film)")
            if o.template in TV_SUFFIXES:
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
    if "|}}" in o.original:
        m = re.search("\{\{([A-z_ ]+)\|([0-9]+)\|}}", o.original)
        if m and m.group(1) in TEMPLATES:
            targets.append(f"{TEMPLATES[m.group(1)]} {m.group(2)}")

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


def match_by_target(t, o, by_target, other_targets, log):
    if t in by_target:
        if len(by_target[t]) == 1:
            return ItemId(o, by_target[t][0], o.collapsed, False)
        if log and not o.both_continuities:
            print(f"Multiple matches found for {t}")
        for x in by_target[t]:
            if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''", ""):
                return ItemId(o, x, o.collapsed, False)
            elif not o.template and not x.template and not o.parent and not x.parent:
                return ItemId(o, x, o.collapsed, False)
            elif x.url and o.url and do_urls_match(o.url, o.template, x, True, True):
                return ItemId(o, x, o.collapsed, False)
        return ItemId(o, by_target[t][0], o.collapsed, False)
    elif other_targets and t in other_targets:
        if len(other_targets[t]) == 1:
            return ItemId(o, other_targets[t][0], o.collapsed, True)
        if log and not o.both_continuities:
            print(f"Multiple matches found for {t}")
        for x in other_targets[t]:
            if x.format_text and o.format_text and x.format_text.replace("''", "") == o.format_text.replace("''", ""):
                return ItemId(o, x, o.collapsed, False)
            elif not o.template and not x.template and not o.parent and not x.parent:
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
    if template and "youtube" in template.lower() and not alternate_url and d_url and d_url.startswith("-"):
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
    elif d_url and d_url.replace("en/", "").replace("en-gb/", "").replace("en-us/", "") == url.replace("en/", "").replace("en-gb/", "").replace("en-us/", ""):
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
    elif template == "SonyCite" and d.template == "SonyCite" and (url.startswith("players/") or url.startswith("en_US/players/")):
        if d_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("players/", "").replace("&resource=features", ""):
            return 2
        elif alternate_url and alternate_url.replace("&resource=features", "") == url.replace("en_US/players/", "").replace("players/", "").replace("&resource=features", ""):
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


def match_url(o: Item, u: str, data: dict, other_data: dict):
    m = match_by_urls(o, u, data, other_data, False)
    if not m and o.url.endswith("?"):
        m = match_by_urls(o, u[:-1], data, other_data, False)
    if not m and "indexp" in o.url:
        m = match_by_urls(o, u, data, other_data, True)
    if not m and "index.html?page=" in o.url:
        m = match_by_urls(o, u, data, other_data, True)
    # if not m and "/#/" in o.url:
    #     m = match_by_url(o, u.split("/#/")[0], data, False)
    if not m and o.template == "WebCite":
        m = match_by_urls(o, u.replace("http:", "https:").split("//", 1)[-1].replace("www.", ""), data, other_data, True)
        if not m:
            m = match_by_urls(o, u.replace("http:", "https:").split("//", 1)[-1].split("/", 1)[-1], data, other_data, True)
    if not m and o.template == "Databank" and o.url.startswith("databank/"):
        m = match_by_urls(o, u.replace("databank/", ""), data, other_data, True)
    if not m and o.template == "Databank" and not o.url.startswith("databank/"):
        m = match_by_urls(o, f"databank/{u}", data, other_data, True)
    if not m and o.template == "Blog" and not o.url.endswith("/comments"):
        m = match_by_urls(o, f"{u}/comments", data, other_data, True)
    if not m and o.template == "Blog" and o.url.endswith("/comments"):
        m = match_by_urls(o, u.replace("/comments", ""), data, other_data, True)
    if not m and o.template == "SonyCite" and "&month=" in o.url:
        m = match_by_urls(o, u.split("&month=")[0], data, other_data, False)
    if not m and o.template == "Faraway" and "starwarsknightsoftheoldrepublic" in o.url:
        x = re.sub("kotor([0-9]+)\|", "kotor0\\1|", re.sub("starwarsknightsoftheoldrepublic/starwarsknightsoftheoldrepublic([0-9]+)(\.html)?/?", "swknights/swkotor\\1.html", u))
        m = match_by_urls(o, x.replace("starwarsknightsoftheoldrepublicwar", "swkotorwar"), data, other_data, False)
    if not m and "%20" in o.url:
        m = match_by_urls(o, u.replace("%20", "-"), data, other_data, False)
    if not m and o.template in ["SW", "Databank"] and o.url in DATABANK_OVERWRITE:
        m = match_by_urls(o, DATABANK_OVERWRITE[o.url], data, other_data, False)
        if not m:
            m = match_by_urls(o, "databank/" + DATABANK_OVERWRITE[o.url], data, other_data, False)
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
    y = re.search("(archive(date|url)=.*?)(\|.*?)?}}", o.original)
    ad = y.group(1) if y else None
    for k, d in data.items():
        x = do_urls_match(url, o.template, d, replace_page)
        if x == 2:
            if d.original and "oldversion=1" in d.original and ad and ad in d.original:
                return ItemId(o, d, False, False)
            elif d.original and "oldversion=1" in d.original and not ad:
                old_versions.append(d)
            elif ad and (o.mode == d.mode or (o.mode in valid and d.mode in valid)):
                old_versions.append(d)
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
    if old_versions:
        return ItemId(o, old_versions[-1], ad is not None, False)
    if partial_matches:
        print(len(partial_matches), [x.template for x in partial_matches])
        return ItemId(o, partial_matches[0], False, False)
    return None
