import codecs
import re
from typing import Set
import pywikibot
from pywikibot import pagegenerators, Page, textlib, Category

LAMBDA = lambda:0


class CanonLegendsSwitcher:
    def __init__(self):
        self.site = pywikibot.Site()
        self.accept_all = True
        self.editSummary = "Bot: Fixing redirects"

    def build_replacements(self, title):
        func = lambda s: s[:1].lower() + s[1:] if s else ''

        if "/Canon" in title:
            ct = title.replace('/Canon', '')
            repl = [
                ("\[\[%s/Canon\|''%s''(?P<suffix>[A-Za-z']+)\]\]" % (ct, ct),
                 lambda m: f"''[[{ct}]]''{m.group('suffix')}"),
                ("\[\[%s/Canon\|''%s''(?P<suffix>[A-Za-z']+)\]\]" % (func(ct), ct),
                 lambda m: f"''[[{ct}]]''{m.group('suffix')}"),
                ("\[\[%s/Canon\|%s(?P<suffix>[A-Za-z']+)\]\]" % (ct, ct),
                 lambda m: f"[[{ct}]]{m.group('suffix')}"),
                ("\[\[%s/Canon\|%s(?P<suffix>[A-Za-z']+)\]\]" % (func(ct), ct),
                 lambda m: f"[[{ct}]]{m.group('suffix')}"),
                ("\[\[%s/Canon\|%s(?P<suffix>[A-Za-z']+)\]\]" % (ct, func(ct)),
                 lambda m: f"[[{func(ct)}]]{m.group('suffix')}"),
                ("\[\[%s/Canon\|%s(?P<suffix>[A-Za-z']+)\]\]" % (func(ct), func(ct)),
                 lambda m: f"[[{func(ct)}]]{m.group('suffix')}"),
                (f"{{Main|{ct}/Canon}}", f"{{Main|{ct}}}"),
                (f"{{main|{ct}/Canon}}", f"{{Main|{ct}}}"),
                (f"{{ACprobe|{ct}/Canon|", f"{{ACprobe|{ct}/Canon|newpage={ct}|"),
                (f"{{ECprobe|{ct}/Canon|", f"{{ECprobe|{ct}/Canon|newpage={ct}|"),
                (f"{{Inqprobe|{ct}/Canon|", f"{{Inqprobe|{ct}/Canon|newpage={ct}|"),
                (f"[[{ct}/Canon|{ct}]]", f"[[{ct}]]"),
                (f"[[{func(ct)}/Canon|{ct}]]", f"[[{ct}]]"),
                (f"[[{ct}/Canon|{func(ct)}]]", f"[[{func(ct)}]]"),
                (f"[[{func(ct)}/Canon|{func(ct)}]]", f"[[{func(ct)}]]"),
                (f"[[{ct}/Canon|", f"[[{ct}|"),
                (f"[[{func(ct)}/Canon|", f"[[{ct}|")
            ]

        else:
            repl = [("\[\[%s\]\](?!'')(?P<suffix>[A-Za-z']+)" % title,
                     lambda m: f"[[{title}/Legends|{title}{m.group('suffix')}]]"),
                    ("\[\[%s\]\](?!'')(?P<suffix>[A-Za-z']+)" % func(title),
                     lambda m: f"[[{title}/Legends|{func(title)}{m.group('suffix')}]]"),
                    (f"[[{title}]]", f"[[{title}/Legends|{title}]]"),
                    (f"[[{func(title)}]]", f"[[{title}/Legends|{func(title)}]]"),
                    (f"[[{title}|", f"[[{title}/Legends|"),
                    (f"[[{func(title)}|", f"[[{title}/Legends|"),
                    (f"{{Main|{title}}}", f"{{Main|{title}/Legends}}"),
                    (f"{{main|{title}}}", f"{{Main|{title}/Legends}}"),
                    (f"{{ACprobe|{title}|", f"{{ACprobe|{title}|newpage={title}/Legends|"),
                    (f"{{ECprobe|{title}|", f"{{ECprobe|{title}|newpage={title}/Legends|"),
                    (f"{{Inqprobe|{title}|", f"{{Inqprobe|{title}|newpage={title}/Legends|"),
                    ]

        flags = re.UNICODE
        results = []
        for old, new in repl:
            if not isinstance(new, type(LAMBDA)):
                old = re.escape(old)
            old_r = re.compile(old, flags)
            results.append((old_r, new))
        return results

    def fix_redirects(self, text, replacements, rep=None):
        exceptions = []

        if rep:
            oldR = re.compile(re.escape(rep[0]), re.UNICODE)
            return textlib.replaceExcept(text, oldR, rep[1], exceptions)

        for old, new in replacements:
            text = textlib.replaceExcept(text, old, new, exceptions)

        return text

    def check_page(self, page, master_replacements, ghost=False):
        if page.isRedirectPage():
            target = page.getRedirectTarget()
            if "/Canon" in target.title():
                page.set_redirect_target(target_page=target.title().replace('/Canon', ''))
            else:
                page.set_redirect_target(target_page=target.title() + "/Legends")
            return True

        try:
            old_text = page.get()
            new_text = page.get()
        except pywikibot.exceptions.NoPageError:
            print(f"{page.title()} no longer exists")
            return False

        for target, replacements in master_replacements.items():
            new_text = self.fix_redirects(new_text, replacements)

            if new_text == old_text:
                continue
            elif self.accept_all:
                continue

            pywikibot.showDiff(old_text, new_text)
            choice = pywikibot.input_choice(
                u'Do you want to accept these changes to %s?' % page.title(),
                [['Yes', 'y'], ['No', 'n'], ['Edit', 'e'], ['All', 'a'], ['Quit', 'q']], 'N')
            if choice == 'q':
                return False
            if choice == 'a':
                self.accept_all = True
            if choice == 'e':
                err = pywikibot.input(u'Enter the target text:', )
                fix = pywikibot.input(u'Enter the target replacement:', )
                new_text = self.fix_redirects(old_text, [], rep=[err, fix])
            if choice == 'y':
                old_text = new_text

        try:
            if new_text != page.get():
                page.put(new_text, self.editSummary)
            elif ghost:
                page.put(old_text, "Bot: Ghost edit to update WhatLinksHere. Tell Cade if you see this.")
            else:
                pywikibot.output(u'No changes were necessary in %s' % page.title(as_link=True))
        except pywikibot.exceptions.PageSaveRelatedError as e:
            print(f"{page.title()}: {e}")

        return True


