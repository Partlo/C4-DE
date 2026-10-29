import re
import traceback
from typing import List

from pywikibot import Page

from c4de.common import fix_redirects, prepare_title
from c4de.sources.determine import determine_id_for_item
from c4de.sources.domain import Item, ItemId, FullListData
from c4de.sources.expansion import handle_expansion
from c4de.sources.external import prepare_basic_url
from c4de.sources.extract import extract_item, convert_issue_to_template, swap_parameters, is_nav_or_date_template

TEMPLATE_SKIPS = ["'}}", "'s}}", "Blogspot", "Cite", "PageNumber", "UnlinkedRef", "C|", "SWG", "DatapadCite", "TORcite", "TCWA", "SliceRegion", "GalaxyMapHyperlanes", "Planetnamia", "Battlenamia"]
REF_REPLACEMENTS = [("film]] film", "film]]"), ("|reprint=yes", ""), ("|reprint=1", ""), ("|audiobook=yes", ""), ("|audiobook=1", "")]

SPECIAL = {
    "Star Wars: X-Wing vs. TIE Fighter": ["Star Wars: X-Wing vs. TIE Fighter: Balance of Power"],
    "Star Wars: The Essential Atlas Online Companion": ["''[[Star Wars: The Essential Atlas Online Companion]]''"]
}


def check_format_text(o: ItemId, x: Item):
    if o.current.followed_redirect and o.current.original_target:
        return _check_format_text(o.current.original_target, x.format_text)
    return _check_format_text(o.master.target, x.format_text)


def _clean_simple(t):
    return t.replace("''", "").strip().lower().replace("paperback novel", "junior novelization").replace("novelization", "novel").replace("comic series", "comics")


def _full_clean(t, y):
    x = _clean_simple(t).replace(":", "").replace("(", "").replace(")", "")
    z = _clean_simple(y).replace(":", "").replace("(", "").replace(")", "")
    if x.startswith("star wars ") and not z.startswith("star wars "):
        return x.replace("star wars ", "") in z
    elif x.startswith("the ") and not z.startswith("the "):
        return x.split("the ", maxsplit=1)[1] in z
    return x in z


def _check_format_text(t, y):
    return t and y and "(" in t and (not _full_clean(t.split("(")[0], y) and not _full_clean(t, y))


def link_pattern(t):
    return r"^['\"]*\[\[" + prepare_title(t) + r"(\|.*?)?]][,'\"]*"


def attempt_conversion(new_ref, page: Page, types, appearances: FullListData, sources: FullListData, remap: dict, canon: bool, log: bool):
    z = re.search(r"^(<!--.*?)?['\"]*\[\[([^\n\[\]|]*?)(\|[^\n\[\]|]*?)?]]['\"]* ?(-|—|&.dash;) ?['\"]*\[\[(?!:File:)([^\n\[\]|]*?)(\|[^\n\[\]|]*?)?]]['\"]* ?((<small>\(|\{\{[Cc]\|)[Rr]eprinted.*?(}}|\)</small>))?", new_ref)
    if not z:
        return new_ref

    attempt1 = extract_item("{{StoryCite|story=" + z.group(2) + "|book=" + z.group(5) + "}}", False, "reference", types)
    attempt2 = extract_item("{{StoryCite|book=" + z.group(2) + "|story=" + z.group(5) + "}}", False, "reference", types)
    o1 = determine_id_for_item(attempt1, page, appearances.unique, appearances.urls, appearances.target, sources.unique,
                               sources.urls, sources.target, remap, canon, log)
    o2 = determine_id_for_item(attempt2, page, appearances.unique, appearances.urls, appearances.target, sources.unique,
                               sources.urls, sources.target, remap, canon, log)
    found = None
    if o1 and o2:
        if o1.master.target == z.group(2) and o1.master.parent == z.group(5):
            found = o1
        elif o2.master.target == z.group(5) and o2.master.parent == z.group(2):
            found = o1
        elif o1.master.from_extra and not o2.master.from_extra:
            found = o2
        elif o2.master.from_extra and not o1.master.from_extra:
            found = o1

    elif o1 and not o1.master.from_extra:
        found = o1
    elif o2 and not o2.master.from_extra:
        found = o2

    if found:
        return new_ref.replace(z.group(0), found.master.original)
    return new_ref


STORY_TEMPLATES = ["StoryCite", "WEGCite", "LivingForce", "DoD", "CWACite", "Tales"]


