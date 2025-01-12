import re
import traceback
from datetime import datetime

from pywikibot import Page, Category
from c4de.sources.domain import Item, FullListData
from c4de.sources.determine import extract_item, TEMPLATE_MAPPING
from c4de.common import build_redirects, fix_redirects


SUBPAGES = [
    "Canon/General", "Legends/General/1977-2000", "Legends/General/2000s", "Legends/General/2010s", "Canon/Toys",
    "Legends/Toys", "CardSets", "Soundtracks", "Canon/RefMagazine", "Legends/RefMagazine", "Reprint"
]

HYPERSPACE = {
    "hyperspace/fiction/fiction20090920/index.html": "The Longest Fall",
    "hyperspace/fiction/n20090923fiction/index.html": "Betrayal by Knight",
    "hyperspace/member/fiction/f20040206/index.html": "First Contact",
    "hyperspace/member/fiction/f20040211/index.html": "Day of the Sepulchral Night (short story)",
    "hyperspace/member/fiction/f20040319/index.html": "Bane of the Sith",
    "hyperspace/member/fiction/f20040416/index.html": "Murder in Slushtime",
    "hyperspace/member/fiction/f20040430/index.html": "Tinian on Trial",
    "hyperspace/member/fiction/f20040507/index.html": "Mist Encounter",
    "hyperspace/member/fiction/f20040521/index.html": "Missed Chance",
    "hyperspace/member/fiction/f20040604/index.html": "The Crystal",
    "hyperspace/member/fiction/f20040618/index.html": "Whispers in the Dark",
    "hyperspace/member/fiction/f20040702/index.html": "Handoff",
    "hyperspace/member/fiction/f20040719/index.html": "The Monster",
    "hyperspace/member/fiction/f20040720/index.html": "Changing Seasons",
    "hyperspace/member/fiction/f20040730/index.html": "Out of the Cradle",
    "hyperspace/member/fiction/f20040809/index.html": "The Emperor's Trophy",
    "hyperspace/member/fiction/f20040903/index.html": "Mission to Zila",
    "hyperspace/member/fiction/f20040924/index.html": "Dark Vendetta (short story)",
    "hyperspace/member/fiction/f20041001/index.html": "The Final Exit",
    "hyperspace/member/fiction/f20041015/index.html": "Double Cross on Ord Mantell",
    "hyperspace/member/fiction/f20041029/index.html": "Darkness Shared",
    "hyperspace/member/fiction/f20041105/index.html": "Changing Seasons",
    "hyperspace/member/fiction/f20041117/index.html": "Escape from Balis-Baurgh",
    "hyperspace/member/fiction/f20041217/index.html": "One of a Kind (short story)",
    "hyperspace/member/fiction/f20041222/index.html": "The Apprentice (short story)",
    "hyperspace/member/fiction/f20050107/index.html": "The Breath of Gelgelar",
    "hyperspace/member/fiction/f20050121/index.html": "Shadows of Darkness",
    "hyperspace/member/fiction/f20050218/index.html": "Or Die Trying",
    "hyperspace/member/fiction/f20050304/index.html": "When the Domino Falls",
    "hyperspace/member/fiction/f20050325/index.html": "Spare Parts (short story)",
    "hyperspace/member/fiction/f20050401/index.html": "Hunting the Hunters",
    "hyperspace/member/fiction/f20050415/index.html": "A Bitter Winter",
    "hyperspace/member/fiction/f20050429/index.html": "Pearls in the Sand",
    "hyperspace/member/fiction/f20050513/index.html": "Side Trip",
    "hyperspace/member/fiction/f20050520/index.html": "Side Trip",
    "hyperspace/member/fiction/f20050603/index.html": "Side Trip",
    "hyperspace/member/fiction/f20050617/index.html": "Side Trip",
    "hyperspace/member/fiction/f20050701/index.html": "Elusion Illusion",
    "hyperspace/member/fiction/f20050722/index.html": "Droid Trouble",
    "hyperspace/member/fiction/f20050805/index.html": "Turning Point (Charlene Newcomb)",
    "hyperspace/member/fiction/f20050819/index.html": "Changing the Odds: The Adventures of Dannen Lifehold",
    "hyperspace/member/fiction/f20050902/index.html": "Command Decision",
    "hyperspace/member/fiction/f20050923/index.html": "To Fight Another Day",
    "hyperspace/member/fiction/f20051007/index.html": "Finder's Fee",
    "hyperspace/member/fiction/f20051028/index.html": "The Trouble with Squibs",
    "hyperspace/member/fiction/f20051104/index.html": "Ringers",
    "hyperspace/member/fiction/f20051118/index.html": "Rendezvous with Destiny",
    "hyperspace/member/fiction/f20051202/index.html": "Kella Rand, Reporting...",
    "hyperspace/member/fiction/f20051216/index.html": "Uhl Eharl Khoehng (short story)",
    "hyperspace/member/fiction/f20060106/index.html": "Blaze of Glory (short story)",
    "hyperspace/member/fiction/f20060127/index.html": "The Clone Wars: The Pengalan Tradeoff",
    "hyperspace/member/fiction/f20060317/index.html": "Slaying Dragons",
    "hyperspace/member/fiction/f20060328/index.html": "Combat Moon (short story)",
    "hyperspace/member/fiction/f20060331/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060403/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060405/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060407/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060410/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060412/index.html": "Emissary of the Void",
    "hyperspace/member/fiction/f20060428/index.html": "A Certain Point of View (short story)",
    "hyperspace/member/fiction/f20060512/index.html": "Firepower",
    "hyperspace/member/fiction/f20060526/index.html": "Deep Spoilers",
    "hyperspace/member/fiction/f20060911/index.html": "Do No Harm",
    "hyperspace/member/fiction/f20060918/index.html": "The Most Dangerous Foe",
    "hyperspace/member/fiction/f20070111/index.html": "Only Droids Serve the Maker",
    "hyperspace/member/fiction/f20070709/index.html": "The Capture of Imperial Hazard",
    "hyperspace/member/fiction/f20080310/index.html": "Retreat from Coruscant",
    "hyperspace/member/fiction/f20080311/index.html": "MedStar: Intermezzo",
    "hyperspace/member/fiction/f20080313/index.html": "League of Spies",
}

