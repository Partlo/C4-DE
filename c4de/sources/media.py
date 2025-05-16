from itertools import chain
import re

from c4de.sources.external import is_commercial
from pywikibot import Page
from typing import List, Tuple, Union, Dict, Optional, Set


from c4de.common import sort_top_template, fix_redirects
from c4de.sources.domain import FullListData, PageComponents, SectionLeaf, Item, SectionComponents

NEW_APP_TEMPLATE = """{{IncompleteApp}}
{{App
|characters=
|organisms=
|droids=
|events=
|locations=
|organizations=
|species=
|vehicles=
|technology=
|miscellanea=
}}""".splitlines()

COVER_GALLERY_MEDIA = ["ComicBook", "ComicCollection", "Book", "ReferenceBook", "MagazineIssue", "GraphicNovel", "VideoGame"]
REMOVE_LINKS = ["Opening Crawl", "Publisher Summary", "Official Description"]

MEDIA_STRUCTURE = {
    "Publisher Summary": "==Publisher's summary==",
    "Official Description": "==Official description==",
    "Opening Crawl": "==Opening crawl==",
    "Plot Summary": "==Plot summary==",
    "Contents": "==Contents==",
    "Card List": "==Card list==",
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
    "Media": ["Issues", "Editions", "Episodes", "Seasons", "Cover gallery", "Poster gallery", "Content gallery", "Collections"],
    "Appearances": ["Out of universe appearances"]
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

PUBLISHERS = {
    "Jedi Quest 1": "{{DarkHorse|url=Comics/99-309/Star-Wars-Jedi-Quest-1-of-4|text=Star Wars: Jedi Quest #1 (of 4)}}",
    "Jedi Quest 2": "{{DarkHorse|url=Comics/99-314/Star-Wars-Jedi-Quest-2-of-4|text=Star Wars: Jedi Quest #2 (of 4)}}",
    "Jedi Quest 3": "{{DarkHorse|url=Comics/99-321/Star-Wars-Jedi-Quest-3-of-4|text=Star Wars: Jedi Quest #3 (of 4)}}",
    "Jedi Quest 4": "{{DarkHorse|url=Comics/99-323/Star-Wars-Jedi-Quest-4-of-4|text=Star Wars: Jedi Quest #4 (of 4)}}",
    "Jedi — The Dark Side 2": "{{DarkHorse|url=Comics/18-034/Star-Wars-Jedi-The-Dark-Side-2|text=Star Wars: Jedi - The Dark Side #2}}",
    "Jedi — The Dark Side 3": "{{DarkHorse|url=Comics/18-035/Star-Wars-Jedi-The-Dark-Side-3|text=Star Wars: Jedi - The Dark Side #3}}",
    "Jedi — The Dark Side 4": "{{DarkHorse|url=Comics/18-036/Star-Wars-Jedi-The-Dark-Side-4|text=Star Wars: Jedi - The Dark Side #4}}",
    "Jedi — The Dark Side 5": "{{DarkHorse|url=Comics/18-037/Star-Wars-Jedi-The-Dark-Side-5|text=Star Wars: Jedi - The Dark Side #5}}",
    "Knight Errant: Aflame 4": "{{DarkHorse|url=Comics/17-159/Star-Wars-Knight-Errant-4-Aflame-part-4|text=Star Wars: Knight Errant #4 - Aflame part 4}}",
    "Knight Errant: Aflame 5": "{{DarkHorse|url=Comics/17-160/Star-Wars-Knight-Errant-Aflame-5|text=Star Wars: Knight Errant - Aflame #5}}",
    "Knight Errant: Escape 2": "{{DarkHorse|url=Comics/18-904/Star-Wars-Knight-Errant-Escape-2|text=Star Wars: Knight Errant - Escape #2}}",
    "Knight Errant: Escape 3": "{{DarkHorse|url=Comics/18-905/Star-Wars-Knight-Errant-Escape-3|text=Star Wars: Knight Errant - Escape #3}}",
    "Knights of the Old Republic 24": "{{DarkHorse|url=Comics/14-777/Star-Wars-Knights-of-the-Old-Republic-24--Knights-of-Suffering-part-3|text=Star Wars: Knights of the Old Republic #24--Knights of Suffering part 3}}",
    "Knights of the Old Republic 25": "{{DarkHorse|url=Comics/14-912/Star-Wars-Knights-of-the-Old-Republic-25--Vector-part-1|text=Star Wars: Knights of the Old Republic #25--Vector part 1}}",
    "Knights of the Old Republic 26": "{{DarkHorse|url=Comics/14-913/Star-Wars-Knights-of-the-Old-Republic-26-Vector-part-2|text=Star Wars: Knights of the Old Republic #26-Vector part 2}}",
    "Knights of the Old Republic 27": "{{DarkHorse|url=Comics/14-914/Star-Wars-Knights-of-the-Old-Republic-27--Vector-part-3|text=Star Wars: Knights of the Old Republic #27--Vector part 3}}",
    "Knights of the Old Republic 28": "{{DarkHorse|url=Comics/15-002/Star-Wars-Knights-of-the-Old-Republic-28--Vector-part-4|text=Star Wars: Knights of the Old Republic #28--Vector part 4}}",
    "Knights of the Old Republic 29": "{{DarkHorse|url=Comics/15-003/Star-Wars-Knights-of-the-Old-Republic-29--Exalted-part-1|text=Star Wars: Knights of the Old Republic #29--Exalted part 1}}",
    "Knights of the Old Republic 30": "{{DarkHorse|url=Comics/15-004/Star-Wars-Knights-of-the-Old-Republic-30--Exalted-part-2|text=Star Wars: Knights of the Old Republic #30--Exalted part 2}}",
    "Knights of the Old Republic 31": "{{DarkHorse|url=Comics/15-494/Star-Wars-Knights-of-the-Old-Republic-31--Turnabout|text=Star Wars: Knights of the Old Republic #31--Turnabout}}",
    "Knights of the Old Republic 32": "{{DarkHorse|url=Comics/15-495/Star-Wars-Knights-of-the-Old-Republic-32--Vindication-part-1|text=Star Wars: Knights of the Old Republic #32--Vindication part 1}}",
    "Knights of the Old Republic 33": "{{DarkHorse|url=Comics/15-496/Star-Wars-Knights-of-the-Old-Republic-33--Vindication-pt-2|text=Star Wars: Knights of the Old Republic #33--Vindication pt. 2}}",
    "Knights of the Old Republic 34": "{{DarkHorse|url=Comics/15-497/Star-Wars-Knights-of-the-Old-Republic-34--Vindication-part-3|text=Star Wars: Knights of the Old Republic #34--Vindication part 3}}",
    "Knights of the Old Republic 35": "{{DarkHorse|url=Comics/15-732/Star-Wars-Knights-of-the-Old-Republic-35--Vindication-part-4|text=Star Wars: Knights of the Old Republic #35--Vindication part 4}}",
    "Knights of the Old Republic 36": "{{DarkHorse|url=Comics/15-785/Star-Wars-Knights-of-the-Old-Republic-36--Prophet-Motive-part-1|text=Star Wars: Knights of the Old Republic #36--Prophet Motive part 1}}",
    "Knights of the Old Republic 37": "{{DarkHorse|url=Comics/15-786/Star-Wars-Knights-of-the-Old-Republic-37--Prophet-Motive-part-2-of-2|text=Star Wars: Knights of the Old Republic #37--Prophet Motive part 2 (of 2)}}",
    "Knights of the Old Republic 38": "{{DarkHorse|url=Comics/15-787/Star-Wars-Knights-of-the-Old-Republic-38----Faithful-Execution|text=Star Wars: Knights of the Old Republic #38 -- Faithful Execution}}",
    "Knights of the Old Republic 39": "{{DarkHorse|url=Comics/15-788/Star-Wars-Knights-of-the-Old-Republic-39--Dueling-Ambitions-part-1|text=Star Wars: Knights of the Old Republic #39--Dueling Ambitions part 1}}",
    "Knights of the Old Republic 40": "{{DarkHorse|url=Comics/15-789/Star-Wars-Knights-of-the-Old-Republic-40----Dueling-Ambitions-part-2-of-3|text=Star Wars: Knights of the Old Republic #40 -- Dueling Ambitions part 2 (of 3)}}",
    "Knights of the Old Republic 41": "{{DarkHorse|url=Comics/15-790/Star-Wars-Knights-of-the-Old-Republic-41----Dueling-Ambitions-part-3-of-3|text=Star Wars: Knights of the Old Republic #41 -- Dueling Ambitions part 3 (of 3)}}",
    "Knights of the Old Republic 42": "{{DarkHorse|url=Comics/15-954/Star-Wars-Knights-of-the-Old-Republic-42--Masks|text=Star Wars: Knights of the Old Republic #42--Masks}}",
    "Knights of the Old Republic 43": "{{DarkHorse|url=Comics/15-955/Star-Wars-Knights-of-the-Old-Republic-43--The-Reaping-part-1|text=Star Wars: Knights of the Old Republic #43--The Reaping part 1}}",
    "Knights of the Old Republic 44": "{{DarkHorse|url=Comics/15-956/Star-Wars-Knights-of-the-Old-Republic-44----The-Reaping-part-2|text=Star Wars: Knights of the Old Republic #44 -- The Reaping part 2}}",
    "Knights of the Old Republic 45": "{{DarkHorse|url=Comics/15-957/Star-Wars-Knights-of-the-Old-Republic-45---Destroyer-part-1|text=Star Wars: Knights of the Old Republic #45 - Destroyer part 1}}",
    "Knights of the Old Republic 46": "{{DarkHorse|url=Comics/15-958/Star-Wars-Knights-of-the-Old-Republic-46---Destroyer-part-2|text=Star Wars: Knights of the Old Republic #46 - Destroyer part 2}}",
    "Knights of the Old Republic 47": "{{DarkHorse|url=Comics/15-959/Star-Wars-Knights-of-the-Old-Republic-47----Demon-part-1|text=Star Wars: Knights of the Old Republic #47 -- Demon part 1}}",
    "Knights of the Old Republic 48": "{{DarkHorse|url=Comics/16-136/Star-Wars-Knights-of-the-Old-Republic-48----Demon-part-2|text=Star Wars: Knights of the Old Republic #48 -- Demon part 2}}",
    "Knights of the Old Republic 49": "{{DarkHorse|url=Comics/16-419/Star-Wars-Knights-of-the-Old-Republic-49----Demon-part-3|text=Star Wars: Knights of the Old Republic #49 -- Demon part 3}}",
    "Knights of the Old Republic 50": "{{DarkHorse|url=Comics/16-420/Star-Wars-Knights-of-the-Old-Republic-50----Demon-part-4|text=Star Wars: Knights of the Old Republic #50 -- Demon part 4}}",
    "Knights of the Old Republic: War 4": "{{DarkHorse|url=Comics/18-912/Star-Wars-Knights-of-the-Old-Republic-War-4|text=Star Wars: Knights of the Old Republic - War #4}}",
    "Knights of the Old Republic: War 5": "{{DarkHorse|url=Comics/18-913/Star-Wars-Knights-of-the-Old-Republic-War-5|text=Star Wars: Knights of the Old Republic - War #5}}",
    "Legacy (2006) 1": "{{DarkHorse|url=Comics/13-453/Star-Wars-Legacy-1|text=Star Wars: Legacy #1}}",
    "Legacy (2006) 10": "{{DarkHorse|url=Comics/14-073/Star-Wars-Legacy-10|text=Star Wars: Legacy #10}}",
    "Legacy (2006) 11": "{{DarkHorse|url=Comics/14-074/Star-Wars-Legacy-11|text=Star Wars: Legacy #11}}",
    "Legacy (2006) 12": "{{DarkHorse|url=Comics/14-075/Star-Wars-Legacy-12|text=Star Wars: Legacy #12}}",
    "Legacy (2006) 13": "{{DarkHorse|url=Comics/14-545/Star-Wars-Legacy-13--Ready-to-Die|text=Star Wars: Legacy #13--Ready to Die}}",
    "Legacy (2006) 14": "{{DarkHorse|url=Comics/14-435/Star-Wars-Legacy-14--Claws-of-the-Dragon-pt-1|text=Star Wars: Legacy #14--Claws of the Dragon pt. 1}}",
    "Legacy (2006) 15": "{{DarkHorse|url=Comics/14-437/Star-Wars-Legacy-15--Claws-of-the-Dragon-pt-2|text=Star Wars: Legacy #15--Claws of the Dragon pt. 2}}",
    "Legacy (2006) 16": "{{DarkHorse|url=Comics/14-438/Star-Wars-Legacy-16--Claws-of-the-Dragon-pt-3|text=Star Wars: Legacy #16--Claws of the Dragon pt. 3}}",
    "Legacy (2006) 17": "{{DarkHorse|url=Comics/14-439/Star-Wars-Legacy-17--Claws-of-the-Dragon-pt-4|text=Star Wars: Legacy #17--Claws of the Dragon pt. 4}}",
    "Legacy (2006) 18": "{{DarkHorse|url=Comics/14-603/Star-Wars-Legacy-18--Claws-of-the-Dragon-part-5|text=Star Wars: Legacy #18--Claws of the Dragon part 5}}",
    "Legacy (2006) 19": "{{DarkHorse|url=Comics/14-778/Star-Wars-Legacy-19-Claws-of-the-Dragon-part-6-of-6|text=Star Wars: Legacy #19-Claws of the Dragon part 6 (of 6)}}",
    "Legacy (2006) 2": "{{DarkHorse|url=Comics/13-454/Star-Wars-Legacy-2|text=Star Wars: Legacy #2}}",
    "Legacy (2006) 21": "{{DarkHorse|url=Comics/14-882/Star-Wars-Legacy-21|text=Star Wars: Legacy #21}}",
    "Legacy (2006) 22": "{{DarkHorse|url=Comics/14-883/Star-Wars-Legacy-22|text=Star Wars: Legacy #22}}",
    "Legacy (2006) 24": "{{DarkHorse|url=Comics/14-885/Star-Wars-Legacy-24|text=Star Wars: Legacy #24}}",
    "Legacy (2006) 26": "{{DarkHorse|url=Comics/15-529/Star-Wars-Legacy-26|text=Star Wars: Legacy #26}}",
    "Legacy (2006) 27": "{{DarkHorse|url=Comics/15-530/Star-Wars-Legacy-27|text=Star Wars: Legacy #27}}",
    "Legacy (2006) 28": "{{DarkHorse|url=Comics/15-531/Star-Wars-Legacy-28--Vector-part-9|text=Star Wars: Legacy #28--Vector part 9}}",
    "Legacy (2006) 29": "{{DarkHorse|url=Comics/15-532/Star-Wars-Legacy-29--Vector-part-10|text=Star Wars: Legacy #29--Vector part 10}}",
    "Legacy (2006) 3": "{{DarkHorse|url=Comics/13-455/Star-Wars-Legacy-3|text=Star Wars: Legacy #3}}",
    "Legacy (2006) 30": "{{DarkHorse|url=Comics/15-533/Star-Wars-Legacy-30---Vector-part-11|text=Star Wars: Legacy #30 - Vector part 11}}",
    "Legacy (2006) 31": "{{DarkHorse|url=Comics/15-534/Star-Wars-Legacy-31--Vector-part-12|text=Star Wars: Legacy #31--Vector part 12}}",
    "Legacy (2006) 32": "{{DarkHorse|url=Comics/15-535/Star-Wars-Legacy-32----Fight-Another-Day-part-1|text=Star Wars: Legacy #32 -- Fight Another Day part 1}}",
    "Legacy (2006) 33": "{{DarkHorse|url=Comics/15-536/Star-Wars-Legacy-33----Fight-Another-Day-pt-2-of-2|text=Star Wars: Legacy #33 -- Fight Another Day pt. 2 of 2}}",
    "Legacy (2006) 34": "{{DarkHorse|url=Comics/15-537/Star-Wars-Legacy-34--Storms-part-1|text=Star Wars: Legacy #34--Storms part 1}}",
    "Legacy (2006) 37": "{{DarkHorse|url=Comics/15-977/Star-Wars-Legacy-37---Tatooine-part-1|text=Star Wars: Legacy #37 - Tatooine (part 1)}}",
    "Legacy (2006) 38": "{{DarkHorse|url=Comics/16-137/Star-Wars-Legacy-38--Tatooine-part-2|text=Star Wars: Legacy #38--Tatooine part 2}}",
    "Legacy (2006) 39": "{{DarkHorse|url=Comics/16-138/Star-Wars-Legacy-39----Tatooine-part-3|text=Star Wars: Legacy #39 -- Tatooine part 3}}",
    "Legacy (2006) 40": "{{DarkHorse|url=Comics/16-139/Star-Wars-Legacy-40----Tatooine-part-4|text=Star Wars: Legacy #40 -- Tatooine part 4}}",
    "Legacy (2006) 41": "{{DarkHorse|url=Comics/16-140/Star-Wars-Legacy-41----Rogues-End|text=Star Wars: Legacy #41 -- Rogue's End}}",
    "Legacy (2006) 42": "{{DarkHorse|url=Comics/16-141/Star-Wars-Legacy-42----Divided-Loyalties|text=Star Wars: Legacy #42 -- Divided Loyalties}}",
    "Legacy (2006) 43": "{{DarkHorse|url=Comics/16-142/Star-Wars-Legacy-43----Vongspawn|text=Star Wars: Legacy #43 -- Vongspawn}}",
    "Legacy (2006) 44": "{{DarkHorse|url=Comics/16-335/Star-Wars-Legacy-44----Monster-part-2|text=Star Wars: Legacy #44 -- Monster part 2}}",
    "Legacy (2006) 45": "{{DarkHorse|url=Comics/16-336/Star-Wars-Legacy-45----Monster-part-3|text=Star Wars: Legacy #45 -- Monster part 3}}",
    "Legacy (2006) 46": "{{DarkHorse|url=Comics/16-337/Star-Wars-Legacy-46----Monster-part-4|text=Star Wars: Legacy #46 -- Monster part 4}}",
    "Legacy (2006) 47": "{{DarkHorse|url=Comics/16-338/Star-Wars-Legacy-47----The-Fate-of-Dac|text=Star Wars: Legacy #47 -- The Fate of Dac}}",
    "Legacy (2006) 5": "{{DarkHorse|url=Comics/13-457/Star-Wars-Legacy-5|text=Star Wars: Legacy #5}}",
    "Legacy (2006) 6": "{{DarkHorse|url=Comics/13-458/Star-Wars-Legacy-6|text=Star Wars: Legacy #6}}",
    "Legacy (2006) 8": "{{DarkHorse|url=Comics/14-071/Star-Wars-Legacy-8|text=Star Wars: Legacy #8}}",
    "Legacy (2006) 9": "{{DarkHorse|url=Comics/14-072/Star-Wars-Legacy-9--Trust-Issues-part-1|text=Star Wars: Legacy #9--Trust Issues part 1}}",
    "Legacy — War 2": "{{DarkHorse|url=Comics/17-113/Star-Wars-Legacy-War-2|text=Star Wars: Legacy - War #2}}",
    "Legacy — War 3": "{{DarkHorse|url=Comics/17-430/Star-Wars-Legacy-War-3|text=Star Wars: Legacy - War #3}}",
    "Legacy — War 4": "{{DarkHorse|url=Comics/17-431/Star-Wars-Legacy-War-4|text=Star Wars: Legacy - War #4}}",
    "Legacy — War 6": "{{DarkHorse|url=Comics/17-433/Star-Wars-Legacy-War-6|text=Star Wars: Legacy - War #6}}",
    "Lost Tribe of the Sith — Spiral 1": "{{DarkHorse|url=Comics/21-321/Star-Wars-Lost-Tribe-of-the-Sith---Spiral-1|text=Star Wars: Lost Tribe of the Sith - Spiral #1}}",
    "Lost Tribe of the Sith — Spiral 2": "{{DarkHorse|url=Comics/21-322/Star-Wars-Lost-Tribe-of-the-Sith-Spiral-2|text=Star Wars: Lost Tribe of the Sith - Spiral #2}}",
    "Lost Tribe of the Sith — Spiral 3": "{{DarkHorse|url=Comics/21-323/Star-Wars-Lost-Tribe-of-the-Sith-Spiral-3|text=Star Wars: Lost Tribe of the Sith - Spiral #3}}",
    "Lost Tribe of the Sith — Spiral 4": "{{DarkHorse|url=Comics/21-324/Star-Wars-Lost-Tribe-of-the-Sith-Spiral-4|text=Star Wars: Lost Tribe of the Sith - Spiral #4}}",
    "Lost Tribe of the Sith — Spiral 5": "{{DarkHorse|url=Comics/21-325/Star-Wars-Lost-Tribe-of-the-Sith-Spiral-5|text=Star Wars: Lost Tribe of the Sith - Spiral #5}}",
    "Mara Jade – By the Emperor's Hand 1": "{{DarkHorse|url=Comics/97-638/Star-Wars-Mara-Jade---By-The-Emperors-Hand-1-of-6|text=Star Wars: Mara Jade - By The Emperor's Hand #1 (of 6)}}",
    "Mara Jade – By the Emperor's Hand 3": "{{DarkHorse|url=Comics/97-642/Star-Wars-Mara-Jade---By-The-Emperors-Hand-3-of-6|text=Star Wars: Mara Jade - By The Emperor's Hand #3 (of 6)}}",
    "Mara Jade – By the Emperor's Hand 4": "{{DarkHorse|url=Comics/97-645/Star-Wars-Mara-Jade---By-The-Emperors-Hand-4-of-6|text=Star Wars: Mara Jade - By The Emperor's Hand #4 (of 6)}}",
    "Mara Jade – By the Emperor's Hand 5": "{{DarkHorse|url=Comics/97-648/Star-Wars-Mara-Jade---By-The-Emperors-Hand-5-of-6|text=Star Wars: Mara Jade - By The Emperor's Hand #5 (of 6)}}",
    "Mara Jade – By the Emperor's Hand 6": "{{DarkHorse|url=Comics/97-650/Star-Wars-Mara-Jade---By-The-Emperors-Hand-6-of-6|text=Star Wars: Mara Jade - By The Emperor's Hand #6 (of 6)}}",
    "Obsession 1": "{{DarkHorse|url=Comics/10-563/Star-Wars-Obsession-1-of-5|text=Star Wars: Obsession #1 (of 5)}}",
    "Obsession 3": "{{DarkHorse|url=Comics/10-639/Star-Wars-Obsession-3-of-5|text=Star Wars: Obsession #3 (of 5)}}",
    "Obsession 4": "{{DarkHorse|url=Comics/10-640/Star-Wars-Obsession-4-of-5|text=Star Wars: Obsession #4 (of 5)}}",
    "Obsession 5": "{{DarkHorse|url=Comics/10-641/Star-Wars-Obsession-5-of-5|text=Star Wars: Obsession #5 (of 5)}}",
    "Qui-Gon and Obi-Wan: The Aurorient Express 1": "{{DarkHorse|url=Comics/11-434/Star-Wars-Qui-Gon-and-Obi-Wan---The-Aurorient-Express-1-of-2|text=Star Wars: Qui-Gon and Obi-Wan - The Aurorient Express #1 (of 2)}}",
    "Qui-Gon and Obi-Wan: The Aurorient Express 2": "{{DarkHorse|url=Comics/11-437/Star-Wars-Qui-Gon-and-Obi-Wan---The-Aurorient-Express-2-of-2|text=Star Wars: Qui-Gon and Obi-Wan - The Aurorient Express #2 (of 2)}}",
    "Rebellion 1": "{{DarkHorse|url=Comics/13-359/Star-Wars-Rebellion---My-Brother-My-Enemy-1|text=Star Wars: Rebellion - My Brother, My Enemy #1}}",
    "Rebellion 10": "{{DarkHorse|url=Comics/14-009/Star-Wars-Rebellion-10|text=Star Wars: Rebellion #10}}",
    "Rebellion 11": "{{DarkHorse|url=Comics/14-787/Star-Wars-Rebellion-11--Small-Victories-part-1-of-4|text=Star Wars: Rebellion #11--Small Victories part 1 (of 4)}}",
    "Rebellion 12": "{{DarkHorse|url=Comics/14-909/Star-Wars-Rebellion-12--Small-Victories-part-2|text=Star Wars: Rebellion #12--Small Victories part 2}}",
    "Rebellion 13": "{{DarkHorse|url=Comics/14-910/Star-Wars-Rebellion-13--Small-Victories-part-3|text=Star Wars: Rebellion #13--Small Victories part 3}}",
    "Rebellion 14": "{{DarkHorse|url=Comics/14-911/Star-Wars-Rebellion-14--Small-Victories-part-4|text=Star Wars: Rebellion #14--Small Victories part 4}}",
    "Rebellion 16": "{{DarkHorse|url=Comics/11-560/Star-Wars-Rebellion-16--Vector-part-8|text=Star Wars: Rebellion #16--Vector part 8}}",
    "Rebellion 2": "{{DarkHorse|url=Comics/13-360/Star-Wars-Rebellion---My-Brother-My-Enemy-2|text=Star Wars: Rebellion - My Brother, My Enemy #2}}",
    "Rebellion 3": "{{DarkHorse|url=Comics/13-361/Star-Wars-Rebellion---My-Brother-My-Enemy-3|text=Star Wars: Rebellion - My Brother, My Enemy #3}}",
    "Rebellion 4": "{{DarkHorse|url=Comics/13-362/Star-Wars-Rebellion---My-Brother-My-Enemy-4|text=Star Wars: Rebellion - My Brother, My Enemy #4}}",
    "Rebellion 5": "{{DarkHorse|url=Comics/13-363/Star-Wars-Rebellion-My-Brother-My-Enemy-5|text=Star Wars: Rebellion My Brother, My Enemy #5}}",
    "Rebellion 6": "{{DarkHorse|url=Comics/14-004/Star-Wars-Rebellion-6--The-Ahakista-Gambit|text=Star Wars: Rebellion #6--The Ahakista Gambit}}",
    "Rebellion 7": "{{DarkHorse|url=Comics/14-006/Star-Wars-Rebellion-7--The-Ahakista-Gambit-pt-2|text=Star Wars: Rebellion #7--The Ahakista Gambit pt. 2}}",
    "Rebellion 8": "{{DarkHorse|url=Comics/14-007/Star-Wars-Rebellion-8|text=Star Wars: Rebellion #8}}",
    "Rebellion 9": "{{DarkHorse|url=Comics/14-008/Star-Wars-Rebellion-9|text=Star Wars: Rebellion #9}}",
    "Republic 46": "{{DarkHorse|url=Comics/11-687/Star-Wars-Republic-46|text=Star Wars: Republic #46}}",
    "Republic 47": "{{DarkHorse|url=Comics/11-689/Star-Wars-Republic-47|text=Star Wars: Republic #47}}",
    "Republic 48": "{{DarkHorse|url=Comics/11-692/Star-Wars-Republic-48|text=Star Wars: Republic #48}}",
    "Republic 49": "{{DarkHorse|url=Comics/11-695/Star-Wars-Republic-49|text=Star Wars: Republic #49}}",
    "Republic 50": "{{DarkHorse|url=Comics/11-697/Star-Wars-Republic-50|text=Star Wars: Republic #50}}",
    "Republic 51": "{{DarkHorse|url=Comics/11-702/Star-Wars-Republic-51|text=Star Wars: Republic #51}}",
    "Republic 52": "{{DarkHorse|url=Comics/11-704/Star-Wars-Republic-52|text=Star Wars: Republic #52}}",
    "Republic 53": "{{DarkHorse|url=Comics/12-199/Star-Wars-Republic-53Blast-Radius|text=Star Wars: Republic #53 - Blast Radius}}",
    "Republic 54": "{{DarkHorse|url=Comics/12-200/Star-Wars-Republic-54|text=Star Wars: Republic #54}}",
    "Republic 55": "{{DarkHorse|url=Comics/12-201/Star-Wars-Republic-55The-Battle-of-Jabiim-Part-1-of-4|text=Star Wars: Republic #55 - The Battle of Jabiim (Part 1 of 4)}}",
    "Republic 57": "{{DarkHorse|url=Comics/12-203/Star-Wars-Republic-57The-Battle-of-Jabiim-Part-3-of-4|text=Star Wars: Republic #57 - The Battle of Jabiim (Part 3 of 4)}}",
    "Republic 58": "{{DarkHorse|url=Comics/12-204/Star-Wars-Republic-58The-Battle-of-Jabiim-Part-4-of-4|text=Star Wars: Republic #58 - The Battle of Jabiim (Part 4 of 4)}}",
    "Republic 59": "{{DarkHorse|url=Comics/12-205/Star-Wars-Republic-59Enemy-Lines|text=Star Wars: Republic #59 - Enemy Lines}}",
    "Republic 60": "{{DarkHorse|url=Comics/12-321/Star-Wars-Republic-60|text=Star Wars: Republic #60}}",
    "Republic 61": "{{DarkHorse|url=Comics/13-075/Star-Wars-Republic-61|text=Star Wars: Republic #61}}",
    "Republic 62": "{{DarkHorse|url=Comics/13-076/Star-Wars-Republic-62|text=Star Wars: Republic #62}}",
    "Republic 64": "{{DarkHorse|url=Comics/13-078/Star-Wars-Republic-64|text=Star Wars: Republic #64}}",
    "Republic 65": "{{DarkHorse|url=Comics/13-079/Star-Wars-Republic-65Show-of-Force-Part-1-of-2|text=Star Wars: Republic #65 - Show of Force Part 1 (of 2)}}",
    "Republic 66": "{{DarkHorse|url=Comics/13-080/Star-Wars-Republic-66Show-of-Force-Part-2-of-2|text=Star Wars: Republic #66 - Show of Force Part 2 (of 2)}}",
    "Republic 67": "{{DarkHorse|url=Comics/13-081/Star-Wars-Republic-67|text=Star Wars: Republic #67}}",
    "Republic 68": "{{DarkHorse|url=Comics/13-082/Star-Wars-Republic-68|text=Star Wars: Republic #68}}",
    "Republic 69": "{{DarkHorse|url=Comics/13-083/Star-Wars-Republic-69|text=Star Wars: Republic #69}}",
    "Republic 70": "{{DarkHorse|url=Comics/13-084/Star-Wars-Republic-70|text=Star Wars: Republic #70}}",
    "Republic 71": "{{DarkHorse|url=Comics/13-085/Star-Wars-Republic-71|text=Star Wars: Republic #71}}",
    "Republic 72": "{{DarkHorse|url=Comics/10-192/Star-Wars-Republic-72|text=Star Wars: Republic #72}}",
    "Republic 73": "{{DarkHorse|url=Comics/10-438/Star-Wars-Republic-73|text=Star Wars: Republic #73}}",
    "Republic 74": "{{DarkHorse|url=Comics/10-440/Star-Wars-Republic-74|text=Star Wars: Republic #74}}",
    "Republic 75": "{{DarkHorse|url=Comics/10-441/Star-Wars-Republic-75|text=Star Wars: Republic #75}}",
    "Republic 76": "{{DarkHorse|url=Comics/10-442/Star-Wars-Republic-76|text=Star Wars: Republic #76}}",
    "Republic 77": "{{DarkHorse|url=Comics/10-444/Star-Wars-Republic-77|text=Star Wars: Republic #77}}",
    "Republic 79": "{{DarkHorse|url=Comics/10-446/Star-Wars-Republic-79|text=Star Wars: Republic #79}}",
    "Republic 80": "{{DarkHorse|url=Comics/10-448/Star-Wars-Republic-80|text=Star Wars: Republic #80}}",
    "Republic 81": "{{DarkHorse|url=Comics/10-452/Star-Wars-Republic-81-The-Hidden-Enemy-part-1-of-3|text=Star Wars: Republic #81 The Hidden Enemy part 1 (of 3)}}",
    "Republic 83": "{{DarkHorse|url=Comics/10-455/Star-Wars-Republic-83-The-Hidden-Enemy-part-3-of-3|text=Star Wars: Republic #83 The Hidden Enemy part 3 (of 3)}}",
    "River of Chaos 4": "{{DarkHorse|url=Comics/94-256/Star-Wars-River-of-Chaos-4-of-4|text=Star Wars: River of Chaos #4 (of 4)}}",
    "Shadows of the Empire: Evolution 1": "{{DarkHorse|url=Comics/96-977/Star-Wars-Shadows-of-the-Empire---Evolution-1-of-5|text=Star Wars: Shadows of the Empire - Evolution #1 (of 5)}}",
    "Shadows of the Empire: Evolution 2": "{{DarkHorse|url=Comics/96-980/Star-Wars-Shadows-of-the-Empire---Evolution-2-of-5|text=Star Wars: Shadows of the Empire - Evolution #2 (of 5)}}",
    "Shadows of the Empire: Evolution 3": "{{DarkHorse|url=Comics/96-982/Star-Wars-Shadows-of-the-Empire---Evolution-3-of-5|text=Star Wars: Shadows of the Empire - Evolution #3 (of 5)}}",
    "Shadows of the Empire: Evolution 4": "{{DarkHorse|url=Comics/96-985/Star-Wars-Shadows-of-the-Empire---Evolution-4-of-5|text=Star Wars: Shadows of the Empire - Evolution #4 (of 5)}}",
    "Shadows of the Empire: Evolution 5": "{{DarkHorse|url=Comics/97-281/Star-Wars-Shadows-of-the-Empire---Evolution-5-of-5|text=Star Wars: Shadows of the Empire - Evolution #5 (of 5)}}",
    "Splinter of the Mind's Eye 1": "{{DarkHorse|url=Comics/93-816/Star-Wars-Splinter-of-the-Minds-Eye-1-of-4|text=Star Wars: Splinter of the Mind's Eye #1 (of 4)}}",
    "Splinter of the Mind's Eye 2": "{{DarkHorse|url=Comics/93-832/Star-Wars-Splinter-of-the-Minds-Eye-2-of-4|text=Star Wars: Splinter of the Mind's Eye #2 (of 4)}}",
    "Star Wars (1998) 15": "{{DarkHorse|url=Comics/99-104/Star-Wars-15Emissaries-to-Malastare-Part-3-of-6|text=Star Wars #15 - Emissaries to Malastare (Part 3 of 6)}}",
    "Star Wars (1998) 19": "{{DarkHorse|url=Comics/99-123/Star-Wars-19Twilight-Part-1-of-4|text=Star Wars #19 - Twilight (Part 1 of 4)}}",
    "Star Wars (1998) 32": "{{DarkHorse|url=Comics/00-459/Star-Wars-32Darkness-Part-1-of-4|text=Star Wars #32 - Darkness (Part 1 of 4)}}",
    "Star Wars (1998) 36": "{{DarkHorse|url=Comics/11-378/Star-Wars-36The-Stark-Hyperspace-War-Part-1-of-4|text=Star Wars #36 - The Stark Hyperspace War (Part 1 of 4)}}",
    "Star Wars (1998) 39": "{{DarkHorse|url=Comics/11-391/Star-Wars-39The-Stark-Hyperspace-War-Part-3-of-4|text=Star Wars #39 - The Stark Hyperspace War (Part 3 of 4)}}",
    "Star Wars (1998) 41": "{{DarkHorse|url=Comics/11-398/Star-Wars-41The-Devaronian-Version-Part-2-of-2|text=Star Wars #41 - The Devaronian Version (Part 2 of 2)}}",
    "Star Wars: A New Hope - The Special Edition 1": "{{DarkHorse|url=Comics/95-368/Star-Wars-A-New-Hope---The-Special-Edition-1-of-4|text=Star Wars: A New Hope - The Special Edition #1 (of 4)}}",
    "Star Wars: A New Hope - The Special Edition 2": "{{DarkHorse|url=Comics/95-371/Star-Wars-A-New-Hope---The-Special-Edition-2-of-4|text=Star Wars: A New Hope - The Special Edition #2 (of 4)}}",
    "Star Wars: A New Hope - The Special Edition 3": "{{DarkHorse|url=Comics/95-374/Star-Wars-A-New-Hope---The-Special-Edition-3-of-4|text=Star Wars: A New Hope - The Special Edition #3 (of 4)}}",
    "Star Wars: A New Hope - The Special Edition 4": "{{DarkHorse|url=Comics/95-377/Star-Wars-A-New-Hope---The-Special-Edition-4-of-4|text=Star Wars: A New Hope - The Special Edition #4 (of 4)}}",
    "Star Wars: Episode III — Revenge of the Sith 2": "{{DarkHorse|url=Comics/13-196/Star-Wars-Episode-III----Revenge-of-the-Sith-2|text=Star Wars: Episode III -- Revenge of the Sith #2}}",
    "Star Wars: Episode III — Revenge of the Sith 3": "{{DarkHorse|url=Comics/13-197/Star-Wars-Episode-III----Revenge-of-the-Sith-3|text=Star Wars: Episode III -- Revenge of the Sith #3}}",
    "Starfighter: Crossbones 1": "{{DarkHorse|url=Comics/11-543/Star-Wars-Starfighter----Crossbones-1-of-3|text=Star Wars: Starfighter -- Crossbones #1 (of 3)}}",
    "Starfighter: Crossbones 2": "{{DarkHorse|url=Comics/11-547/Star-Wars-Starfighter----Crossbones-2-of-3|text=Star Wars: Starfighter -- Crossbones #2 (of 3)}}",
    "Starfighter: Crossbones 3": "{{DarkHorse|url=Comics/11-551/Star-Wars-Starfighter----Crossbones-3-of-3|text=Star Wars: Starfighter -- Crossbones #3 (of 3)}}",
    "Tales of the Jedi 2": "{{DarkHorse|url=Comics/93-122/Star-Wars-Tales-of-the-Jedi-2-of-5|text=Star Wars: Tales of the Jedi #2 (of 5)}}",
    "Tales of the Jedi 3": "{{DarkHorse|url=Comics/93-130/Star-Wars-Tales-of-the-Jedi-3-of-5|text=Star Wars: Tales of the Jedi #3 (of 5)}}",
    "Tales of the Jedi – The Fall of the Sith Empire 3": "{{DarkHorse|url=Comics/95-299/Star-Wars-Tales-of-the-Jedi---The-Fall-of-the-Sith-Empire-3-of-5|text=Star Wars: Tales of the Jedi - The Fall of the Sith Empire #3 (of 5)}}",
    "Tales of the Jedi – The Freedon Nadd Uprising 2": "{{DarkHorse|url=Comics/94-155/Star-Wars-Tales-of-the-Jedi---The-Freedon-Nadd-Uprising-2-of-2|text=Star Wars: Tales of the Jedi - The Freedon Nadd Uprising #2 (of 2)}}",
    "Tales of the Jedi – The Sith War 4": "{{DarkHorse|url=Comics/93-644/Star-Wars-Tales-of-the-Jedi---The-Sith-War-4-of-6|text=Star Wars: Tales of the Jedi - The Sith War #4 (of 6)}}",
    "The Clone Wars 6": "{{DarkHorse|url=Comics/15-684/Star-Wars-The-Clone-Wars-6-of-6|text=Star Wars: The Clone Wars #6 (of 6)}}",
    "The Last Command 3": "{{DarkHorse|url=Comics/96-481/Star-Wars-The-Last-Command-3-of-6|text=Star Wars: The Last Command #3 (of 6)}}",
    "The Old Republic — The Lost Suns 1": "{{DarkHorse|url=Comics/17-772/Star-Wars-The-Old-Republic-The-Lost-Suns-1|text=Star Wars: The Old Republic - The Lost Suns #1}}",
    "The Old Republic — The Lost Suns 2": "{{DarkHorse|url=Comics/17-774/Star-Wars-The-Old-Republic-The-Lost-Suns-2|text=Star Wars: The Old Republic - The Lost Suns #2}}",
    "The Old Republic — The Lost Suns 3": "{{DarkHorse|url=Comics/17-775/Star-Wars-The-Old-Republic-The-Lost-Suns-3|text=Star Wars: The Old Republic - The Lost Suns #3}}",
    "The Old Republic — The Lost Suns 4": "{{DarkHorse|url=Comics/17-776/Star-Wars-The-Old-Republic-The-Lost-Suns-4|text=Star Wars: The Old Republic - The Lost Suns #4}}",
    "The Old Republic — The Lost Suns 5": "{{DarkHorse|url=Comics/17-777/Star-Wars-The-Old-Republic-The-Lost-Suns-5|text=Star Wars: The Old Republic - The Lost Suns #5}}",
    "The Return of Tag & Bink: Special Edition": "{{DarkHorse|url=Comics/13-691/Star-Wars-The-Return-of-Tag-Bink---Special-Edition-1|text=Star Wars: The Return of Tag & Bink - Special Edition #1}}",
    "Union 2": "{{DarkHorse|url=Comics/98-437/Star-Wars-Union-2-of-4|text=Star Wars: Union #2 (of 4)}}",
    "X-Wing Rogue Squadron 10": "{{DarkHorse|url=Comics/94-888/Star-Wars-X-Wing-Rogue-Squadron-10Battleground-Tatooine-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #10 - Battleground Tatooine (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 11": "{{DarkHorse|url=Comics/94-901/Star-Wars-X-Wing-Rogue-Squadron-11Battleground-Tatooine-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #11 - Battleground Tatooine (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 12": "{{DarkHorse|url=Comics/94-917/Star-Wars-X-Wing-Rogue-Squadron-12Battleground-Tatooine-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #12 - Battleground Tatooine (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 13": "{{DarkHorse|url=Comics/96-482/Star-Wars-X-Wing-Rogue-Squadron-13The-Warrior-Princess-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #13 - The Warrior Princess (Part 1 of 4)}}",
    "X-Wing Rogue Squadron 16": "{{DarkHorse|url=Comics/96-495/Star-Wars-X-Wing-Rogue-Squadron-16The-Warrior-Princess-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #16 - The Warrior Princess (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 17": "{{DarkHorse|url=Comics/96-668/Star-Wars-X-Wing-Rogue-Squadron-17Requiem-for-a-Rogue-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #17 - Requiem for a Rogue (Part 1 of 4)}}",
    "X-Wing Rogue Squadron 18": "{{DarkHorse|url=Comics/96-671/Star-Wars-X-Wing-Rogue-Squadron-18Requiem-for-a-Rogue-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #18 - Requiem for a Rogue (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 19": "{{DarkHorse|url=Comics/96-674/Star-Wars-X-Wing-Rogue-Squadron-19Requiem-for-a-Rogue-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #19 - Requiem for a Rogue (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 20": "{{DarkHorse|url=Comics/96-679/Star-Wars-X-Wing-Rogue-Squadron-20Requiem-for-a-Rogue-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #20 - Requiem for a Rogue (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 22": "{{DarkHorse|url=Comics/96-847/Star-Wars-X-Wing-Rogue-Squadron-22In-the-Empires-Service-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #22 - In the Empire's Service (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 23": "{{DarkHorse|url=Comics/96-850/Star-Wars-X-Wing-Rogue-Squadron-23In-the-Empires-Service-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #23 - In the Empire's Service (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 24": "{{DarkHorse|url=Comics/96-854/Star-Wars-X-Wing-Rogue-Squadron-24In-the-Empires-Service-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #24 - In the Empire's Service (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 26": "{{DarkHorse|url=Comics/96-863/Star-Wars-X-Wing-Rogue-Squadron-26Family-Ties-Part-1-of-2|text=Star Wars: X-Wing Rogue Squadron #26 - Family Ties (Part 1 of 2)}}",
    "X-Wing Rogue Squadron 27": "{{DarkHorse|url=Comics/96-865/Star-Wars-X-Wing-Rogue-Squadron-27Family-Ties-Part-2-of-2|text=Star Wars: X-Wing Rogue Squadron #27 - Family Ties (Part 2 of 2)}}",
    "X-Wing Rogue Squadron 28": "{{DarkHorse|url=Comics/96-868/Star-Wars-X-Wing-Rogue-Squadron-28Masquerade-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #28 - Masquerade (Part 1 of 4)}}",
    "X-Wing Rogue Squadron 29": "{{DarkHorse|url=Comics/96-871/Star-Wars-X-Wing-Rogue-Squadron-29Masquerade-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #29 - Masquerade (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 3": "{{DarkHorse|url=Comics/94-451/Star-Wars-X-Wing-Rogue-Squadron-3The-Rebel-Opposition-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #3 - The Rebel Opposition (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 30": "{{DarkHorse|url=Comics/96-873/Star-Wars-X-Wing-Rogue-Squadron-30Masquerade-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #30 - Masquerade (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 31": "{{DarkHorse|url=Comics/96-876/Star-Wars-X-Wing-Rogue-Squadron-31Masquerade-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #31 - Masquerade (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 32": "{{DarkHorse|url=Comics/96-880/Star-Wars-X-Wing-Rogue-Squadron-32Mandatory-Retirement-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #32 - Mandatory Retirement (Part 1 of 4)}}",
    "X-Wing Rogue Squadron 33": "{{DarkHorse|url=Comics/97-766/Star-Wars-X-Wing-Rogue-Squadron-33Mandatory-Retirement-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #33 - Mandatory Retirement (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 34": "{{DarkHorse|url=Comics/97-768/Star-Wars-X-Wing-Rogue-Squadron-34Mandatory-Retirement-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #34 - Mandatory Retirement (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 35": "{{DarkHorse|url=Comics/97-771/Star-Wars-X-Wing-Rogue-Squadron-35Mandatory-Retirement-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #35 - Mandatory Retirement (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 4": "{{DarkHorse|url=Comics/94-460/Star-Wars-X-Wing-Rogue-Squadron-4The-Rebel-Opposition-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #4 - The Rebel Opposition (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 5": "{{DarkHorse|url=Comics/94-820/Star-Wars-X-Wing-Rogue-Squadron-5The-Phantom-Affair-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #5 - The Phantom Affair (Part 1 of 4)}}",
    "X-Wing Rogue Squadron 6": "{{DarkHorse|url=Comics/94-832/Star-Wars-X-Wing-Rogue-Squadron-6The-Phantom-Affair-Part-2-of-4|text=Star Wars: X-Wing Rogue Squadron #6 - The Phantom Affair (Part 2 of 4)}}",
    "X-Wing Rogue Squadron 7": "{{DarkHorse|url=Comics/94-840/Star-Wars-X-Wing-Rogue-Squadron-7The-Phantom-Affair-Part-3-of-4|text=Star Wars: X-Wing Rogue Squadron #7 - The Phantom Affair (Part 3 of 4)}}",
    "X-Wing Rogue Squadron 8": "{{DarkHorse|url=Comics/94-856/Star-Wars-X-Wing-Rogue-Squadron-8The-Phantom-Affair-Part-4-of-4|text=Star Wars: X-Wing Rogue Squadron #8 - The Phantom Affair (Part 4 of 4)}}",
    "X-Wing Rogue Squadron 9": "{{DarkHorse|url=Comics/94-871/Star-Wars-X-Wing-Rogue-Squadron-9Battleground-Tatooine-Part-1-of-4|text=Star Wars: X-Wing Rogue Squadron #9 - Battleground Tatooine (Part 1 of 4)}}",
    "X-Wing: Rogue Leader 1": "{{DarkHorse|url=Comics/11-980/Star-Wars-X-Wing---Rogue-Leader-1-of-3|text=Star Wars: X-Wing - Rogue Leader #1 (of 3)}}",
    "X-Wing: Rogue Leader 2": "{{DarkHorse|url=Comics/12-000/Star-Wars-X-Wing---Rogue-Leader-2-of-3|text=Star Wars: X-Wing - Rogue Leader #2 (of 3)}}",
    "X-Wing: Rogue Leader 3": "{{DarkHorse|url=Comics/12-111/Star-Wars-X-Wing---Rogue-Leader-3-of-3|text=Star Wars: X-Wing - Rogue Leader #3 (of 3)}}",
}


def remove(s, x: list):
    y = f"{s}"
    for i in x:
        y = y.replace(f"{i} ", "")
    return y


def match(s, x):
    return s.lower() == x.lower()


def match_header(header: str, infobox):
    # i = (infobox or '').replace("_", " ").lower()
    h = header.lower().strip().replace("'", "").replace("-", " ")
    if infobox and infobox == "BookSeries" and h == "novels":
        return "Contents"
    elif infobox and infobox.startswith("Television") and remove(h, ["official"]) == "description":
        return "Official Description"

    if h in ["behind the scenes", "main characters", "characters", "major characters"]:
        return "FLAG"
    elif h == "sources":
        return "Sources"
    elif h == "external links":
        return "Links"
    elif h == "references" or h.startswith("notes and ref") or h.startswith("notes an ref"):
        return "References"
    elif h in ["collections", "collected in"]:
        return "Collections"

    if h in ["plot summary", "synopsis", "story"]:
        return "Plot Summary"
    elif remove(h, ["publisher", "publishers", "publishing", "official", "product", "manufacturers", "publication"]) in [
        "summary", "description", "from the publisher", "back cover summary",
    ]:
        return "Publisher Summary"
    elif h in ["opening crawl", "opening crawls", "opening inscription"]:
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
    elif h in ["out-of-universe appearances", "out of universe appearances"]:
        return "Out of universe appearances"
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
    elif h in ["cards", "card lists", "card list", "card set", "list of cards"]:
        return "Card List"

    if h in ["content", "contents", "tracks", "track list", "track listing", "comic strip", "features",
             "stories", "short stories", "other stories", "articles", "adventures",
             "collects", "collected issues", "collected stories", "collected comic strips", "collected novellas",
             "collected short stories"]:
        return "Card List" if infobox == "TradingCardSet" else "Contents"
    return None


def check_for_cover_image(lines, images: list):
    to_remove = []
    for i, ln in enumerate(lines):
        if ln.startswith("[[File:") and re.search("\[\[File:.*?\|.*?[Cc]over.*?]]", ln):
            a, z = re.sub("^.*?\[\[([Ff]ile:.*?)(\|(thumb|[0-9]+px|left|right))*(\|.*?)?\.?]].*?$", "\\1\\4", ln).split("|", 1)
            a = a.replace(" ", "_")
            images.append(f"{a}|{z}" if z else a)
            to_remove.append(i)
    if to_remove:
        return [ln for i, ln in enumerate(lines) if i not in to_remove]
    return lines


def get_listings(title, appearances: FullListData, sources: FullListData):
    return (appearances.target.get(title) or sources.target.get(title)) or []


def remove_links(ln):
    if "[[" in ln:
        while re.search("\[\[([^\n\[\]|{}]*?\|)?([^\n\[\]|{}]*?)]]", ln):
            ln = re.sub("\[\[([^\n\[\]|{}]*?\|)?([^\n\[\]|{}]*?)]]", "\\2", ln)
    return ln


def rearrange_sections(target: Page, results: PageComponents, valid: Dict[str, List[SectionLeaf]],
                       appearances: FullListData, sources: FullListData, novel: Page, images: List[str]):
    if not results.real:
        return {k: v[0] for k, v in valid.items()}

    sections = {}
    has_summary = False
    for key, items in valid.items():
        if key == "Publisher Summary" or key == "Official Description":
            if has_summary:
                items[0].flag = True
            has_summary = True
            # apply italicization
            for i in items:
                if not any(ln.startswith("''") for ln in i.lines if ln):
                    i.lines = [f"''{ln}''" if ln and not ln.startswith("''") else ln for ln in i.lines]

        if results.media:
            items = remap_sections(key, items, valid, sections, appearances, sources, results.infobox)
        if not items:
            continue

        if key in MEDIA_STRUCTURE and key in sections:
            if len(items) > 1:
                print(f"combining: {key}, {len(items)}")
                items[0].lines = combine_sections(items)
            if len(items[0].lines) > 0:
                if len(sections[key].lines) > 0:
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
                if results.infobox in ["BoardGame", "CardGame", "TabletopGame", "ExpansionPack", "TradingCardSet"] and "Gallery" in kx:
                    kx = "Content Gallery"
                if len(items) > 1:
                    print(f"Unexpected state: multiple sections found for {kx} header")
                sections[parent].subsections[kx] = combine_and_demote_sections(items, key, kx)
                sections[parent].subsections[kx].master_num = children.index(key)

    return add_and_cleanup_sections(target, results, sections, valid, appearances, sources, novel, images)


def remap_sections(key, items: List[SectionLeaf], valid: Dict[str, List[SectionLeaf]], sections: Dict[str, SectionLeaf],
                   appearances: FullListData, sources: FullListData, infobox):
    new_items = []
    for it in items:
        if key != "Opening Crawl":
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

        if key == "Contents" and infobox not in ["MagazineArticle"]:
            lines = []
            for ln in it.lines:
                z = re.search("\*'*\[\[(.*?)(\|.*?)?]]'*", ln)
                if z and (z.group(1) in appearances.target or z.group(1) in sources.target):
                    x = [i for i in appearances.target.get(z.group(1), sources.target.get(z.group(1), [])) if not i.reprint]
                    if x and '"[[' in x[0].original:
                        lines.append(ln.replace(z.group(0), f"*{x[0].original.split(' {{')[0]}"))
                        continue
                    elif x and x[0].template == "StoryCite" and "smanual" not in x[0].original:
                        y = re.search("\|(stext|sformat[a-z]+?)=(.*?)(\|.*?)?}}", x[0].original)
                        if y:
                            lines.append(ln.replace(z.group(0), f'*"[[{x[0].target}|{y.group(2)}]]"'))
                        else:
                            lines.append(ln.replace(z.group(0), f'*"[[{x[0].target}]]"'))
                        continue
                lines.append(ln)
            it.lines = lines

        if key == "Release/Reception":
            to_pop = set()
            for sx, sk in it.subsections.items():
                if sx.startswith("Merchandise") or "tie-ins" in sx:
                    if "Adaptations" in valid:
                        valid["Adaptations"][0].lines += sk.lines
                    elif "Adaptations" not in sections:
                        sections["Adaptations"] = SectionLeaf("Adaptations", MEDIA_STRUCTURE["Adaptations"], 0, 2, sk.lines)
                    else:
                        sections["Adaptations"].lines += sk.lines
                    to_pop.add(sx)
            for x in to_pop:
                it.subsections.pop(x)

        if not it.remove:
            new_items.append(it)
    return new_items


def add_and_cleanup_sections(target: Page, results: PageComponents, sections: Dict[str, SectionLeaf],
                             valid: Dict[str, List[SectionLeaf]],
                             appearances: FullListData, sources: FullListData, novel: Page, images: List[str]):

    title = target.title()
    if results.infobox in ["TelevisionEpisode", "MagazineArticle", "Adventure", "ShortStory", "ComicStory"]:
        handle_published_in_and_collections(target, title, results, appearances, sources)

    if results.infobox == "TradingCardSet":
        add_sections_if_missing(sections, "Card List", lines=["{{IncompleteList|oou=1}}"])

    if results.infobox in ["ShortStory", "ComicBook", "ComicStory", "WebStrip"]:
        add_plot_summary(sections, results)
        if any(a.is_true_appearance for a in appearances.target.get(target.title(), [])):
            add_sections_if_missing(sections, "Appearances", lines=NEW_APP_TEMPLATE)

    elif results.infobox == "Audiobook":
        tx = re.sub("^(.*?)( \(.*?\))$", "|''\\1''\\2", title) if "(" in title else ""
        add_sections_if_missing(sections, "Plot Summary", lines=[f"{{{{Plot-link|{title}{tx}}}}}"])

        if "Appearances" not in valid and "(" in title and "(abridged" not in title and novel:
            sections["Appearances"] = SectionLeaf("Appearances", "==Appearances==", 0, 2)
            if novel.exists() and not novel.isRedirectPage() and "Plot summary" in novel.get() and "<onlyinclude>\n{{App" not in novel.get():
                sections["Appearances"].lines = [f"{{{{:{title.split(' (')[0]}}}}}"]
            else:
                sections["Appearances"].lines = ["{{MissingAppFlag}}"]

    if results.collections.items:
        add_sections_if_missing(sections, "Media", "Collections", actual="Collected in")

    if images:
        add_sections_if_missing(sections, "Media", "Cover gallery", child_lines=["<gallery>"])
        sections["Media"].subsections["Cover gallery"].lines += images
        if not any("</gallery" in ln for ln in sections["Media"].subsections["Cover gallery"].lines):
            sections["Media"].subsections["Cover gallery"].lines.append("</gallery>")

    for key in REMOVE_LINKS:
        if key in sections:
            sections[key].lines = [remove_links(ln) for ln in sections[key].lines]

    # Validation
    if "Contents" in sections and "Plot Summary" in sections:   # Contents & Plot Summary should not be used together
        sections["Plot Summary"].flag = True
    if "Media" in sections and len(sections["Media"].subsections) == 0:
        sections["Media"].flag = True
    # TODO: flag book collections/etc. with missing Contents sections

    return sections


def add_sections_if_missing(sections: Dict[str, SectionLeaf], name: str, child: str = None, actual: str = None,
                            other_names: List[str] = None, lines: List[str] = None, child_lines: List[str] = None):
    if name not in sections:
        sections[name] = SectionLeaf(name, MEDIA_STRUCTURE.get(name, f"=={name}=="), 0, 2)
        if lines:
            sections[name].lines = lines

    if child:
        if other_names and sections[name].has_subsections(other_names):
            return False
        elif actual and sections[name].has_subsections(actual, child):
            return False
        elif not sections[name].has_subsections(child):
            sections[name].subsections[child] = SectionLeaf(child, f"==={actual or child}===", 0, 3)
            if child_lines:
                sections[name].subsections[child].lines = child_lines
            if name in SUBSECTIONS and child in SUBSECTIONS[name]:
                sections[name].subsections[child].master_num = SUBSECTIONS[name].index(child)


def add_plot_summary(sections: Dict[str, SectionLeaf], results: PageComponents):
    if "Plot Summary" not in sections and "Contents" not in sections:
        if not any(f"|{x}=1\n" in results.before for x in ["reprint", "anthology", "not_appearance"]):
            sections["Plot Summary"] = SectionLeaf("Plot summary", "==Plot summary==", 0, 2)
    if "Plot Summary" in sections and sections["Plot Summary"].is_empty_section():
        sections["Plot Summary"].lines.append("{{Plot}}")


def handle_published_in_and_collections(target: Page, title: str, results: PageComponents, appearances: FullListData,
                                        sources: FullListData):
    drx = re.search(
        "\|(publish date|publication date|first aired|airdate|start date|first date|release date|released|published)=.*?(<ref name ?= ?\".*?\")/?>",
        target.get())
    date_ref = drx.group(2) + " />" if drx else None
    current = targets(results.collections)
    added = []
    links, refs, contents = set(), {}, {}
    if results.infobox == "TelevisionEpisode":
        items_to_check = [k for k, v in DVDS.items() if title in v and k not in current]
    else:
        items_to_check = [i.parent for i in get_listings(title, appearances, sources) if i.parent and i.parent not in current]

    for item in items_to_check:
        x = get_listings(item, appearances, sources)
        if x:
            results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents, date_ref))
            current.append(item)
        else:
            print(f"Unknown state: {item} not found in Sources")

    for field in ["published", "reprinted"]:
        rx = re.search("\|" + field + " in=\n?((\*?'*\[\[(.*?)(\|.*?)]]'*.*?\n)+)", target.get())
        if rx:
            zx = rx.group(1).splitlines()
            for z in zx:
                y = re.search("^\*?'*\[\[(.*?)(\|.*?)?]]", z)
                if y and y.group(1) not in current:
                    x = get_listings(y.group(1), appearances, sources)
                    if x:
                        results.collections.items.append(copy_listing(x[0], target.site, links, refs, contents, date_ref))
                        current.append(y.group(1))
                    else:
                        print(f"Unknown {field}-in value: {y.group(1)}")

    to_remove = []
    for i in range(len(results.src.items)):
        if results.src.items[i].target == title:
            print(f"Removing self-listing from Sources")
            to_remove.append(i)
        elif results.src.items[i].target and results.src.items[i].target in current:
            print(f"Removing Collections listing from Sources (new={results.src.items[i].target in added})")
            to_remove.append(i)
        elif results.src.items[i].parent and results.src.items[i].parent in current and "{{PAGENAME}}" in results.src.items[i].original:
            print(f"Removing Collections listing from Sources (new={results.src.items[i].target in added})")
            to_remove.append(i)
    if to_remove:
        results.src.items = [x for i, x in enumerate(results.src.items) if i not in to_remove]


