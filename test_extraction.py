import re
import sys
import traceback
from datetime import datetime

from pywikibot import Site, Page, handle_args, pagegenerators, showDiff, input_choice

from c4de.sources.analysis import build_new_text
from c4de.sources.engine import load_full_sources, load_full_appearances, load_remap, build_template_types
from c4de.sources.infoboxer import list_all_infoboxes


STATUS = ["Category:Wookieepedia Featured articles", "Category:Wookieepedia Good articles", "Category:Wookieepedia Comprehensive articles"]


def analyze(*args):
    gen_factory = pagegenerators.GeneratorFactory()
    log = False
    for arg in handle_args(*args):
        if arg.startswith("-page:"):
            log = True
        gen_factory.handle_arg(arg)
    gen_factory.site.login(user="C4-DE Bot")

    start = datetime.now()
    types = build_template_types(gen_factory.site)
    appearances = load_full_appearances(gen_factory.site, types, log)
    sources = load_full_sources(gen_factory.site, types, log)
    remap = load_remap(gen_factory.site)
    infoboxes = list_all_infoboxes(gen_factory.site)
    duration = datetime.now() - start
    print(f"Loaded {len(appearances.unique)} appearances and {len(sources.unique)} sources in {duration.seconds} seconds")

    include_date = any("date:true" in s.lower() for s in args[0])
    save = any("save:true" in s.lower() for s in args[0])
    s = [s.split(":", 1)[1] for s in args[0] if "skipto:" in s.lower()]
    start_skip = s[0] if s else None

    s = [s.split(":", 1)[1] for s in args[0] if "stopat:" in s.lower()]
    end_skip = s[0] if s else None

    gen = pagegenerators.PreloadingGenerator(gen_factory.getCombinedGenerator(), groupsize=50)

    i = -1
    x = True
    always = False
    always_comment = False
    found = False
    message = "Source Engine analysis of Appearances, Sources and references"
    for page in gen:
        i += 1
        z = str(i / 114806 * 100).zfill(10)[:6]
        if i % 100 == 0:
            print(f"{i} -> {z} -> {page.title()}")
        if start_skip and not found:
            if page.title() >= start_skip.replace("_", " "):
                print(page.title())
                found = True
            else:
                continue
        elif end_skip:
            if page.title() <= end_skip.replace("_", " "):
                print(page.title())
            else:
                continue
        try:
            bf = True
            if any(c.title() in STATUS for c in page.categories()):
                bf = False

            old_text = page.get(force=True)
            text = build_new_text(page, infoboxes, types, appearances, sources, remap,
                                  include_date=include_date, log=log, handle_references=True)

            if text == old_text:
                print(f"{i} -> {z} -> No changes found for {page.title()}")
                continue
            z1 = re.sub("(\|[A-z _0-9]+=.*?(\n.+?)?)}}(\n((The |A )?'''|\{\{Quote))", "\\1\n}}\\3",
                        re.sub("(\|.*?=)\}\}\n", "\\1\n}}\n", re.sub("<!--.*?-->", "", text).replace("{{!}}", "|")))
            z2 = re.sub("(\|[A-z _0-9]+=.*?(\n.+?)?)}}(\n((The |A )?'''|\{\{Quote))", "\\1\n}}\\3",
                        re.sub("(\|.*?=)\}\}\n", "\\1\n}}\n", re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", re.sub("<!--.*?-->", "", old_text).replace("text=SWCC 2022", "text=SWCA 2022").replace("{{!}}", "|"))))
            z2 = re.sub("(\{\{1st.*?\|\[\[(.*?) \(.*?audiobook\)\|)''\\2'' (.*?audiobook)", "\\1\\3", z2)

            match = z1.replace("–", "&ndash;").replace("—", "&mdash;").replace("|nolive=1", "").replace("'' unabridged audiobook]]", "'' audiobook]]").replace("'' abridged audiobook]]", "'' audiobook]]") == \
                    z2.replace("–", "&ndash;").replace("—", "&mdash;").replace("|nolive=1", "").replace("'' unabridged audiobook]]", "'' audiobook]]").replace("'' abridged audiobook]]", "'' audiobook]]")

            override = old_text.count("nterlang") > text.count("nterlang") or old_text.count("ategory:") > text.count("ategory:")
            if not override and (always or (match and always_comment)):
                page.put(text, message, botflag=match or bf)
                continue

            # showDiff(old_text, text, context=1)
            showDiff(z2, z1, context=1)

            c = '(comment-only) ' if match else ''
            choice = input_choice(
                f'Do you want to accept these {c}changes to {page.title()}?',
                [('Yes', 'y'), ('No', 'n'), ('All', 'a'), ('B', 'b'), ('Quit', 'q')],
                default='N')
            if choice == 'q':
                break
            if choice == 'y':
                page.put(text, message, botflag=bf)
            if choice == 'b' and match:
                page.put(text, message, botflag=bf)
                always_comment = True
            if choice == 'a':
                page.put(text, message, botflag=bf)
                always = True
            else:
                continue
        except Exception as e:
            traceback.print_exc()
            print(e)


if __name__ == "__main__":
    analyze(sys.argv)
