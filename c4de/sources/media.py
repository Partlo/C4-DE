from itertools import chain
import re
from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional, Set


from c4de.common import sort_top_template, fix_redirects
from c4de.sources.domain import FullListData, PageComponents, SectionLeaf, Item, NewComponents, SectionComponents
from c4de.sources.index import build_date_and_ref, convert_date_str

MEDIA_STRUCTURE = {
    "Publisher Summary": "==Publisher's summary==",
    "Official Description": "==Official description==",
    "Opening Crawl": "==Opening crawl==",
    "Plot Summary": "==Plot summary==",
    "Contents": "==Contents==",
    "Gameplay": "==Gameplay==",
    "Development": "==Development==",
    "Release/Reception": "==Release and reception==",
    "Continuity": "==Continuity==",
    "Adaptations": "==Adaptations and tie-in media==",
    "Legacy": "==Legacy==",
    "Media": "==Media==",
    # "Issues": "===Issues===",
    # "Editions": "===Editions===",
    # "Episodes": "===Episodes===",
    # "Seasons": "===Seasons===",
    # "Cover gallery": "===Cover gallery===",
    # "Poster Gallery": "===Poster gallery===",
    # "Content Gallery": "===Content gallery===",
    # "Collections": "==Collections==",
    "Credits": "==Credits==",
    "Appearances": "==Appearances==",
    "Sources": "==Sources==",
    "References": "==Notes and references==",
    "Links": "==External links=="
}

SUBSECTIONS = {
    "Contents": ["Articles", "Departments", "Features"],
    "Development": ["Conception", "Production"],
    "Media": ["Issues", "Editions", "Episodes", "Seasons", "Cover gallery", "Poster gallery", "Content gallery", "Collections"]
}

