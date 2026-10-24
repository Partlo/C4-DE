import re
import traceback

from pywikibot import Page

from c4de.common import fix_redirects, prepare_title
from c4de.sources.determine import determine_id_for_item
from c4de.sources.domain import Item, ItemId, FullListData
from c4de.sources.external import prepare_basic_url
from c4de.sources.extract import extract_item, convert_issue_to_template, swap_parameters, is_nav_or_date_template

TEMPLATE_SKIPS = ["'}}", "'s}}", "Blogspot", "Cite", "PageNumber", "UnlinkedRef", "C|", "SWG", "TORcite", "TCWA", "SliceRegion", "GalaxyMapHyperlanes", "Planetnamia", "Battlenamia"]
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
    return t.replace("''", "").strip().lower().replace("novelization", "novel").replace("comic series", "comics")


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


STORY_TEMPLATES = ["StoryCite", "WEGCite", "LivingForce", "CWACite", "Tales"]


def is_plain_short_story_link(o: ItemId, link: str, ref_length):
    if not (o.master.magazine or o.master.tv or o.master.template in STORY_TEMPLATES):
        return False
    elif (ref_length - len(link)) < 5:
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


def handle_reference(full_ref, ref: str, page: Page, new_text, types, appearances: FullListData, sources: FullListData,
                     remap: dict, disambigs: dict, redirects, canon: bool, media: bool, log: bool):
    try:
        new_ref = re.sub(r"<!--( ?Unknown ?|[ 0-9/X-]+)-->", "", ref).replace("{{PageNumber}} ", "").replace("{{UnlinkedRef}} ", "")
        new_ref = re.sub(r"\|set=(.*?) \(.*?\)\|(sformatt?e?d?|stext)=.*?\|", "|set=\\1|", new_ref)
        new_ref = new_ref.replace(" {{Un}}", "")
        new_ref = convert_issue_to_template(new_ref).replace("{{=}}", "=")
        new_ref = attempt_conversion(new_ref, page, types, appearances, sources, remap, canon, log)

        links = re.findall(r"(['\"]*\[\[(?!([Ww]:c:|[Ww]ikipedia:)).*?(\|.*?)?]]['\"]*)", new_ref)
        templates = re.findall(r"(\{\{[^{}\n]+}})", new_ref)
        templates += re.findall(r"(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)
        templates += re.findall(r"(\{\{[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+\{\{[^{}\n]+}}[^{}\n]+}})", new_ref)

        new_links = []
        found = []
        for link in links:
            x = extract_item(link[0], False, "reference", types)
            if x:
                o = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target, sources.unique, sources.urls, sources.target, remap, canon, log)
                if o and not o.use_original_text and o.replace_references and o.master.original != link[0]:
                    found.append(o)
                    if is_plain_short_story_link(o, link[0], len(ref)):
                        simple_link = f'"[[' + re.sub(r"^(.*?)( \(.*?\))$", "\\1\\2|\\1", x.target) + ']]"'
                        if simple_link != link[0]:
                            new_links.append((link[0], simple_link))
                    elif o.master.template and not x.template and x.target and not re.search(link_pattern(x.target) + r"$", new_ref):
                        if o.master.template != "Film" and re.sub(r"\[\[(.*?)( \(.*?\))]]", "[[\\1\\2|\\1]]", f'"[[{x.target}]]') not in new_ref:
                            print(f"Skipping {link[0]} due to extraneous text")
                    elif link[0].startswith('"') and link[0].endswith('"') and (len(ref) - len(link[0])) > 5:
                        if o.master.template != "StoryCite" and o.master.mode != "TV" and o.master.mode != "Magazine":
                            print(f"Skipping quote-enclosed link {link[0]} in longer reference (likely an episode name)")
                    elif "{{" in o.master.original and len(templates) > 0:
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
                        if link_match and link[0] != o.master.original.replace("|audiobook=1", "").split(" {{Ab|")[0]:
                            new_links.append((link[0], o.master.original.replace("|audiobook=1", "").split(" {{Ab|")[0]))
                elif o:
                    found.append(o)
                elif x.mode == "Basic":
                    new_links.append((link[0], prepare_basic_url(x)))

        for ot, ni in new_links:
            new_ref = new_ref.replace(ot, swap_parameters(ni))

        new_templates, unknown_templates = [], []
        for t in templates:
            if "bypass=1" in t or types.get(t) == "Dates" or any(t.lower().startswith("{{" + i.lower()) for i in TEMPLATE_SKIPS):
                continue
            x = extract_item(t, False, "reference", types)
            if x:
                if x.template and is_nav_or_date_template(x.template, types):
                    continue
                o = determine_id_for_item(x, page, appearances.unique, appearances.urls, appearances.target, sources.unique, sources.urls, sources.target, {}, canon, log, ref=True)
                if o and o.current.is_card_or_mini():
                    new_templates.append((t, o, []))
                elif o:
                    found.append(o)
                    if o.use_original_text or o.current.protected_format:
                        continue
                    elif t != (o.master.original.replace(f"|int={page.title()}|", "|").replace(f"|int={page.title()}" + "}", "}") if media else o.master.original):
                        ex = []
                        if "|author=" in t:
                            ex += [r[0] for r in re.findall(r"(\|author=(\[\[.*?\|.*?]])?.*?)[|}]", t)]
                        if "|date=" in t:
                            ex += re.findall(r"(\|date=.*?)[|}]", t)
                        if "|quote=" in t:
                            ex += re.findall(r"(\|quote=.*?)[|}]", t)
                        new_templates.append((t, o, ex))
                else:
                    unknown_templates.append(x)

        for ot, ni, extra in new_templates:
            if ni.master.is_card_or_mini():
                z = build_card_text(ni, ni, replace_parent=page.title() != ni.master.target)
            elif ni.master.ref_magazine:
                z = re.sub(r"'*?(\{\{(?!FactFile)[A-z0-9]+\|[0-9]+\|.*?)(\|.*?(\{\{'s?}})?.*?)?}}'*?", "\\1}}", ni.master.original)
            else:
                z = swap_parameters(ni.master.original)
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
        if not media and new_ref.count('[') == 0 and new_ref.count("]") == 0 and new_ref.count("{") == 0:
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
    except Exception as e:
        traceback.print_exc()
        print(f"Encountered {e} while handling reference", type(e))
    return new_text