def do_work(fixer, titles, always):

    site = pywikibot.Site(user="RoboCade")
    site.login(user="RoboCade")

    main_pages = []
    legends_reference_names = set()
    legends_references = []
    legends_templates = {}
    legends_ghost = {}
    legends_replacements = {}

    canon_pages = []
    canon_reference_names = set()
    canon_references = []
    canon_templates = {}
    canon_ghost = {}
    canon_replacements = {}
    at_canon = {}
    for title in titles:
        main_page = pywikibot.Page(site, title)
        main_pages.append(main_page)
        at_legends = False
        at_canon[f"{title}/Canon"] = False
        try:
            legends_page = pywikibot.Page(site, f"{title}/Legends")
            legends_page.get()
            at_legends = True
        except pywikibot.exceptions.NoPageError:
            legends_page = main_page
        except pywikibot.exceptions.IsRedirectPageError:
            legends_page = main_page

        try:
            canon_page = pywikibot.Page(site, f"{title}/Canon")
            canon_page.get()
            at_canon[f"{title}/Canon"] = True
        except pywikibot.exceptions.NoPageError:
            canon_page = main_page
        except pywikibot.exceptions.IsRedirectPageError:
            canon_page = main_page
        canon_pages.append(canon_page)

        c = 0
        for p in main_page.backlinks(filter_redirects=True):
            if p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in legends_reference_names:
                    legends_references.append(p)
                c += 1
        for p in main_page.getReferences(follow_redirects=False):
            if p.namespace() == 2:
                continue
            elif p.namespace() == 10:
                print(main_page.title(), p.title())
                if p.title() not in legends_templates and p.title(with_ns=False) not in ["App", "RandomStatus", "ArticleShowcase", "Mainpage Box Showcase"]:
                    legends_templates[p.title()] = list(p.getReferences(follow_redirects=False))
                legends_ghost[title] = True
            elif p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in legends_reference_names:
                    legends_references.append(p)
                c += 1
        print(f"{title}: {c}")

        legends_replacements[title] = fixer.build_replacements(title)

        if not at_legends:
            try:
                legends_page.move(f"{title}/Legends", reason="/Legends /Canon switchover", movetalk=True, noredirect=True, movesubpages=False)
            except Exception as e:
                print(e)

        c = 0
        for p in pywikibot.Page(site, f"{title}/Canon").backlinks(filter_redirects=True):
            if p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in canon_reference_names:
                    canon_references.append(p)
                c += 1
        for p in pywikibot.Page(site, f"{title}/Canon").getReferences(follow_redirects=False):
            if p.namespace() == 2:
                continue
            elif p.namespace() == 10:
                if p.title() not in canon_templates:
                    canon_templates[p.title()] = list(p.getReferences(only_template_inclusion=True))
                canon_ghost[title] = True
            elif p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in canon_reference_names:
                    canon_references.append(p)
                c += 1
        print(f"{title}/Canon: {c}")

        canon_replacements[title] = fixer.build_replacements(f"{title}/Canon")

    # Handle templates for Legends pages
    handle_references(site=site, fixer=fixer, replacements=legends_replacements, templates=legends_templates, references=legends_references)

    for page in main_pages:
        c = 0
        for ref in page.getReferences(follow_redirects=False):
            if ref.namespace() != 2 and ref.title() not in [page.title(), f"{page.title()}/Canon", f"{page.title()}/Legends"]:
                c += 1
        print(f"{page.title()}: {c}")

    if not always:
        choice = pywikibot.input_choice(
            u'Proceed with moving /Canon pages?',
            [['Yes', 'y'], ['No', 'n']], 'n')
        if choice != 'y':
            return

    for page in canon_pages:
        if at_canon.get(page.title()):
            try:
                page.move(page.title().replace('/Legends/Canon', '/Canon').replace('/Canon', ''), reason="/Legends /Canon switchover", movetalk=True, noredirect=True, movesubpages=False)
            except Exception as e:
                print(e)
        else:
            print(f"{page.title()} already moved to main page")

    # Handle templates for Canon pages
    handle_references(site=site, fixer=fixer, replacements=canon_replacements, templates=canon_templates, references=canon_references)