def copy_listing(x: Item, site, links: set, refs: dict, contents: dict, date_ref=None):
    nx = x.copy()
    date_str = None
    # if date_ref:
    #     date_str, _ = convert_date_str(nx.date, links)
    # else:
    #     rn = nx.target.replace("(", "").replace(")", "").replace("'", "")
    #     date_str, date_ref = build_date_and_ref(nx, site, links, refs, contents, ref_name=rn)
    if date_str:
        nx.extra = f" &mdash; {date_str}{date_ref}"
    return nx


def targets(s: SectionComponents):
    return [i.target for i in s.items]


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
            if any(sx in v for k, v in SUBSECTIONS.items() if k != kx):
                continue

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


ITALICIZE = ["Book", "Audiobook", "ComicSeries", "ComicCollection", "ComicArc", "GraphicNovel", "ReferenceBook"]
ISSUE = ["Magazine", "MagazineIssue", "ComicBook", "Comic", "ReferenceMagazine"]
QUOTES = ["MagazineArticle", "MagazineDepartment", "ShortStory", "ComicStory", "Adventure", "ComicStrip"]
ADD_REF = ["ReferenceBook", "Magazine", "MagazineArticle", "MagazineDepartment", "Soundtrack", "MagazineSeries",
           "ToyLine"]


