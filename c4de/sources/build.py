import codecs
import re
from datetime import datetime

from c4de.sources.cleanup import clear_page_numbers
from pywikibot import Page, Category, showDiff

from c4de.common import error_log, fix_redirects, do_final_replacements, sort_top_template, to_duration, \
    report_duration, MULTIPLE_ISSUE_CONVERSION
from c4de.protocols.cleanup import clean_archive_usages
from c4de.sources.analysis import analyze_section_results
from c4de.sources.determine import determine_id_for_item
from c4de.sources.domain import Item, ItemId, FullListData, PageComponents, SectionComponents, FinishedSection, \
    NewComponents, UnknownItems
from c4de.sources.extract import extract_item
from c4de.sources.index import create_index
from c4de.sources.media import MEDIA_STRUCTURE, prepare_media_infobox_and_intro
from c4de.sources.parsing import build_initial_components, build_page_sections, MASTER_STRUCTURE, build_card_text


def build_section_from_pieces(section: SectionComponents, items: FinishedSection, log, media_cat, start=False):
    if log and items.text:
        print(f"Creating {items.name} section with {items.rows} / {len(items.text.splitlines())} items")

    pieces = [items.name] if items.text else []
    if items.rows >= 20 and not any("{{scroll" in i.lower() for i in section.preceding):
        pieces.append("{{ScrollBox|content=")

    pieces += section.preceding
    added_media_cat = any("{{mediacat" in i.lower() for i in pieces)
    if not added_media_cat and media_cat and items.text:
        if start:
            pieces.insert(0, media_cat)
        else:
            pieces.append(media_cat)
        added_media_cat = True

    remove_scroll = False
    if items.rows <= 20 and any("{{scroll" in i.lower() for i in pieces):
        pieces = [ln for ln in pieces if not "{{scroll" in ln.lower()]
        remove_scroll = True

    if items.text:
        pieces.append(items.text)
    if section.trailing:
        pieces.append("")
        pieces += section.trailing
    diff = 0
    for i in range(len(pieces)):
        diff += pieces[i].count("{{")
        diff -= pieces[i].count("}}")
        if diff == -2 and remove_scroll:
            pieces[i] = re.sub("^(.*?)}}([^}]*?)$", "\\1\\2", pieces[i])
    if diff > 0:
        pieces.append("}}")
    pieces.append("")
    pieces.append(section.after)
    # return do_final_replacements("\n".join(pieces).strip() + "\n\n", True), added_media_cat
    return "\n".join(pieces).strip() + "\n\n", added_media_cat


def check_for_media_cat(section: SectionComponents):
    return any("{{mediacat" in i.lower() for i in section.preceding) or "{{mediacat" in section.after.lower()