def do_canon_work(fixer, titles):

    site = pywikibot.Site()

    canon_pages = []
    canon_reference_names = set()
    canon_references = []
    canon_templates = {}
    canon_ghost = {}
    canon_replacements = {}
    at_canon = {}
    for title in titles:
        main_page = pywikibot.Page(site, title)
        at_canon[f"{title}/Canon"] = False
        try:
            canon_page = pywikibot.Page(site, f"{title}/Canon")
            canon_page.get()
            at_canon[f"{title}/Canon"] = True
        except pywikibot.exceptions.NoPageError:
            canon_page = main_page
        canon_pages.append(canon_page)

        c = 0
        for p in pywikibot.Page(site, f"{title}/Canon").backlinks(filter_redirects=True):
            if p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in canon_reference_names:
                    canon_references.append(p)
                c += 1
        for p in pywikibot.Page(site, f"{title}/Canon").getReferences(follow_redirects=False):
            if p.namespace() == 2:
                continue
            elif p.namespace() == 10:
                if p.title() not in canon_templates:
                    canon_templates[p.title()] = list(p.getReferences(follow_redirects=False))
                canon_ghost[title] = True
            elif p.title() not in [title, f"{title}/Canon", f"{title}/Legends"]:
                if p.title() not in canon_reference_names:
                    canon_references.append(p)
                c += 1
        print(f"{title}/Canon: {c}")

        canon_replacements[title] = fixer.build_replacements(f"{title}/Canon")

    # Handle templates for Canon pages
    handle_references(site=site, fixer=fixer, replacements=canon_replacements, templates=canon_templates, references=canon_references)


def handle_references(*, site, fixer: CanonLegendsSwitcher, replacements: dict, templates: dict, references: list):
    # fixer.accept_all = False
    canon_template_refs = []
    for template, refs in templates.items():
        t = pywikibot.Page(site, template)
        fixer.check_page(t, replacements)
        for ref in refs:
            if ref.namespace() != 2 and ref.title() not in canon_template_refs:
                result = fixer.check_page(ref, replacements, True)
                if result:
                    canon_template_refs.append(ref.title())
                else:
                    print(ref.title())

    # fixer.accept_all = False

    for ref in references:
        result = fixer.check_page(ref, replacements)
        if not result:
            print(f"{ref.title()}")


def main(*args):
    text_file_name = None
    c = 50
    for arg in pywikibot.handle_args(*args):
        if arg.startswith('-filename'):
            text_file_name = arg[10:]
            if not text_file_name:
                text_file_name = pywikibot.input(u'Please enter the local file name:')
        if arg.startswith("-num:"):
            c = int(arg[5:])

    titles = []
    if text_file_name:
        with codecs.open(text_file_name, 'r', 'utf-8') as f:
            for title in f.readlines():
                titles.append(title.strip().replace('/Canon', ''))
                print(title.strip().replace('/Canon', ''))
    else:
        i = 0
        for page in Category(pywikibot.Site(), "Articles with /Canon").articles():
            if i < c:
                titles.append(page.title().replace('/Canon', ''))
                i += 1

    fixer = CanonLegendsSwitcher()

    do_work(fixer, titles, True)


if __name__ == "__main__":
    try:
        main()
    finally:
        pywikibot.stopme()