SERIES_MAPPING = {
    "Star Wars (1977)": ["Star Wars (1977)", 1, 108],
    "Star Wars (1998)": ["Star Wars (1998)", 1, 45],
    "Star Wars (2013)": ["Star Wars (2013)", 1, 20],
    "Star Wars: Dark Times: Parallels": ["Dark Times", 6, 10],
    "Star Wars: Dark Times: The Path to Nowhere": ["Dark Times", 1, 5],
    "Star Wars: Dark Times: Vector": ["Dark Times", 11, 12],
    "Star Wars: Empire: A Little Piece of Home": ["Empire", 20, 21],
    "Star Wars: Empire: Betrayal": ["Empire", 1, 4],
    "Star Wars: Empire: Darklighter": ["Empire", 8, 9],
    "Star Wars: Empire: Idiot's Array": ["Empire", 24, 25],
    "Star Wars: Empire: In the Shadows of Their Fathers": ["Empire", 29, 34],
    "Star Wars: Empire: Princess... Warrior": ["Empire", 5, 6],
    "Star Wars: Empire: The Short, Happy Life of Roons Sewell": ["Empire", 10, 11],
    "Star Wars: Empire: The Wrong Side of the War": ["Empire", 36, 40],
    "Star Wars: Empire: To the Last Man": ["Empire", 16, 18],
    "Star Wars: Empire: \"General\" Skywalker": ["Empire", 26, 27],
    "Star Wars: Knights of the Old Republic: Commencement": ["Knights of the Old Republic", 1, 6],
    "Star Wars: Knights of the Old Republic: Days of Fear": ["Knights of the Old Republic", 13, 15],
    "Star Wars: Knights of the Old Republic: Daze of Hate": ["Knights of the Old Republic", 19, 21],
    "Star Wars: Knights of the Old Republic: Destroyer": ["Knights of the Old Republic", 45, 46],
    "Star Wars: Knights of the Old Republic: Demon": ["Knights of the Old Republic", 47, 50],
    "Star Wars: Knights of the Old Republic: Dueling Ambitions": ["Knights of the Old Republic", 39, 41],
    "Star Wars: Knights of the Old Republic: Exalted": ["Knights of the Old Republic", 29, 30],
    "Star Wars: Knights of the Old Republic: Flashpoint": ["Knights of the Old Republic", 7, 10],
    "Star Wars: Knights of the Old Republic: Knights of Suffering": ["Knights of the Old Republic", 22, 24],
    "Star Wars: Knights of the Old Republic: Nights of Anger": ["Knights of the Old Republic", 16, 18],
    "Star Wars: Knights of the Old Republic: Prophet Motive": ["Knights of the Old Republic", 36, 37],
    "Star Wars: Knights of the Old Republic: Reunion": ["Knights of the Old Republic", 11, 12],
    "Star Wars: Knights of the Old Republic: The Reaping": ["Knights of the Old Republic", 43, 44],
    "Star Wars: Knights of the Old Republic: Vector": ["Knights of the Old Republic", 25, 28],
    "Star Wars: Knights of the Old Republic: Vindication": ["Knights of the Old Republic", 32, 35],
    "Star Wars: Knights of the Old Republic: War": ["Knights of the Old Republic: War", 1, 5],
    "Star Wars: Legacy: Broken": ["Legacy (2006)", 1, 7],
    "Star Wars: Legacy: Claws of the Dragon": ["Legacy (2006)", 14, 19],
    "Star Wars: Legacy: Extremes": ["Legacy (2006)", 48, 50],
    "Star Wars: Legacy: Fight Another Day": ["Legacy (2006)", 32, 33],
    "Star Wars: Legacy: Ghosts": ["Legacy (2006)", 11, 12],
    "Star Wars: Legacy: Indomitable": ["Legacy (2006)", 20, 21],
    "Star Wars: Legacy: Loyalties": ["Legacy (2006)", 23, 24],
    "Star Wars: Legacy: Monster": ["Legacy (2006)", 43, 46],
    "Star Wars: Legacy: Storms": ["Legacy (2006)", 34, 35],
    "Star Wars: Legacy: Tatooine": ["Legacy (2006)", 37, 40],
    "Star Wars: Legacy: The Hidden Temple": ["Legacy (2006)", 25, 26],
    "Star Wars: Legacy: Trust Issues": ["Legacy (2006)", 9, 10],
    "Star Wars: Legacy: Vector": ["Legacy (2006)", 28, 31],
    "Star Wars: Legacy: Prisoner of the Floating World": ["Legacy (2013)", 1, 5],
    "Star Wars: Legacy: Outcasts of the Broken Ring": ["Legacy (2013)", 6, 10],
    "Star Wars: Legacy: Wanted: Ania Solo": ["Legacy (2013)", 11, 15],
    "Star Wars: Legacy: Empire of One": ["Legacy (2013)", 16, 18],
    "Star Wars: Rebellion: My Brother, My Enemy": ["Rebellion", 1, 5],
    "Star Wars: Rebellion: The Ahakista Gambit": ["Rebellion", 6, 10],
    "Star Wars: Rebellion: Small Victories": ["Rebellion", 11, 14],
    "Star Wars: Rebellion: Vector": ["Rebellion", 15, 16],
    "Star Wars: Prelude to Rebellion": ["Star Wars (1998)", 1, 6],
    "Star Wars: Outlander": ["Star Wars (1998)", 7, 12],
    "Star Wars: Emissaries to Malastare": ["Star Wars (1998)", 13, 18],
    "Star Wars: Twilight": ["Star Wars (1998)", 19, 22],
    "Star Wars: Infinity's End": ["Star Wars (1998)", 23, 26],
    "Star Wars: The Hunt for Aurra Sing": ["Star Wars (1998)", 28, 31],
    "Star Wars: Darkness": ["Star Wars (1998)", 32, 35],
    "Star Wars: The Stark Hyperspace War": ["Star Wars (1998)", 36, 39],
    "Star Wars: The Devaronian Version": ["Star Wars (1998)", 40, 41],
    "Star Wars: Rite of Passage": ["Star Wars (1998)", 42, 45],
    "Star Wars: Republic: Honor and Duty": ["Republic", 46, 48],
    "Star Wars: Republic: The New Face of War": ["Republic", 51, 52],
    "Star Wars: Republic: The Battle of Jabiim": ["Republic", 55, 58],
    "Star Wars: Republic: Show of Force": ["Republic", 65, 66],
    "Star Wars: Republic: Dreadnaughts of Rendili": ["Republic", 69, 71],
    "Star Wars: Republic: Trackdown": ["Republic", 72, 73],
    "Star Wars: Republic: Siege of Saleucami": ["Republic", 74, 77],
    "Star Wars: Republic: Into the Unknown": ["Republic", 79, 80],
    "Star Wars: Republic: Hidden Enemy": ["Republic", 81, 83],
    "Star Wars: X-Wing Rogue Squadron: The Rebel Opposition": ["X-Wing Rogue Squadron", 1, 4],
    "Star Wars: X-Wing Rogue Squadron: The Phantom Affair": ["X-Wing Rogue Squadron", 5, 8],
    "Star Wars: X-Wing Rogue Squadron: Battleground: Tatooine": ["X-Wing Rogue Squadron", 9, 12],
    "Star Wars: X-Wing Rogue Squadron: The Warrior Princess": ["X-Wing Rogue Squadron", 13, 16],
    "Star Wars: X-Wing Rogue Squadron: Requiem for a Rogue": ["X-Wing Rogue Squadron", 17, 20],
    "Star Wars: X-Wing Rogue Squadron: In the Empire's Service": ["X-Wing Rogue Squadron", 21, 24],
    "Star Wars: X-Wing Rogue Squadron: Family Ties": ["X-Wing Rogue Squadron", 25, 27],
    "Star Wars: X-Wing Rogue Squadron: Masquerade": ["X-Wing Rogue Squadron", 28, 31],
    "Star Wars: X-Wing Rogue Squadron: Mandatory Retirement": ["X-Wing Rogue Squadron", 33, 35],
    "Star Wars 3-D": ["Star Wars 3-D", 1, 3],
    "Star Wars Manga: A New Hope": ["Star Wars Manga: A New Hope", 1, 4],
    "Star Wars Manga: Return of the Jedi": ["Star Wars Manga: Return of the Jedi", 1, 4],
    "Star Wars Manga: The Empire Strikes Back": ["Star Wars Manga: The Empire Strikes Back", 1, 4],
    "Star Wars Manga: The Phantom Menace": ["Star Wars Manga: The Phantom Menace", 1, 2],
    "Star Wars: A New Hope - The Special Edition": ["Star Wars: A New Hope - The Special Edition", 1, 4],
    "Star Wars: Agent of the Empire—Hard Targets": ["Agent of the Empire – Hard Targets", 1, 5],
    "Star Wars: Agent of the Empire—Iron Eclipse": ["Agent of the Empire – Iron Eclipse", 1, 5],
    "Star Wars: Blood Ties: A Tale of Jango and Boba Fett": ["Blood Ties: A Tale of Jango and Boba Fett", 1, 4],
    "Star Wars: Blood Ties: Boba Fett is Dead": ["Blood Ties: Boba Fett is Dead", 1, 4],
    "Star Wars: Boba Fett: Enemy of the Empire": ["Boba Fett: Enemy of the Empire", 1, 4],
    "Star Wars: Chewbacca (2000)": ["Chewbacca (2000)", 1, 4],
    "Star Wars: Crimson Empire II: Council of Blood": ["Crimson Empire II: Council of Blood", 1, 6],
    "Star Wars: Crimson Empire III—Empire Lost": ["Crimson Empire III: Empire Lost", 1, 6],
    "Star Wars: Crimson Empire": ["Crimson Empire", 1, 6],
    "Star Wars: Dark Empire II": ["Dark Empire II", 1, 6],
    "Star Wars: Dark Empire": ["Dark Empire", 1, 6],
    "Star Wars: Dark Force Rising": ["Dark Force Rising", 1, 6],
    "Star Wars: Dark Times": ["Dark Times", 1, 17],
    "Star Wars: Dark Times: Blue Harvest": ["Dark Times: Blue Harvest, Part", 1, 2],
    "Star Wars: Dark Times—A Spark Remains": ["Dark Times—A Spark Remains", 1, 5],
    "Star Wars: Dark Times—Fire Carrier": ["Dark Times—Fire Carrier", 1, 5],
    "Star Wars: Dark Times—Out of the Wilderness": ["Dark Times—Out of the Wilderness", 1, 5],
    "Star Wars: Darth Maul (2000)": ["Darth Maul (2000)", 1, 4],
    "Star Wars: Darth Maul—Death Sentence": ["Darth Maul—Death Sentence", 1, 4],
    "Star Wars: Darth Maul—Son of Dathomir": ["Darth Maul—Son of Dathomir", 1, 4],
    "Star Wars: Darth Vader and the Cry of Shadows": ["Darth Vader and the Cry of Shadows", 1, 5],
    "Star Wars: Darth Vader and the Ghost Prison": ["Darth Vader and the Ghost Prison", 1, 5],
    "Star Wars: Darth Vader and the Lost Command": ["Darth Vader and the Lost Command", 1, 5],
    "Star Wars: Darth Vader and the Ninth Assassin": ["Darth Vader and the Ninth Assassin", 1, 5],
    "Star Wars: Dawn of the Jedi: Force Storm": ["Dawn of the Jedi: Force Storm", 1, 5],
    "Star Wars: Dawn of the Jedi: Force War": ["Dawn of the Jedi: Force War", 1, 5],
    "Star Wars: Dawn of the Jedi: The Prisoner of Bogan": ["Dawn of the Jedi: The Prisoner of Bogan", 1, 5],
    "Star Wars: Droids (1986)": ["Droids (1986)", 1, 8],
    "Star Wars: Droids (1994)": ["Droids (1994)", 1, 6],
    "Star Wars: Droids (1995)": ["Droids (1995)", 1, 8],
    "Star Wars: Empire": ["Empire", 1, 40],
    "Star Wars: Empire's End": ["Empire's End", 1, 2],
    "Star Wars: Episode I — The Phantom Menace": ["Star Wars: Episode I — The Phantom Menace", 1, 4],
    "Star Wars: Episode II — Attack of the Clones": ["Star Wars: Episode II — Attack of the Clones", 1, 4],
    "Star Wars: Episode III — Revenge of the Sith": ["Star Wars: Episode III — Revenge of the Sith", 1, 4],
    "Star Wars: Ewoks (1985)": ["Ewoks (1985)", 1, 14],
    "Star Wars: General Grievous": ["General Grievous", 1, 4],
    "Star Wars: Heir to the Empire": ["Heir to the Empire", 1, 6],
    "Star Wars: In the Shadow of Yavin": ["Star Wars (2013)", 1, 20],
    "Star Wars: Invasion: Refugees": ["Invasion", 1, 5],
    "Star Wars: Invasion: Rescues": ["Invasion: Rescues", 1, 6],
    "Star Wars: Invasion: Revelations": ["Invasion: Revelations", 1, 5],
    "Star Wars: Jango Fett: Open Seasons": ["Jango Fett: Open Seasons", 1, 4],
    "Star Wars: Jedi Academy: Leviathan": ["Jedi Academy: Leviathan", 1, 4],
    "Star Wars: Jedi Council: Acts of War": ["Jedi Council: Acts of War", 1, 4],
    "Star Wars: Jedi Quest (comic series)": ["Jedi Quest", 1, 4],
    "Star Wars: Jedi vs. Sith": ["Jedi vs. Sith", 1, 6],
    "Star Wars: Jedi—The Dark Side": ["Jedi—The Dark Side", 1, 5],
    "Star Wars: Knight Errant: Aflame": ["Knight Errant: Aflame", 1, 5],
    "Star Wars: Knight Errant: Deluge": ["Knight Errant: Deluge", 1, 5],
    "Star Wars: Knight Errant: Escape": ["Knight Errant: Escape", 1, 5],
    "Star Wars: Knights of the Old Republic (comic series)": ["Knights of the Old Republic", 1, 50],
    "Star Wars: Legacy Volume 2": ["Legacy (2013)", 1, 18],
    "Star Wars: Legacy": ["Legacy (2006)", 1, 50],
    "Star Wars: Legacy—War": ["Legacy—War", 1, 6],
    "Star Wars: Lost Tribe of the Sith—Spiral": ["Lost Tribe of the Sith—Spiral", 1, 5],
    "Star Wars: Mara Jade – By the Emperor's Hand": ["Mara Jade – By the Emperor's Hand", 1, 6],
    "Star Wars: Obsession": ["Obsession", 1, 5],
    "Star Wars: Purge – The Tyrant's Fist": ["Purge – The Tyrant's Fist", 1, 2],
    "Star Wars: Qui-Gon and Obi-Wan: Last Stand on Ord Mantell": ["Qui-Gon and Obi-Wan: Last Stand on Ord Mantell", 1, 3],
    "Star Wars: Qui-Gon and Obi-Wan: The Aurorient Express": ["Qui-Gon and Obi-Wan: The Aurorient Express", 1, 2],
    "Star Wars: Rebel Heist": ["Rebel Heist", 1, 4],
    "Star Wars: Rebellion (comic series)": ["Rebellion", 1, 16],
    "Star Wars: Republic": ["Star Wars (1998)", 1, 45],
    "Star Wars: Return of the Jedi (1983)": ["Return of the Jedi", 1, 4],
    "Star Wars: River of Chaos": ["River of Chaos", 1, 4],
    "Star Wars: Shadows of the Empire (comic series)": ["Shadows of the Empire", 1, 6],
    "Star Wars: Shadows of the Empire: Evolution": ["Shadows of the Empire: Evolution", 1, 5],
    "Star Wars: Splinter of the Mind's Eye": ["Splinter of the Mind's Eye", 1, 4],
    "Star Wars: Starfighter: Crossbones": ["Starfighter: Crossbones", 1, 3],
    "Star Wars: Tales of the Jedi (miniseries)": ["Tales of the Jedi", 1, 5],
    "Star Wars: Tales of the Jedi – Dark Lords of the Sith": ["Tales of the Jedi – Dark Lords of the Sith", 1, 6],
    "Star Wars: Tales of the Jedi – Redemption": ["Tales of the Jedi – Redemption", 1, 5],
    "Star Wars: Tales of the Jedi – The Fall of the Sith Empire": ["Tales of the Jedi – The Fall of the Sith Empire", 1, 5],
    "Star Wars: Tales of the Jedi – The Freedon Nadd Uprising": ["Tales of the Jedi – The Freedon Nadd Uprising", 1, 2],
    "Star Wars: Tales of the Jedi – The Golden Age of the Sith": ["Tales of the Jedi – The Golden Age of the Sith", 1, 5],
    "Star Wars: Tales of the Jedi – The Saga of Nomi Sunrider": ["Tales of the Jedi", 3, 5],
    "Star Wars: Tales of the Jedi – The Sith War": ["Tales of the Jedi – The Sith War", 1, 6],
    "Star Wars: Tales of the Jedi – Ulic Qel-Droma and the Beast Wars of Onderon": ["Tales of the Jedi", 1, 2],
    "Star Wars: The Clone Wars: Hero of the Confederacy": ["The Clone Wars", 10, 12],
    "Star Wars: The Clone Wars: In Service of the Republic": ["The Clone Wars", 7, 12],
    "Star Wars: The Clone Wars: Slaves of the Republic": ["The Clone Wars", 1, 12],
    "Star Wars: The Last Command": ["The Last Command", 1, 6],
    "Star Wars: The Old Republic—The Lost Suns": ["The Old Republic—The Lost Suns", 1, 5],
    "Star Wars: Underworld: The Yavin Vassilika": ["Underworld: The Yavin Vassilika", 1, 5],
    "Star Wars: Union": ["Union", 1, 4],
    "Star Wars: Vader's Quest": ["Vader's Quest", 1, 4],
    "Star Wars: X-Wing Rogue Squadron": ["X-Wing Rogue Squadron", 1, 35],
    "Star Wars: X-Wing: Rogue Leader": ["X-Wing: Rogue Leader", 1, 3],

    "Star Wars: Clone Wars": ["Clone Wars Chapter", 1, 22]
}

