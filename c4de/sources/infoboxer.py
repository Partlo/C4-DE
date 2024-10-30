import json
from datetime import datetime
from typing import Dict

from c4de.common import error_log
from pywikibot import Page, Category
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
    def from_json(json):
        return InfoboxInfo(json['params'], json['optional'], json['combo'], json['groups'])


def parse_infobox_category(cat: Category, results):
    for p in cat.articles(namespaces=10):
        x = p.title(with_ns=False).lower().replace("_", " ")
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
        f.writelines(json.dumps(as_json))
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
    if results.get("battle300"):
        results["battle300"].optional += [f for f in results["battle300"].params if f.endswith("3") or f.endswith("4)")]
    if results.get("battle350"):
        results["battle350"].optional += [f for f in results["battle350"].params if f.endswith("4)")]
    duration = datetime.now() - now
    print(f"Loaded {len(results)} infoboxes in {duration.seconds} seconds")
    return results


def build_fields_for_infobox(page) -> InfoboxInfo:
    text = page.get()
    fields = []
    optional = []
    theme = re.search("theme-source=\"(.*?)\"", text)
    if theme:
        fields.append(theme.group(1))
    o = re.search("optional=(.*?)\|", text)
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
        if r[1].startswith('b') and re.match("b[0-9]+", r[1]):
            fields.append(r[1].replace("b", "battles"))
        fields.append(r[1])
    return InfoboxInfo(fields, optional, combo, groups)


def parse_infobox(text: str, all_infoboxes: dict):
    found = None
    done = False
    o, c = 0, 0
    o2, c2 = 0, 0
    field = None
    data = {}
    pre, post = [], []
    on_own_line = False
    scroll_box = False
    text = re.sub("}}([A-Za-z _0-9\[\]/|']+''')", "}}\n\\1", text)
    for line in text.replace("}}{{", "}}\n{{").splitlines():
        if done:
            post.append(line)
        elif "{{scroll" in line.lower():
            scroll_box = True
            break
        elif found:
            if line.strip() == "}}":
                done = True
                on_own_line = True
                continue
            o += line.count("{")
            c += line.count("}")

            if o2 > c2 and line.startswith("|") and line.count("}") > line.count("{"):
                data[field] += line
                o2 += line.count("{")
                c2 += line.count("}")
                continue
            o2 += line.count("{")
            c2 += line.count("}")

            m = re.search("^\|([A-Za-z_ 0-9]+?)\=(.*)$", line)
            if m:
                field = m.group(1).strip()
                data[field] = data.get(field) or m.group(2).strip()
            elif field:
                data[field] += f"\n{line}"

            if o == c:
                if data[field].endswith("}}"):
                    data[field] = data[field][:-2]
                done = True

            if field not in data:
                continue
            n = re.search("\|([A-Za-z_ 0-9]+?)\=(.*)$", data[field].replace("\n", ""))
            while n:
                if data[field].startswith("|"):
                    n = re.search("^\|([A-Za-z_ 0-9]+?)\=(.*)$", data[field].replace("\n", ""))
                    if n:
                        data[field] = ""
                        field = n.group(1).strip()
                        data[field] = data.get(field) or n.group(2).strip()
                elif data[field].count("{{") != data[field].count("}}") or (data[field].count("}}") == 0 and data[field].count("{{") == 0):
                    n = re.search("^.*?(\|([A-Za-z_ 0-9]+?)\=(.*))$", data[field].replace("\n", ""))
                    if n:
                        data[field] = data[field].replace(n.group(1), "")
                        field = n.group(2).strip()
                        data[field] = data.get(field) or n.group(3).strip()
                else:
                    n = None
        else:
            m = re.search("^[ ]*(\{\{.*?\}\})?(\{\{.*?\}\})?(\{\{.*?\}\})?(\{\{([A-Za-z _]+).*)$", line)
            if m:
                if m.group(1):
                    pre.append(m.group(1))
                if m.group(2):
                    pre.append(m.group(2))
                if m.group(3):
                    pre.append(m.group(3))

                t = m.group(5)
                if t.lower().replace("_", " ") in all_infoboxes:
                    found = t.replace("_", " ")
                    o = 2
                    continue
                elif t.lower().replace("_", " ").replace("infobox", "").strip() in all_infoboxes:
                    found = t.replace("_", " ").replace("infobox", "").strip()
                    o = 2
                    continue
                elif m.group(4):
                    pre.append(m.group(4))
                else:
                    pre.append(line)
            elif "[[File:" in line and not data.get("image"):
                data["image"] = line
            elif line.startswith("<!--") or "__NOTOC__" in line:
                pre.append(line)
            else:
                if line.strip():
                    done = True
                post.append(line)

    return data, pre, post, on_own_line, found, scroll_box


