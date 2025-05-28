import codecs
import re
import emoji
import json
import subprocess
import sys
import traceback
import time
import requests

import discord.errors
from urllib import parse
from typing import List, Tuple, Optional

from datetime import datetime, timedelta
from discord import Message, Game, Intents, HTTPException
from discord.abc import GuildChannel
from discord.channel import TextChannel, DMChannel
from discord.ext import commands, tasks
from asyncio.exceptions import TimeoutError
import ssl

from c4de.sources.parsing import fix_template_redirects

ssl._create_default_https_context = ssl._create_unverified_context

from pywikibot import Site, Page, Category, User, FilePage
from pywikibot.exceptions import NoPageError, LockedPageError, OtherPageSaveError

from c4de.common import log, error_log, archive_url
from c4de.data.filenames import *
from c4de.version_reader import report_version_info

from c4de.protocols.cleanup import archive_stagnant_senate_hall_threads, remove_spoiler_tags_from_page, \
    check_preload_for_missing_fields, check_infobox_category, clean_up_archive_categories
from c4de.protocols.edelweiss import run_edelweiss_protocol, calculate_isbns_for_all_pages
from c4de.protocols.rss import check_rss_feed, check_latest_url, check_wookieepedia_feeds, check_sw_news_page, \
    check_review_board_nominations, check_policy, check_consensus_duration, check_user_rights_nominations, \
    check_blog_list, check_ea_news, check_unlimited, check_ubisoft_news, compare_site_map, handle_site_map, \
    check_target_url, compile_tracked_urls, check_title_formatting, check_hunters_news, check_ilm

from c4de.sources.analysis import get_analysis_from_page
from c4de.sources.archive import create_archive_categories
from c4de.sources.build import analyze_target_page
from c4de.sources.domain import FullListData
from c4de.sources.engine import load_full_sources, load_full_appearances, load_remap, reload_auto_categories, \
    load_auto_categories, load_template_types, reload_templates
from c4de.sources.index import create_index, prepare_ordered_list
from c4de.sources.infoboxer import reload_infoboxes, load_infoboxes
from c4de.sources.updates import get_future_products_list, handle_results, search_for_missing

import logging

# noinspection PyUnresolvedReferences
logging.getLogger("discord").setLevel(logging.WARN)


SELF = 880096997217013801
CADE = 346767878005194772
MONITOR = 268478587651358721
MAIN = "wookieepedia"
COMMANDS = "other-commands"
REQUESTS = "bot-requests"
ANNOUNCEMENTS = "announcements"
ADMIN_REQUESTS = "admin-requests"
NOM_CHANNEL = "status-article-nominations"
REVIEW_CHANNEL = "status-article-reviews"
SOCIAL_MEDIA = "social-media-team"
UPDATES = "star-wars-news"
SITE_URL = "https://starwars.fandom.com/wiki"

THUMBS_UP = "👍"
THUMBS_DOWN = "👎"
TIMER = "⏲️"
EXCLAMATION = "❗"
STOP_SIGN = "🛑"
BOARD_EMOTES = {"EduCorps": "EC", "AgriCorps": "AC", "Inquisitorius": "Inq"}

# Readd Andor later
REPOSTS = ["Ahsoka", "Skeleton Crew", "Obi-Wan Kenobi", "Rebels", "Resistance", "The Clone Wars", "The Bad Batch",
           "Tales of the Empire", "Tales of the Jedi", "The Book of Boba Fett", "Visions",
           "The Phantom Menace", "Attack of the Clones", "Revenge of the Sith", "A New Hope", "The Empire Strikes Back",
           "Return of the Jedi", "The Force Awakens", "The Last Jedi", "The Rise of SKywalker",
           "Rogue One", "Rogue One: A Story"]