EXPANSION = {
    "Tales from Jabba's Palace": ["A Bad Feeling: The Tale of EV-9D9", "A Barve Like That: The Tale of Boba Fett", "A Boy and His Monster: The Rancor Keeper's Tale", "A Free Quarren in the Palace: Tessek's Tale", "A Time to Mourn, a Time to Dance: Oola's Tale", "And Then There Were Some: The Gamorrean Guard's Tale", "And the Band Played On: The Band's Tale", "Epilogue: Whatever Became Of...?", "Goatgrass: The Tale of Ree-Yees", "Let Us Prey: The Whiphid's Tale", "Of the Day's Annoyances: Bib Fortuna's Tale", "Old Friends: Ephant Mon's Tale", "Out of the Closet: The Assassin's Tale", "Shaara and the Sarlacc: The Skiff Guard's Tale", "Skin Deep: The Fat Dancer's Tale", "Sleight of Hand: The Tale of Mara Jade", "Taster's Choice: The Tale of Jabba's Chef", "That's Entertainment: The Tale of Salacious Crumb", "The Great God Quay: The Tale of Barada and the Weequays", "Tongue-tied: Bubo's Tale"],
    "Tales from the Mos Eisley Cantina": ["A Hunter's Fate: Greedo's Tale", "At the Crossroads: The Spacer's Tale", "Be Still My Heart: The Bartender's Tale", "Doctor Death: The Tale of Dr. Evazan and Ponda Baba", "Drawing the Maps of Peace: The Moisture Farmer's Tale", "Empire Blues: The Devaronian's Tale", "Hammertong: The Tale of the \"Tonnika Sisters\"", "Nightlily: The Lovers' Tale", "One Last Night in the Mos Eisley Cantina: The Tale of the Wolfman and the Lamproid", "Play It Again, Figrin D'an: The Tale of Muftak and Kabe", "Soup's On: The Pipe Smoker's Tale", "Swap Meet: The Jawa's Tale", "The Sand Tender: The Hammerhead's Tale", "Trade Wins: The Ranat's Tale", "We Don't Do Weddings: The Band's Tale", "When the Desert Wind Turns: The Stormtrooper's Tale"],
    "Tales from the New Republic": ["Conflict of Interest", "Day of the Sepulchral Night (short story)", "Gathering Shadows", "Hutt and Seek", "Interlude at Darkknell", "Jade Solitaire", "The Last Hand (short story)", "The Longest Fall", "No Disintegrations, Please", "Simple Tricks", "Uhl Eharl Khoehng (short story)"],
    "Tales of the Bounty Hunters": ["The Last One Standing: The Tale of Boba Fett", "Of Possible Futures: The Tale of Zuckuss and 4-LOM", "Payback: The Tale of Dengar", "The Prize Pelt: The Tale of Bossk", "Therefore I Am: The Tale of IG-88"],
    "Canto Bight (novella collection)": ["Hear Nothing, See Nothing, Say Nothing", "The Ride", "Rules of the Game", "The Wine in Dreams"],
    "The Clone Wars: Stories of Light and Dark": ["Almost a Jedi", "Bane's Story", "Bug (short story)", "Dark Vengeance: The True Story of Darth Maul and His Revenge Against the Jedi Known as Obi-Wan Kenobi", "Dooku Captured (short story)", "Hostage Crisis (short story)", "Kenobi's Shadow", "The Lost Nightsister", "Pursuit of Peace (short story)", "The Shadow of Umbara", "Sharing the Same Face"],
    "Dark Legends": ["Bakurat (short story)", "A Bitter Harvest", "Blood Moon", "Buyer Beware", "The Dark Mirror", "The Gilded Cage", "A Life Immortal", "The Orphanage", "The Predecessor", "The Sleep of Ages"],
    "From a Certain Point of View": ["Added Muscle", "The Angle", "The Baptist", "Beru Whitesun Lars (short story)", "Born in the Storm", "The Bucket", "Bump", "By Whatever Sun", "Change of Heart", "Contingency Plan", "Desert Son", "Duty Roster", "Eclipse (short story)", "End of Watch", "Far Too Remote", "Fully Operational (short story)", "Grounded", "An Incident Report", "The Kloo Horn Cantina Caper", "Laina (short story)", "The Luckless Rodian", "Master and Apprentice (short story)", "Not for Nothing", "Of MSE-6 and Men", "Palpatine (short story)", "Raymus", "The Red One", "Reirin (short story)", "Rites", "The Secrets of Long Snoot", "The Sith of Datawork", "Sparks (short story)", "Stories in the Sand", "There is Another", "Time of Death", "The Trigger", "Verge of Greatness", "We Don't Serve Their Kind Here", "Whills (short story)", "You Owe Me a Ride"],
    "From a Certain Point of View: Return of the Jedi": ["Ackbar (comic)", "Any Work Worth Doing", "Brotherhood (short story)", "Divine (?) Intervention", "Dune Sea Songs of Salt and Moonlight", "Ending Protocol", "Everyone's a Critic (short story)", "Fancy Man", "Fortuna Favors the Bold", "From a Certain Point of View (short story)", "Gone to the Winner's Circle", "Impact (short story)", "Kernels and Husks", "Kickback (short story)", "My Mouth Never Closes", "No Contingency", "One Normal Day", "Reputation (Boba Fett)", "Return of the Whills", "Satisfaction", "The Ballad of Nanta (short story)", "The Burden of Leadership", "The Buy-In", "The Chronicler", "The Emperor's Red Guards", "The Extra Five Percent", "The Impossible Flight of Ash Angels", "The Key to Remembering", "The Last Flight", "The Light That Falls", "The Man Who Captured Luke Skywalker", "The Plan", "The Steadfast Soldier", "The Veteran", "Then Fall, Sidious", "To the Last", "Trooper Trouble", "Twenty and Out", "When Fire Marked the Sky", "Wolf Trap"],
    "From a Certain Point of View: The Empire Strikes Back": ["Against All Odds", "Amara Kel's Rules for TIE Pilot Survival (Probably)", "The Backup Backup Plan", "Bespin Escape", "Beyond Hope", "Beyond the Clouds", "But What Does He Eat?", "Disturbance", "The Dragonsnake Saves R2-D2", "Due on Batuu", "Eyes of the Empire", "Faith in an Old Friend", "Fake It Till You Make It", "The Final Order", "The First Lesson", "For the Last Time", "A Good Kiss", "Heroes of the Rebellion (short story)", "Hunger (short story)", "Into the Clouds", "Ion Control", "Kendal", "Lord Vader Will See You Now", "The Man Who Built Cloud City", "A Naturalist on Hoth", "No Time for Poetry", "Rendezvous Point (short story)", "Right-Hand Man", "Rogue Two (short story)", "She Will Keep Them Warm", "Standard Imperial Procedure", "STET!", "There Is Always Another", "This Is No Cave", "Tooth and Claw", "The Truest Duty", "Vergence (short story)", "Wait for It", "The Whills Strike Back", "The Witness"],
    "Life Day Treasury": ["A Coruscant Solstice", "The Kindling", "The Kroolok", "An Old Hope", "Reflection Day (short story)", "The Song of Winter's Heart", "The Spirit of Life Day", "The Tree of Life"],
    "Myths & Fables": ["The Black Spire", "Chasing Ghosts", "The Dark Wraith", "The Droid with a Heart", "Gaze of Stone", "The Golden One", "The Knight & the Dragon", "The Leviathan", "The Silent Circle (short story)", "The Skiff & the Galleons", "The Sleeping Eye", "An Unwilling Apprentice", "Vengeful Waves", "The Wanderer (short story)", "The Witch & the Wookiee"],
    "The Rise of the Empire": ["Bottleneck (short story)", "The Levers of Power", "Mercy Mission (short story)"],
    "Stories of Jedi and Sith": ["Blood Moon Uprising (short story)", "The Eye of the Beholder", "The Ghosts of Maul", "A Jedi's Duty", "Luke on the Bright Side", "Masters", "Resolve (short story)", "Through the Turbulence", "What a Jedi Makes", "Worthless"],
    "Tales from a Galaxy Far, Far Away: Aliens: Volume I": ["All Creatures Great and Small", "The Crimson Corsair and the Lost Treasure of Count Dooku", "The Face of Evil", "High Noon on Jakku", "A Recipe for Death", "True Love"],

    "5-Minute Star Wars Hero Stories": ["Destroy the Death Star!", "The Ewoks Join the Fight (short story)", "A Friend for Rey", "A Jedi, You Must Become", "Rathtars on the Loose!"],
    "5-Minute Star Wars Stories": ["The Battle of Hoth (short story)", "Destroy the Death Star!", "Escape from Darth Vader (5-Minute Star Wars Stories)", "The Ewoks Join the Fight (short story)", "A Friend for Rey", "A Jedi, You Must Become", "The Last Adventure", "Race to the Finish Line", "Rathtars on the Loose!", "Rescue from Jabba's Palace (Star Wars Galactic Adventures)", "Yoda and the Count"],
    "5-Minute Star Wars Stories Strike Back": ["Adventure in the Arena", "Captured in Canto Bight", "Clash at Cloud City", "Death Star Battle (short story)", "The Duel for Peace", "The Fight in the Forest (short story)", "Finn and Poe Team Up! (short story)", "A Journey Begins", "Mission to Maz", "Poe's Plan", "Short Negotiations", "Trapped in the Death Star"],
    "5-Minute Star Wars Villain Stories": ["The Battle of Hoth (short story)", "Escape from Darth Vader (5-Minute Star Wars Stories)", "Mission to Maz", "Rescue from Jabba's Palace (Star Wars Galactic Adventures)", "Yoda and the Count"],
    "5-Minute Star Wars Stories (second edition)": ["Attack of the X-Wings", "A Battle for the Galaxy", "Danger in the Desert", "A Duel Against the Dark Side", "The Final Battle", "Fleeing Hoth", "The Heart of a Jedi", "Mission to Mos Eisley (short story)", "The Mystery of the Clones", "A Race to Victory", "A Spark of Hope", "An Unexpected Ally"],
    "Galactic Adventures Storybook Collection": ["C-3PO's New Arm", "Captain Phasma's Escape from Starkiller Base", "Chewie and the Courageous Kid", "Darth Maul and the Rathtars", "Darth Vader and the Weapon of a Sith", "Han and the Rebel Rescue", "A Jedi's Control", "Lando's Big Score", "Leia and the Great Island Escape", "Leia Charts Her Own Course", "Luke and the Lost Jedi Temple", "Poe and the Missing Ship", "R2-D2 and the Renegade Rescue", "The Rebellion's Biggest Heist", "Rey's First Flight", "Rose and Paige Fight for the Resistance", "Size Matters Not (Galactic Adventures Storybook Collection)", "Stormtrooper in Training"],
    "The Original Trilogy Stories": ["AT-AT Attack! (short story)", "A Bad Feeling About This", "The Battle for Endor (short story)", "The Battle of Yavin (short story)", "Betrayal at Bespin", "Escape from Darth Vader (The Original Trilogy Stories)", "Escape from the Death Star (short story)", "The Final Duel", "Flight and Fight!", "The Hero's Journey Begins", "Leia and the Ewoks", "Rescue from Jabba's Palace (The Original Trilogy Stories)", "The Rescue of Princess Leia", "Return to Dagobah", "The Revelation", "Size Matters Not (The Original Trilogy Stories)", "Survival on Hoth", "An Unusual Hiding Place"],
    "The Prequel Trilogy Stories": ["Ambushed!", "Anakin's Vow", "The Brink of War", "The Cyborg and the Jedi", "Darth Vader Rises", "A Deadly Plot", "A Different Path", "Driven to the Dark Side", "Droid Attack!", "The Duel with Dooku", "Empire Ascendant", "Escaping Naboo", "The Final Fight (The Prequel Trilogy Stories)", "Into the Arena", "The Path of a Podracer", "The Rule of Two (short story)", "The Secret Army", "Short Negotiations (The Prequel Trilogy Stories)"],
    "Star Wars Galactic Adventures (2015)": ["Do or Do Not (short story)", "The Ewoks Join the Fight (short story)", "Rescue from Jabba's Palace (Star Wars Galactic Adventures)"],
    "Star Wars Galactic Adventures (2016)": ["The Battle of Hoth (short story)", "Destroy the Death Star!", "Escape from Darth Vader (5-Minute Star Wars Stories)", "The Ewoks Join the Fight (short story)", "A Jedi, You Must Become", "Rescue from Jabba's Palace (Star Wars Galactic Adventures)"],
    "Star Wars Galactic Stories: 7 Stories from a Galaxy Far, Far Away....": ["The Battle of Hoth (short story)", "Do or Do Not (short story)", "Escape from Darth Vader (5-Minute Star Wars Stories)", "The Ewoks Join the Fight (short story)", "A Friend for Rey", "Rathtars on the Loose!", "Rescue from Jabba's Palace (Star Wars Galactic Adventures)"],
    "Star Wars Galactic Storybook": ["Against All Odds (Star Wars Galactic Storybook)", "The Battle Continues", "The Final Fight (Star Wars Galactic Storybook)", "A Jedi Tale", "A New Adventure", "New Heroes for the Galaxy"],

    "Star Wars (radio)": ["A Wind to Shake the Stars", "Points of Origin", "Black Knight, White Princess, and Pawns", "While Giants Mark Time", "Jedi that Was, Jedi to Be", "The Millennium Falcon Deal", "The Han Solo Solution", "Death Star's Transit", "Rogues, Rebels and Robots", "The Luke Skywalker Initiative", "The Jedi Nexus", "The Case for Rebellion", "Force and Counterforce"],
    "The Empire Strikes Back (radio)": ["Freedom's Winter", "The Coming Storm", "A Question of Survival", "Fire and Ice", "The Millennium Falcon Pursuit", "Way of the Jedi (episode)", "New Allies, New Enemies", "Dark Lord's Fury", "Gambler's Choice", "The Clash of Lightsabers"],
    "Return of the Jedi (radio)": ["Tatooine Haunts", "Fast Friends", "Prophecies and Destinies", "Pattern and Web", "So Turns a Galaxy, So Turns a Wheel", "Blood of a Jedi"],

    "Mos Eisley Adventure Set": ["A Line in the Sand...", "The Passage From Perdition", "There's Many a Slip Betwixt Cup and Lip", "Harvest Day (adventure)", "Vested Interest"],

    "Star Wars: X-Wing (novel series)": ["X-Wing: Iron Fist", "X-Wing: Isard's Revenge", "X-Wing: Mercy Kill", "X-Wing: Rogue Squadron", "X-Wing: Solo Command", "X-Wing: Starfighters of Adumar", "X-Wing: The Bacta War", "X-Wing: The Krytos Trap", "X-Wing: Wedge's Gamble", "X-Wing: Wraith Squadron"],
    "Star Wars: The Clone Wars: Secret Missions": ["The Clone Wars: Secret Missions 1: Breakout Squad", "The Clone Wars: Secret Missions 2: Curse of the Black Hole Pirates", "The Clone Wars: Secret Missions 3: Duel at Shattered Rock", "The Clone Wars: Secret Missions 4: Guardians of the Chiss Key"],
    "Dark Times: Blue Harvest 0": ["Dark Times: Blue Harvest, Part 1", "Dark Times: Blue Harvest, Part 2"],
    "Star Wars: The Old Republic, Threat of Peace": ["The Old Republic, Threat of Peace Act 1: Treaty of Coruscant", "The Old Republic, Threat of Peace Act 2: New Galactic Order", "The Old Republic, Threat of Peace Act 3: Uncertain Surrender"],
    "Star Wars: The Old Republic, Blood of the Empire": ["The Old Republic, Blood of the Empire Act 1: Shades of the Sith", "The Old Republic, Blood of the Empire Act 2: The Broken World", "The Old Republic, Blood of the Empire Act 3: Burn the Future"],
    "Adventures of a Jedi Prince": ["The Glove of Darth Vader", "The Lost City of the Jedi", "Mission from Mount Yoda", "Prophets of the Dark Side (novel)", "Queen of the Empire", "Zorba the Hutt's Revenge"],
    "Boba Fett: Part I: Survival": ["Boba Fett: The Fight to Survive", "Boba Fett: Crossfire", "Boba Fett: Maze of Deception"],
    "The Bounty Hunter Wars": ["Hard Merchandise", "The Mandalorian Armor", "Slave Ship"],
    "Star Wars: The Black Fleet Crisis": ["Before the Storm", "Shield of Lies", "Tyrant's Test"],
    "The Black Fleet Crisis": ["Before the Storm", "Shield of Lies", "Tyrant's Test"],
    "Star Wars: The Corellian Trilogy": ["Ambush at Corellia", "Assault at Selonia", "Showdown at Centerpoint"],
    "Star Wars: The Dark Nest Trilogy": ["Dark Nest I: The Joiner King", "Dark Nest II: The Unseen Queen", "Dark Nest III: The Swarm War"],
    "Star Wars: The Han Solo Trilogy": ["The Hutt Gambit", "The Paradise Snare", "Rebel Dawn"],
    "Star Wars: The Jedi Academy Trilogy": ["Champions of the Force", "Dark Apprentice (novel)", "Jedi Search"],
    "Star Wars: The Thrawn Trilogy": ["Heir to the Empire", "Dark Force Rising", "The Last Command"],
    "Star Wars: Fate of the Jedi": ["Fate of the Jedi: Abyss", "Fate of the Jedi: Allies", "Fate of the Jedi: Apocalypse", "Fate of the Jedi: Ascension", "Fate of the Jedi: Backlash", "Fate of the Jedi: Conviction", "Fate of the Jedi: Omen", "Fate of the Jedi: Outcast", "Fate of the Jedi: Vortex"],
    "Star Wars: The New Jedi Order": ["The New Jedi Order: Agents of Chaos I: Hero's Trial", "The New Jedi Order: Agents of Chaos II: Jedi Eclipse", "The New Jedi Order: Balance Point", "The New Jedi Order: Dark Journey", "The New Jedi Order: Dark Tide I: Onslaught", "The New Jedi Order: Dark Tide II: Ruin", "The New Jedi Order: Dark Tide: Siege", "The New Jedi Order: Destiny's Way", "The New Jedi Order: Edge of Victory I: Conquest", "The New Jedi Order: Edge of Victory II: Rebirth", "The New Jedi Order: Enemy Lines I: Rebel Dream", "The New Jedi Order: Enemy Lines II: Rebel Stand", "The New Jedi Order: Force Heretic I: Remnant", "The New Jedi Order: Force Heretic II: Refugee", "The New Jedi Order: Force Heretic III: Reunion", "The New Jedi Order: Recovery", "The New Jedi Order: Star by Star", "The New Jedi Order: The Final Prophecy", "The New Jedi Order: The Unifying Force", "The New Jedi Order: Traitor", "The New Jedi Order: Vector Prime", "The New Jedi Order: Ylesia"],
    "Star Wars: Legacy of the Force": ["Legacy of the Force: Betrayal", "Legacy of the Force: Bloodlines", "Legacy of the Force: Exile", "Legacy of the Force: Fury", "Legacy of the Force: Inferno", "Legacy of the Force: Invincible", "Legacy of the Force: Revelation", "Legacy of the Force: Sacrifice", "Legacy of the Force: Tempest"],
    "Star Wars: Young Jedi Knights": ["Young Jedi Knights: Crisis at Crystal Reef", "Young Jedi Knights: Darkest Knight",
                                      "Young Jedi Knights: Delusions of Grandeur", "Young Jedi Knights: Diversity Alliance",
                                      "Young Jedi Knights: Heirs of the Force", "Young Jedi Knights: Jedi Bounty",
                                      "Young Jedi Knights: Jedi Under Siege", "Young Jedi Knights: Lightsabers",
                                      "Young Jedi Knights: Return to Ord Mantell", "Young Jedi Knights: Shadow Academy",
                                      "Young Jedi Knights: Shards of Alderaan", "Young Jedi Knights: The Emperor's Plague",
                                      "Young Jedi Knights: The Lost Ones", "Young Jedi Knights: Trouble on Cloud City"],
    "Young Jedi Knights: Jedi Shadow": ["Young Jedi Knights: Heirs of the Force", "Young Jedi Knights: Shadow Academy", "Young Jedi Knights: The Lost Ones"],
    "Young Jedi Knights: Jedi Sunrise": ["Young Jedi Knights: Lightsabers", "Young Jedi Knights: Darkest Knight", "Young Jedi Knights: Jedi Under Siege"],
    "Young Jedi Knights: The Fall of the Diversity Alliance": ["Young Jedi Knights: Shards of Alderaan", "Young Jedi Knights: Diversity Alliance", "Young Jedi Knights: Delusions of Grandeur", "Young Jedi Knights: Jedi Bounty", "Young Jedi Knights: The Emperor's Plague"],
    "Young Jedi Knights: The Rise of the Shadow Academy": ["Young Jedi Knights: Heirs of the Force", "Young Jedi Knights: Shadow Academy", "Young Jedi Knights: The Lost Ones", "Young Jedi Knights: Lightsabers", "Young Jedi Knights: Darkest Knight", "Young Jedi Knights: Jedi Under Siege"],
    "Young Jedi Knights: Under Black Sun": ["Young Jedi Knights: Return to Ord Mantell", "Young Jedi Knights: Trouble on Cloud City", "Young Jedi Knights: Crisis at Crystal Reef"],
}