def find_media_categories(page: Page, media, check_audio):
    cc = page.title().replace("/Legends", "")
    lc = f"{page.title()[0].lower()}{cc[1:]}"
    image_cat = ""
    audio_cat = ""
    for t in (["from", "from the"] if media else ["of", "of the"]):
        if not image_cat:
            if Category(page.site, f"Category:Images {t} {cc}").exists():
                image_cat = f"|imagecat=Images {t} {cc}"
            elif Category(page.site, f"Category:Images {t} {lc}").exists():
                image_cat = f"|imagecat=Images {t} {lc}"
            elif Category(page.site, f"Category:Images {t} {cc}s").exists():
                image_cat = f"|imagecat=Images {t} {cc}s"
            elif Category(page.site, f"Category:Images {t} {lc}s").exists():
                image_cat = f"|imagecat=Images {t} {lc}s"
        if check_audio and not audio_cat:
            if Category(page.site, f"Category:Audio files {t} {cc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}"
            elif Category(page.site, f"Category:Audio files {t} {lc}").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}"
            elif Category(page.site, f"Category:Audio files {t} {cc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {cc}s"
            elif Category(page.site, f"Category:Audio files {t} {lc}s").exists():
                audio_cat = f"|soundcat=Audio files {t} {lc}s"
    params = f"{image_cat}{audio_cat}"
    if params and media:
        params = f"|from=1{params}"
    return f"{{{{Mediacat{params}}}}}" if params else None


def matches_category(ln, categories):
    return any(f"[[{c.lower()}|" in ln or f"[[{c.lower()}]]" in ln for c in categories)


def sort_categories(pieces, namespace_id, bad_categories):
    if namespace_id == 6:
        return "\n".join(pieces)
    final = []
    categories = []
    related_cats = []
    rc_count = 0
    has_bad = False
    for line in "\n".join(pieces).splitlines():
        if "{{relatedcategories" in line.lower():
            rc_count += line.count("{")
            related_cats.append(line)
        elif rc_count > 0:
            related_cats.append(line)
            rc_count += line.count("{")
            rc_count -= line.count("}")
        elif line.strip().lower().startswith("[[category:"):
            if bad_categories and matches_category(line.strip().lower(), bad_categories):
                categories.append(f"{line}{{{{InvalidCategory}}}}")
                has_bad = True
            else:
                categories.append(line)
        else:
            final.append(line)

    if has_bad and len(categories) == 1:
        categories = [c.replace("{{InvalidCategory}}", "") for c in categories]

    final += sorted(categories, key=lambda a: a.lower().replace("]", "").replace("_", " ").split("|")[0])
    if related_cats:
        final.append("")
        final += related_cats
    x = "\n".join(final).replace("|\n[[Category:", "|[[Category:")
    x = re.sub("(\[\[Category:.*?)(\|.*?]])\n\\1]]", "\\1\\2", x)
    x = re.sub("(\[\[Category:.*?)]]\n\\1(\|.*?]])", "\\1\\2", x)
    return x


def add_parsed_section(pieces: list, component: SectionComponents, finished: FinishedSection, log, mcs_name, real, media_cat):
    t, added = build_section_from_pieces(component, finished, log, media_cat if (mcs_name == finished.name or real) else None)
    pieces.append(t)
    return None if added else media_cat


MAINTENANCE = ["catneeded", "citation", "cleanup", "cleanup-context", "confirm", "contradict", "disputed", "expand",
               "image", "moresources", "npov", "oou", "plot", "redlink", "split", "stayontarget", "tense", "tone", "update"]


def format_update_contents(ln, page: Page, results: PageComponents, appearances: FullListData, sources: FullListData, types):
    ln = ln.replace("|hide=1", "")
    new_items = []
    for i in re.findall(",? ?('*(\[\[|\{\{)+[^\n\[\]}{]+(}}|]])'*)}?}?", ln):
        if "{{" in i[0]:
            x = extract_item(i[0], False, page.title(), types)
            if x:
                d = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target,
                                          sources.unique, sources.urls, sources.target, {}, results.canon, False)
                if d and x.is_card_or_mini() and d.current.card:
                    new_items.append(build_card_text(d, d).replace("|parent=1", "").replace("|reprint=1", ""))
                    continue
                elif d:
                    new_items.append(d.master.original.replace("|reprint=1", ""))
                    continue
        new_items.append(i[0])
    return ", ".join(new_items)


