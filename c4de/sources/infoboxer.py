import json
from datetime import datetime
from typing import Dict, Tuple, List

from c4de.common import error_log, handle_multiple_issues
from pywikibot import Page, Category, showDiff
import re


class InfoboxInfo:
    def __init__(self, params, optional, combo, groups):
        self.params = params
        self.optional = optional
        self.combo = combo
        self.groups = groups

    def json(self):
        return {"params": self.params, "optional": self.optional, "combo": self.combo, "groups": self.groups}

    @staticmethod
    def from_json(js):
        return InfoboxInfo(js['params'], js['optional'], js['combo'], js['groups'])


def parse_infobox_category(cat: Category, results):
    for p in cat.articles(namespaces=10):
        x = p.title(with_ns=False).replace("_", " ")
        if p.title().endswith("400"):
            results[x.replace('400', '')] = build_fields_for_infobox(p)
        elif any(p.title(with_ns=False).startswith(y) for y in ["Battle", "Duel", "Campaign", "Mission", "Treaty", "War"]):
            results[x] = None
        else:
            results[x] = build_fields_for_infobox(p)
    for c in cat.subcategories():
        if c.title(with_ns=False) != "Preload templates":
            parse_infobox_category(c, results)


def reload_infoboxes(site):
    infoboxes = list_all_infoboxes(site)
    with open("c4de/data/infoboxes.json", "w") as f:
        as_json = {k: v.json() for k, v in infoboxes.items() if v}
        f.writelines(json.dumps(as_json).replace('}}, "', '}},\n  "'))
    print(f"Loaded {len(infoboxes)} infoboxes from cache")
    return infoboxes


def load_infoboxes(site):
    try:
        with open("c4de/data/infoboxes.json", "r") as f:
            infoboxes = json.loads("\n".join(f.readlines()))
            results = {}
            for k, v in infoboxes.items():
                results[k] = InfoboxInfo.from_json(v)
            return results
    except Exception as e:
        error_log(f"Encountered {type(e)} while loading infobox JSON", e)
        return reload_infoboxes(site)


def list_all_infoboxes(site) -> Dict[str, InfoboxInfo]:
    now = datetime.now()
    results = {}
    parse_infobox_category(Category(site, "Category:Infobox templates"), results)
    if results.get("Battle300"):
        results["Battle300"].optional += [f for f in results["Battle300"].params if f.endswith("3") or f.endswith("4)")]
    if results.get("Battle350"):
        results["Battle350"].optional += [f for f in results["Battle350"].params if f.endswith("4)")]
    duration = datetime.now() - now
    print(f"Loaded {len(results)} infoboxes in {duration.seconds} seconds")
    return results


def build_fields_for_infobox(page) -> InfoboxInfo:
    text = page.get()
    fields = []
    optional = ["no_image"]
    theme = re.search("theme-source=\"(.*?)\"", text)
    if theme:
        fields.append(theme.group(1))
    o = re.search("\|optional=(.*?)[|}]", text)
    if o:
        optional += re.split('[,]', o.group(1))
    combo, groups = {}, {}
    for x in optional:
        if ":" in x:
            groups[x] = []
            for y in x.split(":"):
                combo[y] = x
                groups[x].append(y)
    for r in re.findall("<(data|image|title) source=\"(.*?)\" ?/?>", text):
        if r[0] == "image":
            fields.append("image")
            if r[1] == "imagefallback":
                fields += ["option1", "image2", "option2"]
                if "image3" in optional:
                    fields += ["image3", "option3"]
        else:
            if r[1].startswith('b') and re.match("b[0-9]+", r[1]):
                fields.append(r[1].replace("b", "battles"))
            fields.append(r[1])
    if page.title() == "Template:MagazineArticle" and "reprinted in" in optional:
        optional.remove("reprinted in")
    return InfoboxInfo(fields, optional, combo, groups)


NEW_NAMES = {
    "comic story arc": "ComicArc",
    "magazine": "MagazineIssue",
    "oou event": "RealEvent",
    "oou company": "RealCompany",
    "rpg adventure": "Adventure",
    "title infobox": "TitleOrPosition",
    "iu media": "InUniverseMedia"
}


