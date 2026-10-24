from pywikibot import Page
import re

from c4de.sources.domain import Item, ItemId, FullListData

EXPANSION = {
    "Star Wars Technical Journal": [
        "Star Wars Technical Journal of the Planet Tatooine", "Star Wars Technical Journal of the Imperial Forces", "Star Wars Technical Journal of the Rebel Forces"
    ],
    "The Clone Wars: Grievous Attacks!": [
        "Rookies (short story)", "Downfall of a Droid (short story)", "Lair of Grievous (short story)"
    ],
    "Path of the Jedi: A Star Wars Rebels Cinestory Comic": [
        "Call to Action (comic story)", "Empire Day (comic story)", "Gathering Forces (comic story)",
        "Path of the Jedi (comic story)", "Vision of Hope (comic story)"
    ],
    "Maul: A Star Wars Rebels Cinestory Comic": [
        "Twilight of the Apprentice (comic story)", "The Holocrons of Fate (comic story)", "Visions & Voices (comic story)", "Twin Suns (comic story)"
    ],
    "Young Jedi Adventures: My First Comic Reader Level 1": [
        "¡Que Empiece el Entrenamiento!", "Una Nueva Perspectiva", "Pord Recibe una Lección",
        "La Visita del Maestro Yoda", "Entrenando Con Remotos", "La Carrera Contra Taborr"
    ]
}

MANGA = {
    "Star Wars Rebels (webcomic)": {
        "Star Wars Rebels, Vol. 1": ["Star Wars Rebels: Spark of Rebellion"],
        "Star Wars Rebels, Vol. 2": ["Rise of the Old Masters", "Empire Day (episode)", "Gathering Forces"],
        "Star Wars Rebels, Vol. 3": ["Path of the Jedi", "Call to Action", "Rebel Resolve", "Fire Across the Galaxy"]
    },
    "Star Wars: The Mandalorian: The Manga": {
        "The Mandalorian: The Manga, Vol. 1": ["Chapter 1: The Mandalorian"],
        "The Mandalorian: The Manga, Vol. 2": ["Chapter 2: The Child", "Chapter 3: The Sin"],
        "The Mandalorian: The Manga, Vol. 3": ["Chapter 4: Sanctuary", "Chapter 5: The Gunslinger", "Chapter 6: The Prisoner"],
        "The Mandalorian: The Manga, Vol. 4": ["Chapter 6: The Prisoner", "Chapter 7: The Reckoning", "Chapter 8: Redemption"],
    }
}


TEMP_REMAP = {
    "Empire Day (episode)": "Empire Day (comic story)",
    "Gathering Forces": "Gathering Forces (comic story)",
    "Path of the Jedi": "Path of the Jedi (comic story)",
    "Vision of Hope": "Vision of Hope (comic story)",
    "Call to Action": "Call to Action (comic story)",
    "Rookies (episode)": "Rookies (short story)",
    "Downfall of a Droid": "Downfall of a Droid (short story)",
    "Duel of the Droids": "Downfall of a Droid (short story)",
    "Lair of Grievous": "Lair of Grievous (short story)"
}
VALID_COLLECTIONS = ["MagazineArticle", "ComicStory", "ShortStory", "Adventure"]


def expand_listing(target: str, o: Item, data: FullListData, expanded: int):
    x = data.target[target][0].copy()
    x.index = o.index
    x.extra = o.extra
    if expanded:
        x.extra = re.sub(r"\{\{1stm.*?}}", "{{Mo}}", x.extra).strip()
        x.extra = re.sub(r"\{\{1st.*?}}", "", x.extra).strip()
    x.extra_date = o.extra_date
    return ItemId(x, data.target[target][0], False)


def handle_expansion(d: ItemId, o: Item, page: Page, page_links: list, data, already, any_expanded, unexpanded, other_extra):
    if not d:
        return False, unexpanded, other_extra

    to_check = {}
    if d.master.target and d.master.target in EXPANSION:
        to_check = {d.master.target: EXPANSION[d.master.target]}
    elif d.master.target and d.master.target.replace(" (trade paperback)", "") in MANGA:
        to_check = MANGA[d.master.target.replace(" (trade paperback)", "")]

    elif d.master.from_extra and not d.master.is_reprint and not d.master.non_canon and not d.master.collection_type:
        other_extra += 1

    should_skip = False
    if to_check:
        if not page_links:
            for p in page.getReferences(namespaces=0):
                if p.title() in TEMP_REMAP:
                    if TEMP_REMAP[p.title()] not in page_links:
                        page_links.append(TEMP_REMAP[p.title()])
                page_links.append(p.title())

        expanded, existing = 0, 0
        for vol, parts in to_check.items():
            if any(p in already for p in parts):
                existing += 1
            else:
                for p in parts:
                    if p in page_links:
                        any_expanded.append(expand_listing(p, o, data, expanded))
                        expanded += 1
        if expanded or existing:
            print(f"Expanded series/arc listing of {d.master.target} to {expanded} new / {existing} existing")
            should_skip = True
        else:
            print(f"Unable to expand series/arc listing of {d.master.target} on {page.title()}")
            unexpanded += 1
            if d and d.master.target and d.master.target in EXPANSION:
                should_skip = True
    return should_skip, unexpanded, other_extra