def simplify(s):
    return re.sub(
        "(''+|<br ?/?>)", " ",
        s.replace("&#34;", '"').replace("–", "-").replace("—", "-").replace("&mdash;", "-").replace("&ndash;", "-")
        .replace("&hellip;", "...").replace("…", "...").split(" (")[0]
    ).replace("  ", " ").replace("#", "")


def equals_or_starts_with(s, t):
    return s == t or s.startswith(t) or t.startswith(s) or s.endswith(t) or t.endswith(s)


def trim(s, t):
    n = ""
    for c in s:
        if not t.startswith(simplify(f"{n}{c}")):
            break
        n += c
    return n


def prepare_title_format(results: PageComponents, page: Page, appearances: FullListData, sources: FullListData):
    fmt, top_fmt, text_fmt = None, None, None
    skip = False
    if results.infobox == "Audiobook":
        fmt = f"''{page.title().split(' (')[0]}''"
    elif page.title() in appearances.target:
        if not appearances.target[page.title()][0].template:
            fmt = appearances.target[page.title()][0].original
    elif page.title() in sources.target:
        if sources.target[page.title()][0].title_format_text():
            fmt = sources.target[page.title()][0].title_format_text()
            if len(sources.target[page.title()]) > 1 and "department" not in page.title():
                if len([s for s in sources.target[page.title()] if not s.reprint]) == 1:
                    pass
                elif " Part " in fmt:
                    fmt = re.sub("[:,]? Part (One|Two|Three|Four|I+|[0-9]+).*?$", "", fmt)
                else:
                    fmt = None
                    skip = True
        elif not sources.target[page.title()][0].template:
            fmt = sources.target[page.title()][0].original
    if not fmt and results.infobox:
        if results.infobox in ISSUE:
            fmt = re.sub("^(.*?)( \([0-9]+\))? ([0-9]+)( \(.*?\))?$", "''\\1''\\2 \\3", page.title())
        if results.infobox in ITALICIZE or (fmt and "''" in fmt):
            fmt = "''" + re.sub(" \(.*?\)$", "", page.title()) + "''"

    fmt = fmt or page.title()
    if "|" in fmt:
        fmt = re.sub("^.*\[\[.*?\|(.*?)]].*?$", "\\1", fmt)
    elif "[[" in fmt:
        fmt = re.sub("^\"?('')?\[\[(.*?)]]('')?\"?$", "\\1\\2\\3", fmt)
    if fmt and " (" in page.title() and page.title().endswith(")") and " (" not in fmt:
        z = page.title().split(" (")[0]
        fmt = f"''{z}''" if f"''{z}''" in fmt else z

    fmt = "<b>" + re.sub(" \(.*?\)$", "", fmt) + "<b>"
    if results.infobox in QUOTES and not skip and not (page.title().startswith('"') and page.title().endswith('"')) \
            and not (fmt.startswith('"') and fmt.endswith('"')):
        fmt = "<q>" + fmt + "<q>"
    top_fmt = fmt.replace("<q>", "").replace("<b>", "")
    fmt = re.sub("^(.*?) \([0-9]+\) ([0-9]+)", "\\1 \\2", fmt)
    field_fmt = fmt.replace("<q>", "").replace("<b>", "")
    text_fmt = fmt.replace("<q>", "\"").replace("<b>", "'''")

    return top_fmt, field_fmt, text_fmt