DVDS = {
    "Ahsoka: The Complete First Season": ["Part One: Master and Apprentice", "Part Two: Toil and Trouble", "Part Three: Time to Fly", "Part Four: Fallen Jedi", "Part Five: Shadow Warrior", "Part Six: Far, Far Away", "Part Seven: Dreams and Madness", "Part Eight: The Jedi, the Witch, and the Warlord"],
    "Andor: The Complete First Season": ["Kassa (episode)", "That Would Be Me", "Reckoning (episode)", "Aldhani (episode)", "The Axe Forgets", "The Eye", "Announcement", "Narkina 5 (episode)", "Nobody's Listening!", "One Way Out", "Daughter of Ferrix", "Rix Road (episode)"],
    "LEGO Star Wars: The Freemaker Adventures – Complete Season One": ["A Hero Discovered", "The Mines of Graballa", "Zander's Joyride", "The Lost Treasure of Cloud City", "Peril on Kashyyyk", "Crossing Paths", "Race on Tatooine", "The Test", "The Kyber Saber Crystal Chase", "The Maker of Zoh", "Showdown on Hoth", "Duel of Destiny", "Return of the Kyber Saber"],
    "Obi-Wan Kenobi: The Complete Series": ["Part I", "Part II", "Part III", "Part IV", "Part V", "Part VI"],
    "Star Wars Rebels: Complete Season Four": ["Star Wars Rebels: Heroes of Mandalore", "In the Name of the Rebellion", "The Occupation", "Flight of the Defender", "Kindred", "Crawler Commandeers", "Rebel Assault", "Jedi Night", "DUME", "Wolves and a Door", "A World Between Worlds", "A Fool's Hope", "Family Reunion – and Farewell"],
    "Star Wars Rebels: Complete Season One": ["Star Wars Rebels: Spark of Rebellion", "Droids in Distress", "Fighter Flight", "Rise of the Old Masters", "Breaking Ranks", "Out of Darkness", "Empire Day (episode)", "Gathering Forces", "Path of the Jedi", "Idiot's Array (episode)", "Vision of Hope", "Call to Action", "Rebel Resolve", "Fire Across the Galaxy"],
    "Star Wars Rebels: Complete Season Three": ["Star Wars Rebels: Steps Into Shadow", "The Holocrons of Fate", "The Antilles Extraction", "Hera's Heroes", "The Last Battle", "Imperial Supercommandos", "Iron Squadron (episode)", "The Wynkahthu Job", "An Inside Man", "Visions and Voices", "Ghosts of Geonosis", "Warhead (episode)", "Trials of the Darksaber", "Legacy of Mandalore", "Through Imperial Eyes", "Secret Cargo", "Double Agent Droid", "Twin Suns (episode)", "Zero Hour"],
    "Star Wars Rebels: Complete Season Two": ["Star Wars Rebels: The Siege of Lothal", "The Lost Commanders", "Relics of the Old Republic", "Always Two There Are", "Brothers of the Broken Horn", "Wings of the Master", "Blood Sisters", "Stealth Strike", "The Future of the Force", "Legacy (episode)", "A Princess on Lothal", "The Protector of Concord Dawn", "Legends of the Lasat", "The Call", "Homecoming", "The Honorable Ones", "Shroud of Darkness", "The Forgotten Droid", "The Mystery of Chopper Base", "Twilight of the Apprentice"],
    "Star Wars Resistance: Complete Season One": ["The Recruit", "The Triple Dark", "Fuel for the Fire", "The High Tower", "The Children from Tehar", "Signal from Sector Six", "Synara's Score", "The Platform Classic", "Secrets and Holograms", "Station Theta Black (episode)", "Bibo (episode)", "Dangerous Business", "The Doza Dilemma", "The First Order Occupation", "The New Trooper", "The Core Problem", "The Disappeared", "Descent (episode)", "No Escape: Part 1", "No Escape: Part 2"],
    "Star Wars: The Clone Wars The Complete Season Five": ["Revival (episode)", "A War on Two Fronts", "Front Runners", "The Soft War", "Tipping Points", "The Gathering (episode)", "A Test of Strength", "Bound for Rescue", "A Necessary Bond", "Secret Weapons", "A Sunny Day in the Void", "Missing in Action", "Point of No Return (The Clone Wars)", "Eminence (episode)", "Shades of Reason", "The Lawless", "Sabotage (episode)", "The Jedi Who Knew Too Much", "To Catch a Jedi", "The Wrong Jedi"],
    "Star Wars: The Clone Wars The Complete Season Four": ["Water War", "Gungan Attack", "Prisoners", "Shadow Warrior", "Mercy Mission (episode)", "Nomad Droids", "Darkness on Umbara", "The General (episode)", "Plan of Dissent", "Carnage of Krell", "Kidnapped", "Slaves of the Republic", "Escape from Kadavo", "A Friend in Need", "Deception", "Friends and Enemies", "The Box", "Crisis on Naboo", "Massacre", "Bounty (episode)", "Brothers (episode)", "Revenge (episode)"],
    "Star Wars: The Clone Wars The Complete Season One": ["Ambush", "Rising Malevolence", "Shadow of Malevolence", "Destroy Malevolence", "Rookies (episode)", "Downfall of a Droid", "Duel of the Droids", "Bombad Jedi", "Cloak of Darkness", "Lair of Grievous", "Dooku Captured", "The Gungan General", "Jedi Crash", "Defenders of Peace", "Trespass", "The Hidden Enemy", "Blue Shadow Virus (episode)", "Mystery of a Thousand Moons", "Storm Over Ryloth", "Innocents of Ryloth", "Liberty on Ryloth", "Hostage Crisis"],
    "Star Wars: The Clone Wars The Complete Season Three": ["Clone Cadets", "ARC Troopers (episode)", "Supply Lines", "Sphere of Influence", "Corruption (episode)", "The Academy", "Assassin (episode)", "Evil Plans", "Hunt for Ziro", "Heroes on Both Sides", "Pursuit of Peace", "Nightsisters (episode)", "Monster", "Witches of the Mist", "Overlords", "Altar of Mortis (episode)", "Ghosts of Mortis", "The Citadel (episode)", "Counterattack", "Citadel Rescue", "Padawan Lost", "Wookiee Hunt"],
    "Star Wars: The Clone Wars The Complete Season Two": ["Holocron Heist", "Cargo of Doom", "Children of the Force", "Senate Spy", "Landing at Point Rain", "Weapons Factory", "Legacy of Terror", "Brain Invaders", "Grievous Intrigue", "The Deserter", "Lightsaber Lost", "The Mandalore Plot", "Voyage of Temptation", "Duchess of Mandalore", "Senate Murders", "Cat and Mouse", "Bounty Hunters (episode)", "The Zillo Beast", "The Zillo Beast Strikes Back", "Death Trap", "R2 Come Home", "Lethal Trackdown"],
    "Star Wars: The Clone Wars – The Lost Missions": ["The Unknown", "Conspiracy", "Fugitive", "Orders (episode)", "An Old Friend", "The Rise of Clovis", "Crisis at the Heart", "The Disappeared, Part I", "The Disappeared, Part II", "The Lost One", "Voices", "Destiny (The Clone Wars)", "Sacrifice (episode)"],
    "Star Wars: The Clone Wars: A Galaxy Divided": ["Ambush", "Rising Malevolence", "Shadow of Malevolence", "Destroy Malevolence", "Downfall of a Droid"],
    "Star Wars: The Clone Wars: Clone Commandos": ["Rookies (episode)", "Storm Over Ryloth", "Innocents of Ryloth", "Liberty on Ryloth"],
    "Star Wars: The Clone Wars: Darth Maul Returns": ["Massacre", "Bounty (episode)", "Brothers (episode)", "Revenge (episode)"],
    "Star Wars: The Clone Wars 3-Pack": ["Ambush", "Rising Malevolence", "Shadow of Malevolence", "Destroy Malevolence", "Downfall of a Droid", "Rookies (episode)", "Storm Over Ryloth", "Innocents of Ryloth", "Liberty on Ryloth", "Massacre", "Bounty (episode)", "Brothers (episode)", "Revenge (episode)"],
    "The Mandalorian: The Complete First Season": ["Chapter 1: The Mandalorian", "Chapter 2: The Child", "Chapter 3: The Sin", "Chapter 4: Sanctuary", "Chapter 5: The Gunslinger", "Chapter 6: The Prisoner", "Chapter 7: The Reckoning", "Chapter 8: Redemption"],
    "The Mandalorian: The Complete Second Season": ["Chapter 9: The Marshal", "Chapter 10: The Passenger", "Chapter 11: The Heiress", "Chapter 12: The Siege", "Chapter 13: The Jedi", "Chapter 14: The Tragedy", "Chapter 15: The Believer", "Chapter 16: The Rescue"],
    "The Mandalorian: The Complete Third Season": ["Chapter 17: The Apostate", "Chapter 18: The Mines of Mandalore", "Chapter 19: The Convert", "Chapter 20: The Foundling", "Chapter 21: The Pirate", "Chapter 22: Guns for Hire", "Chapter 23: The Spies", "Chapter 24: The Return"],
    "The Nightsisters Trilogy: Feature-Length Cut": ["Nightsisters (episode)", "Monster", "Witches of the Mist"],
}
DVDS["Star Wars: The Clone Wars 3-Pack"] = [chain.from_iterable(DVDS[f"Star Wars: The Clone Wars The Complete Season {x}"] for x in ["One", "Two", "Three", "Four", "Five"])]


