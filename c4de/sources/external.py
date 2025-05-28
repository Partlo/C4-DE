import re

from c4de.sources.domain import Item, ItemId


SUBDOMAINS = ["books", "comicstore", "shop", "digital", "squadbuilder", "comicvine", "cargobay"]
SOLICITS = ["ign.com", "aiptcomics", "gamesradar", "cbr.com", "newsarama", "bleedingcool"]
PRODUCT_DOMAINS = ["phrcomics", "advancedgraphics", "advancedgraphics.com", "blacksabercomics", "comicselitecomics",
                   "inningmoves", "eastsidecomicsdiscogs.com", "blackwells.co.uk", "birdcitycomics", "bigtimecollectibles",
                   "comiccollectorlive", "comics\.org", "phrcomics", "the616comics", "thecomiccornerstore", "thecomicmint",
                   "universal-music.de", "unknowncomicbooks", "frankiescomics", "geekgusher", "hachettebookgroup",
                   "jedi-bibliothek", "kiddinx-shop", "lizzie.audio", "luxor.cz", "midtowncomics", "mikemayhewstudio"]
PRODUCTS = ["LEGOWeb", "Marvel", "DarkHorse", "IDW", "Penguin", "FantasyFlightGames", "AtomicMassGames", "UnlimitedWeb"]
PRODUCT_CHECKS = {
    "AtomicMassGames": {"S": ["character/"], "E": []},
    "FantasyFlightGames": {"S": [], "E": ["-showcase"]}
}
COMMERCIAL_TO_BE_REMOVED = ["Amazon", "Previews"]


def prepare_official_link(o: Item):
    if o.full_url:
        ad = f"|archivedate={o.archivedate}" if o.archivedate else ""
        if "web.archive" in o.extra:
            x = re.search("web/([0-9]+)/", o.extra)
            if x:
                ad = f"|archivedate={x.group(1)}"
                o.extra = re.sub("\{\{C\|\[http.*?web\.archive\.org/.*?}}", "", o.extra)
        return "Official", f"{{{{OfficialSite|url={o.full_url}{ad}}}}}"
    else:
        return "Official", o.original.replace("WebCite", "OfficialSite")


def prepare_basic_url(o: Item):
    if o.original and re.search("official .*?(site|homepage|page)", o.original.lower()):
        return prepare_official_link(o)
    elif o.full_url:
        ad = f"|archivedate={o.archivedate}" if o.archivedate else ""
        u = o.full_url if o.full_url.startswith("http") else f"https://{o.full_url}"
        return "Basic", f"{{{{WebCite|url={u}|text={o.text}{ad}}}}} {o.extra}".strip()
    else:
        return "Basic", o.original


def is_product_page(u: str):
    return ("/product/" in u or "/products/" in u or "/previews" in u or "/preview.php" in u or "/themes/star-wars" in u or
            u.startswith("profile/profile.php") or
            u.startswith("book/") or
            u.startswith("books/") or
            u.startswith("product/") or
            u.startswith("products/") or
            u.startswith("comics/")) and "subdomain=news" not in u


def is_official_product_page(o: Item, real):
    if o and real and _is_official_product_page(o):
        o.mode = "Official"
        return True
    return False


def _is_official_product_page(o: Item):
    if o.url and o.url.startswith("games/"):
        return o.template in ["SW", "LucasArts"]
    elif o.url and o.url.startswith("games-apps/"):
        return o.template in ["SW"]
    elif o.url and o.template == "LucasArts":
        return o.url.startswith("static/") or o.url.startswith("products/")
    return False


def is_publisher(d: ItemId, o: Item):
    if o.template in PRODUCT_CHECKS and o.url and (any(o.url.lower().endswith(s) for s in PRODUCT_CHECKS[o.template]["E"]) or
                                                   any(o.url.lower().startswith(s) for s in PRODUCT_CHECKS[o.template]["S"])):
        return True
    if o.template in PRODUCTS and o.url and is_product_page(o.url.lower()):
        return True
    return False


def is_commercial(o: Item):
    if o.template in PRODUCT_CHECKS and o.url and (any(o.url.lower().endswith(s) for s in PRODUCT_CHECKS[o.template]["E"]) or
                                                   any(o.url.lower().startswith(s) for s in PRODUCT_CHECKS[o.template]["S"])):
        return True
    if o.template in PRODUCTS and o.url and is_product_page(o.url.lower()):
        return True
    if "subdomain=" in o.original and any(f"subdomain={s}" in o.original for s in SUBDOMAINS):
        return True
    if o.template == "SWArchive" and o.url and "/downloads" in o.original:
        return True
    if o.template == "WebCite" and o.url:
        if "/product/" in o.url or "/products/" in o.url or "/collections/" in o.url:
            return True
        if any(f"{s}." in o.url for s in PRODUCT_DOMAINS):
            return True
        if "-solicitations" in o.url and any(s in o.url for s in SOLICITS):
            return True
    return False


