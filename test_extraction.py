import sys
import traceback
from datetime import datetime

from pywikibot import Site, Page, handle_args, pagegenerators, showDiff, input_choice

from c4de.sources.analysis import analyze_target_page, build_new_text
from c4de.sources.engine import load_full_sources, load_full_appearances, load_remap, build_template_types


def analyze(*args):
    gen_factory = pagegenerators.GeneratorFactory()
    for arg in handle_args(*args):
        print(arg)
        gen_factory.handle_arg(arg)
    gen_factory.site.login(user="C4-DE Bot")

    log = False
    start = datetime.now()
    types = build_template_types(gen_factory.site)
    appearances = load_full_appearances(gen_factory.site, types, log)
    sources = load_full_sources(gen_factory.site, types, log)
    remap = load_remap(gen_factory.site)
    duration = datetime.now() - start
    print(f"Loaded {len(appearances.unique)} appearances and {len(sources.unique)} sources in {duration.seconds} seconds")

    include_date = any("date:true" in s.lower() for s in args[0])
    save = any("save:true" in s.lower() for s in args[0])
    s = [s.split(":", 1)[1] for s in args[0] if "skipto:" in s.lower()]
    start_skip = s[0] if s else None

    gen = pagegenerators.PreloadingGenerator(gen_factory.getCombinedGenerator(), groupsize=50)

    i = 0
    x = True
    always = False
    found = False
    message = "Source Engine analysis of Appearances, Sources and references"
    for page in gen:
        if i % 100 == 0:
            print(i, page.title())
        i += 1
        if start_skip and not found:
            if page.title() == start_skip.replace("_", " "):
                found = True
            else:
                continue
        try:
            old_text = page.get()
            text = build_new_text(gen_factory.site, page, types, appearances, sources, remap, include_date=include_date, log=False,
                                  handle_references=True)

            if text == old_text:
                continue

            if always:
                page.put(text, message)
                continue

            showDiff(old_text, text, context=1)

            choice = input_choice(
                f'Do you want to accept these changes to {page.title()}?',
                [('Yes', 'y'), ('No', 'n'), ('All', 'a'), ('Quit', 'q')],
                default='N')
            if choice == 'q':
                break
            if choice == 'y':
                page.put(text, message)
            if choice == 'a':
                always = True
            else:
                continue
        except Exception as e:
            traceback.print_exc()
            print(e)


if __name__ == "__main__":
    analyze(sys.argv)