def build_iu_intro(page: Page, results: PageComponents, appearances: FullListData, sources: FullListData, types: dict):
    pieces = []
    content = results.before.strip().splitlines()
    maintenance_tags = {}
    update_content = None
    expand_content = None
    for ln in content:
        for x in MAINTENANCE:
            if "{{update|" in ln.lower():
                update_content = format_update_contents(ln, page, results, appearances, sources, types)
                maintenance_tags[ln] = "updatecontent"
                break
            elif "{{expand|" in ln.lower():
                x = re.search("expand\|(.*?)}}", ln)
                if x:
                    expand_content = x.group(1)
                    maintenance_tags[ln] = "expand"
                break
            elif f"{{{{{x}|" in ln.lower() or f"{{{{{x}}}}}" in ln.lower():
                maintenance_tags[ln] = x
                break
    if len(maintenance_tags) > 1:
        maintenance_params = sorted(v for v in maintenance_tags.values() if "content" not in v)
        if expand_content:
            maintenance_params.append(f"expandcontent={expand_content}")
        if update_content:
            maintenance_params.append(f"updatecontent={update_content}")
    else:
        maintenance_tags = {}
        maintenance_params = []

    add_multiple_issues = True
    found_section = False
    for ln in content:
        if ln.startswith("==") and not found_section:
            found_section = True
            if results.stub:
                pieces.append("")
                pieces.append(results.stub)

        if "{{top" in ln.lower():
            pieces.append(sort_top_template(page.title(), ln))
        elif "|updatecontent=" in ln.lower():
            x = re.search("updatecontent=(.*?)(\|[a-z0-9=|]*)?}}$", ln)
            if x:
                lx = format_update_contents(x.group(1), page, results, appearances, sources, types)
                pieces.append(ln.replace(x.group(1), lx))
            else:
                pieces.append(ln)
        elif ln in maintenance_tags and add_multiple_issues:
            pieces.append("{{MultipleIssues|" + "|".join(maintenance_params) + "}}")
            add_multiple_issues = False
        elif ln in maintenance_tags:
            pass
        elif "{{update|" in ln.lower() and update_content is not None:
            pieces.append("{{Update|" + update_content + "}}")
        else:
            pieces.append(ln)

    return pieces


NO_AUDIO = ["ComicBook", "ComicCollection", "ComicStory", "ComicSeries", "GraphicNovel"]
NO_MEDIA = ["MagazineArticle", "ShortStory"]


def build_final_text(pieces, otx, page: Page, results: PageComponents, disambigs: list, remap: dict,
                     redirects: dict, sources: FullListData, components: NewComponents, keep_page_numbers: bool,
                     log: bool, redo=False):

    pieces.append("")
    if results.media_cat:
        media_cat = None if results.media_cat == "Ignore" else results.media_cat
    elif results.infobox in NO_MEDIA or "{{Mediacat" in otx:
        media_cat = None
    elif results.canon and not results.real and not results.media:
        media_cat = None
    else:
        media_cat = find_media_categories(page, media=results.media, check_audio=results.infobox not in NO_AUDIO)

    section = sorted([components.links, components.nca, components.apps, components.ncs, components.src], key=lambda a: a.rows)[-1]
    mc_section_name = section.name if section.rows > 3 else None

    structure = MEDIA_STRUCTURE if results.media else MASTER_STRUCTURE
    for key, header_line in structure.items():
        if key == "References":
            if key in results.sections:
                txt, _ = results.sections[key].build_text(media_cat=media_cat)
                pieces.append("\n".join(txt))
                if "{{mediacat" in pieces[-1].lower():
                    media_cat = None
            elif "<ref" in otx and "{{reflist}}" not in otx:
                if media_cat:
                    pieces.append("==Notes and references==\n" + media_cat + "\n{{Reflist}}\n\n")
                    media_cat = None
                else:
                    pieces.append("==Notes and references==\n{{Reflist}}\n\n")
        elif key == "Appearances" and not results.real:
            media_cat = add_parsed_section(pieces, results.apps, components.apps, log, mc_section_name, results.real, media_cat)
        elif key == "Non-Canon Appearances":
            media_cat = add_parsed_section(pieces, results.nca, components.nca, log, mc_section_name, results.real, media_cat)
        elif key == "Sources":
            media_cat = add_parsed_section(pieces, results.src, components.src, log, mc_section_name, results.real, media_cat)
        elif key == "Non-Canon Sources":
            media_cat = add_parsed_section(pieces, results.ncs, components.ncs, log, mc_section_name, results.real, media_cat)
        elif key == "Links":
            media_cat = add_parsed_section(pieces, results.links, components.links, log, mc_section_name, results.real, media_cat)
        elif key not in results.sections:
            continue
        else:
            section = results.sections[key]
            if log:
                print(f"Creating {key} section with {len(section.lines)} lines and {len(section.subsections)} / {len(section.other)} subsections")

            add_cat = False
            if key == "Appearances" or (key == "Contents" and results.infobox == "ExpansionPack") or (results.media and key == "Media"):
                add_cat = True

            lines, added_cat = section.build_text(header_line, media_cat=media_cat if add_cat else None, add_subsections=False)
            if added_cat:
                media_cat = None
            subsections = sorted([(k, v) for k, v in section.subsections.items()], key=lambda a: (a[1].master_num, a[1].num))
            for subheader, subsection in subsections:
                if subheader == "Collections" or subheader == "Collected in":
                    tx, added_cat = build_section_from_pieces(results.collections, components.collections, log, None)
                    txt = [tx]
                else:
                    txt, added_cat = subsection.build_text(subheader)
                lines += txt
                if added_cat:
                    media_cat = None
            for other in section.other:
                txt, _ = other.build_text()
                lines += txt

            if not (lines and not lines[-1].strip()):
                lines.append("")

            text = "\n".join(lines)
            if key == "Appearances" and "{{incomplete" in text:
                text = re.sub("\{\{[Ii]ncomplete[ _]?List.*?}}", "{{IncompleteApp}}", text)
            elif key == "Credits" and "{{incomplete" in text:
                text = re.sub("\{\{[Ii]ncomplete[ _]?List.*?}}", "{{IncompleteCredits}}", text)

            if "onlyinclude" in text:
                text = re.sub("}}\n\n+</onlyinclude>\n+", "}}\n</onlyinclude>\n\n", text)
            if key not in results.redirects_fixed:
                text = fix_redirects(redirects, text, f"Final-{key}", disambigs, remap, canon=results.canon)

            # pieces.append(do_final_replacements(text, True))
            pieces.append(text)
            pieces.append("")

    return final_steps(page, results, components, pieces, disambigs, remap, redirects, media_cat, sources, keep_page_numbers, redo=redo)


