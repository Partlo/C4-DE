import codecs
import re
from datetime import datetime

from c4de.sources.media import MEDIA_STRUCTURE, prepare_media_infobox_and_intro
from c4de.sources.parsing import build_initial_components, build_page_components, build_media_page_components
from pywikibot import Page, Category, showDiff

from c4de.sources.analysis import analyze_section_results
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, SectionComponents, FinishedSection, \
    NewComponents
from c4de.common import error_log, fix_redirects, do_final_replacements, sort_top_template


def build_section_from_pieces(section: SectionComponents, items: FinishedSection, log, media_cat):
    if log and items.text:
        print(f"Creating {items.name} section with {items.rows} / {len(items.text.splitlines())} items")

    pieces = [items.name] if items.text else []
    if section.before:
        pieces.insert(0, "")
        pieces.insert(0, section.before)
    if items.rows >= 20 and not any("{{scroll" in i.lower() for i in section.preceding):
        pieces.append("{{Scroll_box|content=")

    pieces += section.preceding
    added_media_cat = False
    if media_cat and items.text:
        pieces.append(media_cat)
        added_media_cat = True

    if items.text:
        pieces.append(items.text)
    if section.trailing:
        pieces.append("")
        pieces += section.trailing
    diff = 0
    for s in pieces:
        diff += s.count("{{")
        diff -= s.count("}}")
    if diff > 0:
        pieces.append("}}")
    pieces.append("")
    pieces.append(section.after)
    return do_final_replacements("\n".join(pieces).strip() + "\n\n", True), added_media_cat


def check_for_media_cat(section: SectionComponents):
    return any("{{mediacat" in i.lower() or "{{imagecat" in i.lower() for i in section.preceding) or \
           "{{mediacat" in section.after.lower() or "{{imagecat" in section.after.lower()