def determine_field_format(x: str, title: str, types: dict, appearances: FullListData, sources: FullListData, remove_prefix=False):
    ns = _determine_field_format(x, types, appearances, sources)
    if ns:
        if " (" in ns:
            ns = re.sub("'*\[\[([^\n\]\[]*?)( \([0-9]+\))? ([0-9]+)(\|[^\n\]\[]*?)?]]'*", "[[\\1\\2 \\3|''\\1'' \\3]]",
                        ns)
        if remove_prefix and title:
            z, d, e = None, title.rsplit(": ", 1)[0], x.rsplit(": ", 1)[0]
            if d == e:
                z = f"{e}: "
            elif d.rsplit(" ", 1)[-1].isnumeric() and e.rsplit(" ", 1)[0].isnumeric():
                d1, _, d2 = d.rpartition(" ")
                e1, _, e2 = e.rpartition(" ")
                if d1 and d2 and e1 and e2 and d1 == e2:
                    z = f"{e}: "

            if z and "|" in ns:
                a, _, b = ns.partition("|")
                ns = f"{a}|{b.replace(z, '')}"
            elif z:
                ns = re.sub("('')?\[\[(.*?)]]('')?", "[[\\2|\\1" + x.replace(z, "") + "\\3]]", ns)
    return ns


