from typing import Dict
from pywikibot import Page

nom_type_data = {
    "CA": {
        "name": "Comprehensive",
        "page": "Wookieepedia:Comprehensive articles",
        "nominationPage": "Wookieepedia:Comprehensive article nominations",
        "category": "Category:Wookieepedia Comprehensive articles",
        "nominationCategory": "Category:Wookieepedia Comprehensive article nomination pages",
        "votesCategory": "Category:Comprehensive article nominations with sufficient votes",
        "reviewVotes": (4, 4, "{{ec}}"),
        "icon": "File:ComprehensiveIcon.png",
        "premiumIcon": "File:Premium-ComprehensiveArticle.png",
        "channel": "educorps",
        "overdueDays": 7,
        "notificationDays": 6
    },
    "GA": {
        "name": "Good",
        "page": "Wookieepedia:Good articles",
        "nominationPage": "Wookieepedia:Good article nominations",
        "category": "Category:Wookieepedia Good articles",
        "nominationCategory": "Category:Wookieepedia Good article nomination pages",
        "votesCategory": "Category:Good article nominations with sufficient votes",
        "reviewVotes": (5, 3, "{{ac}}"),
        "icon": "File:GoodIcon.png",
        "premiumIcon": "File:Premium-GoodIcon.png",
        "channel": "agricorps",
        "overdueDays": 10,
        "notificationDays": 8
    },
    "FA": {
        "name": "Featured",
        "page": "Wookieepedia:Featured articles",
        "nominationPage": "Wookieepedia:Featured article nominations",
        "category": "Category:Wookieepedia Featured articles",
        "nominationCategory": "Category:Wookieepedia Featured article nomination pages",
        "votesCategory": "Category:Featured article nominations with sufficient votes",
        "reviewVotes": (7, 7, "{{inq}}"),
        "icon": "File:LinkFA-star.png",
        "premiumIcon": "File:Premium-FeaturedIcon.png",
        "channel": "inquisitorius",
        "overdueDays": 14,
        "notificationDays": 10
    }
}


class NominationType:
    def __init__(self, abbr: str, data: Dict[str, str]):
        self.abbreviation = abbr
        self.name = data["name"]
        self.page = data["page"]
        self.category = data["category"]
        self.nomination_page = data["nominationPage"]
        self.nomination_category = data["nominationCategory"]
        self.votes_category = data["votesCategory"]
        self.review_votes = data["reviewVotes"]
        self.icon = data["icon"]
        self.premium_icon = data["premiumIcon"]
        self.channel = data["channel"]
        self.overdue_days = data["overdueDays"]
        self.notification_days = data["notificationDays"]

    def build_report_message(self, page: Page, nominator: str):
        url = page.site.base_url(page.site.article_path) + page.title()
        return f"New **{self.name} article nomination** by **{nominator}**\n<{url.replace(' ', '_')}>"


def build_nom_types():
    result = {}
    for k, v in nom_type_data.items():
        x = NominationType(k, v)
        result[k] = x
        result[f"{k}N"] = x
    return result


NOM_TYPES = build_nom_types()