def remove(s, x: list):
    y = f"{s}"
    for i in x:
        y = y.replace(f"{i} ", "")
    return y


def match_header(header: str, infobox):
    i = (infobox or '').replace("_", " ").lower()
    h = header.lower().strip().replace("'", "").replace("-", " ")
    if i == "book series" and h == "novels":
        return "Contents"
    elif i and i.startswith("television") and remove(h, ["official"]) == "description":
        return "Official Description"

    if h in ["behind the scenes", "main characters", "characters", "major characters"]:
        return "FLAG"
    elif h == "sources":
        return "Sources"
    elif h == "external links":
        return "Links"
    elif h == "references" or h.startswith("notes and ref") or h.startswith("notes an ref"):
        return "References"
    elif h == "collections":
        return "Collections"

    if h in ["plot summary", "synopsis", "story"]:
        return "Plot Summary"
    elif remove(h, ["publisher", "publishers", "publishing", "official", "product", "manufacturers", "publication"]) in [
        "summary", "description", "from the publisher", "back cover summary",
    ]:
        return "Publisher Summary"
    elif h in ["opening crawl", "opening crawls"]:
        return "Opening Crawl"
    elif h in ["gameplay"]:
        return "Gameplay"
    elif h in ["development", "production", "conception"]:
        return "Development"
    elif h in ["continuity"]:
        return "Continuity"
    elif h in ["release", "reception", "release and reception", "release & reception", "critical reception", "critical reaction"]:
        return "Release/Reception"
    elif h in ["legacy", "metaseries"]:
        return "Legacy"
    elif h in ["credits", "cast"]:
        return "Credits"
    elif h in ["appearances"]:
        return "Appearances"
    elif h in ["adaptation", "adaptations", "adaption", "adaptions", "tie in media", "merchandising", "merchandise",
               "merchandise and tie in media"]:
        return "Adaptations"
    elif h in ["cover gallery", "cover art"]:
        return "Cover gallery"
    elif h in ["posters", "poster gallery"]:
        return "Poster gallery"
    elif h in ["content gallery", "media gallery"]:
        return "Content gallery"
    elif h in ["issues"]:
        return "Issues"
    elif h in ["edition", "editions"]:
        return "Editions"
    elif h in ["seasons"]:
        return "Seasons"
    elif h in ["episodes", "videos"]:
        return "Episodes"
    elif h in ["media"]:
        return "Media"

    if h in ["content", "contents", "tracks", "track list", "track listing", "comic strip", "features",
             "stories", "short stories", "other stories", "articles", "adventures",
             "collects", "collected issues", "collected stories", "collected comic strips"]:
        return "Contents"
    return None