def build_new_reference(new_text, ref, final_ref, found, unknown_templates):
    if len(found) == 1 and "{{C|" in final_ref:
        return None
    if len(found) == 1 and found[0].master.target:
        return ensure_unique_references(new_text, found[0].master.target)
    elif len(found) == 1 and found[0].master.template and found[0].master.text:
        return ensure_unique_references(new_text, f"{found[0].master.template}-{found[0].master.text}")
    elif len(found) == 1:
        print(f"Cannot fix nameless reference to {found[0].master.target}: {ref}")
        return None
    elif "|cardname=" in final_ref:
        z = re.sub(r"^.*?\{\{(.*?)\|.*?cardname=(.*?)(\|.*?)?}}.*?$", "\\1-\\2", final_ref)
        return ensure_unique_references(new_text, f"Card-{z}")
    elif len(unknown_templates) == 1 and unknown_templates[0].mode in ("Web", "External", "YT") and "WebCite" not in final_ref:
        return ensure_unique_references(new_text, unknown_templates[0].template)
    elif re.search(r"\{\{[A-Z0-9]+[Dd]ates?[A-Z]?[A-Z]?(\|.*?)?}}", final_ref):
        zx = re.search(r"\{\{(.*?)\|([0-9]+)(\|.*?)?}}", final_ref)
        if zx:
            return ensure_unique_references(new_text, f"{zx.group(1)}-{zx.group(2)}")
        else:
            return ensure_unique_references(new_text, unknown_templates[0].template)
    elif "WebCite" not in final_ref:
        print(f"Cannot fix nameless reference, due to {len(found)} links found in reference: {final_ref}")
    return None


def ensure_unique_references(text, ref_name):
    ref_name = ref_name.replace("|", "-").replace('"', '').replace('(', '').replace(')', '').replace("'''", "").replace("''", "")
    zx = f"<ref name=\"{ref_name}\""
    if zx in text:
        i = 2
        zx = f"<ref name=\"{ref_name}-{i}\""
        while zx in text:
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


def match_unlinked(ref, appearances, sources):
    x = ref.replace("''", "").replace('"', "")
    for c in ["", " (novel)", " (sourcebook)"]:
        if x + c in appearances.target:
            return appearances.target[x + c][0].original
        elif x.replace("Star Wars ", "Star Wars: ") + c in appearances.target:
            return appearances.target[x.replace("Star Wars ", "Star Wars: ") + c][0].original
        elif x + c in sources.target:
            return sources.target[x + c][0].original
        elif x.replace("Star Wars ", "Star Wars: ") + c in sources.target:
            return sources.target[x.replace("Star Wars ", "Star Wars: ") + c][0].original
    return None
