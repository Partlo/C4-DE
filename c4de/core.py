import re
import json
import sys
from urllib import parse
from typing import List, Tuple
from datetime import datetime, timedelta
from discord import Message, Game, Intents
from discord.abc import GuildChannel
from discord.channel import TextChannel, DMChannel
from discord.ext import commands, tasks
import ssl

import time
from pywikibot import Page, Category

ssl._create_default_https_context = ssl._create_unverified_context

import pywikibot
from pywikibot import Site
from c4de.common import log, error_log, archive_url
from c4de.data.filenames import *
from c4de.version_reader import report_version_info

from c4de.protocols.cleanup import archive_stagnant_senate_hall_threads, remove_spoiler_tags_from_page, \
    check_preload_for_missing_fields, check_infobox_category
from c4de.protocols.edelweiss import run_edelweiss_protocol, calculate_isbns_for_all_pages
from c4de.protocols.rss import check_rss_feed, check_latest_url, check_wookieepedia_feeds, check_sw_news_page, \
    check_review_board_nominations, check_policy, check_consensus_track_duration, check_user_rights_nominations
from c4de.data.filenames import INTERNAL_RSS_CACHE, EXTERNAL_RSS_CACHE, BOARD_CACHE


SELF = 880096997217013801
CADE = 346767878005194772
MONITOR = 268478587651358721
MAIN = "wookieepedia"
COMMANDS = "bot-commands"
ANNOUNCEMENTS = "announcements"
NOM_CHANNEL = "article-nominations"
SOCIAL_MEDIA = "social-media-team"
UPDATES = "star-wars-news"
SITE_URL = "https://starwars.fandom.com/wiki"

THUMBS_UP = "👍"
TIMER = "⏲️"
EXCLAMATION = "❗"
BOARD_EMOTES = {"EduCorps": "EC", "AgriCorps": "AC", "Inquisitorius": "Inq"}


