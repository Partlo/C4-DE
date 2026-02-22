import codecs
import warnings
warnings.simplefilter("ignore", SyntaxWarning)

import re
import sys
import traceback
import time
from datetime import datetime

from c4de.sources.domain import Item, ItemId
from pywikibot import Site, Page, handle_args, pagegenerators, showDiff, input_choice, Timestamp
from pywikibot.exceptions import APIMWError

from c4de.sources.build import build_new_text, STATUS
from c4de.sources.engine import load_full_sources, load_full_appearances, load_remap, load_template_types, \
    load_auto_categories
from c4de.sources.infoboxer import load_infoboxes


def to_duration(now: datetime):
    d = datetime.now() - now
    return f"{d.total_seconds()}"


def remove_the(x):
    return x[(4 if x.startswith("The ") else 0):]


def flatten(x):
    z = (x.replace("ncomplete list", "ncompleteList").replace("ncomplete_list", "ncompleteList")
         .replace("–", "&ndash;").replace("—", "&mdash;").replace("theruses|title=", "theruses|")
         .replace("|nolive=1", "").replace("|from=1", "").replace("Journal|", "JournalCite|").replace("{{IU_media", "{{InUniverseMedia")
         .replace("FFGweb", "FantasyFlightGames").replace("AMGweb", "AtomicMassGames").replace("TOMCite", "GermanFanCite")
         .replace("{{Scroll_box", "{{ScrollBox").replace("{{Scroll box", "{{ScrollBox").replace("{{Title_infobox", "{{TitlePosition")
         .replace("{{Canon Imperial Era}}", "{{CanonImperialEraNav}}").replace("{{Canon_Imperial_Era}}", "{{CanonImperialEraNav}}")
         .replace("{{Republic Era}}", "{{RepublicEraNav}}").replace("{{Republic_Era}}", "{{RepublicEraNav}}")
         .replace("{{New Republic Era}}", "{{NewRepublicEraNav}}").replace("{{New_Republic_Era}}", "{{NewRepublicEraNav}}")
         .replace("'' unabridged audiobook]]", "'' audiobook]]").replace("'' abridged audiobook]]", "'' audiobook]]")
         .replace("=Collections=", "=Collected in=").replace("]]\n{{RelatedCategories", "]]\n\n{{RelatedCategories"))
    z = re.sub(r"(\{\{[A-Z][a-z]+)[ _]([A-z])([A-z _]+)([ _]?Nav)?(\n|}})", lambda a: a.group(1) + a.group(2).upper() + a.group(3) + a.group(5), z)
    z = re.sub(r"(\{\{[A-Z][a-z]+)[ _]([A-z])([A-z _]+)([ _]?Nav)?(\n|}})", lambda a: a.group(1) + a.group(2).upper() + a.group(3) + a.group(5), z)
    return re.sub(r"\{\{1stID\|.*?}}", "{{1stID}}", re.sub(r"\|title=\"(.*?)\"", "|title=\\1", re.sub("<!--.*?-->", "", z)))


def prep(text, old_text):
    z1 = re.sub(r"(\|[A-z _0-9]+=.*?(\n.+?)?)}}(\n((The |A )?'''|\{\{Quote))", "\\1\n}}\\3",
                re.sub(r"(\|.*?=)}}\n", "\\1\n}}\n", text.replace("{{!}}", "|")))
    z1 = re.sub(r"\[\[([Cc])redit]](s)?", "[[Galactic Credit Standard|\\1redit\\2]]", z1)
    z2 = re.sub(r"(\|[A-z _0-9]+=.*?(\n.+?)?)}}(\n((The |A )?'''|\{\{Quote))", "\\1\n}}\\3",
                re.sub(r"(\|.*?=)}}\n", "\\1\n}}\n",
                       re.sub(r"(\|book=[^\n}]*?)(\|story=[^\n}]*?)(\|.*?)?}}", "\\2\\1\\3}}",
                              old_text.replace("text=SWCC 2022", "text=SWCA 2022").replace("{{!}}", "|"))))
    z2 = re.sub(r"(\{\{1st.*?\|\[\[(.*?) \(.*?audiobook\)\|)''\\2'' (.*?audiobook)", "\\1\\3", z2)
    z2 = re.sub(r"\[\[([Cc])redit]](s)?", "[[Galactic Credit Standard|\\1redit\\2]]", z2)

    for ix in re.findall(r"((\{\{(BuildFalconCite|BuildR2Cite|BuildXWingCite|BustCollectionCite|DarthVaderCite|FalconCite|FigurineCite|HelmetCollectionCite|ShipsandVehiclesCite|StarshipsVehiclesCite)\|[0-9]+\|[^|\[{}]+?)(\|((?!reprint).)*?)}})", text):
        text = text.replace(ix[0], ix[1] + "}}")
        if ix[1] + "}}" in old_text:
            z1 = z1.replace(ix[0], ix[1] + "}}")
    return text, z1, z2