def extract_date(text):
    date_str = None
    m = re.search("\|(publish date|publication date|airdate|release date|released|published)=(\n\*)?(.*?)[<\n{]", text)
    if m and "Story reel" in m.group(3):
        m = re.search("\*Finished episode.*\n.*?([A-z]+ [0-9]+).*?([0-9]{4})", m.group(3))
    if m:
        date_str = m.group(3).replace("[", "").replace("]", "").replace("*", "").strip()
        date_str = re.sub("\[\[([A-Z][a-z][a-z]+)([A-z]+) ([0-9]+)\|\\1 \\3, ([0-9]+)\]\]", "\\1\\2 \\3, \\4", date_str)
        date_str = re.sub("^.*?([A-Za-z]+ [0-9]*?) ?( ?&[mn]dash; ?[A-Za-z]+( [0-9]+))?,? ([0-9]{4}).*", "\\1, \\4",
                          date_str)
    return date_str


REMAP = {
    "issue": "issues",
    "designer": "publisher",
    "artist": "penciller",
    "release date": "start date",
    "developer": "publisher",
    "media_type": "type",
    "prev": "previous",
    "card": "figures",
    "composer": "author",
}


def handle_infobox_on_page(text, page: Page, all_infoboxes):
    extract = True

    data, pre, post, on_own_line, found, scroll_box = parse_infobox(text, all_infoboxes)
    if scroll_box:
        print(f"Scroll box found in infobox; cannot parse {page.title()}")
        return text
    if not found or found.lower() not in all_infoboxes:
        print(f"ERROR: no infobox found, or infobox below body text; cannot parse {page.title()}")
        return text
    elif found.lower().startswith("year"):
        return text

    infobox = all_infoboxes.get(found.lower())
    if not infobox:
        print(f"ERROR: no infobox found for {found} on {page.title()}")
        return text
    if "pronouns" not in data:
        r = re.search("Category:Individuals with (.*?) pronous", text)
        data["pronouns"] = r.group(1) if r else ""

    i = -1
    for f in infobox.params:
        i += 1
        v = data.get(f)
        if not v or v == "new":
            if f == "not_appearance":
                continue
            if f == "title":
                v = data.get("name") or page.title()
            if f in REMAP.keys():
                # if data.get(REMAP[f]) != "new":
                v = data.get(REMAP[f]) or v
            elif f in REMAP.values():
                # x = [k for k, v in REMAP.items() if v == f and data.get(k) and data.get(k) != "new"]
                x = [k for k, v in REMAP.items() if v == f and data.get(k)]
                v = data.get(x[0] if x else '') or v
            if f == "release date" and found.lower().replace("_", " ") != "iu media":
                x = re.search("([Pp]ublished|[Rr]eleased|[Ii]ncluded|from) (in|on)? ?((\[*(January|February|March|April|May|June|July|August|September|October|November|December|fall|spring|winter|autumn)/?\]* ?)*?([0-9\[\], ]*)?(of )?\[*?[0-9]{4}\]*)",
                              text)
                if x:
                    v = x.group(3)
            if f == "published in" and found.lower().replace("_", " ") != "iu media":
                v = data.get("issue") or ''
                if re.search("\[\[(.*?) ([0-9]+)\|\\2( of .*?)?\]\]", v):
                    v = re.sub("\[\[(.*?) ([0-9]+)\|\\2( of .*?)?\]\]", "[[\\1 \\2|''\\1'' \\2]]", v)
                elif extract:
                    x = re.search(
                        "(published|adventure|released|article|supplement|appearing|appeare?[sd]|included|feature|department) (w?i?t?h?in|of|from) (\[\[(Fantasy Flight Games|De ?Agostini)\]\]'?s? )?(the )?(magazine )?(?P<t>'*\[\[.*?\]\]'*)",
                        text)
                    if not x:
                        x = re.search(
                            "written.* for (\[\[(Fantasy Flight Games|De ?Agostini)\]\]'?s? )?(the )?(magazine )?(?P<t>'*\[\[.*? [0-9]+(\|.*? [0-9]+'*?)?\]\]'*)",
                            text)
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
    new_infobox = ["{{" + current]
    i = -1
    for f in infobox.params:
        i += 1
        v = data.get(f)
        if v and (i + 1) < len(infobox.params) and f"|{infobox.params[i + 1]}=" in v and infobox.params[i + 1] not in data:
            print(f"Separating {f} line from {infobox.params[i + 1]}")
            v, x = v.split(f"|{infobox.params[i + 1]}=", 1)
            data[infobox.params[i + 1]] = x

        if f in infobox.combo and not v and any(i in data for i in infobox.groups[infobox.combo[f]] if i != f):
            continue
        elif f in infobox.optional and not v and f not in data:
            continue
        new_infobox.append(f"|{f}={v or ''}")

    if sum(i.count("{") - i.count("}") for i in new_infobox) > 0:
        # if on_own_line:
        new_infobox.append("}}")
        # else:
        #     new_infobox[-1] += "}}"

    new_text = "\n".join([*pre, *new_infobox, *post])
    if new_text.replace("\n}}", "}}") != page.get().replace("\n}}", "}}"):
        print(f"Found changes for {found} infobox")
    return "\n".join([*pre, *new_infobox, *post])
