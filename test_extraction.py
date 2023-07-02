import sys
from datetime import datetime

from pywikibot import Site, Page, handle_args, pagegenerators

from c4de.sources.analysis import analyze_target_page
from c4de.sources.engine import load_full_sources, load_full_appearances, load_remap


def analyze(*args):
    gen_factory = pagegenerators.GeneratorFactory()
    for arg in handle_args(*args):
        print(arg)
        gen_factory.handle_arg(arg)
    gen_factory.site.login(user="C4-DE Bot")

    log = False
    start = datetime.now()
    appearances = load_full_appearances(gen_factory.site, log)
    sources = load_full_sources(gen_factory.site, log)
    remap = load_remap(gen_factory.site)
    duration = datetime.now() - start
    print(f"Loaded {len(appearances.unique)} appearances and {len(sources.unique)} sources in {duration.seconds} seconds")

    include_date = False
    save = any("save:true" in s.lower() for s in args[0])

    gen = pagegenerators.PreloadingGenerator(gen_factory.getCombinedGenerator(), groupsize=50)

    i = 0
    x = True
    for page in gen:
        # if page.title() == "Graveyard of Lost Ships":
        #     x = False
        # if x:
        #     continue

        if i % 100 == 0:
            print(i, page.title())
        i += 1
        try:
            analyze_target_page(gen_factory.site, page, appearances, sources, remap, save, include_date, log=False)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    analyze(sys.argv)
