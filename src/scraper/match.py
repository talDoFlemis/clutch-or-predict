import re
from scraper.models import MatchResult
import logging
from datetime import datetime
from patchright.async_api import Page
from parsel import Selector

logger = logging.getLogger(__name__)


async def get_match_id(url: str) -> str:
    match = re.search(r"/matches/(\d+)", url)
    if match is None:
        raise ValueError("Failed to find match id")

    return match.group(1)


def get_team_names_from_selector(selector: Selector) -> tuple[str, str]:
    """Extract team names from a parsel Selector."""
    team_1_name = selector.css(".teamsBox .team1-gradient .teamName::text").get()
    team_2_name = selector.css(".teamsBox .team2-gradient .teamName::text").get()

    if not team_1_name or not team_2_name:
        raise ValueError("Failed to extract team names")

    return team_1_name, team_2_name


async def get_team_names(page: Page) -> tuple[str, str]:
    """Extract team names from an already loaded match page using parsel."""
    html = await page.content()
    selector = Selector(html)
    return get_team_names_from_selector(selector)


async def get_match_result(page: Page, match_url: str) -> MatchResult:
    await page.goto(match_url, wait_until="domcontentloaded")

    # Get HTML content and create parsel selector
    html = await page.content()
    selector = Selector(html)

    # Extract team 1 information
    team_1_href = selector.css(".teamsBox .team1-gradient a::attr(href)").get()
    match = re.search(r"/team/(\d+)", team_1_href or "")
    if match is None:
        raise ValueError("Team 1 ID not found")
    team_1_id = match.group(1)

    team_1_name = selector.css(".teamsBox .team1-gradient .teamName::text").get()
    if not team_1_name:
        raise ValueError("Team 1 name not found")

    team_1_map_score_text = selector.css(".teamsBox .team1-gradient > div::text").get()
    if not team_1_map_score_text:
        raise ValueError("Team 1 map score not found")

    # Extract team 2 information
    team_2_href = selector.css(".teamsBox .team2-gradient a::attr(href)").get()
    match = re.search(r"/team/(\d+)", team_2_href or "")
    if match is None:
        raise ValueError("Team 2 ID not found")
    team_2_id = match.group(1)

    team_2_name = selector.css(".teamsBox .team2-gradient .teamName::text").get()
    if not team_2_name:
        raise ValueError("Team 2 name not found")

    team_2_map_score_text = selector.css(".teamsBox .team2-gradient > div::text").get()
    if not team_2_map_score_text:
        raise ValueError("Team 2 map score not found")

    # Extract date
    date = selector.css(".timeAndEvent .time::attr(data-unix)").get()
    if date is None:
        raise ValueError("Date not found")

    # Extract event information
    event_href = selector.css(".timeAndEvent a::attr(href)").get()
    match = re.search(r"/events/(\d+)", event_href or "")
    if match is None:
        raise ValueError("Event ID not found in href")
    event_id = match.group(1)

    event_name = selector.css(".timeAndEvent a::attr(title)").get()

    # Extract match ID from current URL
    match = re.search(r"/matches/(\d+)", page.url)
    if match is None:
        raise ValueError("Failed to find match id")
    match_id = match.group(1)

    team_1_score = int(team_1_map_score_text)
    team_2_score = int(team_2_map_score_text)

    return MatchResult(
        match_id=match_id,
        team_1_id=team_1_id,
        team_2_id=team_2_id,
        team_1_name=team_1_name,
        team_2_name=team_2_name,
        team_1_map_score=team_1_score,
        team_2_map_score=team_2_score,
        team_winner=team_1_id if team_1_score > team_2_score else team_2_id,
        event_name=event_name or "",
        event_id=event_id,
        date=datetime.fromtimestamp(float(date) / 1000),
    )