def final_steps(page: Page, results: PageComponents, components: NewComponents, pieces: list, disambigs: list,
                remap: dict, redirects: dict, media_cat, sources: FullListData, keep_page_numbers, redo=False):
    if components.navs:
        pieces.append("")
        pieces.append("")
        for i in components.navs:
            if i not in pieces:
                pieces.append(i)
        pieces.append("")

    if media_cat and not any("{{mediacat" in p.lower() for p in pieces):
        for i in range(len(pieces)):
            z = re.search("==.*?==+", pieces[-(i + 1)])
            if z:
                pieces[i] = pieces[-(i + 1)].replace(z.group(0), z.group(0) + "\n" + media_cat)
                media_cat = None
                break

    if results.final:
        pieces.append(build_final(results.final, media_cat, redirects))

    # now = datetime.now()
    new_txt = sort_categories(pieces, page.namespace().id, results.flag)
    if results.canon and not results.real and "/Legends" in new_txt:
        new_txt = handle_legends_links(new_txt, page.title())
    new_txt = clean_archive_usages(page, new_txt, sources.archive_data, redo)
    # print(f"archive: {(datetime.now() - now).total_seconds()} seconds")

    if not keep_page_numbers:
        new_txt = clear_page_numbers(new_txt)

    new_txt = re.sub("(\{\{DEFAULTSORT:.*?}})\n\n+\[\[[Cc]ategory", "\\1\n[[Category", new_txt)
    new_txt = re.sub("(?<![\n=}])\n==", "\n\n==", re.sub("\n\n+", "\n\n", new_txt)).strip()
    new_txt = re.sub("(stub|Endgame)}}\n==", "\\1}}\n\n==", new_txt)
    new_txt = re.sub("(\{\{Quote\|[^\n]+}})\n\n", "\\1\n", new_txt)
    new_txt = new_txt.replace("\n\n}}", "\n}}").replace("\n\n{{More", "\n{{More")
    if "{{Multiple" in new_txt:
        if ("{{Plot}}" in new_txt or "{{Plot|" in new_txt or "{{Plot-link" in new_txt) and re.search("==Plot summary==\n\{\{Plot(-link)?(\|.*?)?}}", new_txt):
            new_txt = re.sub("(\{\{Multiple.?[Ii]ssues.*?)\|plot(\|.*?)?}}", "\\1\\2}}", new_txt)

        x = re.search("\{\{Multiple.?[Ii]ssues\|([^|{}\n]+)}}", new_txt)
        if x:
            new_txt = new_txt.replace(x.group(0), "{{" + MULTIPLE_ISSUE_CONVERSION.get(x.group(1), x.group(1).capitalize()) + "}}")

    # print(f"regex: {(datetime.now() - now).total_seconds()} seconds")
    replace = True
    if redirects:
        new_txt = fix_redirects(redirects, new_txt, "Final Body", remap, disambigs)
    if "{{WP}}" in new_txt:
        new_txt = new_txt.replace("{{WP}}", f"{{{{WP|{page.title()}}}}}")
    elif "{{WP|{{PAGENAME}}" in new_txt:
        new_txt = re.sub("(\{\{WP\|[^\n]+?)\{\{PAGENAME}}([^\n}]*?}})", "\\1{{subst:PAGENAME}}\\2",
                         new_txt.replace("{{WP|{{PAGENAME}}", "{{WP|{{subst:PAGENAME}}"))

    # now = datetime.now()
    t = do_final_replacements(new_txt, replace)
    # print(f"replace: {(datetime.now() - now).total_seconds()} seconds")
    return t


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