TEMPLATE_ORDERING = {
    "Disney": 9,
    "FantasyFlightGames": 10,
    "AtomicMassGames": 11,
    "Asmodee": 12,
}


def determine_link_order(mode, o: Item, x):
    if not o:
        return -1, None, x
    elif o.master_page == "Web/Repost":
        return 0.9, o.date, x
    elif o.publisher_listing or o.master_page in ["Web/Target", "Web/Publisher"]:
        z = 0 + (TEMPLATE_ORDERING.get(o.template, 100) / 1000)
        if o.index:
            z += (0.4 if o.template and o.template.startswith("SW") else 0.5) + (o.index / 1000000)
        return z, o.date, x
    elif o.template == "SW" and o.url and o.url.startswith("series/"):
        return 0, o.date, x
    elif mode == "Official":
        return 1.1, o.date, x
    elif mode == "Bio":
        return 1.2, o.date, x
    elif mode == "Profile":
        return 2, o.date, x
    elif mode == "Publisher":
        return 3 + (TEMPLATE_ORDERING.get(o.template, 100) / 1000), o.date, x
    elif mode == "Commercial":
        return 3.2, o.date, x
    elif o.template == "WP":
        return 4.1, o.date, x
    elif mode == "Interwiki" or o.template in ["MobyGames", "BFICite", "BGG", "LCCN", "EndorExpress"]:
        return 4.2, o.date, x
    elif o.template in ["SW", "SWArchive", "Blog", "OfficialBlog", "SWBoards"]:
        return 5.1, o.date, x
    elif o.mode == "Social" and not o.date:
        return 5.2, o.date, x
    else:
        return 5.3, o.date, x


DOMAINS = ["paninishop.de", "prhcomics.com", "music.apple.com", "audible.com", "shop.deagostini", "penguin.com"]


def is_external_link(d: ItemId, o: Item, unknown):
    if not d and o.mode == "Basic":
        if any(o.url and u in o.url for u in DOMAINS):
            o.publisher_listing = True
        unknown.append(o)
        return True
    elif d and d.master.template and "ToyCite" in d.master.template:
        return False
    elif not d and o.original.replace("*", "").startswith("[http"):
        return True
    elif "isprofile=" in o.original:
        o.mode = "Profile"
        return True
    elif not d and o.url and any(o.url.startswith(f"{s}/") for s in ["people", "person", "leadership", "our-team", "bio", "news/contributor"]):
        o.mode = "Bio"
        return True
    elif (o.mode == "Commercial" or o.mode == "Publisher" or o.mode == "Web") and any(x in o.original.lower() for x in ["authors/", "author/", "comics/creators", "book-author"]):
        o.mode = "Profile" if o.template in ["SW", "SWArchive"] else ("Commercial" if o.mode == "Web" else o.mode)
        return True
    elif o.template == "YouTube" and re.search("YouTube\|channel(name)?=[^|}\n]+\|channel(name)?=[^|}\n]+}}", o.original) and "video=" not in o.original:
        o.mode = "Profile"
        return True
    elif d and d.master.external:
        o.mode = "Found-External"
        return True
    elif o.template == "TORweb" and "subdomain=forums" in o.original:
        o.mode = "External"
        return True
    elif o.template and o.url and o.template.startswith("SW") and ("/soundboards" in o.url or o.url.startswith("qa/")):
        o.mode = "External"
        return True
    elif "Folio" not in o.original and o.url and ("images-cdn" in o.url or (("subdomain=dmedmedia" in o.original or "subdomain=press" in o.original) and "news/" not in o.original)):
        o.mode = "CDN"
        return True
    elif o.mode == "Publisher" or is_publisher(d, o):
        o.mode = "Publisher"
        return True
    elif is_commercial(o):
        o.mode = "Commercial"
        return True
    elif o.template == "Blog" and "listing=true" in o.original:
        o.mode = "Profile"
        return True
    elif o.mode == "Social":
        if "||" in o.original or "| |" in o.original or o.template == "LinkedIn":
            o.mode = "Profile"
        elif o.template == "ArtStation" and "artwork/" not in o.original:
            o.mode = "Profile"
        elif o.template == "Twitch" and "video=" not in o.original:
            o.mode = "Profile"
        return True
    elif o.mode in ["External", "Interwiki", "Publisher", "Commercial", "Profile"]:
        if o.template == "MobyGames":
            o.override_date = "Target"
            o.date = "Target"
        return True