def separate_templates(text):
    lines = []
    current_line = ""
    bc = 0
    for c in text:
        if c == "{":
            bc += 1
        elif c == "}":
            bc -= 1
        current_line += c

        if bc == 0:
            lines.append(current_line)
            current_line = ""
    lines.append(current_line)
    return "\n".join(lines)


def separate_template_parameters(text):
    lines = []
    current_line = ""
    bc, sc = 0, 0
    for c in text:
        if sc == 0 and bc == 0 and c == "|":
            lines.append(current_line)
            current_line = f"{c}"
            continue

        if c == "{":
            bc += 1
        elif c == "}":
            bc -= 1
        elif c == "[":
            sc += 1
        elif c == "]":
            sc -= 1
        current_line += c
    lines.append(current_line)
    return lines


def parse_infobox(text: str, all_infoboxes: dict) -> Tuple[dict, List[str], List[str], str, str, bool]:
    found, original = None, None
    done, intro_started = False, False
    oc, oc2 = 0, 0
    field = None
    data = {}
    pre, post = [], []
    scroll_box = False
    text = re.sub("}}(?! ?as)([A-Za-z _0-9\[\]/|']+''')", "}}\n\\1", text).replace("|text=\n", "|text=").replace("|url=\n", "|url=")

    contents = []
    for line in text.replace("}}{{", "}}\n{{").splitlines():
        if done:
            post.append(line)
        elif found:
            contents.append(line)
        else:
            m = re.search("^[ ]*(\{\{[^{}]+?}})?(\{\{[^{}]+?}})?(\{\{[^{}]+?}})?(\{\{([A-Za-z _]+).*?)(\|[a-z]+=.*?)?$", line)
            if m:
                if m.group(1):
                    pre.append(m.group(1))
                if m.group(2):
                    pre.append(m.group(2))
                if m.group(3):
                    pre.append(m.group(3))

                t = m.group(5)
                original = f"{m.group(5)}"
                if t and t.lower().replace("_", " ") in NEW_NAMES:
                    t = NEW_NAMES[t.lower().replace("_", " ")]
                elif t and (" " in t or "_" in t):
                    t = re.sub("(\{\{[^{}|\[\]]*?)[ _]([a-z])", lambda j: f"{j.group(1)}{j.group(2).upper()}", t)
                    t = re.sub("(\{\{[^{}|\[\]]*?)[ _]([a-z])", lambda j: f"{j.group(1)}{j.group(2).upper()}", t)

                z = t.lower().replace("_", "").replace(" ", "").replace("infobox", "").strip()
                for i in all_infoboxes:
                    if z == i.lower():
                        found = i
                        oc = 2
                        break
                if found:
                    if m.group(6):
                        contents += separate_template_parameters(m.group(6))
                    continue
                elif m.group(4):
                    pre.append(m.group(4))
                    if m.group(6):
                        pre[-1] += m.group(6)
                else:
                    pre.append(line)
            elif "[[File:" in line and not data.get("image") and "image2" not in line and "image3" not in line:
                data["image"] = line
            elif line.startswith("<!--") or "__NOTOC__" in line:
                pre.append(line)
            else:
                if line.strip():
                    done = True
                post.append(line)

    for line in contents:
        if done:
            if line.strip() or intro_started:
                intro_started = True
                post.append(line)
            continue

        oc += line.count("{")
        oc -= line.count("}")
        if oc == 0 and line.strip() == "}}":
            done = True
            continue

        continuation = oc2 > 0 and line.startswith("|") and line.count("}") > line.count("{")
        oc2 += line.count("{")
        oc2 -= line.count("}")
        if continuation:
            data[field] += line
            continue

        m = re.search("^\|([A-Za-z_ 0-9]+?)=(.*)$", line)
        if m:
            field = m.group(1).strip()
            data[field] = data.get(field) or m.group(2).strip()
        elif field:
            data[field] = f"{data[field]}\n{line}"

        if oc == 0:
            if field is not None and data[field].endswith("}}"):
                data[field] = data[field][:-2]
            done = True
        elif oc == -1 and data[field].endswith("}}"):
            data[field] = data[field][:-2]
            done = True

        if field not in data:
            continue
        n = re.search("\|([A-Za-z_ 0-9]+?)=(.*)$", data[field].replace("\n", ""))
        while n:
            if data[field].startswith("|"):
                n = re.search("^\|([A-Za-z_ 0-9]+?)=(.*)$", data[field].replace("\n", ""))
                if n:
                    data[field] = ""
                    field = n.group(1).strip()
                    data[field] = data.get(field) or n.group(2).strip()
            elif data[field].count("{{") != data[field].count("}}") or (
                    data[field].count("}}") == 0 and data[field].count("{{") == 0):
                # print(field, line, data[field], n)
                n = re.search("^.*?(\|([A-Za-z_ 0-9]+?)=(.*))$", data[field].replace("\n", ""))
                if n:
                    data[field] = data[field].replace(n.group(1), "")
                    field = n.group(2).strip()
                    data[field] = data.get(field) or n.group(3).strip()
            else:
                n = None

    return data, pre, post, found or "", original, scroll_box