def check_for_cover_image(item: SectionLeaf, valid: dict, images: list):
    to_remove = []
    for i in range(len(item.lines)):
        if item.lines[i].startswith("[[File:") and re.search("\[\[File:.*?\|.*?[Cc]over.*?]]", item.lines[i]):
            if "Cover gallery" not in valid:
                images.append(re.sub("^.*?\[\[([Ff]ile:.*?)[|\]].*?$", "\\1", item.lines[i]).replace(" ", "_"))
                to_remove.append(i)
            else:
                print(f"Possible false positive: {item.lines[i]}")
    if to_remove:
        item.lines = [ln for i, ln in enumerate(item.lines)]


def get_listings(title, appearances, sources):
    return (appearances.target.get(title) or sources.target.get(title)) or []


def rearrange_sections(target: Page, results: PageComponents, valid: Dict[str, List[SectionLeaf]],
                       appearances: FullListData, sources: FullListData, novel: Page):
    if not results.real:
        return {k: v[0] for k, v in valid.items()}

    title = target.title()
    sections = {}
    if results.infobox == "audiobook":
        if "Plot Summary" not in valid:
            sections["Plot Summary"] = SectionLeaf("Plot Summary", "==Plot summary==", 0, 2)
            tx = ""
            if "(" in title:
                tx = re.sub("^(.*?)( \(.*?\))$", "|''\\1''\\2", title)
            sections["Plot Summary"].lines = [f"{{{{Plot-link|{title}{tx}}}}}"]
        if "Appearances" not in valid and "(" in title and "(abridged" not in title and novel:
            sections["Appearances"] = SectionLeaf("Appearances", "==Appearances==", 0, 2)
            if novel.exists() and not novel.isRedirectPage() and "Plot summary" in novel.get() and "<onlyinclude>\n{{App" not in novel.get():
                sections["Appearances"].lines = [f"{{{{:{title.split(' (')[0]}}}}}"]
            else:
                sections["Appearances"].lines = ["{{MissingAppFlag}}"]

    has_summary = False
    images = []
    for key, items in valid.items():
        if key == "Publisher Summary" or key == "Official Description":
            if has_summary:
                items[0].flag = True
            has_summary = True

        items = remap_sections(key, items, valid, sections, images)
        if not items:
            continue

        if key in MEDIA_STRUCTURE and key in sections:
            if len(items) > 0:
                items[0].lines = combine_sections(items)
            if len(items[0].lines) > 0 and len(sections[key].lines) > 0:
                sections[key].lines.append("")
                sections[key].lines += items[0].lines
            for sx, subsection in items[0].subsections.items():
                if sx in sections[key].subsections:
                    print(f"Unexpected state: multiple {sx} subsections for {key}")
                sections[key].subsections[sx] = subsection
            continue
        elif key in MEDIA_STRUCTURE:
            sections[key] = items[0]
            continue

        for parent, children in SUBSECTIONS.items():
            if key in children:
                if parent not in sections:
                    sections[parent] = SectionLeaf(parent, f"=={parent}==", items[0].num, 2)
                kx = f"{key}"
                if results.infobox in ["board game", "card game"] and "Gallery" in kx:
                    kx = "Content Gallery"
                if len(items) > 1:
                    print(f"Unexpected state: multiple sections found for {kx} header")
                sections[parent].subsections[kx] = combine_and_demote_sections(items, key, kx)
                sections[parent].subsections[kx].master_num = children.index(key)

    if results.infobox == "television episode":
        current = targets(results.collections)
        links, refs, contents = set(), {}, {}
        for k, v in DVDS.items():
            if title in v and k not in current:
                x = get_listings(k, appearances, sources)
                if x:
                    results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents))
                else:
                    print(f"Unknown state: {k} not found in Sources")
    elif results.infobox == "magazine article" or results.infobox == "short story":
        drx = re.search("\|(publish date|publication date|first aired|airdate|start date|first date|release date|released|published)=.*?(<ref name ?= ?\".*?\")/?>", target.get())
        date_ref = drx.group(2) + " />" if drx else None
        current = targets(results.collections)
        added = []
        links, refs, contents = set(), {}, {}
        for item in get_listings(title, appearances, sources):
            if item.parent and item.parent not in current:
                x = get_listings(item.parent, appearances, sources)
                if x:
                    results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents, date_ref))
                    added.append(item.parent)
                else:
                    print(f"Unknown state: {item.parent} not found in Sources")
        current += added

        to_remove = []
        for i in range(len(results.src.items)):
            if results.src.items[i].target and results.src.items[i].target in current:
                print(f"Removing Collections listing from Sources (new={results.src.items[i].target in added})")
                to_remove.append(i)
        if to_remove:
            results.src.items = [x for i, x in enumerate(results.src.items) if i not in to_remove]

    if results.collections.items:
        if "Media" not in sections:
            sections["Media"] = SectionLeaf("Media", "==Media==", 0, 2)
        if "Collections" not in sections["Media"].subsections:
            sections["Media"].subsections["Collections"] = SectionLeaf("Collections", "===Collections===", 0, 2)
            sections["Media"].subsections["Collections"].master_num = SUBSECTIONS["Media"].index("Collections")
    if images:
        if "Media" not in sections:
            sections["Media"] = SectionLeaf("Media", "==Media==", 0, 2)
        if "Cover gallery" not in sections["Media"].subsections:
            sections["Media"].subsections["Cover gallery"] = SectionLeaf("Cover gallery", "===Cover gallery===", 0, 2)
            sections["Media"].subsections["Cover gallery"].master_num = SUBSECTIONS["Media"].index("Cover gallery")
        sections["Media"].subsections["Cover gallery"].lines += images

    return sections