SERIES_INDEX = {
    "Classic Star Wars": "Classic Star Wars 1",
    "Classic Star Wars: A Long Time Ago...": "Classic Star Wars: A Long Time Ago... 1",
    "Classic Star Wars: A New Hope": "Classic Star Wars: A New Hope 1",
    "Classic Star Wars: Devilworlds": "Classic Star Wars: Devilworlds 1",
    "Classic Star Wars: Return of the Jedi": "Classic Star Wars: Return of the Jedi 1",
    "Classic Star Wars: The Early Adventures": "Classic Star Wars: The Early Adventures 1",
    "Classic Star Wars: The Empire Strikes Back": "Classic Star Wars: The Empire Strikes Back 1",
    "Star Wars (1977)": "Star Wars (1977) 1",
    "Star Wars (2013)": "Star Wars (2013) 1",
    "Star Wars 3-D": "Star Wars 3-D 1",
    "Star Wars Manga: A New Hope": "Star Wars Manga: A New Hope 1",
    "Star Wars Manga: Return of the Jedi": "Star Wars Manga: Return of the Jedi 1",
    "Star Wars Manga: The Empire Strikes Back": "Star Wars Manga: The Empire Strikes Back 1",
    "Star Wars Manga: The Phantom Menace": "Star Wars Manga: The Phantom Menace 1",
    "Star Wars: A New Hope - The Special Edition": "Star Wars: A New Hope - The Special Edition 1",
    "Star Wars: Agent of the Empire": "Agent of the Empire – Iron Eclipse 1",
    "Star Wars: Agent of the Empire—Hard Targets": "Agent of the Empire – Hard Targets 1",
    "Star Wars: Agent of the Empire—Iron Eclipse": "Agent of the Empire – Iron Eclipse 1",
    "Star Wars: Blood Ties": "Blood Ties: A Tale of Jango and Boba Fett 1",
    "Star Wars: Blood Ties: A Tale of Jango and Boba Fett": "Blood Ties: A Tale of Jango and Boba Fett 1",
    "Star Wars: Blood Ties: Boba Fett is Dead": "Blood Ties: Boba Fett is Dead 1",
    "Star Wars: Boba Fett (comic series)": "Boba Fett: Bounty on Bar-Kooda",
    "Star Wars: Boba Fett: Enemy of the Empire": "Boba Fett: Enemy of the Empire 1",
    "Star Wars: Chewbacca (2000)": "Chewbacca (2000) 1",
    "Star Wars: Crimson Empire (comic series)": "Crimson Empire 1",
    "Star Wars: Crimson Empire": "Crimson Empire 1",
    "Star Wars: Crimson Empire II: Council of Blood": "Crimson Empire II: Council of Blood 1",
    "Star Wars: Crimson Empire III—Empire Lost": "Crimson Empire III: Empire Lost 1",
    "Star Wars: Dark Empire II": "Dark Empire II 1",
    "Star Wars: Dark Empire": "Dark Empire 1",
    "Star Wars: Dark Force Rising": "Dark Force Rising 1",
    "Star Wars: Dark Times": "Dark Times 1",
        "Star Wars: Dark Times: The Path to Nowhere": "Dark Times 1",
        "Star Wars: Dark Times: Parallels": "Dark Times 6",
        "Star Wars: Dark Times: Vector": "Dark Times 11",
    "Star Wars: Dark Times: Blue Harvest": "Dark Times: Blue Harvest, Part 1",
    "Star Wars: Dark Times—A Spark Remains": "Dark Times—A Spark Remains 1",
    "Star Wars: Dark Times—Fire Carrier": "Dark Times—Fire Carrier 1",
    "Star Wars: Dark Times—Out of the Wilderness": "Dark Times—Out of the Wilderness 1",
    "Star Wars: Darth Maul (2000)": "Darth Maul (2000) 1",
    "Star Wars: Darth Maul—Death Sentence": "Darth Maul—Death Sentence 1",
    "Star Wars: Darth Maul—Son of Dathomir": "Darth Maul—Son of Dathomir 1",
    "Star Wars: Darth Vader (2011)": "Darth Vader and the Lost Command 1",
    "Star Wars: Darth Vader and the Cry of Shadows": "Darth Vader and the Cry of Shadows 1",
    "Star Wars: Darth Vader and the Ghost Prison": "Darth Vader and the Ghost Prison 1",
    "Star Wars: Darth Vader and the Lost Command": "Darth Vader and the Lost Command 1",
    "Star Wars: Darth Vader and the Ninth Assassin": "Darth Vader and the Ninth Assassin 1",
    "Star Wars: Dawn of the Jedi": "Dawn of the Jedi: Force Storm 1",
    "Star Wars: Dawn of the Jedi: Force Storm": "Dawn of the Jedi: Force Storm 1",
    "Star Wars: Dawn of the Jedi: Force War": "Dawn of the Jedi: Force War 1",
    "Star Wars: Dawn of the Jedi: The Prisoner of Bogan": "Dawn of the Jedi: The Prisoner of Bogan 1",
    "Star Wars: Droids (1986)": "Droids (1986) 1",
    "Star Wars: Droids (1994)": "Droids (1994) 1",
    "Star Wars: Droids (1995)": "Droids (1995) 1",
    "Star Wars: Empire's End": "Empire's End 1",
    "Star Wars: Empire": "Empire 1",
        "Star Wars: Empire: Betrayal": "Empire 1",
        "Star Wars: Empire: Princess... Warrior": "Empire 5",
        "Star Wars: Empire: Darklighter": "Empire 8",
        "Star Wars: Empire: The Short, Happy Life of Roons Sewell": "Empire 10",
        "Star Wars: Empire: To the Last Man": "Empire 16",
        "Star Wars: Empire: A Little Piece of Home": "Empire 20",
        "Star Wars: Empire: Idiot's Array": "Empire 24",
        'Star Wars: Empire: "General" Skywalker': "Empire 26",
        "Star Wars: Empire: In the Shadows of Their Fathers": "Empire 29",
        "Star Wars: Empire: The Wrong Side of the War": "Empire 36",
    "Star Wars: Episode I — The Phantom Menace": "Star Wars: Episode I — The Phantom Menace 1",
    "Star Wars: Episode II — Attack of the Clones": "Star Wars: Episode II — Attack of the Clones 1",
    "Star Wars: Episode III — Revenge of the Sith": "Star Wars: Episode III — Revenge of the Sith 1",
    "Star Wars: Ewoks (1985)": "Ewoks (1985) 1",
    "Star Wars: General Grievous": "General Grievous 1",
    "Star Wars: Heir to the Empire": "Heir to the Empire 1",
    "Star Wars: In the Shadow of Yavin": "Star Wars (2013) 1",
    "Star Wars: Invasion": "Invasion 1",
    "Star Wars: Invasion: Refugees": "Invasion 1",
    "Star Wars: Invasion: Rescues": "Invasion: Rescues 1",
    "Star Wars: Invasion: Revelations": "Invasion: Revelations 1",
    "Star Wars: Jabba the Hutt": "Jabba the Hutt: The Gaar Suppoon Hit",
    "Star Wars: Jango Fett: Open Seasons": "Jango Fett: Open Seasons 1",
    "Star Wars: Jedi Academy: Leviathan": "Jedi Academy: Leviathan 1",
    "Star Wars: Jedi Council: Acts of War": "Jedi Council: Acts of War 1",
    "Star Wars: Jedi Quest (comic series)": "Jedi Quest 1",
    "Star Wars: Jedi vs. Sith": "Jedi vs. Sith 1",
    "Star Wars: Jedi": "Jedi: Mace Windu",
    "Star Wars: Jedi—The Dark Side": "Jedi—The Dark Side 1",
    "Star Wars: Knight Errant": "Knight Errant: Aflame 1",
    "Star Wars: Knight Errant: Aflame": "Knight Errant: Aflame 1",
    "Star Wars: Knight Errant: Deluge": "Knight Errant: Deluge 1",
    "Star Wars: Knight Errant: Escape": "Knight Errant: Escape 1",
    "Star Wars: Knights of the Old Republic (comic series)": "Knights of the Old Republic 1",
        "Star Wars: Knights of the Old Republic: Commencement": "Knights of the Old Republic 1",
        "Star Wars: Knights of the Old Republic: Flashpoint": "Knights of the Old Republic 7",
        "Star Wars: Knights of the Old Republic: Reunion": "Knights of the Old Republic 11",
        "Star Wars: Knights of the Old Republic: Days of Fear": "Knights of the Old Republic 13",
        "Star Wars: Knights of the Old Republic: Nights of Anger": "Knights of the Old Republic 16",
        "Star Wars: Knights of the Old Republic: Daze of Hate": "Knights of the Old Republic 19",
        "Star Wars: Knights of the Old Republic: Knights of Suffering": "Knights of the Old Republic 22",
        "Star Wars: Knights of the Old Republic: Vector": "Knights of the Old Republic 25",
        "Star Wars: Knights of the Old Republic: Exalted": "Knights of the Old Republic 29",
        "Star Wars: Knights of the Old Republic: Vindication": "Knights of the Old Republic 32",
        "Star Wars: Knights of the Old Republic: Prophet Motive": "Knights of the Old Republic 36",
        "Star Wars: Knights of the Old Republic: Dueling Ambitions": "Knights of the Old Republic 39",
        "Star Wars: Knights of the Old Republic: The Reaping": "Knights of the Old Republic 43",
        "Star Wars: Knights of the Old Republic: Destroyer": "Knights of the Old Republic 45",
        "Star Wars: Knights of the Old Republic: Demon": "Knights of the Old Republic 47",
        "Star Wars: Knights of the Old Republic: War": "Knights of the Old Republic: War 1",
    "Star Wars: Legacy": "Legacy (2006) 1",
        "Star Wars: Legacy: Broken": "Legacy (2006) 1",
        "Star Wars: Legacy: Trust Issues": "Legacy (2006) 9",
        "Star Wars: Legacy: Ghosts": "Legacy (2006) 11",
        "Star Wars: Legacy: Claws of the Dragon": "Legacy (2006) 14",
        "Star Wars: Legacy: Indomitable": "Legacy (2006) 20",
        "Star Wars: Legacy: Loyalties": "Legacy (2006) 23",
        "Star Wars: Legacy: The Hidden Temple": "Legacy (2006) 25",
        "Star Wars: Legacy: Vector": "Legacy (2006) 28",
        "Star Wars: Legacy: Fight Another Day": "Legacy (2006) 32",
        "Star Wars: Legacy: Storms": "Legacy (2006) 34",
        "Star Wars: Legacy: Tatooine": "Legacy (2006) 37",
        "Star Wars: Legacy: Monster": "Legacy (2006) 43",
        "Star Wars: Legacy: Extremes": "Legacy (2006) 48",
    "Star Wars: Legacy Volume 2": "Legacy (2013) 1",
        "Star Wars: Legacy: Prisoner of the Floating World": "Legacy (2013) 1",
        "Star Wars: Legacy: Outcasts of the Broken Ring": "Legacy (2013) 6",
        "Star Wars: Legacy: Wanted: Ania Solo": "Legacy (2013) 11",
        "Star Wars: Legacy: Empire of One": "Legacy (2013) 16",
    "Star Wars: Legacy—War": "Legacy—War 1",
    "Star Wars: Lost Tribe of the Sith—Spiral": "Lost Tribe of the Sith—Spiral 1",
    "Star Wars: Mara Jade – By the Emperor's Hand": "Mara Jade – By the Emperor's Hand 1",
    "Star Wars: Obsession": "Obsession 1",
    "Star Wars: Purge – The Tyrant's Fist": "Purge – The Tyrant's Fist 1",
    "Star Wars: Qui-Gon and Obi-Wan": "Qui-Gon and Obi-Wan: Last Stand on Ord Mantell 1",
    "Star Wars: Qui-Gon and Obi-Wan: Last Stand on Ord Mantell": "Qui-Gon and Obi-Wan: Last Stand on Ord Mantell 1",
    "Star Wars: Qui-Gon and Obi-Wan: The Aurorient Express": "Qui-Gon and Obi-Wan: The Aurorient Express 1",
    "Star Wars: Rebel Heist": "Rebel Heist 1",
    "Star Wars: Rebellion (comic series)": "Rebellion 1",
        "Star Wars: Rebellion: My Brother, My Enemy": "Rebellion 1",
        "Star Wars: Rebellion: The Ahakista Gambit": "Rebellion 6",
        "Star Wars: Rebellion: Small Victories": "Rebellion 11",
        "Star Wars: Rebellion: Vector": "Rebellion 15",
    "Star Wars: Republic": "Star Wars (1998) 1",
        "Star Wars: Prelude to Rebellion": "Star Wars (1998) 1",
        "Star Wars: Outlander": "Star Wars (1998) 7",
        "Star Wars: Emissaries to Malastare": "Star Wars (1998) 13",
        "Star Wars: Twilight": "Star Wars (1998) 19",
        "Star Wars: Infinity's End": "Star Wars (1998) 23",
        "Star Wars: The Hunt for Aurra Sing": "Star Wars (1998) 28",
        "Star Wars: Darkness": "Star Wars (1998) 32",
        "Star Wars: The Stark Hyperspace War": "Star Wars (1998) 36",
        "Star Wars: The Devaronian Version": "Star Wars (1998) 40",
        "Star Wars: Rite of Passage": "Star Wars (1998) 42",
        "Star Wars: Republic: Honor and Duty": "Republic 46",
        "Star Wars: Republic: The New Face of War": "Republic 51",
        "Star Wars: Republic: The Battle of Jabiim": "Republic 55",
        "Star Wars: Republic: Show of Force": "Republic 65",
        "Star Wars: Republic: Dreadnaughts of Rendili": "Republic 69",
        "Star Wars: Republic: Trackdown": "Republic 72",
        "Star Wars: Republic: Siege of Saleucami": "Republic 74",
        "Star Wars: Republic: Into the Unknown": "Republic 79",
        "Star Wars: Republic: Hidden Enemy": "Republic 81",
    "Star Wars: Return of the Jedi (1983)": "Return of the Jedi 1",
    "Star Wars: River of Chaos": "River of Chaos 1",
    "Star Wars: Shadows of the Empire": "Shadows of the Empire 1",
    "Star Wars: Shadows of the Empire (comic series)": "Shadows of the Empire 1",
    "Star Wars: Shadows of the Empire: Evolution": "Shadows of the Empire: Evolution 1",
    "Star Wars: Splinter of the Mind's Eye": "Splinter of the Mind's Eye 1",
    "Star Wars: Starfighter: Crossbones": "Starfighter: Crossbones 1",
    "Star Wars: Tales of the Jedi (comic series)": "Tales of the Jedi 1",
    "Star Wars: Tales of the Jedi (miniseries)": "Tales of the Jedi 1",
    "Star Wars: Tales of the Jedi – The Saga of Nomi Sunrider": "Tales of the Jedi 3",
    "Star Wars: Tales of the Jedi – Dark Lords of the Sith": "Tales of the Jedi – Dark Lords of the Sith 1",
    "Star Wars: Tales of the Jedi – Redemption": "Tales of the Jedi – Redemption 1",
    "Star Wars: Tales of the Jedi – The Fall of the Sith Empire": "Tales of the Jedi – The Fall of the Sith Empire 1",
    "Star Wars: Tales of the Jedi – The Freedon Nadd Uprising": "Tales of the Jedi – The Freedon Nadd Uprising 1",
    "Star Wars: Tales of the Jedi – The Golden Age of the Sith": "Tales of the Jedi – The Golden Age of the Sith 1",
    "Star Wars: Tales of the Jedi – The Sith War": "Tales of the Jedi – The Sith War 1",
    "Star Wars: Tales of the Jedi – Ulic Qel-Droma and the Beast Wars of Onderon": "Tales of the Jedi 1",
    "Star Wars: The Bounty Hunters": "The Bounty Hunters: Aurra Sing",
    "Star Wars: The Clone Wars (comic series)": "The Clone Wars 1",
    "Star Wars: The Clone Wars: Hero of the Confederacy": "The Clone Wars 10",
    "Star Wars: The Clone Wars: In Service of the Republic": "The Clone Wars 7",
    "Star Wars: The Clone Wars: Slaves of the Republic": "The Clone Wars 1",
    "Star Wars: The Last Command": "The Last Command 1",
    "Star Wars: The Old Republic (comics)": "The Old Republic, Blood of the Empire Act 1: Shades of the Sith",
    "Star Wars: The Old Republic, Blood of the Empire": "The Old Republic, Blood of the Empire Act 1: Shades of the Sith",
    "Star Wars: The Old Republic, Threat of Peace": "The Old Republic, Threat of Peace Act 1: Treaty of Coruscant",
    "Star Wars: The Old Republic—The Lost Suns": "The Old Republic—The Lost Suns 1",
    "Star Wars: Underworld: The Yavin Vassilika": "Underworld: The Yavin Vassilika 1",
    "Star Wars: Union": "Union 1",
    "Star Wars: Vader's Quest": "Vader's Quest 1",
    "Star Wars: X-Wing Rogue Squadron": "X-Wing Rogue Squadron 1",
        "Star Wars: X-Wing Rogue Squadron: The Rebel Opposition": "X-Wing Rogue Squadron 1",
        "Star Wars: X-Wing Rogue Squadron: The Phantom Affair": "X-Wing Rogue Squadron 5",
        "Star Wars: X-Wing Rogue Squadron: Battleground: Tatooine": "X-Wing Rogue Squadron 9",
        "Star Wars: X-Wing Rogue Squadron: The Warrior Princess": "X-Wing Rogue Squadron 13",
        "Star Wars: X-Wing Rogue Squadron: Requiem for a Rogue": "X-Wing Rogue Squadron 17",
        "Star Wars: X-Wing Rogue Squadron: In the Empire's Service": "X-Wing Rogue Squadron 21",
        "Star Wars: X-Wing Rogue Squadron: Family Ties": "X-Wing Rogue Squadron 25",
        "Star Wars: X-Wing Rogue Squadron: Masquerade": "X-Wing Rogue Squadron 28",
        "Star Wars: X-Wing Rogue Squadron: Mandatory Retirement": "X-Wing Rogue Squadron 33",
    "Star Wars: X-Wing: Rogue Leader": "X-Wing: Rogue Leader 1",
    "Thrawn Trilogy (comics)": "Heir to the Empire 1",

    "Star Wars: Clone Wars": "Chapter 1 (Clone Wars)",
    "Star Wars (radio)": "A Wind to Shake the Stars",
    "The Empire Strikes Back (radio)": "Freedom's Winter",
    "Return of the Jedi (radio)": "Tatooine Haunts",

    "Boba Fett: Part I: Survival": "Boba Fett: The Fight to Survive",

    "Adventures of a Jedi Prince": "The Glove of Darth Vader",
    "Star Wars: The Hand of Thrawn Duology": "Specter of the Past",
    "Star Wars: The Last of the Jedi": "The Last of the Jedi: The Desperate Mission",
    "Star Wars: The New Jedi Order": "The New Jedi Order: Vector Prime",
    "Star Wars: Legacy of the Force": "Legacy of the Force: Betrayal",
    "Star Wars: X-Wing (novel series)": "X-Wing: Rogue Squadron",
}


