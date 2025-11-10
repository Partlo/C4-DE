import re
import sys
import traceback
from datetime import datetime

from c4de.sources.archive import clean_archive_usages
from pywikibot import handle_args, pagegenerators, showDiff, input_choice


def analyze(*args):
    gen_factory = pagegenerators.GeneratorFactory()
    start_on, skip_start, skip_end, redo = None, None, None, None
    always = False
    for arg in handle_args(*args):
        gen_factory.handle_arg(arg.replace("::", ":"))
        if arg.startswith("-st:"):
            _, _, start_on = arg.replace('"', '').partition("-st:")
        if arg.startswith("-et:"):
            _, _, end_on = arg.replace('"', '').partition("-et:")
        if arg.startswith("-s1:"):
            _, _, skip_start = arg.replace('"', '').partition("-s1:")
        if arg.startswith("-s2:"):
            _, _, skip_end = arg.replace('"', '').partition("-s2:")
        if arg.startswith("-redo:"):
            _, _, redo = arg.replace('"', '').partition("-redo:")
        if "always" in arg.lower():
            always = True
    gen_factory.site.login(user="C4-DE Bot")
    if start_on:
        print(f"Starting on {start_on}")

    gen = pagegenerators.PreloadingGenerator(gen_factory.getCombinedGenerator(), groupsize=50)

    i = 0
    processed = []
    message = "Cleaning redundant archive date & URL values"
    archive_data = {}
    for page in gen:
        if page.title().startswith("Map:") or page.title() == "Forum:WPWeb:Template icons standardization":
            continue
        elif page.namespace().id == 2:
            continue
        elif page.title() in processed:
            continue
        else:
            processed.append(page.title())

        i += 1
        if i % 100 == 0:
            print(f"{i} -> {page.title()}")

        try:
            now = datetime.now()
            before = page.get(force=True)
            text = before.replace("{{SWArchive|subdomain=cargobay|url=webapps/cargobay/", "{{CargoBay|url=")
            text = (text.replace("Youtube", "YouTube").replace("|oldversion=}}", "}}").replace("|oldversion=|", "|")
                    .replace("|archivefile=}}", "}}").replace("|archivefile=|", "|")
                    .replace("|nolive=}}", "}}").replace("|nolive=|", "|")).replace("Unlimitedweb", "SWUweb")

            text, archive_data = clean_archive_usages(page, text, archive_data)
            text = text.replace("|title=''{{PAGENAME}}''}}", "|italics=1}}").replace("|domain=com|", "|").replace("|}}", "}}")
            text = re.sub(r"(\|[a-z]+)=[0-9]=", "\\1=", text)
            text = re.sub(r"(?<!WP)\|(.*?)( \(.*?\))\|\\1([|}])", r"|\\1\\2\\3", text)
            text = re.sub(r"((Armada|CCG|Destiny|FFGTCG|FFGXW|FFGXW2|ForceCollection|JKTCG|Legion|Merlin|MetallicImpressions|SWCT|SWGTCG|SWIA|SWMB|SWMiniCite|SWOR|SWPM|SWR|SWU|Shatterpoint|Smith's|TCG|TopTrumps|Topps|YJCCG)\|set=[^|\n{}]*?)(\|s?text=.*?)(\|.*?)?}}", r"\\1\\4}}", text)
            text = re.sub(r"(\|url=[^|{}\n]+?)/\|", "\\1|", text)
            text = re.sub(r"\|oldversion=1(\|.*?)?\|archivedate=", "\\1|oldversion=", text)
            text = re.sub(r"\|archivedate=(.*?)(\|.*?)?\|oldversion=1", "|oldversion=\\1\\2", text)
            text = text.replace("{{Scroll box", "{{ScrollBox").replace("{{Scroll_box", "{{ScrollBox")

            text = re.sub(r"(\{\{(SWMiniCite|Armada|Legion|FFGXW2?)\|[^\n{}]+?)\|link=[^\n{}|\[\]]*?(\|[^\n{}]*?)?}}", r"\\1\\3}}", text)
            text = re.sub(r"(\{\{(BuildR2Cite|BuildXWingCite|BuildFalconCite|FalconCite|HelmetCollectionCite|BustCollectionCite)\|[0-9]+\|[^{}\n]*?)\|[^{}\n]*?}}", r"\\1}}", text)

            # text = re.sub("\|release date=\n?\*(.*?)\n\*", "|release date=\\1\n|rereleased=*", text)
            # text = re.sub("\|release date=\n?\*(.*?)\n\*(.*?)\n\|(?!rereleased)", "|release date=\\1\n|rereleased=\\2\n|", text)
            # text = re.sub("(\|release date=(?!\*).*?)\n\|(?!rereleased)", "\\1\n|rereleased=\n|", text)
            if before.count("|archive") == text.count("|archive"):
                print(f"No changes found for {page.title()}")
                continue

            showDiff(before, text, context=1)
            if text == before:
                print(f"No changes found for {page.title()}")
                continue
            elif always:
                page.put(text, message, botflag=True)
                continue

            choice = input_choice(
                f'Do you want to accept these changes to {page.title()}?',
                [('Yes', 'y'), ('No', 'n'), ('All', 'a'), ('B', 'b'), ('Quit', 'q')],
                default='N')
            if choice == 'q':
                break
            if choice == 'y':
                page.put(text, message, botflag=True)
            if choice == 'a':
                page.put(text, message, botflag=True)
                always = True
            else:
                continue
        # except KeyboardInterrupt as e:
        #     quit()
        except Exception as e:
            traceback.print_exc()
            print(e)


if __name__ == "__main__":
    analyze(sys.argv)