def copy_listing(x: Item, site, links: set, refs: dict, contents: dict, date_ref=None):
    nx = x.copy()
    if date_ref:
        date_str, _ = convert_date_str(nx.date, links)
    else:
        rn = nx.target.replace("(", "").replace(")", "").replace("'", "")
        date_str, date_ref = build_date_and_ref(nx, site, links, refs, contents, ref_name=rn)
    if date_str:
        nx.extra = f" &mdash; {date_str}{date_ref}"
    return nx


def targets(s: SectionComponents):
    return [i.target for i in s.items]


def remap_sections(key, items: List[SectionLeaf], valid: Dict[str, List[SectionLeaf]], sections: Dict[str, SectionLeaf],
                   images: list):
    new_items = []
    for it in items:
        check_for_cover_image(it, valid, images)
        if key == "Plot Summary":
            if any("{{opening" in ln.lower() for ln in it.lines):
                crawl, other, ct = [], [], 0
                for ln in it.lines:
                    if "{{opening" in ln.lower() or (crawl and ct != 0):
                        crawl.append(ln)
                        ct += (ln.count("{{") - ln.count("}}"))
                    else:
                        other.append(ln)
                it.lines = other
                if len(other) == 0 and not it.subsections:
                    it.remove = True
                add_correct_section("Opening Crawl", "==Opening crawl==", valid, sections, crawl)
        # if key == "Release/Reception":
        #     to_pop = set()
        #     for sx, sk in it.subsections.items():
        #         if sx.startswith("Merchandise") or "tie-ins" in sx:
        #             if "Adaptations" in valid:
        #                 valid["Adaptations"][0].lines += sk.lines
        #             elif "Adaptations" not in sections:
        #                 sections["Adaptations"] = SectionLeaf("Adaptations", MEDIA_STRUCTURE["Adaptations"], 0, 2, sk.lines)
        #             else:
        #                 sections["Adaptations"].lines += sk.lines
        #             to_pop.add(sx)
        #     for x in to_pop:
        #         it.subsections.pop(x)

        if not it.remove:
            new_items.append(it)
    return new_items