# noinspection PyPep8Naming
class C4DE_Bot(commands.Bot):
    """
    :type site: Site
    :type channels: dict[str, GuildChannel]
    :type emoji_storage: dict[str, int]
    :type rss_data: dict[str, dict]
    :type internal_rss_cache: dict[str, dict[str, list[str]]]
    :type external_rss_cache: dict[str, dict[str, list[str]]]
    :type board_nominations: dict[str, list[str]]
    :type policy_updates: dict[str, list[str]]
    :type rights_cache: dict[str, list[str]]
    :type report_dm: discord.DMChannel
    """

    def __init__(self, *, loop=None, **options):
        intents = Intents.default()
        intents.members = True
        super().__init__("", loop=loop, intents=intents, **options)
        log("C4-DE online!")
        self.timezone_offset = 5

        self.initial_run = True
        self.run_edelweiss = False
        self.rss_data = {}

        self.version = None
        with open(VERSION_FILE, "r") as f:
            self.version = f.readline()

        self.site = Site(user="C4-DE Bot")
        self.site.login(user="C4-DE Bot")

        self.bots = ["01miki10-bot", "C4-DE Bot", "EcksBot", "JocastaBot", "RoboCade", "PLUMEBOT", "TOM-E Macaron.ii"]

        self.channels = {}
        self.emoji_storage = {}

        self.ready = False

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

        self.overdue_cts = []
        self.project_data = {}

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

        try:
            info = report_version_info(self.site, self.version)
            if info:
                await self.text_channel(ANNOUNCEMENTS).send(info)
        except Exception as e:
            error_log(type(e), e)

        if not self.ready:
            self.check_membership_nominations.start()
            self.check_rights_nominations.start()
            self.check_consensus_track_statuses.start()
            self.check_policy.start()
            self.check_internal_rss.start()
            self.check_external_rss.start()
            self.check_senate_hall_threads.start()
            self.check_spoiler_templates.start()
            self.load_isbns.start()
            self.check_edelweiss.start()
            self.ready = True

            # for message in await self.text_channel(ANNOUNCEMENTS).history(limit=25).flatten():
            #     if message.id == 1089920440388026530:
            #         await message.edit(content=f"📢 **LucaRoR has been nominated for Rollback rights!**\n<{SITE_URL}/Wookieepedia:Requests_for_user_rights/Rollback/LucaRoR>")
            #     elif message.id == 1089753200040611952:
            #         await message.edit(content=f"📢 **AnilSerifoglu has been nominated for Rollback rights!**\n<{SITE_URL}/Wookieepedia:Requests_for_user_rights/Rollback/AnilSerifoglu>")

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
        return False

    def get_user_ids(self):
        results = {}
        for user in self.text_channel(MAIN).guild.members:
            results[user.name] = user.id
        return results

    async def report_error(self, command, text, *args):
        try:
            await self.report_dm.send(f"Command: {command}")
            await self.report_dm.send(f"ERROR: {text}\t{args}")
        except Exception:
            error_log(text, *args)

    commands = {
        "is_reload_command": "handle_reload_command",
        "is_single_preload_command": "handle_single_preload_command",
        "is_preload_command": "handle_preload_command"
    }

    async def on_message(self, message: Message):
        if message.author == self.user:
            return
        elif isinstance(message.channel, DMChannel):
            await self.handle_direct_message(message)
            return
        elif not (self.is_mention(message) or "@C4DE" in message.content or "@C4-DE" in message.content):
            return

        log(f'Message from {message.author} in {message.channel}: [{message.content}]')

        if "Hello!" in message.content:
            await message.channel.send("Hello there!")
            return

        await self.handle_commands(message, False)

        for identifier, handler in self.commands.items():
            command_dict = getattr(self, identifier)(message)
            if command_dict:
                await getattr(self, handler)(message, command_dict)
                return

    async def handle_direct_message(self, message: Message):
        if message.author.id != CADE:
            return

        if message.content == "end" or message.content == "kill":
            sys.exit()

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

    async def delete_message(self, id_string, channel):
        message_ids = [i.strip() for i in id_string.split(",")]
        for message in await self.text_channel(channel).history(limit=30).flatten():
            if str(message.id) in message_ids:
                await message.delete()

    async def handle_commands(self, message: Message, dm):
        channel = self.text_channel("bot-requests") if dm else message.channel

        if "list all commands" in message.content:
            await self.update_command_messages()
            return

        if "rss" in message.content.lower():
            await self.check_internal_rss()
            return

        if "edelweiss" in message.content.lower():
            self.run_edelweiss = False
            messages = run_edelweiss_protocol(self.site)
            for m in messages:
                await channel.send(m)
            return

        if "ghost touch" in message.content.lower():
            await self.ghost_touch(message)
            return

        if "spoiler" in message.content.lower():
            for page in pywikibot.Category(self.site, "Articles with expired spoiler notices").articles(namespaces=0):
                try:
                    remove_spoiler_tags_from_page(self.site, page, offset=self.timezone_offset)
                except Exception as e:
                    error_log(f"Encountered {type(e)} while removing spoiler template from {page.title()}", e)
                    await self.text_channel(COMMANDS).send(f"Encountered {type(e)} while removing expired spoiler template from {page.title()}. Please check template usage for anomalies.")
            return

        if "isbn" in message.content.lower():
            page = pywikibot.Page(self.site, "Template:ISBN/data")
            last_revision = next(r for r in page.revisions(reverse=True, total=10) if r["user"] == "JocastaBot")
            time_since_last_edit = (datetime.now() + timedelta(hours=self.timezone_offset)) - last_revision['timestamp']
            if time_since_last_edit.total_seconds() < (60 * 60 * 6):
                print(time_since_last_edit.total_seconds(), 60 * 60 * 6)
                log(f"Skipping ISBN reload, last edit was {last_revision['timestamp']}, {datetime.now()}")
                return
            print("Loading ISBNs")
            calculate_isbns_for_all_pages(self.site)
            return

    def list_commands(self):
        text = [
            f"Current C4DE Commands (v. {self.version}):",
            f"- **@C4-DE reload data** - reloads data from User:C4-DE/RSS and User:JocastaBot/Project Data",
            f"- **@C4-DE RSS** - check internal RSS feeds and report changes to #announcements (runs every 5 minutes)",
            f"- **@C4-DE Edelweiss** - analyzes Edelweiss publishing catalog and reports new items or changes"
            f" (runs at 8 AM CST)",
            f"- **@C4-DE ISBN** - updates Template:ISBN/data with the ISBNs present in all articles (runs at 7 AM CST)",
            f"- **@C4-DE spoiler** - removes expired spoiler notices from articless (runs at 6 AM CST)",
            f"- **@C4-DE check preloads** - checks all infobox preloads for missing fields, and also reports fields"
            f" missing from InfoboxParamCheck",
            f"- **@C4-DE check preload for Template:<template>** - checks a particular infobox and its preload",
            f"- **@C4-DE update preload for Template:<template>** - checks a particular infobox and its preload, and"
            f" updates the preload with the missing parameters. Does not change the parameters in InfoboxParamCheck."
        ]

        related = [
            "**Additional Protocols:**",
            "- Archives stagnant Senate Hall threads (runs every 4 hours)",
            "**Additional Info (contact Cade if you have questions):**",
            f"- RSS feed configuration JSON: {SITE_URL}/User:C4-DE/RSS",
        ]

        return {1072245240913723522: "\n".join(text), 1072245242566299698: "\n".join(related)}

    async def update_command_messages(self):
        posts = self.list_commands()
        pins = await self.text_channel(COMMANDS).pins()
        target = None
        for post in pins:
            if post.id in posts:
                await post.edit(content=posts[post.id])
            if post.id == 1072245240913723522:
                target = post

        if target:
            await target.reply("**Commands have been updated! Please view this channel's pinned messages for more info.**")

    async def ghost_touch(self, message: Message):
        match = re.search("[Gg]host touch Category:(.*?)$", message.content)
        if match:
            await message.add_reaction(TIMER)
            category = Category(self.site, match.group(1))
            if not category.exists():
                await message.add_reaction(EXCLAMATION)
                return
            for page in category.articles():
                try:
                    text = page.get()
                    page.put(text, "Bot: Ghost edit to update WhatLinksHere. Tell Cade if you see this.")
                except pywikibot.exceptions.NoPageError:
                    continue
                except pywikibot.exceptions.LockedPageError:
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
        page = pywikibot.Page(self.site, "User:C4-DE Bot/RSS")
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
        self.rss_data = data

    async def reload_project_data(self):
        log("Loading news filters")
        page = pywikibot.Page(self.site, "User:JocastaBot/Project Data")
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

    @tasks.loop(hours=4)
    async def check_senate_hall_threads(self):
        archive_stagnant_senate_hall_threads(self.site, self.timezone_offset)

    @tasks.loop(hours=1)
    async def check_spoiler_templates(self):
        if datetime.now().hour != 6:
            return
        log("Scheduled Operation: Checking {{Spoiler}} templates")
        for page in pywikibot.Category(self.site, "Articles with expired spoiler notices").articles(namespaces=0):
            remove_spoiler_tags_from_page(self.site, page, offset=self.timezone_offset)

    @tasks.loop(hours=1)
    async def load_isbns(self):
        if datetime.now().hour != 7:
            return
        page = pywikibot.Page(self.site, "Template:ISBN/data")
        last_revision = next(r for r in page.revisions(reverse=True, total=10) if r["user"] == "JocastaBot")
        time_since_last_edit = (datetime.now() + timedelta(hours=self.timezone_offset)) - last_revision['timestamp']
        if time_since_last_edit.total_seconds() < (60 * 60 * 6):
            log(f"Skipping ISBN reload, last edit was {last_revision['timestamp']}")
            return
        log("Scheduled Operation: Calculating ISBNs")
        calculate_isbns_for_all_pages(self.site)

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
        messages = run_edelweiss_protocol(self.site, True)
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
        updates = check_policy(self.site)
        messages = []
        for date, posts in updates.items():
            for post in posts:
                if post['link'] not in self.policy_updates.get(date, []):
                    link = self.prepare_link(post['link'])
                    messages.append(f"🗨️ **{post['link']}** has completed with the following result: **{post['result']}**\n<{SITE_URL}/{link}>")

        for message in messages:
            await self.text_channel(ANNOUNCEMENTS).send(message)

        self.policy_updates = {d: [l['link'] for l in v] for d, v in updates.items()}

        with open(POLICY_CACHE, "w") as f:
            f.writelines(json.dumps(self.policy_updates, indent=4))

    @tasks.loop(minutes=15)
    async def check_membership_nominations(self):
        log("Checking board membership nominations")
        current_nominations = check_review_board_nominations(self.site)
        messages = []
        for board, noms in current_nominations.items():
            for user in noms:
                if user not in self.board_nominations[board]:
                    username = self.prepare_link(user)
                    emote = self.emoji_by_name(BOARD_EMOTES[board])
                    messages.append(f"{emote} **{user} has been nominated for membership in the {board}!**\n<{SITE_URL}/Wookieepedia:Review_board_membership_nominations#{username}>")

        for message in messages:
            await self.text_channel(ANNOUNCEMENTS).send(message)

        self.board_nominations = current_nominations

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
                        messages.append(f"📢 **{user} has been nominated for removal of their user rights. Please weigh in here.**\n<{SITE_URL}/Wookieepedia:Requests_for_removal_of_user_rights/{right}/{username}>")
                    else:
                        messages.append(f"📢 **{user} has been nominated for {right} rights!**\n<{SITE_URL}/Wookieepedia:Requests_for_user_rights/{right}/{username}>")

        for message in messages:
            await self.text_channel(ANNOUNCEMENTS).send(message)

        self.rights_cache = current_nominations

        with open(RIGHTS_CACHE, "w") as f:
            f.writelines(json.dumps(self.rights_cache, indent=4))

    @tasks.loop(minutes=30)
    async def check_consensus_track_statuses(self):
        log("Checking status of active Consensus Track votes")
        cts = check_consensus_track_duration(self.site, self.timezone_offset)
        overdue = []
        for page, duration in cts.items():
            print(f"{page}: {duration} ({page in self.overdue_cts})")
            if page in self.overdue_cts or duration.days >= 14:
                overdue.append(page)

        for page in overdue:
            if page in self.overdue_cts:
                continue
            link = self.prepare_link(page)
            message = f"**{page}** has been open for 14 days and can now be archived\n<{SITE_URL}/{link}>"
            await self.text_channel("admin-help").send(message)
        self.overdue_cts = overdue

    CHANNEL_FILTERS = {
        "the-high-republic": ["high republic"],
        "galaxys-edge": ["galaxys edge", "galaxy's edge", "halcyon", "galactic starcruiser"]
    }

    @tasks.loop(minutes=5)
    async def check_internal_rss(self):
        log("Checking internal RSS feeds")

        messages_to_post = check_wookieepedia_feeds(self.site, self.internal_rss_cache)

        for channel, message in messages_to_post:
            try:
                await self.text_channel(channel).send(message)
            except Exception as e:
                await self.report_error(f"RSS: {message}", type(e), e)

        with open(INTERNAL_RSS_CACHE, "w") as f:
            f.writelines(json.dumps(self.internal_rss_cache, indent=4))

    @tasks.loop(minutes=10)
    async def check_external_rss(self):
        log("Checking external RSS feeds")

        messages_to_post = []

        for site, site_data in self.rss_data["sites"].items():
            if site == "StarWars.com":
                messages = check_sw_news_page(site_data["url"], self.external_rss_cache["sites"], site_data["title"])
            elif site_data.get("url"):
                messages = check_latest_url(site_data["url"], self.external_rss_cache["sites"], site, site_data["title"])
            else:
                messages = check_rss_feed(site_data["rss"], self.external_rss_cache["sites"], site, site_data["title"],
                                          site_data.get("nonSW", False))
            for m in reversed(messages):
                messages_to_post += await self.prepare_new_rss_message(m, site_data, False)

        for site, site_data in self.rss_data["YouTube"].items():
            messages = check_rss_feed(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={site_data['channelId']}",
                self.external_rss_cache["YouTube"], site, "<h1 class=\"title.*?><.*?>(.*?)</.*?></h1>", site_data.get("sw"))
            for m in reversed(messages):
                messages_to_post += await self.prepare_new_rss_message(m, site_data, True)

        for channel, message in messages_to_post:
            try:
                await self.text_channel(channel).send(message)
            except Exception as e:
                await self.report_error(f"RSS: {message}", type(e), e)

        with open(EXTERNAL_RSS_CACHE, "w") as f:
            f.writelines(json.dumps(self.external_rss_cache, indent=4))

    async def prepare_new_rss_message(self, m: dict, site_data: dict, youtube: bool) -> List[Tuple[str, str]]:
        log(f"Archiving URL: {m['url']}")
        success, archivedate = archive_url(m["url"])
        if youtube:
            t = f"New Video on the official {m['site']} YouTube channel"
        else:
            t = f"New Article on {m['site']}"
        f = m["title"].replace("''", "*")
        msg = "{0} **{1}:**    {2}\n- <{3}>".format(self.emoji_by_name(site_data["emoji"]), t, f, m["url"])

        include_archivedate = success
        if success and site_data.get("addToArchive"):
            try:
                self.add_urls_to_archive(site_data["template"], m["url"].replace(site_data["baseUrl"] + "/", ""),
                                         archivedate)
                include_archivedate = False
            except Exception as e:
                await self.report_error(m["url"], type(e), e)

        template = self.build_citation_template(m, youtube, site_data, archivedate if include_archivedate else None)
        msg += f"\n- `{template}`"

        if success:
            msg += f"\n- Wayback Archive Date: {archivedate}"
        else:
            msg += f"\n- Unable to archive URL: {archivedate.splitlines()[0]}"

        results = [(UPDATES, msg)]
        for c in site_data.get("channels", []):
            results.append((c, msg))

        for project, data in self.project_data.items():
            if data.get("newsFilters"):
                for f in data["newsFilters"]:
                    if f in msg.replace("-", "").lower() or f in m["content"].lower():
                        results.append((data["channel"], msg))

        return results

    @staticmethod
    def build_citation_template(msg: dict, youtube, site_data: dict, archivedate):
        t = msg['title'].replace("|", "&#124;")
        if youtube:
            result = f"{site_data['template']}|{msg['videoId']}|{t}"
        else:
            url = msg["url"].replace(site_data["baseUrl"] + "/", "")
            result = f"{site_data['template']}|url={url}|text={t}"
        if archivedate:
            result += f"|archivedate={archivedate}"
        return "{{" + result + "}}"

    def add_urls_to_archive(self, template, new_url, archivedate):
        page = pywikibot.Page(self.site, f"Template:{template}/Archive")
        if page.exists():
            text = page.get()
            new_text = self.build_archive_template_text(text, new_url, archivedate)
        else:
            page = pywikibot.Page(self.site, f"Module:ArchiveAccess/{template}")
            text = page.get()
            new_text = self.build_archive_module_text(text, new_url, archivedate)

        if text == new_text:
            return

        try:
            page.put("\n".join(new_text), f"Archiving {archivedate} for new URL: {new_url}")
        except pywikibot.exceptions.OtherPageSaveError:
            self.site.login()
            page.put("\n".join(new_text), f"Archiving {archivedate} for new URL: {new_url}")

    @staticmethod
    def build_archive_template_text(text, new_url, archivedate):
        special_start = "<!-- Start" in text
        new_text = []
        found, start = False, False
        u = new_url.replace("=", "{{=}}")
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
        special_start = "p.knownArchiveDates = {" in text
        new_text = []
        found, start = False, False
        u = new_url.replace("=", "{{=}}")
        for line in text.splitlines():
            if not start and special_start:
                start = "p.knownArchiveDates = {" in line
            elif not start:
                start = line.strip().startswith("|")
            elif not found and f"| ['{u}']" in line:
                log(f"URL {u} is already archived")
                return
            elif not found and u < line.strip()[1:].strip():
                new_text.append(f"	['{u}'] = '{archivedate}',")
                found = True
            new_text.append(line)

        return new_text