def analyze(*args, to_save):
    gen_factory = pagegenerators.GeneratorFactory()
    log = False
    start_on, end_on, skip_start, skip_end, redo = None, None, None, None, None
    include_date = False
    legends, canon = False, False
    always = False
    bot = True
    count = 0
    encyclopedia, ultimate, ultimate2 = [], [], []
    for arg in handle_args(*args):
        if arg.startswith("-page:"):
            log = True
        if arg.startswith("-st:"):
            _, _, start_on = arg.replace('"', '').partition("-st:")
        elif arg.startswith("-et:"):
            _, _, end_on = arg.replace('"', '').partition("-et:")
        elif arg.startswith("-s1:"):
            _, _, skip_start = arg.replace('"', '').partition("-s1:")
        elif arg.startswith("-s2:"):
            _, _, skip_end = arg.replace('"', '').partition("-s2:")
        elif arg.startswith("-redo:"):
            _, _, redo = arg.replace('"', '').partition("-redo:")
        else:
            gen_factory.handle_arg(arg.replace("::", ":"))

        if "date:true" in arg.lower():
            include_date = True
        if "legends" in arg.lower():
            legends = True
        if "canon:" in arg.lower():
            canon = True
        if "always" in arg.lower():
            always = True
        if "-bot:" in arg.lower():
            bot = False
        if "-count:" in arg.lower():
            count = int(arg.replace("-count:", ""))
    gen_factory.site.login(user="C4-DE Bot")
    if start_on:
        print(f"Starting on {start_on}")

    start = datetime.now()
    types = load_template_types(gen_factory.site)
    cats = load_auto_categories(gen_factory.site)
    appearances = load_full_appearances(gen_factory.site, types, False, log_match=False)
    sources = load_full_sources(gen_factory.site, types, False)
    remap = load_remap(gen_factory.site)
    infoboxes = load_infoboxes(gen_factory.site)
    duration = datetime.now() - start
    print(f"Loaded {len(appearances.unique)} appearances and {len(sources.unique)} sources in {duration.seconds} seconds")

    save = any("save:true" in s.lower() for s in args[0])
    passive = False

    gen = pagegenerators.PreloadingGenerator(gen_factory.getCombinedGenerator(), groupsize=50)

    ci = 50623
    li = 116357
    i = count - 1
    if any("Legends articles" in a or "C4-DE traversal" in a for a in args):
        i += ci
    # total = ci + li
    total = li
    checked = []
    processed = []
    always_comment = False
    found = False
    message = "Source Engine analysis of Appearances, Sources and references"
    media_msg = "Source Engine media page analysis and overhaul"
    since = Timestamp(2025, 5, 20)
    for page in gen:
        if page.title().startswith("Map:") or page.title() == "Forum:WPWeb:Template icons standardization":
            continue
        elif page.namespace().id == 2:
            continue
        elif page.title() in processed or page.title().startswith("List of") or page.title().startswith("Timeline of"):
            continue
        else:
            processed.append(page.title())

        i += 1
        z = str(i / total * 100).zfill(10)[:6]
        if i % 100 == 0:
            print(f"{i} -> {z}% -> {page.title()}")
        if i % 250 == 0 and i > 0 and not start_on:
            appearances = load_full_appearances(gen_factory.site, types, False, log_match=False)
            sources = load_full_sources(gen_factory.site, types, False)
            switch = Page(gen_factory.site, "User:C4-DE Bot/Kill Switch")
            if switch.exists() and "stop" in switch.get(force=True).lower():
                print("Kill switch active; stopping script")
                quit()

        if start_on:
            if remove_the(page.title()).lower() >= start_on.lower() and not page.title().startswith("Wookieepedia:"):
                print(f"Found: {page.title()}")
                start_on = None
            else:
                continue
        if end_on and page.title() > end_on.lower():
            quit()

        if skip_start and skip_end:
            if skip_start.lower() <= page.title().lower() <= skip_end.lower():
                continue
        # if legends:
        #     if not any(c.title(with_ns=False) == "Legends articles" for c in page.categories()):
        #         continue
        # elif canon:
        #     if not any(c.title(with_ns=False) == "Canon articles" for c in page.categories()):
        #         continue
        try:
            now = datetime.now()
            bf = bot
            media = False
            for c in page.categories():
                if c.title() in STATUS:
                    bf = False
                elif c.title(with_ns=False) == "Real-world media":
                    media = True

            before = page.get(force=True)
            old_text = f"{before}"
            # if "{{HelmetCollection" not in old_text and "{{ForceCollection" not in old_text:
            #     continue

            old_revision = None
            if redo and redo >= page.title(with_ns=False): #and "audiobook" in old_text:
                for r in page.revisions(total=10, content=True):
                    old_revision = r['text']
                    if r['timestamp'] < since or (r['user'] != 'C4-DE Bot'):
                        print(f"Reloaded revision {r['revid']} for {page.title()}")
                        break

            subpage = None
            extra = []
            text, subtext, u1, u2 = build_new_text(page, infoboxes, types, [], appearances, sources, cats, remap, include_date,
                                                   checked, log=log, collapse_audiobooks=True, manual=old_revision, extra=extra, keep_pages=False, redo=redo)

            if subtext:
                subpage = Page(page.site, f"{page.title()}/Sources")
                compare_text1 = re.sub(r"\{\{SourcesPage.*?}}", subtext, text)
                compare_text2 = re.sub(r"\{\{SourcesPage.*?}}", subpage.get(), old_text)
                _, z1, z2 = prep(compare_text1, compare_text2)
            else:
                text, z1, z2 = prep(text, old_text)
            dx = to_duration(now)

            if text.replace("E -->", " -->") == old_text.replace("E -->", " -->"):
                print(f"{i} -> {z} -> No changes found for {page.title()} -> {to_duration(now)} seconds")
                continue
            elif len(text) - len(old_text) == 1 and text.replace("\n", "") == old_text.replace("\n", ""):
                print(f"Skipping {page.title()}; infobox newline is only change -> {to_duration(now)} seconds")
                continue

            match = flatten(z1) == flatten(z2)

            override = old_text.count("nterlang") > text.count("nterlang") #or (old_text.count("[[Category:") + old_text.count("[[category:")) > (text.count("[[Category:") + text.count("[[category:"))
            if override:
                p = Page(gen_factory.site, f"User:Cade Calrayn/Test5")
                p.put((p.get() if p.exists() else "") + f"\n#[[{page.title()}]]")
                continue
            if not override and match and always_comment:
                page.put(text, media_msg if media else message, botflag=match or bf)
                if subpage and subtext:
                    subpage.put(subtext, media_msg if media else message, botflag=match or bf)
                continue
            # if not override:
            #     override = "RelatedCategories" in text and "RelatedCategories" not in old_text
            # if override:
            #     continue

            if passive:
                print(f"Changes found for {page.title()}")
                to_save.append(page.title())
                continue

            # showDiff(old_text, text, context=1)
            z1 = re.sub(r"\|stext=.*?(\|.*?)?}}", "\\1}}", z1).replace("Journal|", "JournalCite|").replace("=Collections=", "=Collected in=") + "\n"
            z2 = re.sub(r"\|stext=.*?(\|.*?)?}}", "\\1}}", z2).replace("Journal|", "JournalCite|").replace("=Collections=", "=Collected in=") + "\n"

            if include_date:
                showDiff(z2, z1, context=1)
            else:
                showDiff(re.sub("<!--.*?-->", "", z2), re.sub("<!--.*?-->", "", z1), context=1)
            zx = []
            for u in u1:
                print(f"Unknown: {u}")
                zx.append(u)
            for n, x in {"Appearance": u2.apps, "Source": u2.src, "Final": u2.final_items}.items():
                if x:
                    for o in x:
                        if isinstance(o, ItemId):
                            y = o.current.original
                        elif isinstance(o, Item):
                            y = o.original
                        else:
                            y = o
                        if y not in zx:
                            print(f"Unknown {n}: {y}")
                        zx.append(y)

            print(f"{page.title()} -> {dx} seconds")
            if not override and always:
                page.put(text, media_msg if media else message, botflag=match or bf)
                if subpage and subtext:
                    subpage.put(subtext, media_msg if media else message, botflag=match or bf)
                continue

            c = '(comment-only) ' if match else ''
            choice = input_choice(
                f'Do you want to accept these {c}changes to {page.title()}?',
                [('Yes', 'y'), ('No', 'n'), ('All', 'a'), ('B', 'b'), ('Quit', 'q')],
                default='N')
            if choice == 'q':
                break
            if choice == 'y':
                page.put(text, media_msg if media else message, botflag=bf, force=True)
                if subpage and subtext:
                    subpage.put(subtext, media_msg if media else message, botflag=match or bf, force=True)
            if choice == 'b' and match:
                page.put(text, media_msg if media else message, botflag=bf)
                if subpage and subtext:
                    subpage.put(subtext, media_msg if media else message, botflag=match or bf)
                always_comment = True
            if choice == 'a':
                page.put(text, media_msg if media else message, botflag=bf)
                if subpage and subtext:
                    subpage.put(subtext, media_msg if media else message, botflag=match or bf)
                always = True
            else:
                continue
        # except KeyboardInterrupt as e:
        #     quit()
        except APIMWError as e:
            print(e)
            time.sleep(30)
            continue
        except Exception as e:
            traceback.print_exc()
            print(e)


if __name__ == "__main__":
    to_save = []
    # try:
    analyze(sys.argv, to_save=to_save)
    # except KeyboardInterrupt:
    #     if to_save:
    #         with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/review.txt", mode="a", encoding="utf-8") as f:
    #             f.writelines("\n".join(to_save))
