import re
from datetime import datetime, timedelta

from c4de.common import log_time
from pywikibot import Page, showDiff

from c4de.sources.infoboxer import handle_infobox_on_page


REPLACEMENTS = [
    ("==Work==", "==Works=="), ("Apearance", "Appearance"), ("Appearence", "Appearance"), ("&#40;&#63;&#41;", "(?)"),
    ("===Non-canonical appearances===\n*", "===Non-canon appearances===\n*"), ("\n*\n{{", "\n*{{"),
    ("==Traits and personality==", "==Personality and traits=="), ("Souces", "Sources"), ("=Source=", "=Sources="),
    ("{{mO}}", "{{Mo}}"), ("*{{Indexpage", "{{Indexpage"), ("<br>", "<br />"), ("{{InvalidCategory}}", ""),
    ("Youtube", "YouTube"), ("{{Scrollbox", "{{ScrollBox"), ("referneces", "references"), ("{{MO}}", "{{Mo}}"),
    ("{{C|variant cover only}}", "{{Vco}}"), ("{{C|Variant cover only}}", "{{Vco}}"),
    ("{{scrollbox", "{{ScrollBox"), ("</reF>", "</ref>"), ("\n</ref>", "</ref>"), ("†", "&dagger:"),
    ("<nowiki>|</nowiki>", "&#124;"), ("||text=", "|text="), ("|Parent=1", "|parent=1"),
    ("[[:category:", "[[:Category:"), ("[[category:", "[[Category:"), ("[[Image:", "[[File:"),
    ("{{IntroMissingTitle}} ", ""), ("{{IntroMissingTitle}}\n", ""),
    ("==Media==\n*{{ISBN|", "==Media==\n===Editions===\n*{{ISBN|"),
    ("\n==Back-cover summary==\n", "\n===Back-cover summary===\n"),
    ("{{App|characters=", "{{App\n|characters="), ("PenguinRandomHouse|old=1", "RandomHouseOld"),
    ("<onlyinclude>\n{{Incomplete_app}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("<onlyinclude>\n{{IncompleteApp}}", "{{IncompleteApp}}\n<onlyinclude>"),
    ("{{C|non-canon|reprint=1}}", ""), ("[[Category: ", "[[Category:"), ("{{c|", "{{C|"),
    ('">*{{', '">{{'), (">*''[[", ">''[["), (">*[[", ">[["), (">'>{{", ">{{"),

    ("[[Black]]", "[[Color/Legends|Black]]"), ("[[black]]", "[[Color/Legends|black]]"),
    ("parent=Riddell mini-helmet", "parent=Riddell"),

    ("{{EncyclopediaCite|Padmé Amidala Naberrie}}", "{{EncyclopediaCite|Padmé Amidala}}"),
    ("set=Twilight of the Republic (Star Wars: Unlimited)", "set=Twilight of the Republic"),
    ("|work=[[Entertainment Weekly Books|''Entertainment Weekly'']]", ""),
    ("|work=''[[Wikipedia:Entertainment Weekly|Entertainment Weekly]]''", ""),
    ("|work=[[Wikipedia:Entertainment Weekly|''Entertainment Weekly'']]", ""),
]


GAMESPOT = {
"/": '20210601080030',
"a/bundles/gamespotsite/images/favicon.ico": '20250618213730',
"a/uploads/original/0/77/244924-174523-john-cassaday.jpg": "20260721184518",
"a/uploads/original/1/15659/2796353-lost_light_crew_tf_more_than_meets_the_eye_by_nick_roche_josh_burcham.jpg": '20230930142518',
"a/uploads/original/3/38826/1147856-0abnick.jpg": "20260721214801",
"a/uploads/original/536/5360430/2796353-f-16c aircraft_cptfalcon_c1_02.jpg": '20230930142248',
"a/uploads/original/7/71975/2494954-29161_397991700924_8029657_n.jpg": "20211211202015",
"a/uploads/original/7/75334/1398398-alex_maleev6.jpg": "20260721183208",
"a/uploads/original/mig/7/2/7/4/917274-946617_20081112_010.jpg": '20230928130836',
"alex-maleev/4040-3122/images/?tag=Alex%20Maleev": "20260721182618",
"arcade/563968-star-wars-the-empire-strikes-back/boxes": '20250621102430',
"arcade/564018-star-wars-return-of-the-jedi/boxes": '20250620102430',
"arcade/583802-star-wars/boxes": '20241223102430',
"articles/an-episode-of-lucasfilm-comedy-star-wars-detours-has-leaked-online/1100-6484977": '20201130105825',
"articles/analyst-predicts-october-npd-sales-up-15/1100-6284000": '20240417155909',
"articles/artist-claims-han-solo-movie-posters-plagiarize-hi/1100-6457159": '20180309135233',
"articles/bioware-is-officially-handing-off-development-of-star-wars-the-old-republic/1100-6515522": '20230823212619',
"articles/bioware-to-hand-off-star-wars-mmo-to-focus-on-mass-effect-dragon-age-report/1100-6514870": '20231001123323',
"articles/bioware-unveils-texas-mmorpg-studio/1100-6145813": '20180330125850',
"articles/canceled-star-wars-projects-revealed/1100-6415086": '20190321005141',
"articles/canceled-star-wars-rogue-squadron-game-details-eme/1100-6422908": '20150720121302',
"articles/dice-says-creating-star-wars-battlefront-is-scary/1100-6415603": '20190525074753',
"articles/disney-abandons-star-wars-1313-trademark/1100-6417208": '20160919060635',
"articles/e3-2008-ea-ceo-confirms-kotor-mmo/1100-6194664": '20180330125633',
"articles/e3-2019-star-wars-jedi-fallen-order-did not-begin-as/1100-6467511": "20260717203534",
"articles/e3-2019-star-wars-jedi-fallen-order-didnt-begin-as/1100-6467511": '20190611021118',
"articles/ea-buying-bioware-pandemic-for-860m/1100-6180818": '20200525005648',
"articles/ea-now-owns-titanfall-developer-respawn/1100-6455409": '20190719080449',
"articles/exclusive-star-wars-hunters-adds-huttball-mode-from-star-wars-the-old-republic/1100-6500645": '20220214173725',
"articles/fall-guys-was-pitched-to-10-publishers-before-devo/1100-6481241": '20240509082620',
"articles/first-galaxies-jedi-confirmed-hunted/1100-6081665": '20160107101919',
"articles/first-star-wars-jedi-survivor-gameplay-shows-dual-sabers-confirms-march-17-release/1100-6509864": '20230101190557',
"articles/force-unleashed-sells-7-million-hoth-dlc-arrives/1100-6251593": '20211228112759',
"articles/former-lucasarts-employee-on-why-star-wars-battlefront-iii-failed/1100-6400936": '20191111102800',
"articles/heres-whats-in-lego-star-wars-7s-season-pass/1100-6440204": '20161125054755',
"articles/jedi-fallen-order-didnt-start-out-as-a-star-wars-g/1100-6467511": '20230320184555',
"articles/lego-star-wars-the-complete-saga-for-ios-includes-one-episode-you-must-pay-for-the-rest/1100-6416685": '20190805210519',
"articles/lucasarts-free-radical-going-next-gen/1100-6156330": '20190313225421',
"articles/more-vader-down-retailer-variants-revealed/1100-153968": '20200916112221',
"articles/new-indiana-jones-game-coming-from-wolfenstein-developer/1100-6486174": '20230103161607',
"articles/new-star-wars-battlefront-details-revealed/1100-6424986": '20160415152027',
"articles/no-microtransactions-in-star-wars-battlefront-says/1100-6431154": '20181211045123',
"articles/preview-darth-vader-13/1100-154242": '20220125043246',
"articles/preview-star-wars-11/1100-154053": '20251108075700',
"articles/preview-star-wars-16/1100-154894": '20201010064158',
"articles/preview-star-wars-journey-to-the-force-awakens-sha/1100-153441": '20200916081455',
"articles/sdcc-2014-interview-jason-aaron-discusses-upcoming/1100-149373": '20200809075421',
"articles/sdcc-2014-interview-mark-waid-talks-star-wars-prin/1100-149379": '20201112011556',
"articles/see-star-wars-battlefronts-rogue-one-dlc-in-action/1100-6445890": '20171030233643',
"articles/shortly-before-star-wars-battlefront-2s-release-ea/1100-6455042": '20191203110812',
"articles/star-wars-1313-revealed/1100-6379758": '20190810111526',
"articles/star-wars-1313-was-always-in-danger-report/1100-6406402": '20201011043227',
"articles/star-wars-ask-yoda-hands-on/1100-6121272": '20190808125328',
"articles/star-wars-battlefront-2-will-use-the-clone-wars-an/1100-6462603": '20190121171931',
"articles/star-wars-battlefront-2s-best-version-is-free-for-game-pass-members-right-now/1100-6528572": '20250601125248',
"articles/star-wars-battlefront-classic-collection-releasing-on-switch-in-march/1100-6521243": '20240222175008',
"articles/star-wars-battlefront-iii-footage-leaks-online/1100-6203249": '20190714003518',
"articles/star-wars-battlefront-release-date-listed-in-websi/1100-6426689": '20150418190241',
"articles/star-wars-battlefront-won-t-use-battlefield-s-batt/1100-6426735": '20150420141903',
"articles/star-wars-bounty-hunter-qanda/1100-2885159": '20160124141953',
"articles/star-wars-empire-at-war-forces-of-corruption-designer-diary-5-the-sounds-of-corruption/1100-6159916": '20170618202625',
"articles/star-wars-galaxies-commits-seppuku-in-japan/1100-6136964": '20210213214512',
"articles/star-wars-galaxies-episode-iii-rage-of-the-wookiees-designer-diary-1/1100-6122291": '20210211213745',
"articles/star-wars-galaxies-episode-iii-rage-of-the-wookiees-designer-diary-3-introducing-space-mining/1100-6123569": '20220127212057',
"articles/star-wars-galaxies-episode-iii-rage-of-the-wookies-designer-diary-2/1100-6123211": '20210619171440',
"articles/star-wars-galaxies-features-delayed/1100-2910404": '20241130232844',
"articles/star-wars-kotor-2-restored-content-dlc-canceled-on-switch/1100-6514788": '20230605142552',
"articles/star-wars-open-world-game-in-the-works-at-ea-accor/1100-6457652": '20200606204637',
"articles/star-wars-outlaws-developers-on-creating-the-most-ambitious-star-wars-game-yet/1100-6515135": '20230613024602',
"articles/star-wars-puzzle-blaster-hands-on/1100-6121285": '20250225084700',
"articles/star-wars-republic-commando-designer-diary-2-clone-differentiation/1100-6116078": '20210802225926',
"articles/star-wars-republic-commando-designer-diary-2-clone-differentiation/1100-6116079": '20230927224255',
"articles/star-wars-squadrons-gameplay-reveal-shows-dogfight/1100-6478719": '20200730110417',
"articles/star-wars-squadrons-gameplay-reveal-shows-dogfight/1100-6478719/?ftag=nls-04-10aaa1d": "20250120192642",
"articles/star-wars-the-old-republic-creative-director-is-leaving-bioware/1100-6505574": '20230613041300',
"articles/star-wars-video-games-now-live-under-the-lucasfilm-games-umbrella/1100-6486107": '20230103161354',
"articles/star-wars-x-wing-trilogy/1100-2647970": '20190209112151',
"articles/the-cautious-return-of-star-wars-battlefront/1100-6426701": '20150419031215',
"articles/this-130-star-wars-battlefront-bundle-comes-with-h/1100-6430598": '20150917132751',
"articles/wall-street-taking-notice-of-battlefield-4-issues-as-ea-stock-falls/1100-6416566": '20131206060705',
"articles/why-star-wars-resistance-is-ending-before-the-rise/1100-6470187": '20191217234812',
"atari2600/585157-star-wars-the-empire-strikes-back/boxes": '20241223102430',
"atari5200/585359-star-wars-return-of-the-jedi-death-star-battle/boxes": '20241223102430',
"brian-wood/4040-40795/images": "20211211210903",
"famous-monsters-of-filmland-star-wars-spectacular-/4000-441169": '20200826074130',
"features/6077307/index.html": '20031029034440',
"features/maxis/index.html": '19990508161449',
"gallery/59-star-wars-galaxys-edge-photos-from-disneylands-/2900-2803/3": '20230928150033',
"gallery/the-mandalorian-experience-74-photos-from-the-star-wars-celebration-exhibit/2900-4118": '20220613162242',
"gamecube/action/starwarsroguesquadron3/review.html": '20100411014754',
"games/star-wars-battlefront-2004/images": '20210208131358',
"games/star-wars-battlefront-classic-collection": '20240223021759',
"games/star-wars-chess": '20210512160956',
"games/star-wars-demolition": '20210512121807',
"games/star-wars-demolition/cheats": '20200806015211',
"games/star-wars-episode-iii-revenge-of-the-sith-2005/images": '20210623131143',
"games/star-wars-galactic-battlegrounds": '20201203224932',
"games/star-wars-knights-of-the-old-republic/images": '20210208165537',
"games/star-wars-obi-wan/reviews/?subTypeId=star&subId=wars-obi-wan-review-2836797": '20201108141821',
"games/star-wars-puzzle-blaster/reviews": '20230713162916',
"games/star-wars-republic-commando": '20200711145218',
"games/star-wars-republic-commando-order-66/news": '20230713163702',
"gamespot/features/all/bestof2003/day4_16.html": '20090402173406',
"gamespot/features/all/bestof2003/day5_4.html": '20031226130927',
"gamespot/features/all/greatestgames/p-55.html": '20060415101422',
"images/1300-1549497": '20250503183121',
"images/1300-2796353": '20230930142420',
"images/1300-917274": '20230928130027',
"jo-chen/4040-1934": "20251008002102",
"john-cassaday/4040-1816/images/?tag=John%20Cassaday": "20260721184328",
"lego-star-wars-iii-the-clone-wars": "20121026080755",
"lego-star-wars-the-complete-saga/platform/pc": '20121105105851',
"lego-star-wars-the-complete-saga/platform/xbox360": '20121031232323',
"luis-antonio-delgado/4040-54658": '20201025074534',
"luke-ross/4040-23686/news": '20160803093833',
"marco-checchetto/4040-55782/images": '20210424063303',
"matt-kindt/4040-52118/images/?tag=Matt+Kindt": '20210503090203',
"mobile/action/starwarsrepubliccommandoorder66/review.html": '20100413190521',
"n64/198789-star-wars-shadows-of-the-empire": '20230411085000',
"nes/924878-star-wars-1987/boxes": '20241223102430',
"news/6155908.html": '20070120131941',
"news/6254566.html": '20100417183937',
"news/97_07/28_ea/index.html": '19990423194615',
"news/97_10/15_lucas/index.html": '19990302023456',
"news/analyst-predicts-october-npd-sales-up-15-6284000": '20120815191550',
"news/canceled-star-wars-games-revealed-6415086": '20130929213713',
"news/electronic-arts-moves-maxis-6089213": '20171201083449',
"nick-runge/4040-54678/images": "20201123175646",
"pages/unions/read_article.php?topic_id=25852853&union_id=14038": 'https://archive.is/OqOL3',
"pc/930450-star-wars-galaxies-starter-kit/data": '20190329002918',
"pc/action/jediknightdarkforces2/index.html": '20111026162310',
"pc/action/swtfuultimatesithedition/index.html": '20091004230142',
"pc/action/swtfuultimatesithedition/index.html?tag=result;title;0": '20091211201041',
"pc/rpg/kotor2/images.html?cat=31&mode=user": '20090302000454',
"pc/rpg/starwarstheoldrepublic/images.html": '20100411024615',
"pc/rpg/starwarstheoldrepublic/news.html?page=1&sid=6145813": '20090228185829',
"pc/rpg/starwarstheoldrepublic/news.html?sid=6241909&mode=previews": '20100224030012',
"pc/rpg/starwarstheoldrepublic/news.html?sid=6254499&mode=previews": '20100416074438',
"pc/strategy/starwarsforcecommander/review.html": '20111107122837',
"pc/strategy/starwarsrts/review.html": '20060314201450',
"ps2/action/starwarsjedistarfighter/review.html": '20030402033243',
"ps2/driving/starwarsracerrevenge/images/0/23": '20100323021400',
"ps3/action/soulcaliburiv/images.html?om_act=convert&om_clk=gsimage&tag=images;all": '20070621061207',
"ps3/action/starwars2007/index.html": '20100224224001',
"ps3/action/starwarstheforceunleashed2/video/6265814": '20100819080341',
"psp/action/starwarsbattlefrontelitesquadron/images.html": '20090531152903',
"psp/action/starwarsbattlefrontelitesquadron/images/0/9": '20090602134019',
"psp/action/starwarsbattlefrontelitesquadron/review.html": '20091108180729',
"psp/action/starwarsbattlefrontrenegadesquadron": '20071012091405',
"psp/action/starwarsbattlefrontrenegadesquadron/images.html": '20070518191100',
"psp/action/starwarsbattlefrontrenegadesquadron/images.html?om_act=convert&om_clk=gsimage&tag=images%3Ball&page=2": '20071011133028',
"psp/action/starwarsbattlefrontrenegadesquadron/news.html?sid=6170474&mode=recent": '20090122083124',
"return-of-the-jedi-10-rotj-10/4000-367333": '20201031045224',
"return-of-the-jedi-100-rotj-100/4000-397430": '20210516154528',
"return-of-the-jedi-101-rotj-101/4000-397433": '20210502171808',
"return-of-the-jedi-102-rotj-102/4000-397434": '20210502171928',
"return-of-the-jedi-103-rotj-103/4000-397435": '20211204095015',
"return-of-the-jedi-104-rotj-104/4000-397436": '20210502180310',
"return-of-the-jedi-105-rotj-105/4000-397437": '20210502180739',
"return-of-the-jedi-106-rotj-106/4000-397438": '20210502180836',
"return-of-the-jedi-107-rotj-107/4000-397439": '20220116232635',
"return-of-the-jedi-108-rotj-108/4000-397440": '20210502181048',
"return-of-the-jedi-109-rotj-109/4000-397441": '20220128082212',
"return-of-the-jedi-11-rotj-11/4000-368439": '20210502181413',
"return-of-the-jedi-110-rotj-110/4000-397442": '20210502181554',
"return-of-the-jedi-111-rotj-111/4000-397443": '20210502181750',
"return-of-the-jedi-112-rotj-112/4000-397444": '20230131233737',
"return-of-the-jedi-113-rotj-113/4000-397445": '20210502182153',
"return-of-the-jedi-114-rotj-114/4000-397446": '20210503084336',
"return-of-the-jedi-115-rotj-115/4000-397447": '20210503084632',
"return-of-the-jedi-116-rotj-116/4000-397448": '20210503084856',
"return-of-the-jedi-117-rotj-117/4000-397449": '20210503085012',
"return-of-the-jedi-118-rotj-118/4000-397450": '20210503085319',
"return-of-the-jedi-119-rotj-119/4000-397451": '20210503085435',
"return-of-the-jedi-12-rotj-12/4000-368440": '20230131233737',
"return-of-the-jedi-120-rotj-120/4000-397452": '20210503085512',
"return-of-the-jedi-121-rotj-121/4000-397453": '20210503085433',
"return-of-the-jedi-122-rotj-122/4000-406173": '20210503085501',
"return-of-the-jedi-123-rotj-123/4000-406174": '20210503085625',
"return-of-the-jedi-124-rotj-124/4000-406175": '20210503085415',
"return-of-the-jedi-125-rotj-125/4000-406176": '20210503085427',
"return-of-the-jedi-126-rotj-126/4000-406177": '20210503110405',
"return-of-the-jedi-127-rotj-127/4000-406178": '20210503110558',
"return-of-the-jedi-128-rotj-128/4000-406179": '20210503110528',
"return-of-the-jedi-129-rotj-129/4000-406180": '20210503110554',
"return-of-the-jedi-13-rotj-13/4000-368441": '20210503094015',
"return-of-the-jedi-130-rotj-130/4000-406181": '20210503110516',
"return-of-the-jedi-131-rotj-131/4000-406200": '20210503110654',
"return-of-the-jedi-132-rotj-132/4000-406201": '20210503110640',
"return-of-the-jedi-133-rotj-133/4000-406202": '20210503110632',
"return-of-the-jedi-134-rotj-134/4000-406203": '20210503110617',
"return-of-the-jedi-135-rotj-135/4000-406204": '20210503110538',
"return-of-the-jedi-136-rotj-136/4000-406205": '20210503110652',
"return-of-the-jedi-137-rotj-137/4000-406206": '20210503110606',
"return-of-the-jedi-138-rotj-138/4000-406207": '20210503110557',
"return-of-the-jedi-139-rotj-139/4000-406208": '20210503110600',
"return-of-the-jedi-14-rotj-14/4000-368442": '20210503093937',
"return-of-the-jedi-140-rotj-140/4000-406209": '20210503110439',
"return-of-the-jedi-141-rotj-141/4000-406215": '20210503110701',
"return-of-the-jedi-142-rotj-142/4000-406216": '20210503110518',
"return-of-the-jedi-144-rotj-144/4000-406218": '20210503131018',
"return-of-the-jedi-145-rotj-145/4000-406219": '20210503125949',
"return-of-the-jedi-146-rotj-146/4000-406220": '20210503130018',
"return-of-the-jedi-147-rotj-147/4000-406221": '20210503125948',
"return-of-the-jedi-148-rotj-148/4000-406222": '20210503130025',
"return-of-the-jedi-149-rotj-149/4000-406223": '20210503130003',
"return-of-the-jedi-15-rotj-15/4000-368443": '20210503182716',
"return-of-the-jedi-150-rotj-150/4000-406224": '20210503130029',
"return-of-the-jedi-151-rotj-151/4000-368599": '20210503125938',
"return-of-the-jedi-152-rotj-152/4000-368600": '20210503130919',
"return-of-the-jedi-153-rotj-153/4000-368601": '20210503130926',
"return-of-the-jedi-154-rotj-154/4000-368602": '20210503130914',
"return-of-the-jedi-155-rotj-155/4000-368603": '20210503130859',
"return-of-the-jedi-16-rotj-16/4000-368445": '20210503182846',
"return-of-the-jedi-17-rotj-17/4000-368446": '20210503183012',
"return-of-the-jedi-18-rotj-18/4000-368447": '20210503182833',
"return-of-the-jedi-19-rotj-19/4000-368448": '20210503183033',
"return-of-the-jedi-20-rotj-20/4000-368449": '20210503182829',
"return-of-the-jedi-21-rotj-21/4000-368450": '20210503183024',
"return-of-the-jedi-22-rotj-22/4000-368451": '20210503183012',
"return-of-the-jedi-23-rotj-23/4000-368452": '20210503183004',
"return-of-the-jedi-24-rotj-24/4000-368453": '20210503182932',
"return-of-the-jedi-25-rotj-25/4000-368454": '20210503182819',
"return-of-the-jedi-26-rotj-26/4000-368455": '20210503183017',
"return-of-the-jedi-27-rotj-27/4000-368456": '20210503182807',
"return-of-the-jedi-28-rotj-28/4000-368457": '20210503182906',
"return-of-the-jedi-29-rotj-29/4000-368458": '20210503182800',
"return-of-the-jedi-30-rotj-30/4000-368459": '20210503182903',
"return-of-the-jedi-31-rotj-31/4000-368460": '20210503182858',
"return-of-the-jedi-32-rotj-32/4000-368471": '20210503182813',
"return-of-the-jedi-33-rotj-33/4000-368472": '20210503182739',
"return-of-the-jedi-34-rotj-34/4000-368473": '20210508075108',
"return-of-the-jedi-35-rotj-35/4000-368474": '20210508075343',
"return-of-the-jedi-36-rotj-36/4000-368475": '20210508075143',
"return-of-the-jedi-37-rotj-37/4000-368476": '20210508075420',
"return-of-the-jedi-38-rotj-38/4000-368477": '20210508075201',
"return-of-the-jedi-39-rotk-39/4000-368478": '20210508075958',
"return-of-the-jedi-40-rotj-40/4000-368479": '20210508075408',
"return-of-the-jedi-41-rotj-41/4000-368480": '20210508075243',
"return-of-the-jedi-42-rotj-42/4000-368481": '20210508075239',
"return-of-the-jedi-43-rotj-43/4000-368482": '20210508075239',
"return-of-the-jedi-44-rotj-44/4000-368483": '20210508075237',
"return-of-the-jedi-45-rotj-45/4000-368484": '20210508075223',
"return-of-the-jedi-46-rotj-46/4000-368485": '20210508075414',
"return-of-the-jedi-47-rotj-47/4000-368486": '20210508075307',
"return-of-the-jedi-48-rotj-48/4000-368487": '20210508075156',
"return-of-the-jedi-49-rotj-49/4000-368488": '20210508075337',
"return-of-the-jedi-50-rotj-50/4000-368489": '20210508075259',
"return-of-the-jedi-51-rotj-51/4000-368490": '20210508075225',
"return-of-the-jedi-52-rotj-52/4000-368491": '20210508075255',
"return-of-the-jedi-53-rotj-53/4000-368492": '20210508080034',
"return-of-the-jedi-54-rotj-54/4000-368493": '20210508080025',
"return-of-the-jedi-55-rotj-55/4000-368494": '20210508080014',
"return-of-the-jedi-56-rotj-56/4000-368495": '20210508080023',
"return-of-the-jedi-57-rotj-57/4000-368496": '20210514195258',
"return-of-the-jedi-58-rotj-58/4000-368497": '20210514195519',
"return-of-the-jedi-59-rotj-59/4000-368498": '20210514195458',
"return-of-the-jedi-60-rotj-60/4000-368499": '20210514195521',
"return-of-the-jedi-61-rotj-61/4000-368500": '20210514195444',
"return-of-the-jedi-62-rotj-62/4000-368501": '20210514195434',
"return-of-the-jedi-63-rotj-63/4000-368502": '20210514195314',
"return-of-the-jedi-64-rotj-64/4000-368504": '20210514195335',
"return-of-the-jedi-65-rotj-65/4000-368505": '20210514195454',
"return-of-the-jedi-66-rotj-66/4000-368506": '20210514195514',
"return-of-the-jedi-67-rotj-67/4000-368507": '20210514195400',
"return-of-the-jedi-68-rotj-68/4000-368508": '20210514195449',
"return-of-the-jedi-69-rotj-69/4000-368509": '20210514195517',
"return-of-the-jedi-70-rotj-70/4000-368510": '20210514195349',
"return-of-the-jedi-71-rotj-71/4000-368511": '20210514195251',
"return-of-the-jedi-72-rotj-72/4000-368512": '20210514195247',
"return-of-the-jedi-73-rotj-73/4000-368513": '20210515193239',
"return-of-the-jedi-74-rotj-74/4000-368514": '20210515193437',
"return-of-the-jedi-75-rotj-75/4000-368515": '20210515193538',
"return-of-the-jedi-76-rotj-76/4000-368516": '20210515193450',
"return-of-the-jedi-77-rotj-77/4000-368517": '20210515193610',
"return-of-the-jedi-78-rotj-78/4000-368518": '20210515193514',
"return-of-the-jedi-79-rotj-79/4000-368519": '20210515193505',
"return-of-the-jedi-80-rotj-80/4000-368520": '20210515193302',
"return-of-the-jedi-81-rotj-81/4000-303911": '20210515193318',
"return-of-the-jedi-82-rotj-82/4000-368521": '20210515193554',
"return-of-the-jedi-83-rotj-83/4000-368522": '20210515193411',
"return-of-the-jedi-84-rotj-84/4000-368523": '20210515193433',
"return-of-the-jedi-85-rotj-85/4000-368524": '20210515193412',
"return-of-the-jedi-86-rotj-86/4000-368594": '20210515193316',
"return-of-the-jedi-87-rotj-87/4000-368595": '20210515193407',
"return-of-the-jedi-88-rotj-88/4000-368596": '20210515193344',
"return-of-the-jedi-89-rotj-89/4000-303917": '20210515193304',
"return-of-the-jedi-9-rotj-9/4000-367325": '20210514200141',
"return-of-the-jedi-90-rotj-90/4000-368597": '20210515193419',
"return-of-the-jedi-91-rotj-91/4000-397421": '20210515193436',
"return-of-the-jedi-92-rotj-92/4000-397422": '20210516154201',
"return-of-the-jedi-93-rotj-93/4000-397423": '20210516154450',
"return-of-the-jedi-94-rotj-94/4000-397424": '20210516154519',
"return-of-the-jedi-95-rotj-95/4000-397425": '20210516154248',
"return-of-the-jedi-96-rotj-96/4000-397426": '20210516154505',
"return-of-the-jedi-97-rotj-97/4000-397427": '20210516154336',
"return-of-the-jedi-98-rotj-98/4000-397428": '20210516154459',
"return-of-the-jedi-99-rotj-99/4000-397429": '20210516154358',
"return-of-the-jedi-rotj-143/4000-406217": '20210503130809',
"reviews/jedi-knight-dark-forces-ii-review/1900-2535572": '20160103015744',
"reviews/lego-star-wars-ii-the-original-trilogy-review/1900-6157719": '20160508044211',
"reviews/shadows-of-the-empire-review/1900-2532961": '20190520102707',
"reviews/star-wars-force-commander-review/1900-2536084": '20190520100333',
"reviews/star-wars-rogue-squadron-3d-review/1900-2532848": '20210121190655',
"reviews/star-wars-rogue-squadron-review/1900-2545130": '20201020221326',
"reviews/star-wars-the-old-republic-rise-of-the-hutt-cartel/1900-6408738": '20190430071245',
"reviews/x-wing-collector-series-review/1900-2532008": '20150524042732',
"rodolfo-migliari/4040-1385/images/?tag=Rodolfo%20Migliari": "20260724184253",
"ryan-kelly/4040-48997/images/?tag=Ryan%20Kelly": "20260724184545",
"snes/563220-super-star-wars-return-of-the-jedi": '20210228215257',
"snes/563221-super-star-wars-the-empire-strikes-back": '20210307094656',
"star-wars-160/4000-329455": '20200926133402',
"star-wars-161/4000-329456": '20200926133531',
"star-wars-162/4000-329457": '20200926133529',
"star-wars-163/4000-329458": '20200926133431',
"star-wars-168/4000-329463": '20200926133601',
"star-wars-169/4000-329464": '20200926133447',
"star-wars-170/4000-329465": '20200926133445',
"star-wars-171/4000-329466": '20200926133541',
"star-wars-adventures-tales-from-vaders-castle-1-tp/4000-706227": '20190520194205',
"star-wars-battlefront-2004/images/?tag=All%20Images": 'https://archive.is/VmutH',
"star-wars-battlefront-ii-2005/images/?tag=All%20Images": 'https://archive.is/9Ssd7',
"star-wars-chess": '20210512160956',
"star-wars-episode-i-the-phantom-menace-3/4000-125632": '20210620135817',
"star-wars-insider-125/4000-445530": '20201201100447',
"star-wars-insider-130/4000-445535": '20210807153725',
"star-wars-insider-171/4000-585132": '20180221023814',
"star-wars-insider-175/4000-619674": '20180213223234',
"star-wars-insider-176/4000-630629": '20180213225253',
"star-wars-insider-177/4000-643124": '20180213233105',
"star-wars-insider-178/4000-655360": '20180213233931',
"star-wars-jedi-master-magazine-1/4000-506732": '20230930141529',
"star-wars-jedi-master-magazine-2/4000-511575": '20230930141617',
"star-wars-jedi-master-magazine-3/4000-520273": '20230930141717',
"star-wars-jedi-master-magazine-4/4000-530799": '20230930141810',
"star-wars-jedi-master-magazine-5/4000-540140": '20230930141853',
"star-wars-jedi-master-magazine-6/4000-551728": '20230930141939',
"star-wars-jedi-of-the-republic-mace-windu-1-tpb/4000-661161": '20180304193145',
"star-wars-knights-of-the-old-republic-ii-the-sit": '20180107021022',
"star-wars-knights-of-the-old-republic/images": '20130605024133',
"star-wars-obi-wan/reviews/star-wars-obi-wan-review-2836797": '20130705232457',
"star-wars-rebels-magazine-5/4000-541275": '20230930144215',
"star-wars-return-of-the-jedi": '20210602142309',
"star-wars-the-empire-strikes-back-144/4000-329439": '20200927095336',
"star-wars-the-empire-strikes-back-150/4000-329445": '20200927095510',
"star-wars-the-old-republic/previews/star-wars-the-old-republic-exclusive-hands-on-bounty-hunter-trooper-imperial-agent-smuggler-sith-inquisitor-and-sith-warrior-6265070": '20111128080839',
"star-wars-the-old-republic/reviews/star-wars-the-old-republic-review-6348266": '20120109231554',
"story/6215526/star-wars-the-old-republic-updated-qanda-the-sith-warrior": '20091227114615',
"story/6265070/star-wars-the-old-republic-exclusive-hands-on-bounty-hunter-trooper-imperial-agent-smuggler-sith-inquisitor-and-sith-warrior?tag=top_stories%3Btitle%3B1&page=2": '20100710093631',
"tonci-zonjic/4040-52971": '20160909142703',
"uploads/original/1365/13658182/2885930-star_wars_battlefront_darth_vader.jpg": '20181211045357',
"uploads/original/1365/13658182/2885932-star_wars_battlefront_luke_skywalker.jpg": '20181211045818',
"video/6265814": '20100622072832',
"walter-simonson/4040-7943": "20250304083537",
"wii/action/starwars2007/index.html": '20100225113821',
"xbox/action/starwarsjedistarfighter/review.html": '20030405063728',
"xbox/rpg/kotor2/news.html?sid=6109428&mode=previews": '20121107210948',
"xbox/rpg/kotor2/screenindex.html?page=10": '20041216151129',
"xbox/rpg/kotor2/screenindex.html?page=9": '20041128052504',
"xbox/rpg/kotor2/tech_info.html": '20060417150307',
"xbox/rpg/kotor2/video/6095390/star-wars-knights-of-the-old-republic-ii-the-sith-lords-developer-interview": '20081208165353',
"xbox/rpg/kotor2/video/6096604/star-wars-knights-of-the-old-republic-ii-the-sith-lords-developer-interview-2": '20090707163225',
"xbox/rpg/starwarsknightsoftor/news.html?sid=6194664": '20090228203241',
"xbox/rpg/starwarsknightsoftor/screenindex.html": '20031209100303',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=13": '20040204005325',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=14": '20040228010943',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=15": '20040204005333',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=16": '20040204005329',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=18": '20031212040516',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=19": '20040624205045',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=20": '20031210195056',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=23": '20031211120551',
"xbox/rpg/starwarsknightsoftor/screenindex.html?page=9": '20031102200403',
"xbox360/action/crackdown2/video/6285608": '20101224234213',
"xbox360/action/soulcaliburiv/images.html?om_act=convert&om_clk=gsimage&tag=images;all": '20071022032534',
"xbox360/action/starwars2007/index.html": '20100224070656',
"xbox360/action/starwars2007/news.html?sid=6186606": '20110711071741',
"xbox360/action/starwars2007/video/6197956/star-wars-the-force-unleashed-launch-event-visit-1": '20090411144040',
}

EXTRA = r"\{+ ?(1st[A-z]*|[Cc]|V?[A-z][od]|[Bb]ts[Oo]nly|DLC|[Ll]n|[Cc]rp|[Uu]n|[Nn]c[ms]?|[Aa]mbig|[Aa]dvert|[Mm]ap[Pp]oint|[Cc]osmetic|[Gg]amecameo|[Cc]odex|[Cc]irca|[Cc]orpse|[Rr]etcon|[Ff]lash(back)?|[Uu]nborn|[Gg]host|[Dd]el|[Hh]olo(cron|gram)|[Ii]mo|ID|[Rr]et|[Ss]im|[Vv]ideo|[Vv]ision|[Vv]oice|[Ww]reck|[Cc]utscene|[Cc]rawl) ?[|}]"


def clean_references(before):
    before = re.sub(r"<ref name ?=([^'\">]*?) ?[\"'] ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=([^'\">]*?) ?[\"'] ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"<ref name ?=[\"']([^'\" ]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=[\"']([^'\" ]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"<ref name ?=([^'\">]+?) ?/ ?>", "<ref name=\"\\1\" />", before)
    before = re.sub(r"<ref name ?=([^'\">]+?) ?>", "<ref name=\"\\1\">", before)
    before = re.sub(r"(<ref name=\"(.*?)\")>[ \n\t]*?</ref>", "\\1 />", before)
    before = re.sub(r"</ref>([A-z])", "</ref> \\1", before)
    before = re.sub(r"(<ref( name=\".*?\")?>)\*", "\\1", before)
    if "\n</ref>" in before:
        before = re.sub(r"(<ref name=((?!</ref>).)*?)\n</ref>", "\\1</ref>", before)
    return before.replace(r"\"/>", "\" />")


def initial_cleanup(target: Page, all_infoboxes, before: str=None, infobox_log=True):
    now = datetime.now()
    if not before:
        before = target.get(force=True)
    # priority fixes
    before = before.replace(r"\u202c", "")
    before = re.sub(r"(\{\{WebCite[^\n}]*?)\|title=(.*?}})", "\\1|text=\\2", before)
    before = before.replace("\n}}</ref>", "}}</ref>")
    before = re.sub(r"(\{\{(SWGcite|TORcite).*?)\|type=", "\\1|TORTYPE=", before)
    before = re.sub(r"(\{\{(SWGcite|TORcite)[^}]*?)\n?\|type=", "\\1|TORTYPE=", before)
    before = re.sub(r"((\{\{Top(\|.*?)?}})(\n.*?)*?)\n\{\{Top}}", "\\1", before)    # Duplicate {{Top}}

    # whitespace/spacing issues
    before = re.sub(r"\* +([A-z0-9'\[{])", "*\\1", before)
    before = re.sub(r"\n<br ?/?>(\n+==)", "\\1", before)
    before = re.sub(r"([A-z'0-9\]]+)  +([A-z'0-9\[]+)", "\\1 \\2", before)
    before = re.sub(r"\n[ ]+\n", "\n\n", before)

    log_time("retrieval", now)
    if "]]{{" in before or "}}{{" in before:
        before = re.sub(r"(]]|}})(" + EXTRA + ")","\\1 \\2", before)

    # Handle title parameters in Template:Top
    before = handle_top_title(before, target.title())

    now = datetime.now()
    while "== " in before or " ==" in before:
        before = before.replace(r"== ", "==").replace(" ==", "==")
    for (x, y) in REPLACEMENTS:
        before = before.replace(x, y)

    # inline files, text/etc. in image field
    before = re.sub(r"([A-z0-9.>])(\[\[File:.*?]]\n)", "\\1\n\\2", before)
    before = re.sub(r"\|image=(File:)?([A-Z0-9 _]+\..+)(?=\n)", "|image=[[File:\\2]]", before)
    before = re.sub(r"(\|image=\[\[File:[^\n\]]+?)\|.+?]]", "\\1]]", before)
    before = re.sub(r"(\|image=\[\[File:.*?)(\|alt=.*?)]]\n", "\\1]]\n\\2\\n", before)

    # multi-line templates, extra/wrong brackets, etc.
    before = re.sub(r"\{\{C\|([^\[{}]+)(]]}})", "{{C|[[\\1\\2", before)
    before = re.sub(r"(?<!\[)\[((?!Original)[^\[\]\n]+)]]", "[[\\1]]", before)
    before = re.sub(r"([*#]\{\{[^}\n]+)\n([^{\n]+}})", "\\1\\2", before)
    before = re.sub(r"\{\{([^\n{}\[]+?)]]", "{{\\1}}", before)
    before = re.sub(r"\{\{(.*?[^\n\]])]}(?!})", "{{\\1}}", before)
    before = re.sub(r"(?<!\{)\{(\{\{[^\n{}]+}})(?!})", "\\1", before)
    before = re.sub(r"(?<!\{)(\{\{[^\n{}]+})(?!})", "\\1}", before)
    before = re.sub(r"(?<!\{)(\{[^\n{}]+}})(?!})", "{\\1", before)
    before = re.sub(r"(\{\{1st[A-z]*)\|\n}}", "\\1}}", before)
    before = re.sub(r"(\{\{1st[A-z]*\|[^|}\n]*?)\n}}", "\\1}}", before)
    before = re.sub(r"(\{\{[A-z0-9-]+[^{}\n]+?) *\n *}}", "\\1}}", before)
    before = re.sub(r"^([^\[\]\n]+\[\[[^\[\]\n]+)]]]+('*)", "\\1]]\\1", before)
    before = re.sub(r"\[\[(.*?)\|''\1'']]([ .,<])", "''[[\\1]]''\\2", before)
    before = re.sub(r"(\{\{([A-z _0-9]+)\|.*?}}) (\{\{1st[a-z]*)\|\{\{\2.*?}}( \{.*?)?\n", "\\1 \\3}}\\4\n", before)
    before = re.sub(r"\{\{(1st[A-z]*|[Mm]o)}}</ref>", "</ref>", before)
    # missing newline between listings or templates
    before = re.sub(r"(\n\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?)(\*[^\n]*?[\[{]+[^\n]*?[]}]+[^\n]*?\n)", "\\1\n\\2", before)
    before = re.sub(r"(\{\{Quote\|[^\n{}]+?(\{\{[^\n{}]+?}})?[^\n{}]+?}})(?!\n)", "\\1\n", before)

    # fixing same-line infobox fields
    while re.search(r"(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", before):
        before = re.sub(r"(\n\*+\[\[[^\n\]}]+?]])(\|[a-z _]+=)", "\\1\n\\2", before)
    log_time("regex-0", now)

    now = datetime.now()
    infobox, original = None, None
    if all_infoboxes and not target.title().startswith("User:") and not target.title().startswith("File:"):
        before, infobox, original = handle_infobox_on_page(before, target, all_infoboxes, add=False, log=infobox_log)
    log_time("infobox", now)

    now = datetime.now()
    # fixing bad references
    before = clean_references(before)
    log_time("references", now)

    # section header issues
    now = datetime.now()
    before = re.sub(r"\n=([A-z ]+)==", "\n==\\1==", before)
    before = re.sub(r"==((?!Notes and references).)*?==(\n\{.*?}})?\n\{\{[Rr]eflist}}", "==Notes and references==\\2\n{{Reflist}}", before)
    before = re.sub(r"=+ ?([Rr]eferences?|[Nn]otes? (and )?[Rr]ef.*?) ?=+", "==Notes and references==", before)
    before = re.sub(r"= ?([Cc]ollections?|Collected [Ii]n) ?=", "=Collected in=", before)
    # before = re.sub(r"=+ ?'*Non-canon(ical)? ([Aa]ppearances|[Ss]ources)'* ?=+", "===Non-canon \\2===", before)
    before = re.sub(r"\n===(Merchandis(e|ing)(.*?)|Adaptations?|Tie[ -]ins?( media)?)===", "\n==Adaptations==", before)
    before = re.sub(r"(\n===?.*?)<ref name=.*?(/>|</ref>)(.*?==+) ?\n", "\\1\\3\n", before)
    if "<references" in before.lower():
        before = re.sub(r"<[Rr]efe?rences ?/ ?>", "{{Reflist}}", before)

    while re.search(r"\[\[(?!File:)([^\[\]{}\n]+?)&[mn]dash;([^\[\]{}\n]+?)]]", before):
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&ndash;([^\[\]{}\n]+?)]]", "[[\\1–\\2]]", before)
        before = re.sub(r"\[\[(?!File:)([^\[\]{}\n]+?)&mdash;([^\[\]{}\n]+?)]]", "[[\\1—\\2]]", before)

    before = re.sub(r"(\{\{(Unknown|Series)Listing.*?}})\{\{", "\\1 {{", before)
    before = re.sub(r"({{[Ss]croll[_ ]?[Bb]ox\|)\*", "{{ScrollBox|\n*", before)
    before = re.sub(r"<small>\((.*?)\)</small>", "{{C|\\1}}", before)

    before = re.sub(r"(\{\{[A-z]+YouTube\|[^\n[\]{}]*?\|[^\n[\]{}]*?) \| ([^\n[\]{}]*?(\|[a-z]+=.*?)?}})", "\\1 &#124; \\2", before)
    before = re.sub(r"(\{\{Databank[^}\n]*?)\|title=", "\\1|text=", before)

    # removing work= parameters and prioritizing
    before = re.sub(r"(\{\{((?!([wW]ebCite|OfficialSite))[^{}\n])*?\|[^{}\n]+?)\|work=(\[\[[^]]+\|.*?]])?.*?(\|.*?)?}}", "\\1\\4}}", before)
    before = re.sub(r"(\{\{[A-z]+)(\|url=[^\n{}]+?)(\|(subdomain|uk|lang)=[^\n{}]+?)(\|[^\n{}]*?)?}}", "\\1\\3\\2\\5}}", before)

    b1, b2, b3 = before.partition(r"{{App\n")
    b3 = re.sub(r"\n?(\|(c-|l-)?(characters|organisms|droids|events|locations|organizations|species|vehicles|technology|miscellanea)=)\*", "\n\\1\n*", b3)
    before = f"{b1}{b2}{b3}"

    before = re.sub(r"(\[\[[^\n\[{|]+)\|(an?) ([^\n|\[{]+?)]]", "\\2 \\1|\\3]]", before)

    # weird multi-link listings, legacy formatting from the 2000s
    before = re.sub(r"\*('*?)\[\[([^\n\]|{]*?)]]('*?) '*?\[\[(\2\([^\n\]{]*?)\|(.*?)]]'*", "*[[\\4|\\1\\2\\3 \\5]]", before)
    before = re.sub(r"\*'*?\[\[([^\n\]{]*?)(\|[^\n\]{]*?)]]'*? '*?\[\[(\1 \([^\n\]{]*?)\|(.*?)]]'*", "*[[\\3|\\2 \\4]]", before)

    before = re.sub(r"\|story=\[\[(.*?)(\|.*?)?]]", "|story=\\1", before)
    before = re.sub(r"(\|set=(.*?))\|sformatted=''\2''", "\\1", before)
    before = re.sub(r"(\|set=.*?)(\|subset=.*?)(\|stext=.*?)(\|.*?)?}}", "\\1\\3\\2\\4}}", before)
    before = re.sub(r"(\{\{([A-z_ ]+)\|(set=)?[^|=\n}]+?)(\|link=[^|\n}]+?)(\|cardname=[^|\n}]+?)(\|[^\n}]*?)?}}", "\\1\\5\\4\\6}}", before)

    before = re.sub(r"\{\{[Ii]ncomplete[ _]?[Ll]ist.*?}}\n?\{\{(App|Credits)", "{{Incomplete\\1}}\n{{\\1", before)
    before = re.sub(r"( \{\{(C\|Hologram|1st|[MmPpCcVv]o).*?}})\1+", "\\1", before)

    # Visual Editor fix, can't remove
    before = re.sub(r"\[\[(.*?) (.*?)\|('*\1'*)]] \[\[\1 \2\|\2]]", "[[\\1 \\2|\\3 \\2]]", before)

    # temp fixes
    before = re.sub(r"'*\[\[Fortnite]]'* ?&[mn]dash; ?'*\[\[(.*?)(\|.*?)?]]'*", "{{Fortnite|\\1}}", before)
    before = re.sub(r"\{\{InsiderCite\|link=(.*?)(.*?)\|''\1''\2\|(.*?)}}", "{{StoryCite|book=\\1|story=\\3}}", before)
    before = re.sub(r"'*\[(https?://[w.]*?archive.org/.*?) (.*?)]'* (on|at)( the)? ('*\[https?://[w.]*archive\.org/? )?Internet Archive]?'*", "{{WebCite|url=\\1|text=\\2}}", before)
    before = re.sub(r"(\{\{GalaxyMapAppendix}})( |&.dash;)*[Bb]ased on (corresponding )?(info(rmation)?|data) for (the )?(\[\[((?! and ).)*?]]).?</ref>", "\\1 &mdash; Based on corresponding data for the \\7</ref>", before)

    before = re.sub(r"\[\[Star Wars: Force Collection]]'* \{\{C\|Card: (.*?)}}", "{{ForceCollection|\\1}}", before)
    before = re.sub(r">'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r">'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", ">{{Rebels|\\1}}", before)
    before = re.sub(r"'*\[\[Star Wars Rebels: (Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)]]'*", "\"[[\\1]]\"", before)
    before = re.sub(r"'*\[\[(Heroes of Mandalore|Steps Into Shadow|The Siege of Lothal)\|'*Star Wars Rebels: \1'*]]'*", "\"[[\\1]]\"", before)

    gamespot = []
    for x in re.findall(r"(\{\{GameSpot\|subdomain=(.*?)\|url=(.*?)(\|text=(.*?)(\|.*?)?)}})", before):
        gamespot.append((x[0], x[1], x[2], x[3]))
    for x in re.findall(r"(\{\{GameSpot\|url=(.*?)(\|text=(.*?)(\|.*?)?)}})", before):
        gamespot.append((x[0], "www", x[1], x[2]))

    for z, sd, ux, tx in gamespot:
        archive = ""
        if ux in GAMESPOT and GAMESPOT[ux].startswith("2"):
            archive = f"|archivedate={GAMESPOT[ux]}"
        elif ux in GAMESPOT:
            archive = f"|archiveurl={GAMESPOT[ux]}"
        before = before.replace(z, "{{WebCite|url=https://" + sd + ".gamespot.com/" + ux + tx + archive + "}}")

    before = re.sub(r"\[\[Category:Articles with /LEGO.*?\n", "", before)
    before = re.sub(r"\n\[\[Category:Articles with /LEGO.*?]](\{\{.*?}})?$", "", before)

    before = re.sub(r">\[\[Star Wars Galaxy Map \(poster\)\|[^\n\]\[]+]]<", ">{{GalaxyMapPoster}}<", before)
    before = re.sub(r">The \[\[Star Wars Galaxy Map \(poster\)\|[^\n\]\[]+]]", ">The {{GalaxyMapPoster}}", before)
    if "{{TradeRoute" not in before:
        before = re.sub(r"(\*\{\{(StarWarsGalaxyMap|TheStarWarsGalaxy}})}})\n", "*{{StarWarsGalaxyMap}} {{MapPoint}}\n", before)

    while re.search(r"\[\[Category:[^\n|\]_]+_", before):
        before = re.sub(r"(\[\[Category:[^\n|\]_]+)_", "\\1 ", before)
    log_time("regex-1", now)

    now = datetime.now()
    before = regex_cleanup(before)
    log_time("regex-2", now)
    if "{{C|unlicensed}}" in before:
        before = re.sub(r"( {{[Cc]\|[Uu]nlicensed}})+", "", before)
    if "{{Mentioned" in before or "{{mentioned" in before:
        before = re.sub(r"\{\{[Mm]entioned[ _]only\|?}}", "{{Mo}}", before)

    if "‎" in before:
        before = before.replace(r"‎", "")
        print(f"Found ‎ in {target.title()}")
    return before, infobox, original


def regex_cleanup(before: str) -> str:
    if before.count(r"==Appearances==") > 1:
        before = re.sub(r"(==Appearances==(\n.*?)+)\n==Appearances==", "\\1", before)
    if before.count(r"==Sources==") > 1:
        before = re.sub(r"(==Sources==(\n.*?)+)\n==Sources==", "\\1", before)

    if "{{SWU" in before:
        before = re.sub(r"(\{\{SWU\|.*?cardname=[^\n{}]+?)&mdash;([^\n{}]+?}})", "\\1|subtitle=\\2", before)

    if "<nowiki>|" in before:
        while re.search(r"<nowiki>(\|.*?\|.*?)</nowiki>", before):
            before = re.sub(r"<nowiki>\|(.*?)\|(.*?)?</nowiki>", "<nowiki>|\\1&#124;\\2</nowiki>", before)
        before = re.sub(r"<nowiki>\|(.*?)</nowiki>", "&#124;\\1", before)
    if "cardname=" in before:
        before = re.sub(r"(\|cardname=[^\n}]+?)\{\{C\|(.*?)}}", "\\1(\\2)", before)
        before = before.replace(r"cardname=\n", "cardname=")
    if "web.archive" in before:
        before = re.sub(r"(?<!\[)\[https?://(.*?) (.*?)] (\(|\{\{C\|)\[http.*?web.archive.org/web/([0-9]+)/https?://.*?\1.*?][)}]+","{{WebCite|url=https://\\1|text=\\2|archivedate=\\4}}", before)
    if "width=100%" in before:
        before = re.sub(r"\{\{[Ss]croll[ _]?[Bb]ox(\n?\|.*?)?\n?\|width=100%", "{{ScrollBox\\1", before)
    if "simultaneous with" in before:
        before = re.sub(r"<small>\(First appeared(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
        before = re.sub(r"<small>\(First mentioned(, simultaneous with (.*?))?\)</small>", "{{1st|\\2}}", before)
    if "w:c:" in before.lower() or "wikia:c" in before.lower():
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?)]?]? (on|at) (the )?[^\n]*?([Ww]|Wikia):c:[^\n|\]]*?\|(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\9|\\4|\\5}}", before)
        before = re.sub(r"\*'*\[\[:?([Ww]|Wikia):c:(www\.)?([^\n|\]]*?):([^\n|\]]*?)\|([^\n\]]*?) (on|at) (the )?(.*?)]](,.*?$)?","*{{Interwiki|\\3|\\8|\\4|\\5}}", before)

    if "oldversion=1" in before:
        before = re.sub(r"(\|archive(date|url)=([^|\n}{]+))(\|[^\n}{]*?)?\|oldversion=1", "|oldversion=\\3\\4", before)
        before = re.sub(r"\|oldversion=1(\|[^\n}{]*?)?(\|archive(date|url)=([^|\n}{]+))", "|oldversion=\\4\\1", before)

    if "|work=" in before:
        before = re.sub(r"\|work='*?(Slash Film|/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)'*?(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(/Film|ABC News|BBC News Online|Biography|Bleeding Cool|BoardGameGeek|British Academy of Film and Television Arts|CBS News|CNN|Comic Book Resources|ComicBook\.com|Daily Mail|Deadline Hollywood|Discogs)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(E!|Empire|Encyclopædia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(E!|Empire|Encyclopædia Britannica|Engadget|Entertainment Weekly|Esquire|Eurogamer#Digital Foundry|Eurogamer|Forbes|Game Informer|GameSpot|GamesRadar\+|Gizmodo|Good Morning America|Google Books|Hollywood.com|HuffPost)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(IGN|Inverse|Io9|Kotaku|MTV|Mashable|Merriam-Webster|Metro|Midtown Comics|NBC|Nerdist|Newsarama|PC Game[rs]|Polygon|Qidian|Qobuz|Rolling Stone|Screen Rant|Syfy|TMZ|TechRadar)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(The A\.V\. Club|The Daily Telegraph|The Guardian|The Hollywood Reporter|The Huffington Post|The Independent|The New York Times|The New Yorker|The Times|The Verge|The Washington Post|Time|TIME|USA Today|Universal Music Group)( \(.*?\))?\|.*?]]'*", "", before)
        before = re.sub(r"\|work='*?(TheForce\.net|Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)'*(\|.*?)?}}", "\\2}}", before)
        before = re.sub(r"\|work='*?\[\[Wikipedia:(Valnet#Collider|Valnet#Screen_Rant|Vanity Fair|Variety|VentureBeat|Wired|WIRED|Yahoo)( \(.*?\))?\|.*?]]'*", "", before)

    return re.sub(r"(\{\{[A-z0-9 _]+\|.*?\|(.*?) \(.*?\))\|\2}}", "\\1}}", before)


def handle_top_title(before: str, target: str):
    x, _, y = target.replace("/Legends", "").replace("/Canon", "").partition(" (")
    for z in ["{{PAGENAME}}", x, target]:
        for i in ["|", "}"]:
            before = before.replace(f"|title=''{z}''{i}", f"|italics=1{i}")
            if f"Otheruses|title={z}" in before:
                before = re.sub(r"(\{\{Top.*?)\|title=" + z + r"(\|.*?)?}}", "\\1\\2", before)
            else:
                before = before.replace(f"|title={z}{i}", f"{i}")
    if y:
        y = y.replace(")", "").strip()
        if f"|title2=''{y}''" in before:
            before = before.replace(f"|title2=''{y}''", "|italics2=1")
        elif f"|title2={y}" in before:
            before = before.replace(f"|title2={y}", "")
    return before