def add_correct_section(key, header, valid: dict, sections: dict, lines):
    if key in sections:
        sections[key].lines.append("")
        sections[key].lines += lines
    elif key in valid:
        valid[key][0].lines.append("")
        valid[key][0].lines += lines
    else:
        sections[key] = SectionLeaf(key, header, 0, 2)
        sections[key].lines = lines


def combine_sections(items: List[SectionLeaf], sub=False):
    lines = [*items[0].lines]
    for ix in items[1:]:
        lines.append("")
        lines += ix.lines
        if sub:
            for sx, si in ix.subsections.items():
                lines.append("")
                lines.append(si.header_line)
                lines += si.lines
    return lines


def combine_and_demote_sections(items, key, kx):
    new_text = []
    for i in items:
        for ln in i.lines:
            if ln.startswith("=="):
                new_text.append(f"={ln}=")
            else:
                new_text.append(ln)
        for sx, ss in i.subsections.items():
            if key != "Editions":
                new_text.append("")
                new_text.append(f"===={sx}====")
            for ln in ss.lines:
                if ln.startswith("=="):
                    new_text.append(f"={ln}=")
                elif not ln and key == "Editions":
                    pass
                else:
                    new_text.append(ln)
    items[0].lines = new_text
    items[0].level = 3
    items[0].name = kx
    items[0].header_line = f"==={kx}==="
    return items[0]


ITALICIZE = ["book", "audiobook", "comic series", "comic collection", "comic story arc", "graphic novel", "reference book"]
ISSUE = ["magazine", "comic", "comic book"]
QUOTES = ["magazine article", "magazine department", "short story", "comic story", "rpg adventure", "comic strip"]
ADD_REF = ["reference book", "magazine", "magazine article", "magazine department", "soundtrack", "magazine series",
           "toy line"]


def simplify(s):
    return s.replace("–", "-").replace("—", "-").replace("&mdash;", "-").replace("&ndash;", "-")