def list_templates(site, cat, data, template_type, recurse=False):
    for p in Category(site, cat).articles(recurse=recurse):
        if "/" not in p.title() and p.title(with_ns=False).lower() not in data:
            data[p.title(with_ns=False).lower()] = template_type


def build_template_types(site):
    now = datetime.now()
    results = {"db": "DB", "databank": "DB", "swe": "DB", "External": []}

    list_templates(site, "Category:StarWars.com citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates", results, "Web")
    list_templates(site, "Category:Internet citation templates for use in External Links", results, "External")
    list_templates(site, "Category:Social media citation templates", results, "Social")
    list_templates(site, "Category:Commercial and product listing internet citation templates", results, "Commercial")

    list_templates(site, "Category:YouTube citation templates", results, "YT")
    list_templates(site, "Category:Card game citation templates", results, "Cards")
    list_templates(site, "Category:Miniature game citation templates", results, "Cards")
    list_templates(site, "Category:Toy citation templates", results, "Toys")
    list_templates(site, "Category:TV citation templates", results, "TV")

    list_templates(site, "Category:Interwiki link templates", results, "Interwiki")

    results["Magazine"] = {}
    for p in Category(site, "Category:Magazine citation templates").articles(recurse=True):
        txt = p.get()
        if "BaseCitation/Magazine" in txt:
            x = re.search("\|series=([A-z0-9:()\-&/ ]+)[|\n]", txt)
            if x:
                results["Magazine"][p.title(with_ns=False)] = x.group(1)
    results["Magazine"]["InsiderCite"] = "Star Wars Insider"

    for k, cat in {"Nav": "Navigation templates", "Dates": "Dating citation templates"}.items():
        results[k] = []
        for p in Category(site, f"Category:{cat}").articles(recurse=True):
            if p.title(with_ns=False).lower() in results:
                print(f"ERROR: Duplicate template name: {p.title(with_ns=False).lower()}")
            results[k].append(p.title(with_ns=False).lower())

    duration = datetime.now() - now
    print(f"Loaded {len(results)} templates in {duration.seconds} seconds")
    return results