# noinspection PyPep8Naming
class C4DE_Bot(commands.Bot):
    """
    :type site: Site
    :type channels: dict[str, GuildChannel]
    :type emoji_storage: dict[str, int]
    :type rss_data: dict[str, dict]
    :type internal_rss_cache: dict[str, list[str]]
    :type external_rss_cache: dict[str, dict[str, list[str]]]
    :type board_nominations: dict[str, dict]
    :type policy_updates: dict[str, list[str]]
    :type rights_cache: dict[str, list[str]]
    :type appearances: FullListData
    :type sources: FullListData
    :type report_dm: discord.DMChannel
    """

    def __init__(self, *, rss_only=False, loop=None, **options):
        intents = Intents.default()
        intents.members = True
        super().__init__("", loop=loop, intents=intents, log_handler=None, **options)
        if rss_only:
            log("C4-DE online! (RSS Node)")
        else:
            log("C4-DE online! (Sources Node)")
        self.timezone_offset = 5

        self.rss_only = rss_only
        self.initial_run = True
        self.run_edelweiss = False
        self.rss_data = {}

        self.version = None
        with open(VERSION_FILE, "r") as f:
            self.version = f.readline()

        self.site = self.reload_site()
        self.refresh = 0

        self.admin_users = {
            "Imperators II": "Imperators",
            "Master Fredcerique": "MasterFred",
            "Zed42": "Zed"
        }
        self.bots = ["01miki10-bot", "C4-DE Bot", "EcksBot", "JocastaBot", "RoboCade", "PLUMEBOT", "TOM-E Macaron.ii"]

        self.channels = {}
        self.emoji_storage = {}

        self.ready = False
        self.should_archive = True

        self.report_dm = None

        with open(INTERNAL_RSS_CACHE, "r") as f:
            self.internal_rss_cache = json.load(f)

        with open(EXTERNAL_RSS_CACHE, "r") as f:
            self.external_rss_cache = json.load(f)

        with open(BOARD_CACHE, "r") as f:
            self.board_nominations = json.load(f)

        with open(POLICY_CACHE, "r") as f:
            self.policy_updates = json.load(f)

        with open(RIGHTS_CACHE, "r") as f:
            self.rights_cache = json.load(f)

        with open(ADMIN_CACHE, "r") as f:
            self.admin_messages = {int(k): v for k, v in json.load(f).items()}

        with open(EDELWEISS_CACHE, "r") as f:
            self.edelweiss_cache = json.load(f)

        with open(INDEX_CACHE, "r") as f:
            self.index_cache = json.load(f)

        self.overdue_cts = []
        self.project_data = {}
        self.files_to_be_renamed = []
        self.source_rev_ids = {}

        self.infoboxes = {}
        self.templates = {}
        self.disambigs = []
        self.redirect_messages = {}
        self.appearances = None
        self.sources = None
        self.remap = None
        self.auto_cats = []
        self.maintenance_cats = []

        self.last_ran = {}

    def reload_site(self):
        self.site = Site(user="C4-DE Bot")
        self.site.login()
        return self.site

    async def on_ready(self):
        log(f'C4-DE on as {self.user}!')

        self.report_dm = await self.get_user(CADE).create_dm()

        if self.version:
            await self.change_presence(activity=Game(name=f"C4-DE v. {self.version}"))
            log(f"Running version {self.version}")
        else:
            error_log("No version found")

        for c in self.get_all_channels():
            self.channels[c.name] = c

        for e in self.emojis:
            self.emoji_storage[e.name.lower()] = e.id

        await self.reload_rss_data()

        self.get_user_ids()

        if not self.ready:
            if self.rss_only:
                self.check_senate_hall_threads.start()
                self.check_consensus_statuses.start()
                self.check_membership_nominations.start()
                self.check_rights_nominations.start()
                self.check_policy.start()
                self.check_deleted_pages.start()
                self.check_files_to_be_renamed.start()
                self.check_bot_requests.start()

                self.check_spoiler_templates_and_cleanup.start()

                self.check_internal_rss.start()
                self.check_external_rss.start()
                self.check_altaya.start()
            else:
                try:
                    info = report_version_info(self.site, self.version)
                    if info:
                        await self.text_channel(ANNOUNCEMENTS).send(info)
                        await self.text_channel(COMMANDS).send(info)
                except Exception as e:
                    error_log(type(e), e)

                self.check_empty_usage_categories.start()
                self.check_future_products.start()
                self.run_canon_legends_switch.start()
                self.check_for_sources_rebuild.start()
                self.load_isbns.start()
                self.check_edelweiss.start()
                await self.build_sources()
                self.check_index_requests.start()
            log("Startup process completed.")
            self.ready = True

            # for message in await self.text_channel("star-wars-news").history(limit=25).flatten():
            #     if message.id == 1264945242130616444:
            #         await message.edit(content=message.content.replace("", "Battle of Jakku"))

    # noinspection PyTypeChecker
    def text_channel(self, name) -> TextChannel:
        try:
            return self.channels[name]
        except KeyError:
            return next(c for c in self.get_all_channels() if c.name == name)

    def emoji_by_name(self, name):
        if self.emoji_storage.get(name.lower()):
            return self.get_emoji(self.emoji_storage[name.lower()])
        return name

    def is_mention(self, message: Message):
        for mention in message.mentions:
            if mention == self.user:
                return True
        return "@C4-DE" in message.content or "<@&884871018567573605>" in message.content

    def get_user_ids(self):
        results = {}
        for user in self.text_channel(MAIN).guild.members:
            results[user.display_name.lower().replace("_", "").replace(" ", "")] = user.id
        return results

    def get_user_id(self, editor, user_ids=None):
        if not user_ids:
            user_ids = self.get_user_ids()
        z = editor.replace("_", "").replace(" ", "")
        user_id = user_ids.get(self.admin_users.get(editor, z.lower()), user_ids.get(z.lower()))
        return f"<@{user_id}>" if user_id else editor

    async def report_error(self, command, text, *args):
        try:
            await self.report_dm.send(f"Command: {command}")
            await self.report_dm.send(f"ERROR: {text}\t{args}")
        except Exception:
            error_log(text, *args)

    rss_commands = {
        "is_check_target_command": "handle_target_url_check",
        "is_archive_url_command": "handle_archive_url_command",
        "is_record_url_command": "handle_record_source_command",
    }
    rss_command_search = {
        "ghost touch": "ghost_touch",
        "rss": "check_internal_rss",
        "load web": "save_web_sources",
        "clean bot requests": "check_bot_requests",
        "clear bot requests": "check_bot_requests",
    }

    source_commands = {
        "is_reload_command": "handle_reload_command",
        "is_single_preload_command": "handle_single_preload_command",
        "is_preload_command": "handle_preload_command",
        "is_user_eligibility_command": "handle_user_eligibility_command",
        "is_analyze_source_command": "handle_analyze_source_command",
        "is_create_index_command": "handle_create_index_command",
        "is_create_list_command": "handle_create_list_command",
    }
    source_command_search = {
        "create archive categor": "create_archive_categories",
        "recheck nominations": "recheck_nominations",
        "rebuild sources": "build_sources",
        "reload sources": "build_sources",
        "future products": "handle_future_products",
    }

    @staticmethod
    def is_new_nomination_message(message: Message):
        m = re.search("New .*? article nomination.*? by \**(.*?)\**:", message.content)
        if m:
            u = re.search("/wiki/Wookieepedia:.*?_article_nominations/(.*?)(_\(.*?nomination\))?>", message.content)
            if u:
                return {"user": m.group(1), "article": u.group(1)}
        m = re.search("New review.*? requested for .*?(Featured|Good|Comprehensive) article: \[(.*?)\].*?$", message.content)
        if m:
            return {"user": None, "article": m.group(2)}
        return None

    async def on_message(self, message: Message):
        if message.author == self.user:
            return
        elif isinstance(message.channel, DMChannel):
            await self.handle_direct_message(message)
            return
        elif not self.rss_only and message.author.id == 863199002614956043 and (message.channel.name == NOM_CHANNEL or message.channel.name == REVIEW_CHANNEL):
            nom = self.is_new_nomination_message(message)
            if nom:
                await self.handle_new_nomination(message, nom)
            return
        elif not (self.is_mention(message) or "@C4DE" in message.content or "@C4-DE" in message.content):
            return

        log(f'Message from {message.author} in {message.channel}: [{message.content}]')

        if "Hello!" in message.content:
            await message.channel.send("Hello there!")
            return

        if self.rss_only:
            done = await self.handle_rss_node_commands(message, False)
            if not done:
                await self.check_command_handlers(message, self.rss_commands, self.rss_command_search)
        else:
            done = await self.handle_commands(message, False)
            if not done:
                await self.check_command_handlers(message, self.source_commands, self.source_command_search)

    async def check_command_handlers(self, message: Message, fnc: dict, terms: dict):
        for identifier, handler in fnc.items():
            command_dict = getattr(self, identifier)(message)
            if command_dict:
                await getattr(self, handler)(message, command_dict)
                return

        for term, handler in terms.items():
            if term in message.content.lower():
                await getattr(self, handler)(message)
                if not any("bb8thumbsup" in str(r.emoji) for r in message.reactions):
                    await message.add_reaction(THUMBS_UP)
                return

    async def handle_direct_message(self, message: Message):
        print(f"DM: {message.author}: {message.content}")
        if self.rss_only:
            await self.handle_rss_node_commands(message, True)
            return

        if "recheck nominations" in message.content:
            await self.recheck_nominations()
            return

        if message.author.id != CADE:
            return

        if message.content == "end" or message.content == "kill":
            sys.exit()

        match = re.search("analyze message: ([0-9]+)", message.content)
        if match:
            message_id = int(match.group(1))
            for m in await self.text_channel(NOM_CHANNEL).history(limit=200).flatten():
                if m.id == message_id:
                    nom = self.is_new_nomination_message(m)
                    if nom:
                        await self.handle_new_nomination(m, nom)
                    break
            for m in await self.text_channel(REVIEW_CHANNEL).history(limit=200).flatten():
                if m.id == message_id:
                    nom = self.is_new_nomination_message(m)
                    if nom:
                        await self.handle_new_nomination(m, nom)
                    break
            return

        await self.handle_commands(message, True)

        match = re.search("delete messages? in #(?P<channel>.*?): (?P<ids>[0-9, ]+)", message.content)
        if match:
            await self.delete_message(match.groupdict()['ids'], match.groupdict()['channel'])
            return

        match = re.search("message #(?P<channel>.*?): (?P<text>.*?)$", message.content)
        if match:
            channel = match.groupdict()['channel']
            text = match.groupdict()['text'].replace(":star:", "🌠")

            try:
                await self.text_channel(channel).send(text)
            except Exception as e:
                await self.report_error(message.content, type(e), e)

    async def recheck_nominations(self, _=None):
        for m in await self.text_channel(NOM_CHANNEL).history(limit=200).flatten():
            if m.author.id == 863199002614956043 and not any("bb8thumbsup" in str(r.emoji) for r in m.reactions):
                nom = self.is_new_nomination_message(m)
                if nom:
                    await self.handle_new_nomination(m, nom)
        return

    async def delete_message(self, id_string, channel):
        message_ids = [i.strip() for i in id_string.split(",")]
        for message in await self.text_channel(channel).history(limit=30).flatten():
            if str(message.id) in message_ids:
                await message.delete()
                time.sleep(2)

    async def handle_rss_node_commands(self, message: Message, dm):
        channel = self.text_channel("bot-requests") if dm else message.channel
        if "edelweiss" in message.content.lower():
            self.run_edelweiss = False
            messages, _ = run_edelweiss_protocol(self.site, self.edelweiss_cache)
            for m in messages:
                await channel.send(m)
            return True

        if "double redirect" in message.content.lower():
            await message.add_reaction(TIMER)
            self.update_unused_files()
            self.fix_double_redirects()
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(THUMBS_UP)
            return True

        if "spoiler" in message.content.lower():
            tv_dates, default_show = self.extract_tv_spoiler_data()
            for page in Category(self.site, "Articles with expired spoiler notices").articles(namespaces=0):
                try:
                    remove_spoiler_tags_from_page(self.site, page, tv_dates, default_show, offset=self.timezone_offset)
                except Exception as e:
                    error_log(f"Encountered {type(e)} while removing spoiler template from {page.title()}", e)
                    await self.text_channel(COMMANDS).send(f"Encountered {type(e)} while removing expired spoiler template from {page.title()}. Please check template usage for anomalies.")
            return True
        return False

    async def handle_commands(self, message: Message, dm):
        if self.rss_only:
            return await self.handle_rss_node_commands(message, dm)

        if "list all commands" in message.content and not self.rss_only:
            await self.update_command_messages()
            return True

        if "traverse media" in message.content.lower() or "search for missing" in message.content.lower():
            await message.add_reaction(TIMER)
            await self.handle_missing_search()
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(THUMBS_UP)
            return True

        if "isbn" in message.content.lower():
            page = Page(self.site, "Template:ISBN/data")
            last_revision = next(r for r in page.revisions(reverse=True, total=10) if r["user"] == "JocastaBot")
            time_since_last_edit = (datetime.now() + timedelta(hours=self.timezone_offset)) - last_revision['timestamp']
            if time_since_last_edit.total_seconds() < (60 * 60 * 6):
                print(time_since_last_edit.total_seconds(), 60 * 60 * 6)
                log(f"Skipping ISBN reload, last edit was {last_revision['timestamp']}, {datetime.now()}")
                return
            print("Loading ISBNs")
            calculate_isbns_for_all_pages(self.site)
            return True

        return False

    def list_commands(self):
        text = [
            f"Current C4DE Commands (v. {self.version}):",
            f"- **@C4-DE analyze sources for <article> (with date)** - runs the target article through the Source Engine, sorting sources and appearances and standardizing formatting. Including 'with date' will cause it to include the release date in comments.",
            f"- **@C4-DE create index for <article>** - runs analysis for the target article and uses that to create an index page, or updates the existing one if it exists.",
            f"- **@C4-DE create list for <article>** - runs analysis for the target article and uses that to create a list of all Appearances and Sources, sorted chronologically by release date. Currently writes to User:C4-DE Bot/Timeline Request.",
            f"- **@C4-DE rebuild sources** - rebuilds the Source Engine's internal data from the Sources Project pages on Wookieepedia."
            f"- **@C4-DE reload data** - reloads data from User:C4-DE/RSS and User:JocastaBot/Project Data",
            f"- **@C4-DE Edelweiss** - analyzes Edelweiss publishing catalog and reports new items or changes (runs at 8 AM CST)",
            f"- **@C4-DE ISBN** - updates Template:ISBN/data with the ISBNs present in all articles (runs at 7 AM CST)",
            f"- **@C4-DE spoiler** - removes expired spoiler notices from articles (runs at 6 AM CST)",
            f"- **@C4-DE check preloads** - checks all infobox preloads for missing fields, and also reports fields missing from InfoboxParamCheck",
        ]

        text2 = [
            f"- **@C4-DE record Template:<name> <url>** - records a given URL in the Masterlist. The Template: prefix is not required for recognized sites such as SW.com, and a custom date can be given with (YYYY-MM-DD) following the URL."
            f"- **@C4-DE archive Template:<name> <url>** - attempts to archive the given URL in the Wayback Machine, and records the archivedate in the corresponding ArchiveAccess if successful."
            f"- **@C4-DE check target URL: <url>** - mass-record command for episode guide pages on StarWars.com, which checks all subpages and linked Databank entries. Please ask before using.",
            f"- **@C4-DE check preload for Template:<template>** - checks a particular infobox and its preload",
            f"- **@C4-DE update preload for Template:<template>** - checks a particular infobox and its preload, and updates the preload with the missing parameters. Does not change the parameters in InfoboxParamCheck.",
            f"- **@C4-DE create archive categories for Template:<template>** - creates the ArchiveAccess maintenance categories for a given citation template."
            f"- **@C4-DE ghost touch Category:<category>** - ghost-edits (saves with no changes) pages in the category to force an update."
        ]

        related = [
            "**Additional Protocols:**",
            f"- Reports new Senate Hall and Administrator's Noticeboard threads, Consensus Track and Trash Compactor "
            f"votes, file rename requests, and articles flagged for deletion to #announcements and #admin-requests. "
            f"(runs every 5 minutes)",
            f"- Checks the RSS feeds of a variety of sites, such as StarWars.com and SWTOR.com, and reports new "
            f"articles to #star-wars-news",
            f"- Archives stagnant Senate Hall threads (runs every 4 hours)",
            f"- Reports new policy and consensus changes",
            f"- Reports new nominations for user rights and board memberships",
            f"- Updates Special:UnusedFiles every morning, and flags maintenance categories as empty/non-empty on an hourly basis",
            f"**Additional Info (contact Cade if you have questions):**",
            f"- RSS feed configuration JSON: {SITE_URL}/User:C4-DE/RSS",
        ]

        return {1367547381607829534: "\n".join(text), 1367547382413398066: "\n".join(text2), 1367547383650586654: "\n".join(related)}

    async def update_command_messages(self):
        posts = self.list_commands()
        pins = await self.text_channel(COMMANDS).pins()
        target = None
        for post in pins:
            if post.id in posts:
                await post.edit(content=posts[post.id])
            if post.id == 1367547381607829534:
                target = post

        if target:
            await target.reply("**Commands have been updated! Please view this channel's pinned messages for more info.**")

    async def save_web_sources(self, message):
        log("Loading web sources file")
        try:
            by_year = {"Unknown": [], "Current": [], "Special": []}
            with codecs.open("C:/Users/cadec/Documents/projects/C4DE/web.txt", mode="r", encoding="utf-8") as f:
                for i in f.readlines():
                    d, c = i.split("\t", 1)
                    if "®" not in i and "™" not in i and emoji.emoji_count(i) > 0:
                        by_year["Special"].append(f"{d} {c}")
                    elif d.startswith("1") or d.startswith("2"):
                        y = d[:4]
                        if y not in by_year:
                            by_year[y] = []
                        by_year[y].append(f"{d} {c}")
                    elif d.startswith("Current"):
                        by_year["Current"].append(f"{d} {c}")
                    else:
                        by_year["Unknown"].append(f"{d} {c}")

            for k, v in by_year.items():
                p = Page(self.site, f"Wookieepedia:Sources/Web/{k}")
                t = p.get() if p.exists() else ""
                c = len(t.splitlines())
                log(f"{len(v)} sources found for {k}; currently {c - 1} are listed")
                text = ("{{Wookieepedia:Sources/Web/Header}}\n" + "\n".join(f"*{i}".strip() for i in sorted(v))).replace("\n\n", "\n")
                if text != t:
                    p.put(text, "Updating sources list", botflag=False)
            await message.add_reaction(THUMBS_UP)
        except Exception as e:
            error_log(type(e), e)

    async def create_archive_categories(self, message: Message, _=None):
        match = re.search("create archive categor[yies]* for (Template:.*?)$", message.content)
        if match:
            await message.add_reaction(TIMER)
            p = Page(self.site, match.group(1).strip())
            if not p.exists():
                await message.add_reaction(EXCLAMATION)
                return
            create_archive_categories(self.site, p.title(with_ns=False))
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(THUMBS_UP)
            return
        else:
            await message.add_reaction(EXCLAMATION)

    async def ghost_touch(self, message: Message):
        match = re.search("[Gg]host touch (-ref:|-cat:|Category:)?(.*?)$", message.content)
        if match:
            await message.add_reaction(TIMER)
            if match.group(1) == "Category:":
                category = Category(self.site, match.group(2))
                if not category.exists():
                    await message.add_reaction(EXCLAMATION)
                    return
                articles = category.articles()
            elif match.group(1) == "-ref:":
                p = Page(self.site, match.group(2))
                articles = p.backlinks(follow_redirects=False)
            else:
                articles = [Page(self.site, match.group(2))]
            for page in articles:
                try:
                    text = page.get()
                    page.put(text, "Bot: Ghost edit to update WhatLinksHere. Tell Cade if you see this.", botflag=False)
                except NoPageError:
                    continue
                except LockedPageError:
                    continue
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(THUMBS_UP)
            return
        else:
            await message.add_reaction(EXCLAMATION)

    @staticmethod
    def is_reload_command(message: Message):
        return "reload data" in message.content

    async def handle_reload_command(self, message: Message, _):
        await self.reload_rss_data()
        await message.add_reaction(THUMBS_UP)

    async def reload_rss_data(self):
        log("Loading RSS data")
        page = Page(self.site, "User:C4-DE Bot/RSS")
        data = {}
        for rev in page.revisions(content=True, total=5):
            try:
                data = json.loads(rev.text.replace("<pre>", "").replace("</pre>", ""))
            except Exception as e:
                await self.report_error("RSS Reload", type(e), e)
            if data:
                log(f"Loaded valid data from revision {rev.revid}")
                break
        if not data:
            raise Exception("Cannot load RSS data")
        self.rss_data = data

    async def reload_project_data(self):
        log("Loading news filters")
        page = Page(self.site, "User:JocastaBot/Project Data")
        data = {}
        for rev in page.revisions(content=True, total=5):
            try:
                data = json.loads(rev.text)
            except Exception as e:
                await self.report_error("RSS Reload", type(e), e)
            if data:
                log(f"Loaded valid data from revision {rev.revid}")
                break
        if not data:
            raise Exception("Cannot load RSS data")
        self.project_data = data

    def reload_infoboxes(self):
        log("Loading infoboxes")
        self.infoboxes = reload_infoboxes(self.site)

    def reload_templates(self):
        self.templates = reload_templates(self.site)

    def reload_auto_categories(self):
        self.auto_cats = reload_auto_categories(self.site)

    def reload_maintenance_categories(self):
        self.maintenance_cats = [c.title() for c in Category(self.site, f"Category:Articles with maintenance templates").subcategories()]
        for cx in ["High", "Medium", "Low"]:
            self.maintenance_cats += [c.title() for c in Category(self.site, f"Category:{cx}-priority template and page issues").subcategories()]
            self.maintenance_cats += [c.title() for c in Category(self.site, f"Category:{cx}-priority template and page issues/Empty").subcategories()]

        self.maintenance_cats = [c for c in self.maintenance_cats if not c.startswith("Unrecognized listing")]

    async def handle_initial_redirect_request(self, message: Message, command: dict):
        redirect_name = command['redirect']
        target_name = command['target']

        redirect = Page(self.site, redirect_name)
        target = Page(self.site, target_name)
        if not target.exists():
            await message.channel.send(f"Requested target page {target.title()} does not exist.")
            return

        rlc, rlc2 = 0, 0
        for i in redirect.backlinks(follow_redirects=False):
            if i.namespace() in [1, 2, 3, 100]:
                rlc2 += 1
            else:
                rlc += 1

        tlc, tlc2 = 0, 0
        for i in target.backlinks(follow_redirects=False):
            if i.namespace() in [1, 2, 3, 100]:
                tlc2 += 1
            else:
                tlc += 1

        if (rlc + rlc2) == 0:
            await message.channel.send(f"No pages link to specified redirect [{redirect_name}]")
            return
        elif rlc == 0:
            await message.channel.send(f"No editable pages link to specified redirect [{redirect_name}]; {rlc2} links found in User, Talk or Forum namespaces")
            return

        response = [
            f"Redirect: <{redirect.full_url().replace('%2F', '/').replace('%3A', ':')}>",
            f"- {rlc} fixable links found; {rlc2} links found in User, Talk, or Forum namespaces",
            f"Target: <{target.full_url().replace('%2F', '/').replace('%3A', ':')}>",
            f"- {tlc} fixable links found; {tlc2} links found in User, Talk, or Forum namespaces"
            f"Replacements:",
            f"- `[[{redirect.title()}]]` to `[[{target.title()}]]`",
            f"- `[[{redirect.title()}|` to `[[{target.title()}|`",
            "React to this last message with :bb8thumsup: to proceed."
        ]

        contents = []
        for r in response:
            if len(contents) == 0 or (len(r) + len(contents[-1])) >= 500:
                contents.append(r)
            else:
                contents[-1] = contents[-1] + r

        messages = [await message.channel.send(c) for c in contents]
        self.redirect_messages[messages[-1].id] = (message.channel.name, redirect.title(), target.title(), f"""-ref:"{redirect.title()}" "[[{redirect.title()}]]" "[[{target.title()}]]" "[[{redirect.title()}|" "[[{target.title()}|" """)

    @tasks.loop(minutes=2)
    async def handle_redirect_confirmations(self):
        if not self.redirect_messages:
            return
        for message_id, (channel_name, redirect, target, cmd) in self.redirect_messages.items():
            channel = self.text_channel(channel_name)
            for message in channel.history(limit=250).flatten():
                if message.id == message_id:
                    if any("bb8thumbsup" in str(r.emoji) for r in message.reactions):
                        subprocess.run(f"""cd C:/Users/cadec/Documents/projects/C4DE/robo & C:/Users/cadec/Envs/C4DE/Scripts/python replace.py {cmd} -summary:"Redirect fixes" -always""", shell=True)
                        await channel.send(f"Beginning replacement for {redirect} --> {target}")
                        self.redirect_messages.pop(message.id)

    @staticmethod
    def is_user_eligibility_command(message: Message):
        match = re.search("check (user )?(vote ?count|eligi?bi?li?ty) (for )?User:(?P<user>.*?)$", message.content)
        if match:
            return match.groupdict()
        return None

    async def handle_user_eligibility_command(self, message: Message, command: dict):
        u = command['user']
        if not u.startswith("User:"):
            u = "User:" + u
        count = 0
        now = datetime.utcnow()
        await message.add_reaction(TIMER)
        for p, i, t, _ in User(self.site, u).contributions(namespaces=0):
            if count >= 50:
                break
            elif (now - t).days > 180:
                break
            elif not p.exists() or p.isRedirectPage():
                continue
            for r in p.revisions(reverse=True):
                if i == r['revid']:
                    if 'mw-reverted' not in r['tags']:
                        count += 1
                    break

        if count >= 50:
            await message.add_reaction(THUMBS_UP)
        else:
            await message.add_reaction(THUMBS_DOWN)
            await message.channel.send(f"User {u} has only {count} edits")

    @tasks.loop(minutes=60)
    async def run_canon_legends_switch(self):
        now = datetime.now()
        if not (now.weekday() == 0 and now.hour == 4):
            return

        category = Category(self.site, "Category:Articles with /Canon")
        messages = [f"Beginning Canon/Legends swap for {len(list(category.articles()))} articles:", ""]
        for page in category.articles():
            y = f"- {page.title()}"
            if len(y) + len(messages[-1]) > 500:
                messages.append(y)
            else:
                messages[-1] += f"\n{y}"

        for m in messages:
            await self.text_channel("admin-help").send(m)
        subprocess.run(f"""cd C:/Users/cadec/Documents/projects/C4DE/robo & C:/Users/cadec/Envs/C4DE/Scripts/python switch_canon_legends.py""", shell=True)

    @staticmethod
    def is_single_preload_command(message: Message):
        return "preload for Template:" in message.content

    async def handle_single_preload_command(self, message: Message, _):
        apply = "update" in message.content
        r = re.search("(Template:[A-z ]+)$", message.content)
        if r:
            template = r.group(1)
            preload, check = check_preload_for_missing_fields(self.site, Page(self.site, template), apply)
            if preload and apply:
                await message.channel.send(f"Added fields to preload: {preload}")
            elif preload:
                await message.channel.send(f"Preload for {template} missing fields: {preload}")
            if check:
                await message.channel.send(f"The following fields are missing from InfoboxParamCheck: {check}")
            await message.add_reaction(THUMBS_UP)
        else:
            await message.add_reaction(EXCLAMATION)

    @staticmethod
    def is_preload_command(message: Message):
        return "check preloads" in message.content

    async def handle_preload_command(self, message: Message, _):
        await message.add_reaction(TIMER)
        preload, check = check_infobox_category(self.site)
        content = []
        for template, fields in preload.items():
            content.append(f"Preload for {template} missing fields: {fields}")
        for template, fields in check.items():
            content.append(f"InfoboxParamCheck in {template} missing fields: {fields}")
        if content:
            messages = [""]
            for c in content:
                if len(messages[-1] + c) > 1000:
                    messages.append(c)
                else:
                    messages[-1] += f"\n{c}"
            for m in messages:
                await message.channel.send(m)
        else:
            await message.channel.send("No updates required")
        await message.remove_reaction(TIMER, self.user)
        await message.add_reaction(THUMBS_UP)

    async def build_sources(self, _=None):
        try:
            for p in Category(self.site, "Category:Wookieepedia Sources Project").articles():
                self.source_rev_ids[p.title()] = p.latest_revision_id
            self.templates = load_template_types(self.site)
            self.auto_cats = load_auto_categories(self.site)
            self.infoboxes = load_infoboxes(self.site)
            self.disambigs = [p.title() for p in Category(self.site, "Disambiguation pages").articles() if "(disambiguation)" not in p.title()]
            self.appearances = load_full_appearances(self.site, self.templates, False)
            self.sources = load_full_sources(self.site, self.templates, False)
            self.remap = load_remap(self.site)

            self.build_missing_page()
        except Exception as e:
            traceback.print_exc()
            await self.report_error("Sources rebuild", type(e), e)

    def build_missing_page(self):
        skip = [c.title() for c in Category(self.site, "Category:Real-world attractions").articles(recurse=True)]
        skip += [c.title() for c in Category(self.site, "Category:Real-world arcade games").articles()]
        skip += [c.title() for c in Category(self.site, "Category:Mobile games").articles(recurse=True)]
        skip += [c.title() for c in Category(self.site, "Category:Web-based games").articles()]
        skip += [c.title() for c in Category(self.site, "Category:Commercials").articles()]
        skip += [c.title() for c in Category(self.site, "Category:RPGA adventures").articles()]

        page = Page(self.site, "User:C4-DE Bot/Canon Missing")
        text = "" if not page.exists() else page.get()
        pages1, pages2 = [], []
        for i in self.appearances.no_canon_index:
            (pages2 if i.target in skip else pages1).append(i)

        new_text = "\n".join(f"#{x.date}: {x.original}" for x in pages1)
        if pages2:
            new_text += "\n\n==Other==\n"
            new_text += "\n".join(f"#{x.date}: {x.original}" for x in pages2)

        if new_text != text:
            page.put(new_text, "Recording items missing from the canon media timeline", botflag=False)

        page = Page(self.site, "User:C4-DE Bot/Legends Missing")
        text = "" if not page.exists() else page.get()
        pages1, pages2 = [], []
        for i in self.appearances.no_legends_index:
            (pages2 if i.target in skip else pages1).append(i)

        ex_rpg = [c.title() for c in Category(self.site, "Category:West End Games adventure supplements").articles()]
        main, fiction, rpg = [], [], []
        for x in pages1:
            if x.target in ex_rpg:
                rpg.append(f"#{x.date}: {x.original}")
            elif x.template in ["WEGCite", "DarkStryder", "JournalCite", "GamerCite", "LivingForce", "WizCite", "WizardsCite", "FFG", "FFGXW", "DoD"]:
                rpg.append(f"#{x.date}: {x.original}")
                # rpg.append(f"#{x.date}: {x.timeline or 'N/A'}: {x.original}")
            else:
                main.append(f"#{x.date}: {x.original}")
                # main.append(f"#{x.date}: {x.timeline or 'N/A'}: {x.original}")

        nt = ["\n".join(main)]
        if rpg:
            nt.append("==RPG==\n" + "\n".join(rpg))
        if pages2:
            nt.append("==Other==\n" + "\n".join(f"#{x.date}: {x.original}" for x in pages2))
        new_text = re.sub("\|reprint=[A-z0-9]+", "", "\n\n".join(nt))
        if new_text != text:
            page.put(new_text, "Recording items missing from the Legends media timeline", botflag=False)

    def have_sources_changed(self):
        for p in Category(self.site, "Category:Wookieepedia Sources Project").articles():
            if p.title() in self.source_rev_ids and p.latest_revision_id != self.source_rev_ids[p.title()]:
                return True

    @tasks.loop(minutes=30)
    async def check_for_sources_rebuild(self):
        try:
            log("Checking for source changes")
            if self.have_sources_changed():
                await self.build_sources()
        except Exception as e:
            traceback.print_exc()
            await self.report_error("Sources rebuild", type(e), e)

    @staticmethod
    def is_create_list_command(message: Message):
        match = re.search("(create|generate|build) [Ll]ist (for )?(?P<article>.*?)$", message.content)
        if match:
            return match.groupdict()
        return None

    @staticmethod
    def is_create_index_command(message: Message):
        match = re.search("(create|generate|build) [iI]ndex (for )?(?P<article>.*?)$", message.content)
        if match:
            return match.groupdict()
        return None

    @staticmethod
    def is_check_target_command(message: Message):
        match = re.search("check target URLs?( and archive)?: <?(?P<url>.*?starwars\.com.*?)>?$", message.content)
        if match:
            return match.groupdict()
        return None

    @staticmethod
    def is_archive_url_command(message: Message):
        match = re.search("archive( URL)?( (with )?[Tt]emplate:(?P<template>.*?))?:? <?(?P<url>(https?.*?//)?[^ \n]+?)>?( \((?P<date>[0-9X-]+)\))?$", message.content)
        if match:
            return match.groupdict()
        return None

    @staticmethod
    def is_record_url_command(message: Message):
        match = re.search("record( URL)?( (with )?[Tt]emplate:(?P<template>.*?))?:? <?(?P<url>(https?.*?//)?[^ \n]+?)>?( \((?P<date>[0-9X-]+)\))?$", message.content)
        if match:
            return match.groupdict()
        return None

    @staticmethod
    def is_analyze_source_command(message: Message):
        match = re.search("([Aa]naly[zs]e|[Bb]uild|[Cc]heck) sources? (for |on )?(?P<article>.*?)(?P<date> with dates?)?(?P<text> (by|and|with) text)?$", message.content)
        if match:
            return match.groupdict()
        return None

    async def handle_new_nomination(self, message: Message, command: dict):
        try:
            a = command['article'].replace('*', '')
            target = Page(self.site, a)
            if not target.exists():
                await message.add_reaction(EXCLAMATION)
                await message.reply(f"{a} does not exist, cannot run source analysis")
                return
            if any(c.title() == "Category:Real-world articles" for c in target.categories()):
                log(f"Skipping Source Engine processing of real-world article {a}")
                return

            rev_id = target.latest_revision_id
            old_text = target.get()

            await message.add_reaction(TIMER)
            old_text, redirects = fix_template_redirects(target, old_text)
            results = analyze_target_page(target, self.infoboxes, self.templates, self.disambigs, self.appearances,
                                          self.sources, self.auto_cats, self.remap, old_text=old_text,
                                          save=True, include_date=False, use_index=True, redirects=redirects)
            mc = "\n".join([f"- {c.title()}" for c in target.categories() if c.title() in self.maintenance_cats])
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(self.emoji_by_name("bb8thumbsup"))
            if mc:
                await message.reply(f"Maintenance categories detected on nomination:\n{mc}")

            revs = [r for r in target.revisions(content=False, total=3) if r.user == "C4-DE Bot"]
            if not revs or revs[0].revid <= rev_id:
                return

            current_text = target.get(force=True)
            url = f"<{target.full_url()}?diff=next&oldid={rev_id}>"
            if self.flatten_text(current_text) == self.flatten_text(old_text):
                log(f"No major changes found for article: {target.title()}")
                return
            elif command['user']:
                user_ids = self.get_user_ids()
                user_str = self.get_user_id(command['user'], user_ids)
                await message.reply(f"{user_str}: Sources Engine [found changes needed for this article]({url}); please review when you get a chance")
            else:
                await message.reply(f"Sources Engine [found changes needed for this article]({url}); please review")
            for o in results:
                await message.reply(o)
        except Exception as e:
            error_log(type(e), e)
            await self.report_error("Analyze sources on new nomination", type(e), e)
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(EXCLAMATION)
            await message.channel.send("Encountered error while analyzing page")

    async def handle_analyze_source_command(self, message: Message, command: dict):
        try:
            target = Page(self.site, command['article'])
            if not target.exists():
                await message.add_reaction(EXCLAMATION)
                await message.channel.send(f"{command['article']} cannot be found")
                return
            if target.isRedirectPage():
                target = target.getRedirectTarget()
            rev_id = target.latest_revision_id
            use_date = command.get('date') is not None
            use_index = command.get('text') is None

            await message.add_reaction(TIMER)
            results = analyze_target_page(target, self.infoboxes, self.templates, self.disambigs, self.appearances,
                                          self.sources, self.auto_cats, self.remap,
                                          save=True, include_date=use_date, use_index=use_index)
            await message.remove_reaction(TIMER, self.user)

            rev = next(target.revisions(content=False, total=1))
            if rev.revid == rev_id:
                await message.channel.send(f"No changes made to article")
            else:
                await message.channel.send(f"Completed: [View Changes](<{target.full_url().replace('%2F', '/')}?diff=next&oldid={rev_id}>)")
            for o in results:
                await message.channel.send(o)
        except Exception as e:
            traceback.print_exc()
            await self.report_error("Analyze sources", type(e), e)
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(EXCLAMATION)
            await message.channel.send("Encountered error while analyzing page")

    @staticmethod
    def flatten_text(t):
        z = re.sub("<!--.*?-->", "", t.replace("&ndash;", "-").replace("&mdash;", "-").replace("—", "-").replace("—", "-"))
        while re.search("([\n[]File:[^ \n|\]\[]+) ", z):
            z = re.sub("([\n[]File:[^ \n|\]\[]+) ", "\\1_", z)
        z = re.sub("(\|book=.*?)(\|story=.*?)(\|.*?)?}}", "\\2\\1\\3}}", z.replace("\n", "").replace(" ", "")).replace("{{!}}", "|").replace("{{Journal|", "{{JournalCite|")
        return z

    async def handle_create_list_command(self, message: Message, command: dict):
        try:
            target = Page(self.site, command['article'])
            if not target.exists():
                await message.add_reaction(EXCLAMATION)
                await message.channel.send(f"{command['article']} cannot be found")
                return
            if target.isRedirectPage():
                target = target.getRedirectTarget()

            await message.add_reaction(TIMER)
            analysis = get_analysis_from_page(target, self.infoboxes, self.templates, self.disambigs, self.appearances,
                                              self.sources, self.auto_cats, self.remap, False, False)

            results = prepare_ordered_list(analysis)
            page = Page(self.site, f"User:C4-DE Bot/Timeline Request")
            text = f"This is an listing of all Appearances and Sources for [[{target.title()}]], ordered by chronological release date.\n"
            text += "\n".join(results)
            page.put(text, "Completing ordering request", botflag=False)
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(THUMBS_UP)
        except Exception as e:
            print(traceback.format_exc())
            await self.report_error("Create index", type(e), e)
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(EXCLAMATION)
            await message.channel.send("Encountered error while analyzing page")

    @tasks.loop(minutes=5)
    async def check_index_requests(self):
        for page in Category(self.site, "Index requests").articles():
            try:
                if page.exists():
                    if page.isRedirectPage():
                        page = page.getRedirectTarget()
                    analysis = get_analysis_from_page(page, self.infoboxes, self.templates, self.disambigs, self.appearances,
                                                      self.sources, self.auto_cats, self.remap, False, False)
                    create_index(self.site, page, analysis, self.appearances.target, self.sources.target, True)
                    self.add_index_to_page(page)

            except Exception as e:
                await self.report_error("Index requests", type(e), e)

    async def handle_create_index_command(self, message: Message, command: dict):
        try:
            target = Page(self.site, command['article'])
            if not target.exists():
                await message.add_reaction(EXCLAMATION)
                await message.channel.send(f"{command['article']} cannot be found")
                return
            if target.isRedirectPage():
                target = target.getRedirectTarget()
            if not self.index_cache:
                self.index_cache = {}

            if message.author != self.user:
                if target.title() in self.index_cache:
                    user, date = self.index_cache[target.title()]
                    try:
                        in_window = (datetime.now() - datetime.strptime(date, "%Y-%m-%d")).days < 4
                    except Exception:
                        in_window = False
                    if user != message.author.display_name and in_window:
                        await message.add_reaction(STOP_SIGN)
                        await message.channel.send(f"The index for {target.title()} has recently been created by another user. Please update the index manually, or request that the user or Cade recreate it.")
                        return

            await message.add_reaction(TIMER)
            analysis = get_analysis_from_page(target, self.infoboxes, self.templates, self.disambigs, self.appearances,
                                              self.sources, self.auto_cats, self.remap, False, False)
            result, old_id = create_index(self.site, target, analysis, self.appearances.target, self.sources.target, True)
            await message.remove_reaction(TIMER, self.user)
            if message.author != self.user:
                self.index_cache[target.title()] = (message.author.display_name, datetime.now().strftime("%Y-%m-%d"))
                with open(INDEX_CACHE, "w") as f:
                    f.writelines(json.dumps(self.index_cache, indent=4))

            ux = result.full_url().replace('%2F', '/').replace('%3A', ':')
            if old_id:
                await message.channel.send(f"Updated: [{result.title()}](<{ux}?diff=next&oldid={old_id}>)")
            else:
                await message.channel.send(f"Completed: [{result.title()}](<{ux}>)")
                if not self.add_index_to_page(target):
                    await message.channel.send("Could not locate Appearances or Sources header in target article, so {Indexpage} has not been added")
        except Exception as e:
            print(traceback.format_exc())
            await self.report_error("Create index", type(e), e)
            await message.remove_reaction(TIMER, self.user)
            await message.add_reaction(EXCLAMATION)
            await message.channel.send("Encountered error while analyzing page")

    @staticmethod
    def add_index_to_page(target: Page):
        text = target.get()
        new_text = text.replace("{{IndexRequest}}\n", "")
        success = True
        if "{{Indexpage}}" in text:
            msg = "Removing IndexRequest template after index update"
        else:
            msg = "Adding Index"
            if "==Appearances==" in text:
                new_text = new_text.replace("==Appearances==", "==Appearances==\n{{Indexpage}}")
            elif "==Sources==" in text:
                new_text = new_text.replace("==Sources==", "==Sources==\n{{Indexpage}}")
            elif "{{IndexRequest}}" in text:
                msg = "Removing IndexRequest template after index update"
            else:
                success = False

            if new_text != text:
                target.put(new_text, msg, botflag=False)
        return success

    @tasks.loop(hours=1)
    async def check_future_products(self):
        if datetime.now().hour != 5:
            return
        await self.handle_future_products()

    async def handle_future_products(self):
        try:
            results = get_future_products_list(self.site)
            handle_results(self.site, results, [])
            await self.build_sources()
        except Exception as e:
            traceback.print_exc()
            await self.report_error("Future products", type(e), e)

    async def handle_missing_search(self):
        try:
            results, _, collections = search_for_missing(self.site, self.appearances, self.sources)
            handle_results(self.site, results, collections)
            await self.build_sources()
        except Exception as e:
            traceback.print_exc()
            await self.report_error("Future products", type(e), e)

    def update_unused_files(self):
        exception_page = Page(self.site, "Wookieepedia:WookieeProject Images/Unused images/Not unused")
        exceptions = [x.replace("_", " ") for x in re.findall("(File:.*?)\n", exception_page.get())]

        page = Page(self.site, "Wookieepedia:WookieeProject Images/Unused images")
        text = page.get()
        unused = []
        audio1 = []
        for x in self.site.unusedfiles(total=250):
            if x.title() not in exceptions and ":Video" not in x.title():
                if x.title().lower().endswith(".ogg") or x.title().lower().endswith(".flac"):
                    audio1.append(x.title())
                else:
                    unused.append(x.title())

        files, audio2 = [], []
        for ln in text.splitlines():
            if ln.startswith("File:"):
                x = ln.split("|")[0]
                pf = FilePage(self.site, x)
                if not pf.exists():
                    continue
                elif any(up.title() != "Wookieepedia:WookieeProject Images/Unused images" for up in pf.using_pages(total=5)):
                    continue
                if ".ogg" in ln.lower() or ".flac" in ln.lower():
                    audio2.append(ln)
                else:
                    files.append(ln)

        d = datetime.now().strftime("%Y-%m-%d")
        for i in unused:
            if not any(f.startswith(i) for f in files):
                files.append(f"{i}|{d}")
        for i in audio1:
            if not any(f.startswith(i) for f in audio2):
                audio2.append(f"{i}|{d}")

        new_lines = ["{{/Header}}", "", "----", '<gallery widths="120px" position="left" spacing="small" captionalign="left" captionsize="small" bordersize="none" hideaddbutton="true">']
        new_lines += sorted(files, key=lambda a: a.split("|")[-1] if "|" in a else a)
        new_lines.append("</gallery>")

        if audio2:
            new_lines.append("")
            new_lines.append("===Audio Files===")
            new_lines.append('<gallery widths="120px" position="left" spacing="small" captionalign="left" captionsize="small" bordersize="none" hideaddbutton="true">')
            new_lines += sorted(audio2, key=lambda a: a.split("|")[-1] if "|" in a else a)
            new_lines.append("</gallery>")

        text = "\n".join(new_lines)
        if text != page.get():
            page.put(text, botflag=False, summary="Recording newly unused files")

    def fix_double_redirects(self):
        for x in self.site.double_redirects(total=250):
            try:
                if x.namespace().id == 0 or x.namespace().id == 10:
                    y = x.getRedirectTarget().getRedirectTarget()
                    if y.isRedirectPage():
                        y = y.getRedirectTarget()
                    x.put(f"#REDIRECT [[{y.title()}]]", "Fixing double redirects")
            except Exception:
                pass

    @tasks.loop(hours=4)
    async def check_senate_hall_threads(self):
        archive_stagnant_senate_hall_threads(self.site, self.timezone_offset)

    @tasks.loop(hours=1)
    async def check_spoiler_templates_and_cleanup(self):
        if datetime.now().hour != 6:
            return
        log("Scheduled Operation: Updating unused files and double redirects")
        self.update_unused_files()
        self.fix_double_redirects()

        log("Scheduled Operation: Checking {{Spoiler}} templates")
        for page in Category(self.site, "Articles with expired spoiler notices").articles(namespaces=0):
            try:
                tv_dates, default_show = self.extract_tv_spoiler_data()
                remove_spoiler_tags_from_page(self.site, page, tv_dates, default_show, offset=self.timezone_offset)
            except Exception as e:
                error_log(f"Encountered {type(e)} while removing spoiler template from {page.title()}", e)
                await self.text_channel(COMMANDS).send(f"Encountered {type(e)} while removing expired spoiler template from {page.title()}. Please check template usage for anomalies.")

    def extract_tv_spoiler_data(self):
        data = re.findall("\| ([A-z]+) ([0-9]+[AB]?) = .*?\|([0-9]+-[0-9]+-[0-9]+)\|",
                          Page(self.site, "Template:TVspoiler/data").get())
        tv_dates = {}
        for s, n, d in data:
            if s not in tv_dates:
                tv_dates[s] = {}
            tv_dates[s][n] = d
        default_show = re.search("{{{show\|([a-z]+)}}}", Page(self.site, "Template:TVspoiler").get()).group(1)
        return tv_dates, default_show

    @tasks.loop(hours=1)
    async def load_isbns(self):
        if datetime.now().hour != 7:
            if not self.maintenance_cats:
                self.reload_maintenance_categories()
                log(f"{len(self.maintenance_cats)} maintenance categories")
            return
        page = Page(self.site, "Template:ISBN/data")
        last_revision = next(r for r in page.revisions(reverse=True, total=10) if r["user"] == "JocastaBot")
        time_since_last_edit = (datetime.now() + timedelta(hours=self.timezone_offset)) - last_revision['timestamp']
        if time_since_last_edit.total_seconds() < (60 * 60 * 6):
            log(f"Skipping ISBN reload, last edit was {last_revision['timestamp']}")
            return
        log("Scheduled Operation: Calculating ISBNs")
        calculate_isbns_for_all_pages(self.site)
        self.reload_infoboxes()
        self.reload_auto_categories()
        self.reload_maintenance_categories()
        self.reload_templates()
        log(f"{len(self.maintenance_cats)} maintenance categories")

    @tasks.loop(hours=4)
    async def check_altaya(self):
        log("Scheduled Operation: Checking Altaya")
        try:
            with open("C:/Users/cadec/Documents/projects/C4DE/c4de/data/altaya.txt", "r") as f:
                current = "\n".join(f.readlines()).strip()

            x = requests.get("https://www.altaya.fr/fr/miniatures-figurines/star-wars-vaisseaux")
            items = re.findall("<option .*?value=\"([0-9]+)\">[\n\t ]*.*?\+ ?(.*?)[\n\t ]*</option>", x.text)
            latest = str(max(int(a) + 1 for a, b in items))
            log(f"Current Altaya listing: {latest} -> {current}")
            if latest:
                if current != latest:
                    await self.text_channel(UPDATES).send(f"New *Star Wars Starships & Vehicles* issue {latest} found in [Altaya's website](<https://www.altaya.fr/fr/miniatures-figurines/star-wars-vaisseaux>)")
                with open("C:/Users/cadec/Documents/projects/C4DE/c4de/data/altaya.txt", "w") as f:
                    print(latest)
                    f.writelines(latest)
        except Exception as e:
            error_log(f"Encountered {type(e)} while checking Altaya", e)

    @tasks.loop(hours=1)
    async def check_edelweiss(self):
        if self.run_edelweiss:
            self.run_edelweiss = False
        if datetime.now().hour != 8:
            return
        elif not self.channels:
            self.run_edelweiss = True
            return
        log("Scheduled Operation: Checking Edelweiss")
        messages, reprints = run_edelweiss_protocol(self.site, self.edelweiss_cache, True)
        if reprints:
            messages.append("Errors encountered while adding reprint ISBNs to pages:")
            messages += reprints
        with open(EDELWEISS_CACHE, "w") as f:
            f.writelines(json.dumps(self.edelweiss_cache))
        for m in messages:
            try:
                await self.text_channel(UPDATES).send(m)
            except Exception as e:
                print(m)
                print(e)

    def prepare_link(self, link):
        return parse.quote_from_bytes(link.replace(' ', '_').encode(self.site.encoding()), safe='').replace('%3A', ':')

    @tasks.loop(minutes=30)
    async def check_policy(self):
        if self.refresh == 2:
            self.reload_site()
            self.refresh = 0
        else:
            self.refresh += 1

        updates = check_policy(self.site)
        messages = []
        for date, posts in updates.items():
            for post in posts:
                if post['link'] not in self.policy_updates.get(date, []):
                    link = self.prepare_link(post['link'])
                    messages.append(f"🗨️ [**{post['link']}**](<{SITE_URL}/{link}>) has completed with the following result: **{post['result']}**")

        for message in messages:
            await self.text_channel(ANNOUNCEMENTS).send(message)

        self.policy_updates = {d: [l['link'] for l in v] for d, v in updates.items()}

        with open(POLICY_CACHE, "w") as f:
            f.writelines(json.dumps(self.policy_updates, indent=4))

    @tasks.loop(minutes=15)
    async def check_membership_nominations(self):
        log("Checking board membership nominations")
        current_nominations, interested = check_review_board_nominations(self.site)
        messages = []
        for board, noms in current_nominations.items():
            for user in noms:
                if user not in self.board_nominations["Nominations"][board]:
                    username = self.prepare_link(user)
                    emote = self.emoji_by_name(BOARD_EMOTES[board])
                    messages.append((True, board, f"{emote} **{user} has been [nominated for membership in the {board}!](<{SITE_URL}/Wookieepedia:Review_board_membership_nominations#{username}>)**"))

        for board, noms in interested.items():
            for user in list(noms.keys()):
                if user not in self.board_nominations["Interested"][board]:
                    emote = self.emoji_by_name("grogu")
                    messages.append((False, board, f"{emote} **{user} has [expressed interest in joining the {board}!](<{SITE_URL}/Wookieepedia:Review_board_recruitment>)**"))
                else:
                    noms[user] = self.board_nominations["Interested"][board][user]
                    if datetime.now().hour == 12 and datetime.now().minute <= 15:
                        last_checked = self.board_nominations["Interested"][board][user]
                        as_date = datetime.strptime(last_checked, "%Y-%m-%d")
                        diff = (datetime.now() - as_date).days
                        if diff > 0 and diff % 30 == 0:
                            emote = self.emoji_by_name("grogu")
                            messages.append((False, board, f"{emote} {diff} days have passed since **{user}** expressed interest in joining the {board}; please provide feedback if this has not already been done"))

        for (announce, board, message) in messages:
            try:
                if announce:
                    await self.text_channel(ANNOUNCEMENTS).send(message)
                await self.text_channel(board.lower()).send(message)
            except Exception as e:
                error_log(f"Encountered {type(e)} while checking board nominations", e)

        self.board_nominations = {"Nominations": current_nominations, "Interested": interested}

        with open(BOARD_CACHE, "w") as f:
            f.writelines(json.dumps(self.board_nominations, indent=4))

    @tasks.loop(minutes=15)
    async def check_rights_nominations(self):
        log("Checking user rights nominations")
        current_nominations = check_user_rights_nominations(self.site)
        messages = []
        for right, noms in current_nominations.items():
            for user in noms:
                if user not in self.rights_cache[right]:
                    username = self.prepare_link(user)
                    if right == "Removal":
                        messages.append(f"📢 **{user} has been nominated for removal of their user rights. Please weigh in [here](<{SITE_URL}/Wookieepedia:Requests_for_removal_of_user_rights/{username}>)**")
                    else:
                        messages.append(f"📢 **{user} has been nominated for {right} rights! Cast your vote [here!](<{SITE_URL}/Wookieepedia:Requests_for_user_rights/{right}/{username}>)**")

        for message in messages:
            await self.text_channel(ANNOUNCEMENTS).send(message)

        self.rights_cache = current_nominations

        with open(RIGHTS_CACHE, "w") as f:
            f.writelines(json.dumps(self.rights_cache, indent=4))

    @tasks.loop(minutes=30)
    async def check_consensus_statuses(self):
        log("Checking status of active Consensus Track and Trash Compactor votes")
        cts_and_tcs = check_consensus_duration(self.site, self.timezone_offset)
        overdue = []
        for page, duration in cts_and_tcs.items():
            if page in self.overdue_cts or duration.days >= 14:
                overdue.append(page)

        remove = []
        skip = []
        for m, x in self.admin_messages.items():
            if x.startswith("Forum:CT:"):
                if x in overdue:
                    skip.append(x)
                else:
                    remove.append(m)

        for page in overdue:
            if page in self.overdue_cts or page in skip:
                continue
            link = self.prepare_link(page)
            message = f"**{page}** has been open for 14 days and can now be archived\n<{SITE_URL}/{link}>"
            msg = await self.text_channel(ADMIN_REQUESTS).send(message)
            self.admin_messages[msg.id] = page
        self.overdue_cts = overdue
        for i in remove:
            self.admin_messages.pop(i)

        with open(ADMIN_CACHE, "w") as f:
            f.writelines(json.dumps(self.admin_messages, indent=4))

    CHANNEL_FILTERS = {
        "the-high-republic": ["high republic"],
        "galaxys-edge": ["galaxys edge", "galaxy's edge", "halcyon", "galactic starcruiser"]
    }

    @tasks.loop(minutes=30)
    async def check_bot_requests(self):
        log("Checking bot requests")
        try:
            messages = []
            for m in await self.text_channel(REQUESTS).history(limit=500).flatten():
                try:
                    if any("bb8thumbsup" in str(r.emoji) for r in m.reactions):
                        messages.append(m)
                except Exception as e:
                    await self.report_error(f"Bot Request Archival: {e}", type(e), e)

            if messages:
                page = Page(self.site, "Wookieepedia:Bot requests/Archive/Discord")
                text = page.get() if page.exists() else ""
                today = datetime.now().strftime("%B %d, %Y")
                if f"=={today}==" not in text:
                    text += f"\n\n=={today}=="
                users = {}
                for m in reversed(messages):
                    if m.author.display_name != "Wiki-Bot" and m.author != self.user:
                        if m.author.display_name not in users:
                            if Page(self.site, f"User:{m.author.display_name}").exists():
                                users[m.author.display_name] = "{{U|" + m.author.display_name + "}}"
                            else:
                                users[m.author.display_name] = m.author.display_name
                        d = m.created_at.strftime("%H:%M, %B %d %Y")
                        t = f"*{d}: '''{users[m.author.display_name]}''': <nowiki>{m.content}</nowiki>"
                        text += f"\n{t}"
                page.put(text, "Archiving completed bot requests from Discord", force=True, botflag=False)

                for m in messages:
                    try:
                        await m.delete()
                        time.sleep(2)
                    except HTTPException:
                        time.sleep(5)
                        try:
                            await m.delete()
                        except Exception:
                            log(f"Cannot delete message {m.id}")

        except TimeoutError:
            pass
        except Exception as e:
            await self.report_error(f"Bot Request Archival: {e}", type(e), e)

    @tasks.loop(minutes=60)
    async def check_empty_usage_categories(self):
        try:
            clean_up_archive_categories(self.site)
        except TimeoutError:
            pass
        except Exception as e:
            await self.report_error(f"Usage Categories: {e}", type(e), e)

    @tasks.loop(minutes=15)
    async def check_deleted_pages(self):
        log("Checking deleted pages")

        try:
            update = []
            for message_id, title in self.admin_messages.items():
                p = Page(self.site, title)
                if not p.exists():
                    update.append(message_id)
            if not update:
                return

            for message in await self.text_channel(ADMIN_REQUESTS).history(limit=200).flatten():
                try:
                    if message.id in update:
                        await message.edit(content=f"~~{message.content}~~ (completed)")
                        self.admin_messages.pop(message.id)
                        update.remove(message.id)
                        time.sleep(1)
                except discord.errors.HTTPException as e:
                    if "rate limit" in str(e):
                        time.sleep(5)
                    elif "Maximum number of edits" in str(e):
                        await message.add_reaction(self.emoji_by_name("GNK"))
                    else:
                        await self.report_error(f"Deleted Pages (messages): {message.content} -> {e}", type(e), e)
                except Exception as e:
                    await self.report_error(f"Deleted Pages (messages): {message.content} -> {e}", type(e), e)

            if update:
                log(f"Could not find messages {update} in #{ADMIN_REQUESTS} to update")
                for k in update:
                    self.admin_messages.pop(k)
            with open(ADMIN_CACHE, "w") as f:
                f.writelines(json.dumps(self.admin_messages, indent=4))
        except TimeoutError:
            pass
        except Exception as e:
            await self.report_error(f"Deleted Pages: {e}", type(e), e)

    @tasks.loop(minutes=15)
    async def check_files_to_be_renamed(self):
        log("Checking FTBR")

        try:
            files = [p for p in Category(self.site, "Files to be renamed").articles()]
            new_files = []
            for f in files:
                try:
                    if f.title() not in self.files_to_be_renamed:
                        x = re.search("\{\{FTBR\|.*\|(.*?)}}", f.get())
                        new_name_text = f" to **{x.group(1)}**" if x else ""
                        m = f"⚠️ **{f.lastNonBotUser()}** requested [**{f.title()}**](<{f.full_url()}>) be renamed{new_name_text}\n"
                        msg = await self.text_channel(ADMIN_REQUESTS).send(m)
                        self.admin_messages[msg.id] = f.title()
                except Exception as e:
                    await self.report_error(f"FTBR: {f.title()}", type(e), e)

            self.files_to_be_renamed = [f.title() for f in files]
            with open(ADMIN_CACHE, "w") as f:
                f.writelines(json.dumps(self.admin_messages, indent=4))
        except Exception as e:
            await self.report_error(f"FTBR: {e}", type(e), e)

    @tasks.loop(minutes=5)
    async def check_internal_rss(self, _=None):
        log("Checking internal RSS feeds")

        try:
            messages_to_post, to_delete = check_wookieepedia_feeds(self.site, self.internal_rss_cache)
        except Exception as e:
            await self.report_error(f"Encountered {type(e)} while checking internal RSS", e)
            return

        for channel, message, d_page in messages_to_post:
            try:
                m = await self.text_channel(channel).send(message[:4000])
                if d_page:
                    self.admin_messages[m.id] = d_page
            except Exception as e:
                await self.report_error(f"RSS: {message}", type(e), e)

        with open(ADMIN_CACHE, "w") as f:
            f.writelines(json.dumps(self.admin_messages, indent=4))
        with open(INTERNAL_RSS_CACHE, "w") as f:
            f.writelines(json.dumps({k: v[-50:] for k, v in self.internal_rss_cache.items()}, indent=4))

    async def handle_target_url_check(self, message: Message, command: dict):
        if "starwars.com" not in command['url']:
            await message.add_reaction(EXCLAMATION)
            return
        await message.add_reaction(TIMER)

        messages_to_post = []
        templates = []
        new_db_entries = []

        urls = compile_tracked_urls(self.site)
        exists = False
        ep_urls, ep_db = set(), {}
        for u in re.split(">,? <", command['url']):
            print(u)
            e, x, d = check_target_url(u, urls)
            exists = e or exists
            ep_urls.update(x)
            for k, v in d.items():
                ep_db[k] = v
        if not exists:
            await message.add_reaction(EXCLAMATION)
            return
        elif not ep_urls:
            await message.add_reaction(THUMBS_UP)
            return

        updated_db_entries = {u: t for u, t in ep_db.items() if u in urls}
        messages, updated_db_entries = handle_site_map(ep_urls.union(list(ep_db.keys())), urls, [], updated_db_entries, ep_urls)
        if not messages:
            await message.add_reaction(THUMBS_UP)
            return

        site_data = self.rss_data["sites"]["StarWars.com"]
        archive = self.parse_archive(site_data["template"])
        db_archive = self.parse_archive("Databank")
        for m in reversed(messages):
            try:
                msg, d, template = await self.prepare_new_rss_message(
                    m, site_data["baseUrl"], site_data, False, db_archive if m['site'] == "Databank" else archive,
                    should_archive=" archive" in message.content)
                messages_to_post += msg
                print(d, template)
                if m["site"] == "Databank":
                    new_db_entries.append(template)
                else:
                    templates.append((d, template))
            except Exception as e:
                error_log(type(e), e.args)

        await self.report_rss_results(messages_to_post, templates, updated_db_entries, new_db_entries)

        await message.remove_reaction(TIMER, self.user)
        await message.add_reaction(THUMBS_UP)
        return

    async def handle_archive_url_command(self, message: Message, command: dict):
        await message.add_reaction(TIMER)
        success = False
        try:
            template = command["template"]
            youtube = "youtube.com" in command['url']
            if youtube:
                template = "YouTube"
                target = re.search("[?&](videoId|v|playlist)=(.*?)(&.*?)?$", command['url'])
                target = target.group(2) if target else None
            else:
                target_site, site_data = None, {}
                for site, data in self.rss_data["sites"].items():
                    if template and data["template"] == template:
                        target_site = site
                    elif data["baseUrl"] and data["baseUrl"].split("//", 1)[-1].split("www.", 1)[-1] in command["url"]:
                        target_site = site
                        template = template or data["template"]
                    if target_site:
                        break

                site_data = self.rss_data["sites"].get(target_site)
                if site_data:
                    target = command['url'].replace(site_data['baseUrl'] + "/", "")
                else:
                    target = command['url'].split('//', 1)[-1].split('/', 1)[-1]

            r = requests.get(command["url"])
            if r.status_code != 200:
                print(r.status_code, r.url, command['url'])
                # await message.add_reaction(EXCLAMATION)
                # return

            if template and target:
                archive = self.parse_archive(template)
                if target.endswith("/"):
                    target = target[:-1]
                if template == "Databank":
                    target = target.replace("databank/", "")
                already_archived = archive and archive.get(target)
                if already_archived:
                    log(f"URL already archived and recorded: {command['url']}")
                    success, include_archivedate, archivedate = True, False, archive[target]
                else:
                    log(f"Archiving URL: {command['url']}")
                    success, archivedate = archive_url(command['url'], timeout=60 if youtube else 30, enabled=self.should_archive)

                if success and not already_archived:
                    self.add_urls_to_archive(template, target, archivedate)

            await message.add_reaction(THUMBS_UP if success else THUMBS_DOWN)
        except Exception as e:
            traceback.print_exc()
            error_log(type(e), e.args)
            await message.add_reaction(EXCLAMATION)
        await message.remove_reaction(TIMER, self.user)

    async def handle_record_source_command(self, message: Message, command: dict):
        await message.add_reaction(TIMER)
        try:
            template = command["template"]
            target_site = None
            for site, data in self.rss_data["sites"].items():
                if template and data["template"] == template:
                    target_site = site
                elif data["baseUrl"].split("//", 1)[-1].split("www.", 1)[-1] in command["url"]:
                    target_site = site
                    template = template or data["template"]

            if not template:
                return None, "ERROR: Cannot determine template"
            site_data = self.rss_data["sites"].get(target_site)
            if not site_data:
                u = command['url'].split('//', 1)[-1].split('/', 1)[0]
                site_data = {"baseUrl": f"https://{u}", "template": template, "emoji": "HanShrug", "channels": [], "title": "(.*?)"}

            r = requests.get(command["url"])
            if r.status_code != 200:
                await message.add_reaction(EXCLAMATION)
                return
            title = check_title_formatting(r.text, site_data.get("title", "(.*?)"), "")
            m = {"site": target_site, "title": title, "url": r.url, "content": "", "date": command.get('date') or datetime.now().strftime('%Y-%m-%d')}

            archive = self.parse_archive(template)
            msg, d, template = await self.prepare_new_rss_message(m, site_data["baseUrl"], site_data, False, archive)

            if target_site == "Databank":
                templates, new_db_entries = [], [template]
            else:
                templates, new_db_entries = [(d, template)], []

            await self.report_rss_results(msg, templates, {}, new_db_entries)
            await message.add_reaction(THUMBS_UP)
        except Exception as e:
            traceback.print_exc()
            error_log(type(e), e.args)
            await message.add_reaction(EXCLAMATION)
        await message.remove_reaction(TIMER, self.user)

    async def check_sites(self, site, site_data, messages_to_post, db_archive, templates, new_db_entries, custom_date=None):
        db = None
        if site == "StarWars.com":
            messages = check_sw_news_page(site_data["url"], self.external_rss_cache["sites"], site_data["title"])
            try:
                other, db = compare_site_map(self.site, [], messages,
                                             self.external_rss_cache["sites"]["StarWars.com"])
                messages += other
            except Exception as e:
                error_log(f"Encountered {type(e).__name__} while checking site map")
        elif site_data["template"] == "UnlimitedWeb":
            messages = check_unlimited(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data["template"] == "AtomicMassGames":
            messages = check_blog_list(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data["template"] == "ILM":
            messages = check_ilm(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data["template"] == "Ubisoft":
            messages = check_ubisoft_news(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data["template"] == "Hunters":
            messages = check_hunters_news(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data["template"] == "EA":
            messages = check_ea_news(site, site_data["baseUrl"], site_data["rss"], self.external_rss_cache["sites"])
        elif site_data.get("url"):
            messages = check_latest_url(site_data["url"], self.external_rss_cache["sites"], site, site_data["title"])
        else:
            messages = check_rss_feed(site_data["rss"], self.external_rss_cache["sites"], site, site_data["title"],
                                      site_data.get("nonSW", False))

        archive = self.parse_archive(site_data["template"])
        for m in reversed(messages):
            try:
                msg, d, template = await self.prepare_new_rss_message(
                    m, site_data["baseUrl"], site_data, False, db_archive if m['site'] == "Databank" else archive)
                messages_to_post += msg
                if m["site"] == "Databank":
                    new_db_entries.append(template)
                else:
                    templates.append((custom_date or d, template))
            except Exception as e:
                error_log(type(e), e.args)
        return db

    @tasks.loop(minutes=10)
    async def check_external_rss(self):
        log("Checking external RSS feeds")

        messages_to_post = []
        templates = []

        db_archive = self.parse_archive("Databank")
        new_db_entries = []
        updated_db_entries = {}
        for site, site_data in self.rss_data["sites"].items():
            try:
                updated_db_entries = await self.check_sites(site, site_data, messages_to_post, db_archive, templates, new_db_entries)
                if updated_db_entries:
                    break
            except Exception as e:
                error_log(f"Encountered {type(e)} while checking RSS for {site}", e)

        for site, site_data in self.rss_data["YouTube"].items():
            archive = self.parse_archive(site_data["template"])
            messages = check_rss_feed(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={site_data['channelId']}",
                self.external_rss_cache["YouTube"], site, "<h1 class=\"title.*?><.*?>(.*?)</.*?></h1>", site_data.get("nonSW", False))
            for m in reversed(messages):
                try:
                    msg, d, template = await self.prepare_new_rss_message(m, "https://www.youtube.com", site_data, True, archive)
                    messages_to_post += msg
                    templates.append((d, template))
                except Exception as e:
                    error_log(type(e), e.args)

        await self.report_rss_results(messages_to_post, templates, updated_db_entries, new_db_entries)

    async def report_rss_results(self, messages_to_post, templates, updated_db_entries, new_db_entries):

        for channel, message in messages_to_post:
            try:
                await self.text_channel(channel).send(message)
            except Exception as e:
                await self.report_error(f"RSS: {message}", type(e), e)

        if updated_db_entries:
            await self.handle_updated_db_entries(updated_db_entries)

        with open(EXTERNAL_RSS_CACHE, "w") as f:
            f.writelines(json.dumps({k: {i: c[-250:] for i, c in v.items()} for k, v in self.external_rss_cache.items()}, indent=4))

        if templates:
            await self.update_web_sources(templates)
        if new_db_entries:
            await self.update_databank(new_db_entries)
        log("Completed external RSS check")

    async def update_web_sources(self, templates: list):
        nd = datetime.now().strftime("%Y-%m-%d")
        by_year = {}
        for d, t in templates:
            if "®" not in t and "™" not in t and emoji.emoji_count(t) > 0:
                dy = "Special"
            elif d and d.startswith("R:"):
                dy = "Repost"
            else:
                dy = (d or nd).split("-")[0]
            if dy not in by_year:
                by_year[dy] = []
            by_year[dy].append((d, t))
        for y, tx in by_year.items():
            try:
                page = Page(self.site, f"Wookieepedia:Sources/Web/{y}")
                try:
                    text = page.get()
                except NoPageError:
                    text = "{{Wookieepedia:Sources/Web/Header}}"
                for d, t in tx:
                    x = t.split("|archivedate=", 1)[0].rsplit("|", 1)[0]
                    if f"{x}|" not in text and f"{x}}}" not in text:
                        text += f"\n*{d or nd}: {t}"
                if text != page.get():
                    page.put(text, "Adding new sources", botflag=False)
            except Exception as e:
                await self.report_error(f"RSS: Saving sources", type(e), e)

    async def handle_updated_db_entries(self, updated_db_entries):
        new_archivedates = {}
        z = ["The following Databank entries were listed on an Episode Guide page, and may have been updated:"]
        for d, t in updated_db_entries.items():
            try:
                success, archivedate = archive_url(f"https://starwars.com/{d}", force_new=True, enabled=self.should_archive)
                if success:
                    new_archivedates[d.replace("databank/", "")] = archivedate
            except Exception as e:
                error_log(type(e), e.args)
            y = f"- {t}: <https://starwars.com/{d}>"
            if len(y) + len(z[-1]) > 500:
                z.append(y)
            else:
                z[-1] += f"\n{y}"
        for i in z:
            try:
                await self.text_channel("spoiler-editing").send(i)
            except Exception as e:
                await self.report_error(f"RSS: {i}", type(e), e)

        # if new_archivedates:
        #     page = Page(self.site, "Module:ArchiveAccess/Databank")
        #     new_text = page.get()
        #     for u, d in new_archivedates.items():
        #         new_text = re.sub("\[['\"]" + u + "['\"]\].*?=.*?['\"][0-9]+?['\"]", f"['{u}'] = '{d}'", new_text)
        #     if new_text != page.get():
        #         page.put(new_text, "Updating archivedates for changed Databank entries")

    async def update_databank(self, new_entries: list):
        try:
            page = Page(self.site, f"Wookieepedia:Sources/Web/Databank")
            try:
                text = page.get()
            except NoPageError:
                text = "{{Wookieepedia:Sources/Web/Header}}"
            all_entries = [x for x in text.splitlines() if x.startswith("*{{Databank")]
            all_entries += [f"*{t}" for t in new_entries]

            items = []
            for e in all_entries:
                t = re.search("{{Databank\|.*?\|(.*?)(\|.*?)?}}", e)
                txt = t.group(1).lower().replace("'", "").replace('"', "")
                items.append((f"{txt}", e))

            new_text = "\n".join(x for i, x in sorted(items))
            if new_text != page.get():
                page.put(new_text, "Adding new sources", botflag=False)
        except Exception as e:
            await self.report_error(f"RSS: Saving sources", type(e), e)

    async def prepare_new_rss_message(self, m: dict, base_url: str, site_data: dict, youtube: bool, archive: dict, should_archive=True) -> Tuple[List[Tuple[str, str]], str, str]:
        if youtube:
            target = m["videoId"]
        else:
            target = m["url"].replace(base_url + "/", "")

        if target.endswith("/"):
            target = target[:-1]
        if m['site'] == "Databank":
            target = target.replace("databank/", "")
        already_archived = archive and archive.get(target)
        if already_archived:
            log(f"URL already archived and recorded: {m['url']}")
            success, include_archivedate, archivedate = True, False, archive[target]
        else:
            log(f"Archiving URL: {m['url']}")
            success, archivedate = archive_url(m["url"], timeout=60 if youtube else 30, enabled=self.should_archive, skip=not should_archive)
            include_archivedate = success

        f = m["title"].replace("''", "*").replace("’", "'").replace("“", '"').replace('“', '"')
        f = re.sub("^(''[^'\n]+'')'s ", "\\1{{'s}} ", f)
        f = re.sub("( ''[^'\n]+'')'s ", "\\1{{'s}} ", f)

        if success and not already_archived:
            try:
                template = "Databank" if m["site"] == "Databank" else site_data["template"]
                self.add_urls_to_archive(template, target, archivedate)
                include_archivedate = False
            except Exception as e:
                await self.report_error(m["url"], type(e), e)

        date = m.get('date')
        template = self.build_citation_template(m, youtube, site_data, archivedate if include_archivedate and not already_archived else None)

        if youtube:
            t = f"New Video on the official {m['site']} YouTube channel"
            x = re.search("\|.*?\|(Star Wars:? )?(,*?) ?&#124; ?(.*?) ?&#124; ?(Disney\+|Star Wars) *}}", f)
            if (x and x.group(2) in REPOSTS) or f.endswith("Full Episode") or " Full Episode " in f:
                date = f"R: {date}"
                t += " (Repost)"
        elif m["site"] == "Databank":
            t = f"New Entry on the Databank"
        elif not m['site']:
            t = f"New Article"
        else:
            s = (m['site'].split('.com:')[0] + '.com') if '.com:' in m['site'] else m['site']
            t = f"New Article on {s}"

        msg = "{0} **{1}:**    {2}\n- <{3}>".format(self.emoji_by_name(site_data["emoji"]), t, f, m["url"])
        msg += f"\n- `{template}`"

        if success:
            msg += f"\n- Wayback Archive Date: {archivedate}"
        else:
            x = archivedate.splitlines()[0] if archivedate else ''
            msg += f"\n- Unable to archive URL: {'Max retries exceeded with URL' if 'Max retries' in x else x}"

        results = [(UPDATES, msg)]
        if (m["site"] == "Databank" or (m["site"] == "StarWars.com" and "Episode Guide" in m['title'])
                or (m["site"] == "StarWars.com" and "Declassified" in m['title'] and "Highlights" in m['title'])):
            results.append(("spoiler-editing", msg))
        for c in site_data.get("channels", []):
            results.append((c, msg))

        for project, data in self.project_data.items():
            if data.get("newsFilters"):
                for f in data["newsFilters"]:
                    if f in msg.replace("-", "").lower() or f in m["content"].lower():
                        results.append((data["channel"], msg))

        return results, date, template

    @staticmethod
    def build_citation_template(msg: dict, youtube, site_data: dict, archivedate):
        t = msg['title'].replace("|", "&#124;").strip().replace("=", "{{=}}").replace("{{{{=}}}}", "{{=}}")
        x = msg.get('template') or site_data['template']
        if youtube:
            result = f"{x}|{msg['videoId']}|{t}"
        elif msg["site"] == "Databank":
            url = msg["url"].replace(site_data["baseUrl"] + "/", "").replace("databank/", "")
            result = f"Databank|{url}|{t}"
        else:
            url = msg["url"].replace(site_data["baseUrl"] + "/", "")
            if url.endswith("/"):
                url = url[:-1]
            result = f"{x}|url={url}|text={t}"
        if archivedate:
            result += f"|archivedate={archivedate}"
        if "arena-news" in result:
            result = re.sub("Hunters\|url=.*?arena-news/", "ArenaNews|url=", result)
        return "{{" + result + "}}"

    def get_archive_for_site(self, template):
        if "youtube" in template.lower() or template in ["ThisWeek", "HighRepublicShow" "LegoMiniMovie"]:
            template = "YouTube"
        page = Page(self.site, f"Template:{template}/Archive")
        if page.exists():
            return page
        return Page(self.site, f"Module:ArchiveAccess/{template}")

    def add_urls_to_archive(self, template, new_url, archivedate):
        if template == "Hunters" and "arena-news" in new_url:
            new_url = new_url.replace("arena-news/", "")
            template = "ArenaNews"
        page = self.get_archive_for_site(template)
        text = page.get()
        if page.title().startswith("Template"):
            new_text = self.build_archive_template_text(text, new_url, archivedate)
        else:
            new_text = self.build_archive_module_text(text, new_url, archivedate)
        if not new_text:
            return
        new_text = "\n".join(new_text)
        if text == new_text:
            return

        try:
            page.put(new_text, f"Archiving {archivedate} for new URL: {new_url}", botflag=False)
        except OtherPageSaveError:
            self.site.login()
            page.put(new_text, f"Archiving {archivedate} for new URL: {new_url}", botflag=False)

    def parse_archive(self, template):
        page = self.get_archive_for_site(template)
        if not page.exists():
            return None
        archive = {}
        for u, d in re.findall("\[['\"](.*?)['\"]] ?= ?['\"]?([0-9]+)/?['\"]?", page.get()):
            archive[u.replace("\\'", "'")] = d
        return archive

    @staticmethod
    def build_archive_template_text(text, new_url, archivedate):
        special_start = "<!-- Start" in text
        new_text = []
        found, start = False, False,
        u = new_url.replace("watch?v=", "").replace("=", "{{=}}")
        for line in text.splitlines():
            if not start and special_start:
                start = "<!-- Start" in line
            elif not start:
                start = line.strip().startswith("|")
            elif not found and f"| {u} = " in line:
                log(f"URL {u} is already archived")
                return
            elif not found and u < line.strip()[1:].strip():
                new_text.append(f"  | {u} = {archivedate}")
                found = True
            new_text.append(line)

        return new_text

    @staticmethod
    def build_archive_module_text(text, new_url, archivedate):
        new_text = []
        found, start = False, False
        u = new_url.replace("{{=}}", "=")
        for line in text.splitlines():
            if not start:
                start = line.strip().startswith("[")
            elif not found and (f"['{u}']" in line or f'["{u}"]' in line):
                log(f"URL {u} is already archived")
                return
            elif not found and (line.strip().startswith("}") or u < line.strip()[1:].strip()):
                if "[" in new_text[-1] and not new_text[-1].strip().endswith(","):
                    new_text[-1] = new_text[-1].rstrip() + ","
                new_text.append(f'\t["{u}"] = "{archivedate}",')
                found = True
            new_text.append(line)

        return new_text