def extract_date(text):
    date_str = None
    m = re.search("\|(publish date|publication date|airdate|release date|released|published)=(\n\*)?(.*?)[<\n{]", text)
    if m and "Story reel" in m.group(3):
        m = re.search("\*Finished episode.*\n.*?([A-z]+ [0-9]+).*?([0-9]{4})", m.group(3))
    if m:
        date_str = m.group(3).replace("[", "").replace("]", "").replace("*", "").strip()
        date_str = re.sub("\[\[([A-Z][a-z][a-z]+)([A-z]+) ([0-9]+)\|\\1 \\3, ([0-9]+)]]", "\\1\\2 \\3, \\4", date_str)
        date_str = re.sub("^.*?([A-Za-z]+ [0-9]*?) ?( ?&[mn]dash; ?[A-Za-z]+( [0-9]+))?,? ([0-9]{4}).*", "\\1, \\4",
                          date_str)
    return date_str


REMAP = {
    "issue": "issues",
    # "designer": "publisher",
    "artist": "penciller",
    "release date": "start date",
    "developer": "publisher",
    "media_type": "type",
    "prev": "previous",
    "card": "figures",
    "composer": "author",
}


def handle_infobox_on_page(text, page: Page, all_infoboxes, template: str = None, add=False):
    extract = True

    original_text = f"{text}"
    data, pre, post, found, original, scroll_box = parse_infobox(text, all_infoboxes)
    if scroll_box:
        print(f"Scroll box found in infobox; cannot parse {page.title()}")
        return text, found, original
    if not found and add and template:
        if template.lower() not in all_infoboxes:
            return text, found, original
        data = {}
        ix = 0
        for i, ln in enumerate(pre):
            if not ln.startswith("{{") and not ln.startswith("{{Quote") and not ln.startswith("{{Dialogue"):
                ix = i
                break
        post = pre[ix + 1:]
        pre = pre[0:ix + 1]
        found = template
    pre = handle_multiple_issues(pre)

    if not found or found not in all_infoboxes:
        print(f"ERROR: no infobox found, or infobox below body text; cannot parse {page.title()}")
        return text, None, original
    elif found.lower().startswith("year"):
        return text, found, original

    if template and template.lower() in all_infoboxes and template != found:
        print(f"Converting {found} template to {template}")
        found = template

    infobox = all_infoboxes.get(found)
    if not infobox:
        print(f"ERROR: no infobox found for {found} on {page.title()}")
        return text, None, None
    if "pronouns" not in data:
        r = re.search("Category:Individuals with (.*?) pronouns", text)
        data["pronouns"] = r.group(1) if r else ""

    extra = [k for k in infobox.optional if k not in infobox.params]
    params = [*extra, *infobox.params]
    i = -1
    intro_only = text.split("==", 1)[0]
    for f in params:
        i += 1
        v = data.get(f)
        if not v or v == "new":
            if f == "title":
                v = data.get("name") or page.title()
            if f in REMAP.keys():
                # if data.get(REMAP[f]) != "new":
                v = data.get(REMAP[f]) or v
            if f in REMAP.values() and not v:
                # x = [k for k, v in REMAP.items() if v == f and data.get(k) and data.get(k) != "new"]
                x = [k for k, v in REMAP.items() if v == f and data.get(k)]
                v = data.get(x[0] if x else '') or v
            if f == "release date" and found.lower().replace("_", " ") != "iu media":
                x = re.search("([Pp]ublished|[Rr]eleased|[Ii]ncluded|from) (in|on)? ?((\[*(January|February|March|April|May|June|July|August|September|October|November|December|fall|spring|winter|autumn)/?]* ?)*?([0-9\[\], ]*)?(of )?\[*?[0-9]{4}]*)",
                              intro_only)
                if x:
                    v = x.group(3)
            if f == "author" and not v:
                x = re.search("([Ww]ritten|article|interview) by (?P<t>\[\[.*?]])", intro_only)
                if not x:
                    x = re.search("(?P<t>\[\[.*?]]) interviews", intro_only)
                if not x:
                    x = re.search("article (in \[\[.*?]] )?by (?P<t>\[\[.*?]])", intro_only)
                if x:
                    v = x.group('t')
            if f == "published in" and not v and found.lower().replace("_", " ") != "iu media":
                v = data.get("issue") or ''
                if re.search("\[\[(.*?) ([0-9]+)\|\\2( of .*?)?]]", v):
                    v = re.sub("\[\[(.*?) ([0-9]+)\|\\2( of .*?)?]]", "[[\\1 \\2|''\\1'' \\2]]", v)
                elif extract:
                    x = re.search(
                        "(published|adventure|released|article|supplement|appearing|appeare?[sd]|included|feature|department) (w?i?t?h?in|of|from) (\[\[(Fantasy Flight Games|De ?Agostini)]]'?s? )?(the )?(magazine )?(?P<t>'*\[\[.*?]]'*)",
                        intro_only)
                    if not x:
                        x = re.search(
                            "written.* for (\[\[(Fantasy Flight Games|De ?Agostini)]]'?s? )?(the )?(magazine )?(?P<t>'*\[\[.*? [0-9]+(\|.*? [0-9]+'*?)?]]'*)",
                            intro_only)
                    if x:
                        v = x.groupdict()['t']
            if f in infobox.optional and f not in data and not v:
                continue
            elif f in infobox.combo and f not in data and not v and any(i in data for i in infobox.groups[infobox.combo[f]] if i != f):
                continue
            data[f] = v

    if data.get("published in") and "release date" in data and not data["release date"] and found.lower().replace("_", " ") != "iu media":
        p = re.search("\[\[(.*?)(\|.*?)?]]", data["published in"])
        if p:
            parent = Page(page.site, p.group(1))
            if parent.exists() and parent.isRedirectPage():
                parent = parent.getRedirectTarget()
            if parent.exists():
                data["release date"] = extract_date(parent.get())

    current = found.replace(" ", "_") if "{{" + found.lower().replace(" ", "_") in text.lower() else found
    new_infobox = ["{{" + current.replace(" ", "_")]
    i = -1
    added = []
    for f in params:
        if f in added:
            continue
        i += 1
        v = data.get(f)
        if v and (i + 1) < len(params) and f"|{params[i + 1]}=" in v and not data.get(params[i + 1]):
            print(f"Separating {f} line from {params[i + 1]}")
            v, x = v.split(f"|{params[i + 1]}=", 1)
            data[params[i + 1]] = x

        if (f == "no_image" or f == "image") and data.get("no_image"):
            new_infobox.append(f"|no_image=1")
            added += ["no_image", "image"]
        elif f in infobox.combo and not v and any(i in data for i in infobox.groups[infobox.combo[f]] if i != f):
            continue
        elif f in infobox.optional and not v and f not in data:
            continue
        else:
            new_infobox.append(f"|{f}={v or ''}")
            added.append(f)

    if sum(i.count("{") - i.count("}") for i in new_infobox) > 0:
        new_infobox.append("}}")

    new_text = "\n".join([*pre, *new_infobox, *post])
    if new_text.replace("\n}}", "}}") != original_text.replace("\n}}", "}}").replace("{{" + original, "{{" + found):
        print(f"Found changes for {found} infobox")
        showDiff(original_text.replace("\n}}", "}}").replace("{{" + original, "{{" + found), new_text.replace("\n}}", "}}"))
    return "\n".join([*pre, *new_infobox, *post]), found if found else None, original