# TODO: Split Appearances category by type

def load_appearances(site, log, canon_only=False, legends_only=False):
    data = []
    pages = ["Legends", "Canon", "Audiobook", "Unlicensed"]
    other = ["Extra", "Series", "Collections", "Reprint"]
    if canon_only:
        pages = ["Canon", "Audiobook"]
    elif legends_only:
        pages = ["Legends", "Audiobook"]
    for sp in [*pages, *other]:
        i = 0
        collection_type = None
        p = Page(site, f"Wookieepedia:Appearances/{sp}")
        for line in p.get().splitlines():
            if line and sp in ("Extra", "Series") and line.startswith("=="):
                if "Story anthologies" in line:
                    collection_type = "short"
                elif "Home video releases" in line:
                    collection_type = "DVD"
                elif "Toy lines" in line:
                    collection_type = "toy"
                else:
                    collection_type = None
            elif line and not line.startswith("=="):
                if "/Header}}" in line or line == "----":
                    continue
                x = re.search("[*#](.*?)( \(.*?\))?:(<!--.*?-->)? (.*?)$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": f"Appearances/{sp}", "date": x.group(1), "item": x.group(4),
                                 "canon": "Canon" in sp, "extra": sp in other, "audiobook": "Audiobook" in sp,
                                 "collectionType": collection_type})
                else:
                    print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} appearances from Wookieepedia:Appearances/{sp}")

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
            if line and not line.startswith("==") and not "/Header}}" in line and line != "----":
                # if line.count("{{") > line.count("}}"):
                #     if o + 1 != len(lines) and lines[o + 1].count("}}") > lines[o + 1].count("{{"):
                #         line = f"{line}{lines[o + 1]}"
                #         skip = True
                #         bad.append(o)

                if "Toys" in sp:
                    line = re.sub("(\|text=.*?)(\|set=.*?)\|", "\\2\\1|", line)
                    line = re.sub("(\|a?l?t?link=.*?) ?(\|pack=.*?)(\|.*?)?}}", "\\2\\1\\3}}", line)
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
                x = re.search("\*(?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? (?P<t>.*?) ?†?( {{C\|(original|alternate): (?P<a>.*?)}})?( {{C\|int: (?P<i>.*?)}})?( {{C\|d: [0-9X-]+?}})?$", line)
                if x:
                    i += 1
                    data.append({"index": i, "page": f"Web/{y}", "date": x.group("d"), "item": x.group("t"),
                                 "alternate": x.group("a"), "int": x.group("i"), "ref": x.group("r")})
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
            data.append({"index": i, "page": "Web/External", "date": x.group('d'), "item": x.group('t'), "alternate": x.group('a')})
        else:
            print(f"Cannot parse line: {line}")
    if log:
        print(f"Loaded {i} sources from Wookieepedia:Sources/External")

    db_pages = {"DB": "2011-09-13", "SWE": "2014-07-01", "Databank": "Current"}
    for template, date in db_pages.items():
        p = Page(site, f"Wookieepedia:Sources/Web/{template}")
        i = 0
        for line in p.get().splitlines():
            if "/Header}}" in line:
                continue
            x = re.search("\*((?P<d>.*?):(?P<r><ref.*?(</ref>|/>))? )?(?P<t>{{.*?)( {{C\|(original|alternate): (?P<a>.*?)}})?$", line)
            if x:
                i += 1
                data.append({"index": 0, "page": f"Web/{template}", "date": date, "item": x.group("t"),
                             "extraDate": x.group("d"), "ref": x.group("r"), "alternate": x.group('a')})
            else:
                print(f"Cannot parse line: {line}")
        if log:
            print(f"Loaded {i} sources from Wookieepedia:Sources/Web/{template}")

    return data


