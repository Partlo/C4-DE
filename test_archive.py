from pywikibot import Page, Site, Category, showDiff, stopme
from c4de.sources.archive import *


def task():
    site = Site()
    skip = []
    archives = {}
    types = load_template_types(site)
    data, done = {}, []
    # for c in [Category(site, "Social media citations with missing shared permanent archival links")]:
    for c in [Category(site, "Pages with missing shared permanent archival links"), *Category(site, "Unarchived URLs").subcategories()]:
        for p in c.articles():
            if p.title() in done:
                continue
            data = build_missing_and_new(p, types, archives, data, skip)
            done.append(p.title())

    to_check = build_to_check(site, data)
    to_check = {k: v for k, v in to_check.items() if v}

    current = sum(len(v) for k, v in to_check.items())
    prev = -1
    attempts = 0
    while current != prev and attempts < 5:
        prev = current
        # old_info = populate_archives(to_check, skip=True)
        old_info = populate_archives(to_check, skip=bool(attempts))
        attempts += 1
        for k, v in old_info.items():
            if v:
                for t in data:
                    if k in data[t]:
                        y = data[t].get(k, {})
                        y['value'] = v
                        data[t][k] = y
                        print(k, t, v, k in to_check.get(t, []))
                        if t in to_check and k in to_check[t]:
                            to_check[t].pop(k)
        current = sum(len(v) for k, v in to_check.items())

    add_data_to_archive(site, data, archives, True)


if __name__ == "__main__":
    try:
        task()
    finally:
        stopme()
