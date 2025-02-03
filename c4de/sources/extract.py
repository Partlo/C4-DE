import re
from re import Match
from typing import List, Dict, Optional

from pywikibot import Page
from c4de.sources.domain import Item, ItemId


IGNORE_TEMPLATES = ["BookCite", "=", "Subtitles", "PAGENAME"]


COLLAPSE = {
    "HighRepublicReaderGuide": "Star Wars: The High Republic: Chronological Reader's Guide",
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
    "FactFile": ("The Official Star Wars Fact File", ""),
    "FactFile\|y=2013": ("The Official Star Wars Fact File Part", "2013"),
    "FactFile\|y=2014": ("The Official Star Wars Fact File Part", "2014"),
    "FigurineCite": ("Star Wars: The Official Figurine Collection", ""),
    "StarshipsVehiclesCite": ("Star Wars: The Official Starships & Vehicles Collection", "")
}

REFERENCE_MAGAZINES = {
    "BuildFalconCite": "Star Wars: Build the Millennium Falcon <x>",
    "BuildR2Cite": "Star Wars: Build Your Own R2-D2 <x>",
    "BuildXWingCite": "Star Wars: Build Your Own X-Wing <x>",
    "BustCollectionCite": "Star Wars Bust Collection <x>",
    "DarthVaderCite": "Star Wars: Darth Vader <x> (magazine)",
    "HelmetCollectionCite": "Star Wars Helmet Collection <x>",
    "ShipsandVehiclesCite": "Star Wars Starships & Vehicles <x>"
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
    "Jedi Temple Challenge": "Episode <x> (Star Wars: Jedi Temple Challenge)",
    "JTC": "Episode <x> (Star Wars: Jedi Temple Challenge)",
    "CW": "Chapter <x> (Star Wars: Clone Wars)",
    "VaderImmortal": "Vader Immortal – Episode <x>",
    "DisneyGallery": "<x> (Disney Gallery: The Mandalorian)",
    "GroguCutest": "Episode <x> (Grogu Cutest In The Galaxy)"
}