def prepare_media_infobox_and_intro(page: Page, results: PageComponents, comp: NewComponents, redirects, disambigs,
                                    remap, appearances: FullListData, sources: FullListData) -> Tuple[List[str], str]:
    fmt, simple_fmt = None, None
    if results.infobox == "audiobook":
        fmt = f"''{page.title().split(' (')[0]}''"
    elif page.title() in appearances.target:
        if not appearances.target[page.title()][0].template:
            fmt = appearances.target[page.title()][0].original
    elif page.title() in sources.target:
        if not sources.target[page.title()][0].template:
            fmt = sources.target[page.title()][0].original
    if not fmt and results.infobox:
        if results.infobox in ISSUE:
            fmt = re.sub("^(.*?)( \([0-9]+\))? ([0-9]+)( \(.*?\))?$", "<b>''\\1''\\2 \\3<b>", page.title())
        if results.infobox in ITALICIZE or (fmt and "''" in fmt):
            fmt = "<b>''" + re.sub(" \(.*?\)$", "", page.title()) + "''<b>"
        if results.infobox in QUOTES:
            fmt = "\"<b>" + re.sub(" \(.*?\)$", "", page.title()) + "<b>\""
    if fmt:
        if "|" in fmt:
            fmt = re.sub("^.*\[\[.*?\|(.*?)]].*?$", "\\1", fmt)
        elif "[[" in fmt:
            fmt = re.sub("^('')?\[\[(.*?)]]('')?$", "\\1\\2\\3", fmt)
        simple_fmt = fmt.replace("<b>", "")
        fmt = re.sub("^(.*?) \([0-9]+\) ([0-9]+)$", "\\1 \\2", fmt.replace("<b>", "'''"))

    text = fix_redirects(redirects, results.before.strip(), "Intro", disambigs, remap,
                         appearances=appearances.target, sources=sources.target)

    pieces = []
    image = ""
    ct = 0
    publisher_listing = set()
    infobox_found, infobox_done, title_found = False, False, False
    for ln in text.splitlines():
        if "{{top" in ln.lower():
            ln = sort_top_template(ln, results.infobox in ADD_REF)
        elif f"{{{{{results.infobox}" in ln.lower() or f"{{{{{results.infobox.replace(' ', '_')}" in ln.lower():
            infobox_found = True
        elif ln.startswith("|title=") and simple_fmt:
            if "''" in simple_fmt and "''" not in ln:
                ln = f"|title={simple_fmt}"
            elif "''" in ln and "''" not in simple_fmt:
                ln = f"|title={simple_fmt}"
        elif "|series=" in ln:
            x = re.search("series='*\[\[(.*?)(\|.*?)?]]'*", ln)
            if x and x.group(1) in appearances.target:
                ns = appearances.target[x.group(1)][0].original.replace(" comic adaptation]]", "]]")
                ln = ln.replace(x.group(0), f"series={ns}")
        elif "|preceded by" in ln or "|followed by" in ln or "|prev" in ln or "|next" in ln:
            if results.infobox == "television episode":
                ln = re.sub("\|(preceded by|followed by|prev|next) ?= ?[\"']*(\[\[.*?]])[\"']*",
                            '|\\1="\\2"', ln)
            else:
                # TODO: check appearances/sources and use correct formatting
                ln = re.sub("\|(preceded by|followed by|prev|next) ?= ?'*\[\[(.*?)( \([0-9]+\))? ([0-9]+)(\|.*?)?]]'*",
                            "|\\1=[[\\2\\3 \\4|''\\2'' \\4]]", ln)

        if infobox_found:
            ct += (ln.count("{") - ln.count("}"))
            if ct == 0:
                infobox_found = False
                infobox_done = True
        if infobox_done and not title_found and fmt and fmt not in ln and "'''" in ln:
            if ln.count("'''") > 2:
                ft = False
                for x, y in re.findall("(\"?'''+\"?(.*?)\"?'''+\"?)", ln):
                    if simplify(y).lower() == simplify(page.title()).lower():
                        ln = ln.replace(x, fmt)
                        ft = True
                if not ft:
                    print(f"Multiple bolded titles in intro, but no close match; cannot replace title")
            else:
                ln = re.sub("\"?'''+\"?(.*?)\"?'''+\"?", fmt, ln)
            title_found = True
        if "{{Marvel|url=comics/" in ln or "{{DarkHorse|url=Comics/" in ln or "{{IDW|url=product/" in ln:
            x = re.search("(\{\{(DarkHorse|Marvel|IDW)\|url=((product/|[Cc]omics/(?!Preview)).*)\|.*?}})", ln)
            print(f"Found publisher listing: {x}")
            if x:
                publisher_listing.add((x[0], x[1], x[2]))

        if ln.startswith("|image="):
            x = re.search("\|image=\[*([Ff]ile:.*?)[|\n\]]", ln)
            if x:
                image = x.group(1).replace("file:", "File").replace(" ", "_")

        if "{{redlink" in ln:
            count = get_redlink_count(page)
            if count <= 5:
                print(f"{page.title()} has {count} redlinks; removing Redlink template")
                ln = re.sub("\{\{[Rr]edlink.*?}}", "", ln)
                if not ln.strip():
                    continue

        pieces.append(ln)
    for p, template, url in publisher_listing:
        if url in comp.links.text:
            continue
        comp.links.text = f"*{p}\n{comp.links.text}"
        comp.links.rows += 1

    return pieces, image


def get_redlink_count(page: Page):
    count = 0
    for x in page.linkedPages():
        if not x.exists():
            count += 1
    return count

# TODO: italicize publisher's summary
# TODO: split Appearances subsections by length

# TODO: flag pages with both Contents and Plot Summary
# TODO: flag Media sections with no subcats
# TODO: flag articles with multiple sections for the same master header for review (Star Wars Gamer 7)
# TODO: flag book collections/etc. with missing Contents sections

# TODO: use Masterlist formatting for Contents sections
# TODO: Fix redirects in the Contents section without preserving the original pipelink, UNLESS it's a department
# TODO: convert "Introduction" to a Contents bullet

# TODO - Advanced
# TODO: tag issues without DH & Marvel
# TODO: parse and standardize ISBN lines in Editions
# TODO: build prettytable for issues sections?