def build_final(final, media_cat, redirects):
    templates = {k: v for k, v in redirects.items() if k.startswith("Template:")}
    if templates:
        final = fix_redirects(templates, final, "Ending Text", {}, {})

    if "RelatedCategories" not in final and re.search("\n\[\[[Cc]ategory:.*?\| ]]", final):
        cats = []
        lines = []
        regular = 0
        for ln in final.splitlines():
            x = re.search("^(\[\[[Cc]ategory:.*?)\| ]]", ln)
            if x:
                cats.append("|" + x.group(1) + "]]")
            else:
                if "category:" in ln.lower():
                    regular += 1
                lines.append(ln)

        if cats and regular == 0:
            print("Unable to move categories to RelatedCategories, as no categories would be left")
        elif cats:
            related = "\n".join(["{{RelatedCategories", *cats, "}}"])
            final = "\n".join(lines).strip() + "\n\n" + related

    final = re.sub("\|\n+\[\[Category:", "|[[Category:", final)

    if "==\n" in final and media_cat:
        z = final.split("==\n", 1)
        return f"{z[0]}==\n{media_cat}\n{z[1]}"
    elif media_cat:
        return media_cat + "\n" + final
    else:
        return final


def build_text(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
               sources: FullListData, bad_cats: list, remap: dict, include_date: bool, checked: list, *, log=True,
               use_index=True, collapse_audiobooks=True, manual: str = None, extra=None, time=False, keep_pages=False,
               redirects: dict = None, redo=False):
    start = datetime.now()
    now = start
    text, redirects, results = build_initial_components(target, disambigs, infoboxes, bad_cats, manual, keep_pages, redirects)

    if time:
        now = report_duration("initial", now, start)

    unknown = build_page_sections(target, text, results, redirects, disambigs, types, appearances, sources, remap, log, extra=extra)
    if results.media:
        pieces = prepare_media_infobox_and_intro(target, results, redirects, disambigs, types, remap, appearances, sources)
    else:
        pieces = build_iu_intro(target, results, appearances, sources, types)

    if time:
        now = report_duration("components", now, start)
    if results.real and collapse_audiobooks:
        collapse_audiobooks = False

    components, unknown_items, analysis = analyze_section_results(
        target, results, appearances, sources, remap, use_index, include_date, collapse_audiobooks, checked, log)
    if time:
        now = report_duration("analysis", now, start)

    new_txt = build_final_text(pieces, text, target, results, disambigs, remap, redirects, sources, components,
                               keep_page_numbers=keep_pages, log=log, redo=redo)
    if time:
        report_duration("final", now, start)

    if re.search("\{\{[FCG]Anom.*?\|index=.*?}}", target.get()):
        index, old_id = create_index(target.site, target, analysis, appearances.target, sources.target, True)
        if index and "{{Indexpage" not in new_txt:
            if "==Appearances==" in text:
                new_txt = new_txt.replace("==Appearances==", "==Appearances==\n{{Indexpage}}")
            elif "==Sources==" in text:
                new_txt = new_txt.replace("==Sources==", "==Sources==\n{{Indexpage}}")
        new_txt = remove_index_param(new_txt)

    return new_txt, analysis, unknown, unknown_items