def is_plain_short_story_link(o: ItemId, link: str, ref: str, ref_length):
    if not (o.master.magazine or o.master.tv or o.master.template in STORY_TEMPLATES):
        return False
    elif ref_length < 5:
        return False
    elif ref.startswith(f"{link} {{{{AD|"):
        return False

    z = link.replace("''", "").replace('"', "")
    if " (" in o.master.target:
        x, p = o.master.target.split(" (", 1)
        if f"[[{x} ({p}|{x}]]" == z:
            return True

    expected = f"[[{o.master.target}]]"
    if expected == z:
        return True
    elif link == f"''{expected}''":
        return True
    elif link == f'"{expected}"':
        return False
    elif link.startswith(f"[[{o.master.target}|''") and link.endswith("'']]"):
        return True
    return False


def determine_id_for_reference(x: Item, page: Page, appearances: FullListData, sources: FullListData, page_links: list,
                               canon: bool, log: bool):
    o = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target, sources.unique,
                              sources.urls, sources.target, {}, canon, log, ref=True)
    if o:
        expanded, _, _, _ = handle_expansion(o, x, page, page_links, appearances, sources, set(), 0, 0, is_reference=True)
        if len(expanded) == 1:
            return expanded[0], True
    return o, False


def should_flag_series(o: ItemId, is_iu, ref_length):
    if o and o.master.from_extra and is_iu:
        if o.current.is_exception or o.current.override or o.master.future or o.master.has_content:
            return ""
        elif "Weekly" in o.master.target and re.search("(Wars|Back|Jedi) Weekly [0-9]+", o.master.target):
            return ""
        return "{{SeriesRef}} " if ref_length < 5 else ""
    return ""


REMOVE = ["{{PageNumber}}", "{{UnlinkedRef}}", "{{Un}}", "{{SeriesRef}}"]


