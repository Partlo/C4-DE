import re
import pywikibot
from typing import Optional, Tuple

from c4de.common import log, error_log
from c4de.data.filenames import *


def read_version_info(target_version) -> Tuple[str, str]:
    """ Parses the version history file, and also extracts the updates for the current version. """
    changes = []
    text = []
    found = False
    with open(VERSION_HISTORY, "r") as f:
        for line in f.readlines():
            if found and line.startswith("*'''"):
                break
            elif found:
                changes.append(line.replace("**", "- ").replace("'''", "**"))
            elif f"*'''{target_version}'''" in line:
                found = True
            elif line:
                text.append(line.strip())

    if not found:
        pass
        # raise Exception("Version info not found!")

    z = "\n".join(changes)
    return re.sub("(\r?\n)+", "\n", z), "\n".join(text)


def report_version_info(site, version) -> Optional[str]:
    """ Updates User:JocastaBot/History with the new version info. """

    with open(OLD_VERSION_FILE, "r") as f:
        old_version = f.readline()

        if old_version is None:
            error_log("Not found!")
        elif old_version == version:
            return None

    updates, total = read_version_info(version)
    if updates:
        with open(OLD_VERSION_FILE, "w") as f:
            f.write(version)
        page = pywikibot.Page(site, "User:C4-DE Bot/History")
        page.put(total, "Updating C4-DE Bot changelog", botflag=False)
        return f"**C4-DE Bot: Version {version}**\n{updates}"
    else:
        return None