def build_new_text(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                   sources: FullListData, bad_cats: list, remap: dict, include_date: bool, checked: list, *, log=True,
                   use_index=True, collapse_audiobooks=True, manual: str = None, extra=None, keep_pages=False, redo=False):
    new_txt, analysis, unknown, unknown_items = build_text(
        target, infoboxes, types, disambigs, appearances, sources, bad_cats, remap, include_date, checked, log=log,
        use_index=use_index, collapse_audiobooks=collapse_audiobooks, manual=manual, extra=extra, keep_pages=keep_pages, redo=redo)

    record_local_unknown(unknown, unknown_items, target)
    return new_txt, unknown, unknown_items


def remove_index_param(t):
    return re.sub("(\{\{[FCG]Anom.*?)\|index=.*?(\|.*?)?}}", "\\1\\2}}", t)


def analyze_target_page(target: Page, infoboxes: dict, types: dict, disambigs: list, appearances: FullListData,
                        sources: FullListData, bad_cats: list, remap: dict, save: bool, include_date: bool, *,
                        log=True, use_index=True, collapse_audiobooks=True, old_text=None, redirects: dict = None):
    old_text = old_text or target.get(force=True)
    new_txt, analysis, unknown, unknown_items = build_text(
        target, infoboxes, types, disambigs, appearances, sources, bad_cats, remap, include_date, [], log=log,
        use_index=use_index, collapse_audiobooks=collapse_audiobooks, redirects=redirects, manual=old_text)

    with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/test_text.txt", mode="w", encoding="utf-8") as f:
        f.writelines(new_txt)

    # if dates:
    #     with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/protocols/new_dates.txt", mode="a", encoding="utf-8") as f:
    #         date_txt = []
    #         for d in dates:
    #             if d[2] == d[3]:
    #                 date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]}: -> {d[1].master.original}")
    #             else:
    #                 date_txt.append(f"{d[1].master.date} --> {d[0]}: #{d[2]} {d[3]}: -> {d[1].master.original}")
    #         f.writelines("\n" + "\n".join(date_txt))

    if save and new_txt != old_text:
        if "�" in new_txt:
            error_log(f"Unexpected characters found in changes")
            error_log(showDiff(old_text, new_txt))
        z1 = re.sub("<!--.*?-->", "", new_txt)
        z2 = re.sub("<!--.*?-->", "", remove_index_param(old_text))
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


def record_local_unknown(unknown, unknown_items: UnknownItems, target: Page):
    if unknown or unknown_items.found():
        with codecs.open("C:/Users/cadec/Documents/projects/C4DE/c4de/sources/unknown.txt", mode="a",
                         encoding="utf-8") as f:
            for x in unknown:
                f.write(u'%s\t%s\n' % (x, target.title()))
            z = set()
            for o in [*unknown_items.apps, *unknown_items.src]:
                z.add(o.original if isinstance(o, Item) else o)
            for o in unknown_items.links:
                z.add(f"Links: {(o.mode + ' ' + o.original) if isinstance(o, Item) else o}")
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
