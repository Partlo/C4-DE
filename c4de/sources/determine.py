import re
import traceback
from datetime import datetime
from typing import List, Dict, Optional, Tuple

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

    if s.count("[") == 1 and s.count("]") == 1:
        x = re.search("\[https?://(.*?web\.archive.org/web/[0-9]+/)?(.*?\.[a-z]+/(.*?)) .*?]", s)
        if x:
            return Item(z, "Basic", a, url=x.group(3), full_url=x.group(2))
    # elif "{{WP}}" in s:
    #     return Item(z, "External", a, template="WP")
    # elif "Wiki}}" in s:
    #     x = re.search("\{\{([A-z]+?Wiki)}}", s)
    #     if x:
    #         return Item(z, "External", a, template=x.group(1) if x else "Wiki")

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

    m = re.search("[\"']*?\[\[(?P<t>.*?)(\|.*?)?]][\"']*? ?([A-z]*? ?in |,|-|–|—|&mdash;|&ndash;|:) ?['\"]*\[\[(?P<p>.*?)(\|.*?)?]]['\"]*?", s)
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
    if mode == "External":
        return Item(z, "External", a, template=template)

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
            return Item(z, mode, a, target=None, parent=f"HoloNet News Vol. 531 {m.group(2)}", template="HnnAd",
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
        y, _ = match_parent_target(o, o.target, o.parent, by_target, other_targets, False, site)
        if x and y:
            if x.master.parent and y.master.target and x.master.parent == y.master.target:
                return x
            elif x.master.target and y.master.parent and x.master.target == y.master.target:
                return y
        elif x:
            return x
        elif y:
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
            targets = by_target.get(o.target, [])
            if not targets and o.template == "InsiderCite":
                targets = by_target.get(f"{o.target} (Star Wars Insider)", [])
            if not targets and o.template == "InsiderCite":
                targets = by_target.get(f"{o.target} (article)", [])
            print(f"Found unrecognized {o.target} listing for {o.parent} --> {len(targets)} possible matches")

            magazine = [t for t in targets if t.template == o.template]
            numbers = [t for t in targets if t.issue and t.issue.isnumeric()]

            if len(targets) == 1:
                x = ItemId(o, targets[0], False, False, False, ref_magazine=is_ref)
            elif len(magazine) == 1:
                x = ItemId(o, magazine[0], False, False, False, ref_magazine=is_ref)
            elif o.issue and o.issue.isnumeric() and len(numbers) == 1:
                x = ItemId(o, numbers[0], False, False, False, ref_magazine=is_ref)
            else:
                parent = by_target[o.parent][0]
                x = ItemId(o, parent, True, False, by_parent=True, ref_magazine=is_ref)
        if x:
            return x
        if o.target == o.parent and by_target.get(o.parent) and o.text and o.text.replace("'", "") != o.target:
            return ItemId(o, by_target[o.parent][0], True, False, by_parent=True, ref_magazine=is_ref)

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


def match_parent_target(o: Item, parent, target, by_target: Dict[str, List[Item]], other_targets: Dict[str, List[Item]], followed_redirect, site) -> Tuple[Optional[ItemId], bool]:
    if parent and target:
        x = match_by_parent_target(o, parent, target, by_target, other_targets)
        if not x and target and not followed_redirect:
            if follow_redirect(o, site, True):
                followed_redirect = True
                x = match_by_parent_target(o, parent, target, by_target, other_targets)
        if not x and o.template == "StoryCite" and "(short story)" not in o.target:
            x = match_by_parent_target(o, parent, f"{target} (short story)", by_target, other_targets)
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


TEMPLATE_SUFFIXES = {
    "EncyclopediaCite": ["Star Wars Encyclopedia"],
    "StoryCite": ["short story"],
    "CWACite": ["comic"],
    "InsiderCite": ["Star Wars Insider", "article"],
}


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
        if "(" not in o.target and o.template in TEMPLATE_SUFFIXES:
            for i in TEMPLATE_SUFFIXES[o.template]:
                targets.append(f"{o.target} ({i})")
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
        if log and o.template != "TCW" and o.template != "Film":
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
        if log and o.template != "TCW" and o.template != "Film":
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
    old_versions = []
    for k, d in data.items():
        x = do_urls_match(url, o.template, d, replace_page)
        if x == 2 and o.original and "oldversion=1" in o.original:
            old_versions.append(d)
        elif x == 2:
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
    if old_versions:
        return ItemId(o, old_versions[-1], False, False)
    if partial_matches:
        return ItemId(o, partial_matches[0], False, False)
    return None