CUSTOM_SERIES_MAPPING = {
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


def decide_ff_issue(y, i):
    if y and i in ["1", "2", "3", "4", "5"]:
        return f"Part {i} ({y})"
    elif y == "2014":
        return f"Part {i}"
    else:
        return i


def extract_fact_file(z: str, s: str, a: bool):
    x = re.search("\{\{(FactFile(\|y=(201[34]))?)\|([0-9]+)\|?}}", s)
    if x:
        issue = decide_ff_issue(x.group(3), x.group(4))
        return Item(z, "General", a, template=x.group(1), target=f"The Official Star Wars Fact File {issue}")

    x = re.search("(FactFile(\|y=(201[34]))?)\|(?P<i>[0-9]+)\|(German Edition - )?(?P<p>(?P<a>[0-9]* ?[A-Z]+)[ -]?(?P<n>[0-9]+) ?(-|–|—|&mdash;|&ndash;)? ?\\7?(?P<m>[0-9]*)?)(?P<s>[|,])? ?(?P<t>.*?)$", s)
    if x:
        issue = decide_ff_issue(x.group(3), x.group('i'))
        page = x.group('p')
        abbr = x.group('a').upper()
        num1 = x.group('n')
        num2 = x.group('m')
        text = x.group('t') or ''
        num3, num4 = None, None
        y = re.search("<[A-Z]+ ([0-9]+)-([0-9]+)>", text or "")
        if y:
            num3, num4 = y.group(1), y.group(2)
            text = text.replace(y.group(0), "")
        item = Item(z, "General", a, target=f"The Official Star Wars Fact File {issue}", template=x.group(1),
                    issue=issue, text=f"{abbr} {num1} {text.split('}')[0]}")
        item.ff_data = {"page": page, "abbr": abbr, "num1": num1, "num2": num2, "num3": num3, "num4": num4, "text": text, "legacy": x.group('s') == ","}
        return item

    x = re.search("(FactFile(\|y=(201[34]))?)\|([0-9]+)\|'*(.*?)'*}}", s)
    if x:
        issue = decide_ff_issue(x.group(3), x.group(4))
        item = Item(z, "General", a, target=f"The Official Star Wars Fact File {issue}", template=x.group(1),
                    issue=issue, text=x.group(5))
        item.ff_data = {"page": None, "abbr": None, "num1": None, "num2": None, "num3": None, "num4": None, "text": x.group(5), "legacy": True}
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
        x = re.search("\[(https?://)(w?w?w?\.?web\.archive.org/web/([0-9]+)/)?(.*?\.[a-z]+/(.*?)) (.*?)]", s)
        if x:
            return Item(z, "Basic", a, url=x.group(5), full_url=x.group(1) + x.group(4), text=x.group(6), archivedate=x.group(3))
        x = re.search("\[(https?://)(w?w?w?\.?web\.archive.org/web/([0-9]+)/)?(.*?) (.*?)]", s)
        if x:
            return Item(z, "Basic", a, url=x.group(4), full_url=x.group(1) + x.group(4), text=x.group(5), archivedate=x.group(3))

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

    if "FactFile" in s:
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
            m = re.search("\{\{" + i + "\|([0-9]+)(\|(.*?))?(\|(.*?))?}}", s)
            mode = types.get(i, "General")
            if m and m.group(3) and "|parent=" in m.group(0):
                return Item(z, mode, a, target=k.replace("<x>", m.group(1)), template=i, issue=m.group(1), ref_magazine=True)
            elif m and m.group(3):
                return Item(z, mode, a, parent=k.replace("<x>", m.group(1)), template=i, issue=m.group(1), target=m.group(3), text=m.group(5), ref_magazine=True)
            elif m:
                return Item(z, mode, a, parent=k.replace("<x>", m.group(1)), template=i, issue=m.group(1), text=m.group(2), collapsed=True, ref_magazine=True)

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
    elif template == "CelebrationTrailer":
        m = re.search("\{\{CelebrationTrailer\|['\[]*(?P<m>.*?)(\|.*?)?['\]]*\|(?P<c>.*?)}}", s)
        if m:
            return Item(z, mode, a, target=m.groupdict()['c'], issue=m.groupdict()['m'])
    elif template == "HBCite":
        m = re.search("\{\{HBCite\|([0-9]+)", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Homing Beacon (newsletter)", issue=m.group(1))
    elif template == "Visions":
        m = re.search("\{\{Visions\|(?P<f>focus=1\|)?(?P<e>.*?)(\|.*?)?}}", s)
        if not m:
            m = re.search("\{\{Visions\|(?P<e>.*?)(\|.*?(?P<f>focus=1)?.*?)?}}", s)
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
    elif template == "ForceCollection":
        m = re.search("{{[^|\[}\n]+\|(.*?)(\|star=([0-9S]))?(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent="Star Wars: Force Collection",
                        card=m.group(1), special=m.group(3))
        return Item(z, mode, a, target="Star Wars: Force Collection", template=template)
    elif template == "SimpleToyCite":
        m = re.search("\{\{SimpleToyCite\|.*?parent=(?P<p>.*?)(\|.*?)?\|(item|pack|nolink)=(?P<i>.*?)(\|.*?)?}}", s)
        if not m:
            m = re.search("\{\{SimpleToyCite\|.*?(item|pack|nolink)=(?P<i>.*?)(\|.*?)?\|parent=(?P<p>.*?)(\|.*?)?}}", s)
        if m:
            return Item(z, mode, a, target=None, template=template, parent=m.groupdict()['p'], card=m.groupdict()['i'])
    elif mode == "Cards" or mode == "Minis" or mode == "Toys" or "|card" in s:
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
    m = re.search("{{[^|\[}\n]+\|(?P<year>year=[0-9]+\|)?(?P<vol>volume=[0-9]\|)?(issue[0-9]?=)?(?P<issue>(Special |Special Edition |Digital Sampler Edition|Interview Special|Souvenir Special|Premiere Issue)?H?S? ?[0-9.]*)(\|issue[0-9]=.*?)?\|(story=|article=)?\[*(?P<article>.*?)(#.*?)?(\|(?P<text>.*?))?]*(\|.*?)?}}", s.replace("&#61;", "="))
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
            return Item(z, mode, a, target=PREFIXES[template].replace("<x>", i), template=template)
        elif template and template in TEMPLATE_MAPPING and i in TEMPLATE_MAPPING[template]:
            return Item(z, mode, a, target=TEMPLATE_MAPPING[template][i], template=template)
        elif template and i:
            return Item(z, mode, a, target=i, template=template)

    # series, issue1 and story/adventure? is this still a thing?
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
    if mode == "Web" or mode == "External" or mode == "Publisher" or mode == "Commercial":
        m = re.search("{{[^|\[}\n]+\|(date=.*?\|)?(subdomain=.*?\|)?(.*?)\|(.*?)(\|.*?)?}}", s)
        if m:
            y = re.search("\|int=(.*?)[|}]", s)
            return Item(z, mode, a, template=template, url=m.group(3), text=m.group(4), target=y.group(1) if y else None)

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
        p = CUSTOM_SERIES_MAPPING.get(f"{template}|{m.group('year')}")
    elif m.group('vol'):
        p = CUSTOM_SERIES_MAPPING.get(f"{template}|{m.group('vol')}")
    else:
        p = CUSTOM_SERIES_MAPPING.get(template)
    if m.group('issue'):
        if template == "InsiderCite" and m.group('issue').isnumeric() and int(m.group('issue')) <= 23:
            p = "The Lucasfilm Fan Club Magazine"
        elif template == "InQuestCite" and m.group('issue').isnumeric() and int(m.group('issue')) <= 46:
            p = "InQuest"
        elif template == "CalendarCite":
            p = f"Star Wars Day-at-a-Time Calendar 20{m.group('issue')}"
    if not p:
        p = types["Magazine"].get(template)
    if not p:
        p = template.replace('Cite', '')
    return p


def parse_card_line(s: str, z: str, template: str, mode: str, a: bool):
    m = re.search("{[^|\[}\n]+\|(set=)?(?P<set>.*?)[|}]", s)
    card_set = m.group(2) if m else None

    if template in GAME_TEMPLATES and "cardname=" not in s and "mission=" not in s and "set=" not in s:
        return Item(z, mode, a, target=GAME_TEMPLATES[template], template=None)
    elif template in GAME_TEMPLATES and "cardname=" in s and "set=" not in s:
        c = re.search("\|cardname=(.*?)(\|.*?)?}}", s)
        return Item(z, mode, a, target=None, parent=GAME_TEMPLATES[template], template=template, card=c.group(1))

    if template == "SWCT" and "cardname=" not in s:
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

    if card_set and "cardname=" in card_set:
        card = card_set.replace("cardname=", "")
        card_set = None
    else:
        m = re.search("{[^|\[}\n]+\|.*?(cardname|pack|card|mission|scenario)=(?P<card>.*?)?[|}]", s)
        card = m.group(2) if m else None
        if not card and "rulebook=" in s:
            card = "Rulebook"
    u = re.search("(url|link)=(.*?)[|}]", s)
    t = re.search("{[^|\[}\n]+\|.*?text=(?P<text>.*?)[|}]", s)
    sh = re.search("\|ship=(.*?)[|}]", s)
    ship = sh.group(1) if sh else None
    ss = re.search("subset=(.*?)(\|.*?)?}}", s)
    subset = ss.group(1) if ss else None
    if template == "SWIA" and "mission=" in s:
        mode = "Minis"

    if not t:
        t = re.search("{[^|\[}\n]+\|.*?\|(?P<text>.*?)(\|.*?)?}}", s)
        if t and t.group('text') and re.search("^[a-z]+=", t.group('text')):
            t = None
    if card and "|scenario=" in s:
        return Item(z, mode, a, target=None, template=template, parent=card_set, special=card,
                    url=u.group(2) if u else None, text=t.group('text') if t else None)
    elif card:
        return Item(z, mode, a, target=None, template=template, parent=card_set, card=card, subset=subset,
                    url=u.group(2) if u else None, text=t.group('text') if t else None, special=ship)
    elif card_set:
        return Item(z, mode, a, target=card_set, template=template, parent=None, subset=subset,
                    text=t.group('text') if t else None, special=ship)
    else:
        print(s)
    return None