def load_remap(site) -> dict:
    p = Page(site, "Wookieepedia:Appearances/Remap")
    results = {}
    for line in p.get().splitlines():
        x = re.search("\[\[(.*?)(\|.*?)?]].*?[\[{]+(.*?)(\|.*?)?[]}]+", line)
        if x:
            results[x.group(1)] = "Star Wars Galaxies" if x.group(3) == "GalaxiesNGE" else x.group(3)
    print(f"Loaded {len(results)} remap names")
    return results


ISSUE_REPRINTS = ["A Certain Point of View (Star Wars Insider)", "Classic Moment", "Behind the Magic",
                  "In the Star Wars Universe", "Interrogation Droid!", "Jedi Toy Box", "Legendary Authors",
                  "My Star Wars", "Retro", "Red Five (Star Wars Insider)", "Rogues Gallery (Star Wars Insider)",
                  "Set Piece", "Second Trooper", "The Star Wars Archive", "The Wonder Column"]


def load_full_sources(site, types, log) -> FullListData:
    sources = load_source_lists(site, log)
    count = 0
    unique_sources = {}
    full_sources = {}
    target_sources = {}
    both_continuities = set()
    today = datetime.now().strftime("%Y-%m-%d")
    ff_data = {}
    reprints = {}
    for i in sources:
        try:
            unlicensed = "{{c|unlicensed" in i['item'].lower() or "{{un}}" in i['item'].lower()
            non_canon = ("{{c|non-canon" in i['item'].lower() or "{{nc" in i['item'].lower())
            reprint = "{{c|republish" in i['item'].lower() or i["page"] == "Reprint"
            c = ''
            if "{{C|" in i['item'] or "{{nc" in i['item'].lower() or "{{un}}" in i['item'].lower():
                cr = re.search("({{C\|([Aa]bridged|[Rr]epublished|[Uu]nlicensed|[Nn]on[ -]?canon)}}|{{[Uu]n}}|{{[Nn]cs?}})", i['item'])
                if cr:
                    c = ' ' + cr.group(1)
                    i['item'] = i['item'].replace(cr.group(1), '').strip()
            parenthetical = ''
            if "|p=" in i['item']:
                pr = re.search("\|p=(.*?)(\|.*?)?}}", i['item'])
                if pr:
                    parenthetical = pr.group(1)
                    i['item'] = i['item'].replace(f"|p={parenthetical}", "").strip()
            x = extract_item(i['item'], False, i['page'], types, master=True)
            if x and not x.invalid:
                if x.template == "SWCT" and not x.target:
                    x.target = x.card
                if i['page'] == "Web/External":
                    x.external = True
                x.master_page = i['page']
                x.canon = i.get('canon')
                x.date = i['date']
                x.future = x.date and (x.date == 'Future' or x.date > today)
                x.index = i['index']
                x.extra = c
                x.parenthetical = parenthetical
                if (x.mode == "Cards" or x.mode == "Toys") and parenthetical:
                    x.target = f"{x.target} ({parenthetical})"
                if i.get("int"):
                    x.target = f"{i['int']}"
                x.unlicensed = unlicensed
                x.non_canon = non_canon
                x.reprint = reprint
                if x.template == "Hyperspace" and x.url in HYPERSPACE:
                    x.reprint = True
                    x.target = HYPERSPACE[x.url]
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
                if x.ff_data:
                    if x.issue not in ff_data:
                        ff_data[x.issue] = []
                    ff_data[x.issue].append(x)
                if reprint and x.target in ISSUE_REPRINTS:
                    if f"{x.target}|{x.issue}" not in reprints:
                        reprints[f"{x.target}|{x.issue}"] = []
                    reprints[f"{x.target}|{x.issue}"].append(x)
                elif reprint and x.target not in reprints:
                    reprints[x.target] = [x]
                elif reprint:
                    reprints[x.target].append(x)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            print(f"{e}: {i['item']}")
    for k, v in ff_data.items():
        target_sources[f"FFData|{k}"] = v
    for k, v in reprints.items():
        if "|" in k:
            k, _, s = k.partition("|")
            if k in target_sources:
                y = [i for i in target_sources[k] if s == str(i.issue)]
                if y:
                    for i in v:
                        i.original_printing = y[0]
        else:
            if k in target_sources:
                x = target_sources[k][0]
                for i in v:
                    i.original_printing = x
    print(f"{count} out of {len(sources)} unmatched: {count / len(sources) * 100}")
    return FullListData(unique_sources, full_sources, target_sources, set(), both_continuities, reprints)


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
    reprints = {}
    for i in appearances:
        try:
            non_canon = ("{{c|non-canon" in i['item'].lower() or "{{nc" in i['item'].lower())
            reprint = "{{c|republish" in i['item'].lower() or "Reprint" in i["page"]
            repr = ""
            if "{{reprint" in i['item'].lower():
                x = re.search("({{[Rr]eprint\|.*?}})", i['item'])
                if x:
                    repr = x.group(1)
                    i["item"] = i["item"].replace(x.group(1), "").strip()
            is_source = False
            if "{{C|source}}" in i['item']:
                i['item'] = i['item'].replace("{{C|source}}", "").strip()
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
                    alternate = a.group('a')
                    i['item'] = i['item'].replace(a.group(1), '').strip()
            x2 = re.search("\{\{[Aa]b\|.*?}}", i['item'])
            if x2:
                ab = x2.group(0)
                i['item'] = i['item'].replace(ab, '').strip()
            has_content = "(content)" in i['item'] and ("Collections" in i['page'] or "Series" in i['page'] or "Extra" in i['page'])
            # if i['page'] == "Appearances/Collections":
            #     ct = re.search("\(content: \[\[(.*?)(\|.*?)?]]", i['item'])
            #     if ct:
            #         has_content = ct.group(1)
            #     i['item'] = re.sub(" ?\(content: \[\[.*?]]\)", "", i['item'])
            i['item'] = i['item'].replace(" (content)", "")

            x3 = re.search(" ?\{\{[Cc]rp}}", i['item'])
            crp = False
            if x3:
                crp = True
                i['item'] = i['item'].replace(x3.group(0), '').strip()

            x = extract_item(i['item'], True, i['page'], types, master=True)
            if x and (x.template == "Film" or x.template == "TCW" or x.target == "Star Wars: The Clone Wars (film)") and x.unique_id() in unique_appearances:
                x.both_continuities = True
                both_continuities.add(x.target)
                continue
            elif x and x.template and x.template.startswith("FactFile") and "y=2014" in x.original:
                x.both_continuities = True
                both_continuities.add(x.target)

            if x:
                x.master_page = i['page']
                x.canon = None if i.get('extra') else i.get('canon')
                x.from_extra = i.get('extra')
                x.date = i['date']
                x.future = x.date and (x.date == 'Future' or x.date > today)
                x.extra = c
                x.alternate_url = alternate
                x.unlicensed = "Unlicensed" in i['page'] or "unlicensed" in c
                if is_source:
                    x.is_appearance = False
                x.non_canon = non_canon
                x.reprint = reprint
                x.has_content = has_content
                x.ab = ab
                x.repr = repr
                x.crp = crp
                x.collection_type = i.get("collectionType")
                x.abridged = "abridged audiobook" in x.original and "unabridged" not in x.original
                x.audiobook = not ab and ("audiobook)" in x.original or x.target in AUDIOBOOK_MAPPING.values() or i['audiobook'])
                x.german_ad = x.target and (x.target in GERMAN_MAPPING or "German audio drama" in x.target)
                full_appearances[x.full_id()] = x
                unique_appearances[x.unique_id()] = x
                if x.target:
                    c, l = determine_index(x, f"{x.issue}-{x.target}" if x.target == "Galaxywide NewsNets" else x.target, i, canon, legends, c_unknown, l_unknown, log_match)
                    if c:
                        no_canon_index.append(x)
                    if l:
                        no_legends_index.append(x)

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
                elif x.parent and "scenario=" not in x.original:
                    c, l = determine_index(x, x.parent, i, canon, legends, c_unknown, l_unknown, log_match)
                    if c:
                        no_canon_index.append(x)
                    if l:
                        no_legends_index.append(x)

                if reprint and x.target not in reprints:
                    reprints[x.target] = [x]
                elif reprint:
                    reprints[x.target].append(x)
            else:
                print(f"Unrecognized: {i['item']}")
                count += 1
        except Exception as e:
            traceback.print_exc()
            print(f"{type(e)}: {e}: {i['item']}")

    for k, v in reprints.items():
        if k in target_appearances:
            x = target_appearances[k][0]
            for i in v:
                i.original_printing = x

    print(f"{count} out of {len(appearances)} unmatched: {count / len(appearances) * 100}")
    print(f"{len(no_canon_index)} canon items found without index")
    print(f"{len(no_legends_index)} Legends items found without index")
    return FullListData(unique_appearances, full_appearances, target_appearances, parentheticals, both_continuities,
                        reprints, no_canon_index, no_legends_index)