def find_media_categories(page: Page):
    cc = page.title().replace("/Legends", "")
    lc = f"{page.title()[0].lower()}{cc[1:]}"
    image_cat = ""
    audio_cat = ""
    for t in ["of", "of the", "from", "from the"]:
        if not image_cat:
            if Category(page.site, f"Category:Images {t} {cc}").exists():
                image_cat = f"|imagecat=Images {t} {cc}"
            elif Category(page.site, f"Category:Images {t} {lc}").exists():
                image_cat = f"|imagecat=Images {t} {lc}"
            if Category(page.site, f"Category:Images {t} {cc}s").exists():
                image_cat = f"|imagecat=Images {t} {cc}s"
            elif Category(page.site, f"Category:Images {t} {lc}s").exists():
                image_cat = f"|imagecat=Images {t} {lc}s"
        if not audio_cat:
            if Category(page.site, f"Category:Audio files {t} {cc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}"
            if Category(page.site, f"Category:Audio files {t} {lc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}"
            if Category(page.site, f"Category:Audio files {t} {cc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}s"
            if Category(page.site, f"Category:Audio files {t} {lc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}s"
    return image_cat, audio_cat


def sort_categories(text, namespace_id):
    if namespace_id == 6:
        return text
    final = []
    categories = []
    related_cats = []
    rc_count = 0
    for line in text.splitlines():
        if "{{relatedcategories" in line.lower():
            rc_count += line.count("{")
            related_cats.append(line)
        elif rc_count > 0:
            related_cats.append(line)
            rc_count += line.count("{")
            rc_count -= line.count("}")
        elif line.strip().lower().startswith("[[category:"):
            categories.append(line)
        else:
            final.append(line)

    final += sorted(categories, key=lambda a: a.lower().replace("]", "").replace("_", " ").split("|")[0])
    if related_cats:
        final.append("")
        final += related_cats
    x = "\n".join(final).replace("|\n[[Category:", "|[[Category:q")
    x = re.sub("(\[\[Category:.*?)(\|.*?]])\n\\1]]", "\\1\\2", x)
    x = re.sub("(\[\[Category:.*?)]]\n\\1(\|.*?]])", "\\1\\2", x)
    return x


def build_final_text(page: Page, results: PageComponents, disambigs: list, remap: dict, redirects: dict,
                     components: NewComponents, log: bool):
    # now = datetime.now()
    pieces = [sort_top_template(l) if "{{top" in l.lower() else l for l in results.before.strip().splitlines()]
    pieces.append("")

    if "{{mediacat" in results.final.lower() or "{{imagecat" in results.final.lower():
        media_cat = None
    elif any(check_for_media_cat(s) for s in [results.apps, results.nca, results.src, results.ncs]):
        media_cat = None
    else:
        ic, ac = find_media_categories(page)
        media_cat = f"{{{{Mediacat{ic}{ac}}}}}" if (ic or ac) else None
    media_cat = ''

    section = sorted([components.nca, components.apps, components.ncs, components.src], key=lambda a: a.rows)[-1]
    mc_section_name = section.name if section.rows > 3 else None

    if components.apps.text or results.apps.has_text():
        t, added_media_cat = build_section_from_pieces(results.apps, components.apps, log, media_cat if mc_section_name == components.apps.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if components.nca.text or results.nca.has_text():
        t, added_media_cat = build_section_from_pieces(results.nca, components.nca, log, media_cat if mc_section_name == components.nca.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if components.src.text or results.src.has_text():
        t, added_media_cat = build_section_from_pieces(results.src, components.src, log, media_cat if mc_section_name == components.src.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)
    if components.ncs.text or results.ncs.has_text():
        t, added_media_cat = build_section_from_pieces(results.ncs, components.ncs, log, media_cat if mc_section_name == components.ncs.name else None)
        if added_media_cat:
            media_cat = None
        pieces.append(t)

    if "<ref" in results.before and "{{reflist" not in results.original.lower():
        if media_cat:
            pieces.append("==Notes and references==\n" + media_cat + "\n{{Reflist}}\n\n")
        else:
            pieces.append("==Notes and references==\n{{Reflist}}\n\n")

    if components.links.text or results.links.has_text():
        pieces.append("")
        t, added_media_cat = build_section_from_pieces(results.links, components.links, log, None)
        if results.final and "Notes and references" in results.final:
            snip = re.search("(==Notes and references==\n.*?\{\{[Rr]eflist.*?\n\n*)", results.final)
            if snip:
                results.final = results.final.replace(snip.group(1), "")
                pieces.append(f"{snip.group(1)}\n\n")
        pieces.append(t)

    return final_steps(page, results, components, pieces, disambigs, remap, redirects, media_cat)


def final_steps(page: Page, results: PageComponents, components: NewComponents, pieces: list, disambigs: list,
                remap: dict, redirects: dict, media_cat):
    for i in components.navs:
        pieces.append(i)
    if components.navs:
        pieces.append("")

    if results.final:
        pieces.append(build_final(results.final, media_cat, results.real))

    new_txt = sort_categories("\n".join(pieces), page.namespace().id)
    if results.canon and "/Legends" in new_txt:
        new_txt = handle_legends_links(new_txt, page.title())

    new_txt = re.sub("(\{\{DEFAULTSORT:.*?}})\n\n+\[\[[Cc]ategory", "\\1\n[[Category", new_txt)
    new_txt = re.sub("(?<![\n=}])\n==", "\n\n==", re.sub("\n\n+", "\n\n", new_txt)).strip()
    new_txt = re.sub("(stub|Endgame)}}\n==", "\\1}}\n\n==", new_txt)
    new_txt = new_txt.replace("\n\n}}", "\n}}").replace("{{Shortstory|", "{{StoryCite|").replace("\n\n{{More", "\n{{More")

    # print(f"rebuild: {(datetime.now() - now).microseconds / 1000} microseconds")
    replace = True
    # if re.sub("<!--.*?-->", "", page.get(force=True)) != re.sub("<!--.*?-->", "", new_txt):
    if redirects:
        new_txt = fix_redirects(redirects, new_txt, "Body", remap, disambigs)
    if "{{WP}}" in new_txt:
        new_txt = new_txt.replace("{{WP}}", f"{{{{WP|{page.title()}}}}}")
    elif "{{WP|{{PAGENAME}}" in new_txt:
        new_txt = re.sub("(\{\{WP\|[^\n]+?)\{\{PAGENAME}}([^\n}]*?}})", "\\1{{subst:PAGENAME}}\\2",
                         new_txt.replace("{{WP|{{PAGENAME}}", "{{WP|{{subst:PAGENAME}}"))

    # now = datetime.now()
    t = do_final_replacements(new_txt, replace)
    # print(f"replace: {(datetime.now() - now).microseconds / 1000} microseconds")
    return t.replace("\n\n{{RelatedCategories", "\n{{RelatedCategories")


def build_media_page(page: Page, results: PageComponents, disambigs: list, remap: dict, redirects: dict,
                     appearances: FullListData, sources: FullListData, components: NewComponents, log: bool):
    pieces = prepare_media_infobox_and_intro(page, results, appearances, sources)
    pieces.append("")

    media_cat = None
    otx = page.get()
    for key, header_line in MEDIA_STRUCTURE.items():
        if key == "References":
            if key in results.sections:
                pieces.append("\n".join(results.sections[key].build_text()))
                if "{{mediacat" in pieces[-1].lower():
                    media_cat = None
            elif "<ref" in otx and "{{reflist}}" not in otx:
                if media_cat:
                    pieces.append("==Notes and references==\n" + media_cat + "\n{{Reflist}}\n\n")
                else:
                    pieces.append("==Notes and references==\n{{Reflist}}\n\n")
            continue
        elif key == "Sources":
            if components.src.text or results.src.has_text():
                t, added_media_cat = build_section_from_pieces(results.src, components.src, log, media_cat)
                if "and references" in t:
                    print(key, t)
                if added_media_cat:
                    media_cat = None
                pieces.append(t)
            continue
        elif key == "Links":
            if components.links.text or results.links.has_text():
                pieces.append("")
                t, added_media_cat = build_section_from_pieces(results.links, components.links, log, None)
                if "and references" in t:
                    print(key, t)
                if added_media_cat:
                    media_cat = None
                pieces.append(t)
            continue
        elif key not in results.sections:
            continue

        # TODO: mediacat
        section = results.sections[key]
        if log:
            print(f"Creating {key} section with {len(section.lines)} lines and {len(section.subsections)} / {len(section.other)} subsections")

        lines = section.build_text(header_line)
        for subheader, subsection in section.subsections.items():
            print(key, subheader, len(subsection.lines))
            lines += subsection.build_text(subheader)
        for other in section.other:
            lines += other.build_text()

        lines.append("")

        text = "\n".join(lines)
        text = fix_redirects(redirects, text, key, remap, disambigs, overwrite=key == "Appearances")

        pieces.append(do_final_replacements(text, True))
        pieces.append("")

    return final_steps(page, results, components, pieces, disambigs, remap, {}, media_cat)


def handle_legends_links(text, title):
    body, header, bts = text.partition("==Behind the scenes==")
    if "/Legends" in body:
        new_lines = []
        for line in body.splitlines():
            if "/Legends" in line:
                if not ("{{otheruses" in line.lower() or "{{top" in line.lower() or "{{youmay" in line.lower()):
                    x = re.findall("\[\[(.*?)/Legends\|", line)
                    for i in x:
                        if i != title:
                            line = line.replace(f"[[{i}/Legends", f"[[{i}")
            new_lines.append(line)
        body = "\n".join(new_lines)
    return f"{body}{header}{bts}"


def build_final(final, media_cat, real):
    if not real and "RelatedCategories" not in final and re.search("\n\[\[[Cc]ategory:.*?\| ]]", final):
        cats = []
        lines = []
        regular = 0
        for l in final.splitlines():
            x = re.search("^(\[\[[Cc]ategory:.*?)\| ]]", l)
            if x:
                cats.append("|" + x.group(1) + "]]")
            else:
                if "category:" in l.lower():
                    regular += 1
                lines.append(l)

        if cats and regular == 0:
            print("Unable to move categories to RelatedCategories, as no categories would be left")
        elif cats:
            related = "\n".join(["{{RelatedCategories", *cats, "}}"])
            final = "\n".join(lines).strip() + "\n" + related

    final = re.sub("\|\n+\[\[Category:", "|[[Category:", final)

    if "==\n" in final and media_cat:
        z = final.split("==\n", 1)
        return f"{z[0]}==\n{media_cat}\n{z[1]}"
    elif media_cat:
        return media_cat + "\n" + final
    else:
        return final


def build_text(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
               sources: FullListData, remap: dict, include_date: bool, checked: list, log=True, use_index=True,
               collapse_audiobooks=True, manual: str = None, extra=None):
    text, redirects, results = build_initial_components(target, disambigs, infoboxes, manual)
    if results.media:
        unknown = build_media_page_components(target, text, redirects, results, types, disambigs, appearances, sources,
                                              remap, log)
    else:
        unknown = build_page_components(target, text, redirects, results, types, disambigs, appearances, sources, remap,
                                        log=log, extra=extra)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    new_components, dates, unknown_items, analysis = analyze_section_results(
        target, results, disambigs, appearances, sources, remap, use_index, include_date, collapse_audiobooks, checked, log)

    if results.media:
        new_txt = build_media_page(target, results, disambigs, remap, redirects, appearances, sources, new_components, log)
    else:
        new_txt = build_final_text(target, results, disambigs, remap, redirects, new_components, log)
    return new_txt, analysis, dates, unknown, unknown_items


def build_new_text(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                   sources: FullListData, remap: dict, include_date: bool, checked: list, log=True, use_index=True,
                   collapse_audiobooks=True, manual: str = None, extra=None):
    new_txt, analysis, dates, unknown, unknown_items = build_text(
        target, infoboxes, types, disambigs, appearances, sources, remap, include_date, checked, log, use_index,
        collapse_audiobooks, manual, extra)

    record_local_unknown(unknown, unknown_items, target)
    return new_txt


def analyze_target_page(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                        sources: FullListData, remap: dict, save: bool, include_date: bool,
                        log=True, use_index=True, collapse_audiobooks=True):
    new_txt, analysis, dates, unknown, unknown_items = build_text(
        target, infoboxes, types, disambigs, appearances, sources, remap, include_date, [], log, use_index,
        collapse_audiobooks)

    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    if dates:
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/new_dates.txt", mode="a", encoding="utf-8") as f:
            date_txt = []
            for d in dates:
                if d[2] == d[3]:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]}: -> {d[1].master.original}")
                else:
                    date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]} {d[3]}: -> {d[1].master.original}")
            f.writelines("\n" + "\n".join(date_txt))

    if save and new_txt != target.get(force=True):
        if "�" in new_txt:
            error_log(f"Unexpected characters found in changes")
            error_log(showDiff(target.get(force=True), new_txt))
        z1 = re.sub("<!--.*?-->", "", new_txt)
        z2 = re.sub("<!--.*?-->", "", target.get(force=True)).replace("text=SWCC 2022", "text=SWCA 2022")
        match = z1 == z2
        target.put(new_txt, "Source Engine analysis of Appearances, Sources and references", botflag=match, force=True)

    results = []
    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/unknown.txt", mode="a",
                     encoding="utf-8") as f:
        if len(analysis.abridged) == 1:
            results.append(f"1 abridged audiobook was missing from Appearances: {analysis.abridged[0]}")
        elif analysis.abridged:
            results.append(f"{len(analysis.abridged)} abridged audiobooks were missing from Appearances:")
            results.append("\n".join(f"- {a}" for a in analysis.abridged))

        if analysis.mismatch and target.namespace().id == 0:
            c, d = ("Canon", "Legends") if analysis.canon else ("Legends", "Canon")
            results.append(f"The following {len(analysis.mismatch)} entries are marked as {d} in the Masterlist, but are listed on this {c} article: (experimental feature)")
            results.append("\n".join(f"- `{a.master.original}`" for a in analysis.mismatch))

        # if unknown_items.links:
        #     results.append("Could not identify unknown External Links:")
        #     z = [o.original if isinstance(o, Item) else o for o in unknown_items.links]
        #     results.append("\n".join(f"- `{i}`" for i in z))
        #     f.writelines("\n" + "\n".join(z))

        if unknown_items.apps:
            results.append("Could not identify unknown appearances:")
            record_unknown(unknown_items.apps, results, f, target)

        if unknown_items.src:
            results.append("Could not identify unknown sources:")
            record_unknown(unknown_items.src, results, f, target)

    final_results = []
    for i in results:
        if len(i) > 500:
            x = i.split("\n")
            for z in x:
                if len(z) > 500:
                    final_results += [z[o:o+500] for o in range(0, len(z), 500)]
                else:
                    final_results.append(z)
        else:
            final_results.append(i)

    return results


def record_local_unknown(unknown, unknown_items, target: Page):
    if unknown or unknown_items.found():
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/sources/unknown.txt", mode="a",
                         encoding="utf-8") as f:
            for x in unknown:
                f.write(u'%s\t%s\n' % (x, target.title()))
            z = set()
            for o in [*unknown_items.apps, *unknown_items.src]:
                z.add(o.original if isinstance(o, Item) else o)
            for o in unknown_items.links:
                z.add(f"Links: {o.original if isinstance(o, Item) else o}")
            for o in unknown_items.final_items:
                if isinstance(o, ItemId) and o.current.original not in z:
                    z.add(f"No Date: {o.current.original}")
                elif not isinstance(o, ItemId) and o not in z:
                    z.add(f"No Date: {o}")
            if z:
                f.writelines("\n".join([f"{o}\t{target.title()}" for o in z]) + "\n")


def record_unknown(unknown, results, f, target):
    r = ""
    for o in unknown:
        x = f"- `{o.original if isinstance(o, Item) else o}`"
        if len(r) + len(x) > 500:
            results.append(r)
            r = f"{x}"
        else:
            r = f"{r}\n{x}"
        if (o.original if isinstance(o, Item) else o).startswith("*"):
            print(target.title(), o.original)
    if r:
        results.append(r)
    f.writelines("\n" + "\n".join([(o.original if isinstance(o, Item) else o) for o in unknown]))