def _determine_field_format(x, types: dict, appearances: FullListData, sources: FullListData):
    z = get_listings(x, appearances, sources)
    if not z:
        return None
    elif not z[0].template:
        return z[0].original.replace(" comic adaptation]]", "]]").replace(" comic series]]", "]]")
    elif z[0].template == "StoryCite" or types.get(z[0].template) == "TV" or z[0].template in types.get("Magazine", []):
        if z[0].format_text:
            return f"\"[[{z[0].target}|{z[0].format_text}]]\""
        elif "(" in z[0].target:
            return f"\"[[{z[0].target}|{z[0].target.split(' (')[0]}]]\""
        else:
            return f"\"[[{z[0].target}]]\""
    return None


PREV_OR_NEXT = ["|preceded by=", "|followed by=", "|prev=", "|next="]
MEDIA_FIELDS = ["|published in=", "|reprinted in=", "|series=", *PREV_OR_NEXT]


def is_infobox_field(ln, prev, fields):
    for x in fields:
        if x in ln or (x in prev and not ln.startswith("|")):
            return x
    return None


def prepare_media_infobox_and_intro(page: Page, results: PageComponents, redirects, disambigs, types,
                                    remap, appearances: FullListData, sources: FullListData) -> Tuple[List[str], str]:
    top_fmt, field_fmt, text_fmt = prepare_title_format(results, page, appearances, sources)

    text = fix_redirects(redirects, results.before.strip(), "Intro", disambigs, remap,
                         appearances=appearances.target, sources=sources.target)

    pieces = []
    image = ""
    ct = 0
    publisher_listing = set()
    book_publishers = set()
    infobox_found, infobox_done, title_found = not results.infobox, not results.infobox, False
    prev = ""
    flagged = False
    for ln in text.splitlines():
        if "{{top" in ln.lower():
            ln = sort_top_template(ln, results.infobox in ADD_REF, top_fmt)
        elif not infobox_done:  # infobox field handling
            if results.original_infobox and (f"{{{{{results.original_infobox}".lower() in ln.lower() or f"{{{{{results.original_infobox.replace(' ', '_')}".lower() in ln.lower()):
                infobox_found = True
            elif f"{{{{{results.infobox}".lower() in ln.lower() or f"{{{{{results.infobox.replace(' ', '_')}".lower() in ln.lower():
                infobox_found = True
            elif ln.startswith("|"):
                media_field = is_infobox_field(ln, prev, MEDIA_FIELDS)
                if media_field:
                    x = re.search("^((\|[a-z ]+=)?\*?)'*\[\[(.*?)(\|'*(.*?)'*)?]]'*", ln)
                    if x:
                        ns = determine_field_format(x.group(3), page.title(), types, appearances, sources, media_field in PREV_OR_NEXT)
                        if ns:
                            ln = ln.replace(x.group(0), f"{x.group(1)}{ns}")
                elif ln.startswith("|title=") and field_fmt:
                    if ("''" in field_fmt and "''" not in ln) or ("''" in ln and "''" not in field_fmt) or simplify(field_fmt) not in simplify(ln):
                        ln = f"|title={field_fmt}"
                elif ln.startswith("|publisher="):
                    x = re.search("\|publisher=\[\[(.*?)(\|.*?)?]]", ln)
                    if x and "Disney" in x.group(1):
                        book_publishers = {"Disney"}
                    elif x and "Random House" in x.group(1):
                        book_publishers = {"PenguinBooks", "PenguinRandomHouse", "RandomHouseBooks"}
                elif ln.startswith("|image="):
                    x = re.search("\|image=\[*([Ff]ile:.*?)[|\n\]]", ln)
                    if x:
                        image = x.group(1).replace("file:", "File").replace(" ", "_")
                prev = ln
            if infobox_found:
                ct += (ln.count("{") - ln.count("}"))
                infobox_done = ct == 0

            if "{{Marvel|url=comics/" in ln or "{{DarkHorse|url=Comics/" in ln or "{{IDW|url=product/" in ln:
                x = re.search("\{\{(DarkHorse|Marvel|IDW)\|url=((product/|[Cc]omics/(?!Preview)).*)\|.*?}}", ln)
                if x:
                    publisher_listing.add((x[0], x[1], x[2]))

        # introduction handling
        elif not title_found and text_fmt and text_fmt in ln:
            title_found = True
        elif not title_found and text_fmt and ("'''" in ln or simplify(page.title()) in ln):
            ft = False
            if ln.count("'''") >= 2:
                for x, y in re.findall("(\"?'''+\"?(.*?)\"?'''+\"?)", ln):
                    if equals_or_starts_with(simplify(y.replace('"', '')).lower(), simplify(page.title().replace('"', '')).lower()) and "[[" not in y:
                        ln = ln.replace(x, text_fmt)
                        ft = True
                if not ft and re.search("'''''.*?'''.*?'' ", ln):
                    ln = re.sub("'''.*?'''.*?'' ", f"{text_fmt} ", ln)
                    ft = True
                if not ft:
                    print(f"Multiple bolded titles in intro, but no close match; cannot replace title with {text_fmt}")
                    if not flagged:
                        if "IntroMissingTitle" not in ln:
                            ln = "{{IntroMissingTitle}} " + ln
                        flagged = True
            if ft or flagged:
                pass
            elif re.search("\"?'''+\"?(.*?)\"?'''+\"?", ln):
                ln = re.sub("\"?'''+\"?(.*?)\"?'''+\"?", text_fmt, ln)
            else:
                z = re.search("\"(.*?)\"", re.sub("<ref name=\".*?\"(>.*?</ref>| ?/>)", "", ln))
                if z and simplify(page.title()) in z.group(1):
                    ln = ln.replace(z.group(0), text_fmt)
            title_found = True

        multiple_and_redlink = "{{multiple" in ln.lower() and ("|redlink|" in ln or "|redlink}}" in ln)
        if multiple_and_redlink or "{{redlink" in ln.lower():
            count = get_redlink_count(page)
            if count <= 5:
                print(f"{page.title()} has {count} redlinks; removing Redlink template")
                if multiple_and_redlink:
                    ln = re.sub("\|redlink(?=(\||}}))", "", ln)
                else:
                    ln = re.sub("\{\{[Rr]edlink.*?}}", "", ln)
                if not ln.strip():
                    continue

        pieces.append(ln)

    if page.title() in PUBLISHERS:
        x = re.search("\{\{(DarkHorse|Marvel|IDW)\|url=((product/|[Cc]omics/(?!Preview)).*)\|.*?}}", PUBLISHERS[page.title()])
        if x:
            publisher_listing.add((x[0], x[1], x[2]))

    for p, template, url in publisher_listing:
        if any(url == o.url for o in results.links.items):
            continue
        print(f"Found publisher listing: {p} ({url})")
        tz = re.search("\|text=(.*?)(\|.*?)?}}", p)
        results.links.items.append(Item(p, "Publisher", False, template=template, url=url, text=tz.group(1) if tz else None))
    if book_publishers:
        for x in results.links.items:
            if x.template in book_publishers and is_commercial(x):
                x.mark_as_publisher()
    elif results.infobox == "VideoGame" and ("Category:Web-based" in page.get() or " web-based games" in page.get()):
        for x in results.links.items:
            if x.template == "LEGOWeb" and "games/" in x.url:
                x.mark_as_publisher()
            elif "domain=games" in x.original:
                x.mark_as_publisher()

    return pieces, image


def get_redlink_count(page: Page):
    count = 0
    for x in page.linkedPages():
        if not x.exists():
            count += 1
    return count

# TODO: split Appearances subsections by length

# TODO: use Masterlist formatting for Contents sections
# TODO: Fix redirects in the Contents section without preserving the original pipelink, UNLESS it's a department
# TODO: convert "Introduction" to a Contents bullet

# TODO - Advanced
# TODO: parse and standardize ISBN lines in Editions
# TODO: build prettytable for issues sections?
# TODO: flag release date reference with Amazon, Previews, etc.
# TODO: parse Editions and sort ExL publisher listings by that order
# TODO: load comic magazines and add to Collections