def determine_index(x: Item, target, i: dict, canon, legends, c_unknown, l_unknown, log_match):
    c, l = False, False
    o = increment(x)
    canon_index_expected = x.canon and x.match_expected() and not i['audiobook'] and target not in AUDIOBOOK_MAPPING.values() and not x.german_ad and target not in c_unknown
    legends_index_expected = not x.canon and x.match_expected() and not i['audiobook'] and target not in AUDIOBOOK_MAPPING.values() and not x.german_ad and target not in l_unknown

    canon_index = match_audiobook(target, canon, log_match and canon_index_expected, x.master_page)
    if canon_index is not None:
        x.canon_index = canon_index + o
    elif canon_index_expected:
        c = True

    legends_index = match_audiobook(target, legends, log_match and legends_index_expected, x.master_page)
    if legends_index is not None:
        x.legends_index = legends_index + o
    elif legends_index_expected:
        l = True

    return c, l


def increment(x: Item):
    if x.abridged:
        return 0.2
    elif x.target and "audio drama)" in x.target:
        return 0.3
    elif x.target and ("audiobook" in x.target or "script" in x.target or " demo" in x.target):
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
    "The Phantom Menace (German audio drama)": TEMPLATE_MAPPING["Film"]["1"],
    "Attack of the Clones (German audio drama)": TEMPLATE_MAPPING["Film"]["2"],
    "Revenge of the Sith (German audio drama)": TEMPLATE_MAPPING["Film"]["3"],
    "A New Hope (German audio drama)": TEMPLATE_MAPPING["Film"]["4"],
    "The Empire Strikes Back (German audio drama)": TEMPLATE_MAPPING["Film"]["5"],
    "Return of the Jedi (German audio drama)": TEMPLATE_MAPPING["Film"]["6"],
    "The Force Awakens (German audio drama)": TEMPLATE_MAPPING["Film"]["7"],
    "The Last Jedi (German audio drama)": TEMPLATE_MAPPING["Film"]["8"],
    "The Rise of Skywalker (German audio drama)": TEMPLATE_MAPPING["Film"]["9"],
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
}

GERMAN_MAPPING = {
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
    "Lethal Trackdown": "The Clone Wars Episode 22 - R2 Come Home / Lethal Trackdown",
    "The Young Jedi": "Young Jedi Adventures Episode 1 - The Young Jedi / Yoda's Mission / Nash's Race Day / The Lost Jedi Ship",
    "Yoda's Mission": "Young Jedi Adventures Episode 1 - The Young Jedi / Yoda's Mission / Nash's Race Day / The Lost Jedi Ship",
    "Nash's Race Day": "Young Jedi Adventures Episode 1 - The Young Jedi / Yoda's Mission / Nash's Race Day / The Lost Jedi Ship",
    "The Lost Jedi Ship": "Young Jedi Adventures Episode 1 - The Young Jedi / Yoda's Mission / Nash's Race Day / The Lost Jedi Ship",
    "Get Well Nubs": "Young Jedi Adventures Episode 2 - Get Well Nubs / The Junk Giant / Lys and the Snowy Mountain Rescue / Attack of the Training Droids",
    "The Junk Giant": "Young Jedi Adventures Episode 2 - Get Well Nubs / The Junk Giant / Lys and the Snowy Mountain Rescue / Attack of the Training Droids",
    "Lys and the Snowy Mountain Rescue": "Young Jedi Adventures Episode 2 - Get Well Nubs / The Junk Giant / Lys and the Snowy Mountain Rescue / Attack of the Training Droids",
    "Attack of the Training Droids": "Young Jedi Adventures Episode 2 - Get Well Nubs / The Junk Giant / Lys and the Snowy Mountain Rescue / Attack of the Training Droids",
    "Chapter 1: The Mandalorian": "The Mandalorian Episode 1 - The Mandalorian / The Child",
    "Chapter 2: The Child": "The Mandalorian Episode 1 - The Mandalorian / The Child",
    "Chapter 3: The Sin": "The Mandalorian Episode 2 - The Sin / Sanctuary",
    "Chapter 4: Sanctuary": "The Mandalorian Episode 2 - The Sin / Sanctuary",
    "Chapter 5: The Gunslinger": "The Mandalorian Episode 3 - The Gunslinger / The Prisoner",
    "Chapter 6: The Prisoner": "The Mandalorian Episode 3 - The Gunslinger / The Prisoner",
    "Chapter 7: The Reckoning": "The Mandalorian Episode 4 - The Reckoning / Redemption",
    "Chapter 8: Redemption": "The Mandalorian Episode 4 - The Reckoning / Redemption",
}


def match_audiobook(target, data, log, page):
    if target in data:
        return data[target]
    elif target in SPECIAL_INDEX_MAPPING and SPECIAL_INDEX_MAPPING[target] in data:
        return data[SPECIAL_INDEX_MAPPING[target]]
    elif target in SERIES_INDEX and SERIES_INDEX[target] in data:
        return data[SERIES_INDEX[target]]
    elif "Star Wars: Jedi Temple Challenge" in target and "Star Wars: Jedi Temple Challenge" in data:
        return data["Star Wars: Jedi Temple Challenge"] + int(target.replace("Episode ", "").split("(")[0]) / 100
    elif target in TEMPLATE_MAPPING["KOTORbackups"].values():
        issue = next(f"Knights of the Old Republic {k}" for k, v in TEMPLATE_MAPPING["KOTORbackups"].items() if v == target)
        if issue in data:
            return data[issue]

    for x in ["audiobook", "unabridged audiobook", "abridged audiobook", "audio", "script", "audio drama", "German audio drama"]:
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
    if log:
        print(f"{page} No match found: {target}")
    return None


ERAS = {
    "Rise of the Empire era": "32 BBY",
    "Rebellion era": "0 ABY",
    "New Republic era": "10 ABY"
}


def parse_new_timeline(page: Page, types):
    text = page.get()
    redirects = build_redirects(page)
    text = fix_redirects(redirects, text, "Timeline", [], {})
    results = {}
    unique = {}
    index = 0
    unknown = None
    text = re.sub("(\| ?[A-Z]+ ?)\n\|", "\\1|", text).replace("|simple=1", "")
    for line in text.splitlines():
        if "==Unknown placement==" in line:
            unknown = {}
            continue
        line = re.sub("<!--.*?-->", "", line).replace("†", "").strip()

        m = re.search("^\|(data-sort-value=.*?\|)?(?P<date>.*?)\|(\|?style.*?\||\|- ?class.*?\|)?[ ]*?[A-Z]+[ ]*?\n?\|.*?\|+[* ]*?(?P<full>['\"]*[\[{]+.*?[]}]+['\"]*) *?(†|‡|Ω)?$", line)
        if m:
            x = extract_item(m.group('full'), True, "Timeline", types, master=False)
            if x and x.target:
                timeline = None
                # target = Page(page.site, x.target)
                # if target.exists() and not target.isRedirectPage():
                #     dt = re.search("\|timeline=[ \[]+(.*?)(\|.*?)?]+(.*?)\n", target.get())
                #     if dt:
                #         timeline = dt.group(1)
                t = f"{x.issue}-{x.target}" if x.target == "Galaxywide NewsNets" else x.target
                results[t] = {"index": index, "date": m.group("date"), "timeline": timeline}
                if unknown is not None:
                    unknown[t] = index
                elif x.target not in unique:
                    unique[t] = index
                index += 1
        elif "Star Wars (LINE Webtoon)" not in unique and "Star Wars (LINE Webtoon)" in line:
            unique["Star Wars (LINE Webtoon)"] = index
            index += 1

    return results, unique, unknown or {}

# TODO: handle dupes between Legends/Canon