def handle_reference(full_ref, ref: str, page: Page, new_text, types, appearances: FullListData, sources: FullListData,
                     page_links, remap: dict, disambigs: dict, redirects, canon: bool, real_or_bts: bool, media: bool, log: bool):
    try:
        new_ref = f"{ref}"
        for t in REMOVE:
            new_ref = new_ref.replace(f" {t}", "").replace(t, "").strip()
        original_length = len(new_ref)
        new_ref = re.sub(r"<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", new_ref)
        new_ref = re.sub(r"\|set=(.*?) \(.*?\)\|(sformatt?e?d?|stext)=.*?\|", "|set=\\1|", new_ref)
        new_ref = convert_issue_to_template(new_ref).replace("{{=}}", "=")
        new_ref = attempt_conversion(new_ref, page, types, appearances, sources, remap, canon, log)

        links = re.findall(r"(['\"]*\[\[(?!([Ww]:c:|[Ww]ikipedia:)).*?(\|.*?)?]]['\"]*)[,.]?(\"?)", new_ref)
        templates = re.findall(r"(\{\{[^{}\n]+}})", new_ref)
        templates += re.findall(r"(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)
        templates += re.findall(r"(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)

        other_templates = [t for t in templates if not t.startswith("{{C|") and not t.startswith("{{AD|")]
        new_links = []
        found = []
        remove = []
        rename = {}
        for link in links:
            x = extract_item(link[0], False, "reference", types)
            ref_length = original_length - len(link[0])
            if x:
                link_w_quotes = link[0] + link[3]
                o, expanded = determine_id_for_reference(x, page, appearances, sources, page_links, canon, log)
                flag = should_flag_series(o, not real_or_bts, ref_length)
                if o and not o.use_original_text and o.replace_references and o.master.original != link_w_quotes:
                    found.append(o.master)
                    if expanded and ref_length < 5:
                        new_links.append((link[0], flag + o.master.original.replace("|audiobook=1", "").split(" {{Ab|")[0]))
                        if f"name=\"{x.target}\"" in full_ref:
                            rename[f"name=\"{x.target}\""] = f"name=\"{o.master.target}\""
                    elif is_plain_short_story_link(o, link[0], ref, ref_length):
                        simple_link = f'"[[' + re.sub(r"^(.*?)( \(.*?\))$", "\\1\\2|\\1", x.target) + ']]"'
                        if x.target == "Star Wars Rebels: Spark of Rebellion":
                            simple_link = '"[[Star Wars Rebels: Spark of Rebellion|Spark of Rebellion]]"'
                        if simple_link != link_w_quotes and not ("EwoksDate" in ref and f"|{link_w_quotes}}}}}" in ref):
                            new_links.append((link[0], flag + simple_link))
                            if "''" in link[0]:
                                xz = re.sub(r"('*)\[\[(.*?\|)?(.*?)]]('*)", "\\1\\3\\4", link[0])
                                tx = x.target.split(' (')[0]
                                new_links.append((xz, f'"{tx}"'))
                    elif o.master.template and not x.template and x.target and not re.search(link_pattern(x.target) + r"$", new_ref.split(" {{AD|", 1)[0]):
                        if o.master.template != "Film" and re.sub(r"\[\[(.*?)( \(.*?\))]]", "[[\\1\\2|\\1]]", f'"[[{x.target}]]') not in new_ref:
                            print(f"Skipping {link[0]} due to extraneous text ({ref_length} more characters)")
                    elif link_w_quotes.startswith('"') and link_w_quotes.endswith('"') and ref_length > 5:
                        if o.master.template != "StoryCite" and o.master.mode != "TV" and o.master.mode != "Magazine":
                            print(f"Skipping quote-enclosed link {link[0]} in longer reference (likely an episode name)")
                    elif "{{" in o.master.original and len(other_templates) > 0:
                        print(f"Skipping {link[0]} due to presence of other templates in ref note")
                    elif o.master.original.isnumeric():
                        print(f"Skipping {link[0]} due to numeric text")
                    elif check_format_text(o, x):
                        print(f"Skipping {link[0]} due to non-standard pipelink: {x.format_text}")
                    elif x.target in SPECIAL and ((x.text or "").replace("''", "") in SPECIAL[x.target] or x.original in SPECIAL[x.target]):
                        print(f"Skipping exempt {link[0]}")
                    else:
                        link_match = re.search(link_pattern(x.target), new_ref)
                        if not link_match and o.current.original_target:
                            link_match = re.search(link_pattern(o.current.original_target), new_ref)
                        if link_match and link_w_quotes != o.master.original.replace("|audiobook=1", "").split(" {{Ab|")[0]:
                            new_links.append((link[0], flag + o.master.original.replace("|audiobook=1", "").split(" {{Ab|")[0]))
                        elif flag:
                            new_links.append((link[0], flag + link[0]))
                elif o and flag:
                    found.append(o.master)
                    new_links.append((link[0], flag + link[0]))
                elif o:
                    found.append(o.master)
                elif x.mode == "Basic":
                    new_links.append((link[0], prepare_basic_url(x)))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, swap_parameters(ni))
        new_ref = new_ref.replace('","', ',"').replace('", ', '," ')

        new_templates, unknown_templates = [], []
        for t in templates:
            if t.startswith("{{Ab|"):
                remove.append(t)
                continue

            if "bypass=1" in t or types.get(t) == "Dates" or any(t.lower().startswith("{{" + i.lower()) for i in TEMPLATE_SKIPS):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and is_nav_or_date_template(x.template, types):
                    continue
                o, expanded = determine_id_for_reference(x, page, appearances, sources, page_links, canon, log)
                if o and o.current.is_card_or_mini():
                    flag = "{{UnknownRef}}" if o.current.unknown else ""
                    new_templates.append((t, flag, o, []))
                elif o:
                    flag = "{{UnknownRef}}" if o.current.unknown and o.current.mode not in ("Publisher", "External", "Profile", "Social", "Publisher") else ""
                    found.append(o.master)
                    if o.current.protected_format:
                        continue
                    elif o.use_original_text:
                        if flag:
                            new_templates.append((t, flag, o, []))
                        continue
                    elif t != (o.master.original.replace(f"|int={page.title()}|", "|").replace(f"|int={page.title()}" + "}", "}") if media else o.master.original):
                        ex = []
                        if "|author=" in t:
                            ex += [r[0] for r in re.findall(r"(\|author=(\[\[.*?\|.*?]])?.*?)[|}]", t)]
                        if "|date=" in t:
                            ex += re.findall(r"(\|date=.*?)[|}]", t)
                        if "|quote=" in t:
                            ex += re.findall(r"(\|quote=.*?)[|}]", t)
                        new_templates.append((t, flag, o, ex))
                else:
                    unknown_templates.append(x)

        for ot, flag, ni, extra in new_templates:
            if ni.use_original_text:
                z = swap_parameters(ni.current.original)
            elif ni.master.is_card_or_mini():
                z = build_card_text(ni, ni, replace_parent=page.title() != ni.master.target)
            elif ni.master.ref_magazine:
                z = re.sub(r"'*?(\{\{(?!FactFile)[A-z0-9]+\|[0-9]+\|.*?)(\|.*?(\{\{'s?}})?.*?)?}}'*?", "\\1}}", ni.master.original)
            else:
                z = swap_parameters(ni.master.original)
            z = f"{flag} {z}".strip()
            z = z.replace(f"|int={page.title()}|", "|").replace(f"|int={page.title()}" + "}", "}")
            if extra:
                to_use = []
                for i in extra:
                    z = z.replace(i, "")
                    if (i.split("=")[0] + "=") not in z:
                        to_use.append(i)
                z = z[:-2] + "".join(to_use) + "}}"
            if "|d=y" in ni.current.original:
                z = z[:-2] + "|d=y}}"
            new_ref = new_ref.replace(ot, z.replace("–", "&ndash;").replace("—", "&mdash;"))
            if page.title() != ni.master.target or ni.current.card:
                new_ref = re.sub(r"\|parent=1(?!}}( is set| \{\{C\|))", "", new_ref)

        new_ref = fix_redirects(redirects, new_ref, "Reference", disambigs, remap, canon=canon)
        if not media and new_ref.count('[') == 0 and new_ref.count("]") == 0:
            unlinked, match = True, None
            simple = new_ref.replace('"', "").replace("''", "")
            if new_ref.count("{") == 0:
                match = match_unlinked(simple, remap, appearances, sources)
            elif "{{C|" in new_ref and new_ref.count("{") == 2 and new_ref.count("}") == 2:
                match = match_unlinked(re.sub(r"\{\{[Cc]\|(.*?)}}", "(\\1)", simple), remap, appearances, sources)
                if not match:
                    match = match_unlinked(re.sub(r" ?\{\{[Cc]\|(.*?)}}", "", simple), remap, appearances, sources)
            else:
                unlinked = False

            if match and match.original:
                new_ref = match.original
                found.append(match)
            elif unlinked:
                new_ref = "{{UnlinkedRef}} " + new_ref

        final_ref = re.sub(r"\{\{[Aa]b\|.*?}}", "", full_ref.replace(">" + ref, ">" + new_ref))
        if "<ref>" in final_ref:
            named_ref = build_new_reference(new_text, ref, final_ref, found, unknown_templates)
            if named_ref:
                final_ref = final_ref.replace("<ref>", named_ref + ">")
        elif "<ref name=\":" in final_ref:
            rx = re.search("(<ref name=(\":[0-9]+\"))>", final_ref)
            if rx:
                named_ref = build_new_reference(new_text, ref, final_ref, found, unknown_templates)
                if named_ref:
                    final_ref = final_ref.replace(rx.group(1), named_ref)
                    new_text = new_text.replace(rx.group(1) + " />", named_ref + " />").replace(rx.group(1) + "/>", named_ref + " />")

        for r, x in REF_REPLACEMENTS:
            if not ("reprint" in r and "reprint" in full_ref):
                final_ref = final_ref.replace(r, x)
        if "series series" in final_ref:
            final_ref = re.sub(r" series( series)+", " series", final_ref)
        new_text = new_text.replace(full_ref, final_ref)
        for k, v in rename.items():
            new_text = new_text.replace(k, v)
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return new_text


def build_new_reference(full_text, ref, final_ref, found: List[Item], unknown_templates):
    if len(found) == 1 and "{{C|" in final_ref:
        return None
    if len(found) == 1 and found[0].target:
        return ensure_unique_references(full_text, found[0].target)
    elif len(found) == 1 and found[0].template and found[0].text:
        return ensure_unique_references(full_text, f"{found[0].template}-{found[0].text}")
    elif len(found) == 1:
        print(f"Cannot fix nameless reference to {found[0].target}: {ref}")
        return None
    elif "|cardname=" in final_ref:
        z = re.sub(r"^.*?\{\{(.*?)\|.*?cardname=(.*?)(\|.*?)?}}.*?$", "\\1-\\2", final_ref)
        return ensure_unique_references(full_text, f"Card-{z}")
    elif len(unknown_templates) == 1 and unknown_templates[0].mode in ("Web", "External", "YT") and "WebCite" not in final_ref:
        return ensure_unique_references(full_text, unknown_templates[0].template)
    elif re.search(r"\{\{[A-Z0-9]+[Dd]ates?[A-Z]?[A-Z]?(\|.*?)?}}", final_ref):
        zx = re.search(r"\{\{(.*?)\|([0-9]+)(\|.*?)?}}", final_ref)
        if zx:
            return ensure_unique_references(full_text, f"{zx.group(1)}-{zx.group(2)}")
        else:
            return ensure_unique_references(full_text, unknown_templates[0].template)
    elif "TORcite" in final_ref:
        x = re.search(r"TORcite\|.*?(TORTYPE|type)=(faction|class|crewskill|conversation)\|.*?\|(.*?)(\|.*?)?}}", final_ref)
        if not x:
            x = re.search(r"TORcite\|.*?(TORTYPE|type)=([a-z]+)\|(.*?)(\|.*?)?}}", final_ref)
        if x:
            return ensure_unique_references(full_text, ("TOR-" if f'"{x.group(3)}"' in full_text else "") + x.group(3))
        else:
            x = re.search(r"TORcite\|.*?exp=([a-z]+)\|chapter=([0-9]+)", final_ref)
            if x:
                return ensure_unique_references(full_text, f"{x.group(1).upper()} Chapter {x.group(2)}")

    if "WebCite" not in final_ref:
        print(f"Cannot fix nameless reference, due to {len(found)} links found in reference: {final_ref}")
    return None


def ensure_unique_references(text, ref_name):
    ref_name = ref_name.replace("|", "-").replace('"', '').replace("'''", "").replace("''", "")
    parenthetical = None
    if " (" in ref_name and ref_name.endswith(")"):
        ref_name, _, parenthetical = ref_name[:-1].partition(" (")
    zx = f"<ref name=\"{ref_name}\""
    if zx in text:
        i = 2
        if parenthetical:
            zx = f"<ref name=\"{ref_name} {parenthetical}\""
        else:
            zx = f"<ref name=\"{ref_name}-{i}\""
        while zx in text:
            if parenthetical:
                parenthetical = None
            else:
                i += 1
            zx = f"<ref name=\"{ref_name}-{i}\""
            if i > 10:
                break
    return zx


def build_card_text(o: ItemId, c: ItemId, replace_parent=True):
    ot = f"{c.current.original}"
    if c.master.template and c.master.mode == "Minis" and c.master.card:
        ot = f"{c.master.original}"
    if c.current.subset and "subset=" not in ot:
        ot = re.sub(r"({{[^|}]*?\|(set=)?[^|}]*?\|(s?text=.*?\|)?)", f"\\1subset={o.current.subset}|", ot)
    while ot.count("|subset=") > 1:
        ot = re.sub(r"(\|subset=.*?)\1", "\\1", ot)
    if o.master.template and o.master.master_page:
        y = re.sub(r"\|p=.*?(\|.*?)?}}", "\\1", o.master.original.replace("}}", ""))
        z = re.search(r"\{\{([A-z0-9]+)(\|.*?)\|(num=|url=|subset=|scenario=|pack=|unit=|mission=|cardname=|(swg)?(alt)?link=)", y)
        if z and z.group(2) and not re.search(r"\|(num=|url=|subset=|scenario=|pack=|unit=|mission=|cardname=|(swg)?(alt)?link=)", z.group(2)):
            ot = ot.replace(z.group(0), y + "|" + z.group(3))
        if (o.master.mode == "Minis" or o.master.template == "SWIA") and c.master.card:
            ot = re.sub(r"\|link=.*?(\|.*?)?}}", "\\1}}", ot)
            if "link=" in ot:
                ot = re.sub(r"\|link=.*?(\|.*?)?}}", "\\1}}", ot)
            ot = re.sub(r"(\|(cardname|mission)=.*?)(\|.*?)?\|\2=.*?(\|.*?)?}}", "\\1\\3\\4}}", ot)
    ot = re.sub(r"(\{\{.*?\|set=(.*?))\|s?text=\2\|", "\\1|", ot)
    ot = re.sub(r"(\|set='*?(.*?)\|stext=.*?)\|'*?\2'*?\|", "\\1", ot)
    ot = re.sub(r"\|stext=(.*?)\|\1\|", "|stext=\\1|", ot)
    ot = re.sub(r"(\|(ship|pack|cardname)=.*?)(\|.*?)?\1(\|.*?)?}}", "\\1\\3\\4}}", ot)
    ot = ot.replace("–", "&ndash;").replace("—", "&mdash;").replace("  ", " ")
    ot = re.sub(r"(\|reprint=1)\1+", "\\1", ot)
    if replace_parent:
        ot = ot.replace("|parent=1", "")
    return ot


def match_unlinked(ref, remap, appearances: FullListData, sources: FullListData):
    x = ref.replace("''", "").replace('"', "")
    x = remap.get(x, x)
    for c in ["", " (novel)", " (sourcebook)"]:
        if x + c in appearances.target:
            return appearances.target[x + c][0]
        elif x.replace("Star Wars ", "Star Wars: ") + c in appearances.target:
            return appearances.target[x.replace("Star Wars ", "Star Wars: ") + c][0]
        elif x + c in sources.target:
            return sources.target[x + c][0]
        elif x.replace("Star Wars ", "Star Wars: ") + c in sources.target:
            return sources.target[x.replace("Star Wars ", "Star Wars: ") + c][0]
    return None
