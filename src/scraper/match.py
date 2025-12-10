import re
from scraper.models import MatchResult
import logging
from datetime import datetime
from patchright.async_api import Page

logger = logging.getLogger(__name__)


async def get_match_id(url: str) -> str:
    match = re.search(r"/matches/(\d+)", url)
    if match is None:
        raise ValueError("Failed to find match id")

    return match.group(1)


async def get_team_names(page: Page) -> tuple[str, str]:
    """Extract team names from an already loaded match page."""
    team_box = page.locator(".teamsBox")
    team_1_name = (
        await team_box.locator(".team1-gradient").locator(".teamName").inner_text()
    )
    team_2_name = (
        await team_box.locator(".team2-gradient").locator(".teamName").inner_text()
    )
    return team_1_name, team_2_name


async def get_match_result(page: Page, match_url: str) -> MatchResult:
    await page.goto(match_url, wait_until="domcontentloaded")
    team_box = page.locator(".teamsBox")

    team_1 = team_box.locator(".team1-gradient")

    team_1_href = await team_1.get_by_role("link").get_attribute("href")
    match = re.search(r"/team/(\d+)", team_1_href or "")
    if match is None:
        raise ValueError("Team 1 ID not found")
    team_1_id = match.group(1)

    team_1_name = await team_1.locator(".teamName").inner_text()

    team_1_map_score = team_1.locator("xpath=/div")

    team_2 = team_box.locator(".team2-gradient")

    team_2_href = await team_2.get_by_role("link").get_attribute("href")
    match = re.search(r"/team/(\d+)", team_2_href or "")
    if match is None:
        raise ValueError("Team 2 ID not found")
    team_2_id = match.group(1)

    team_2_name = await team_2.locator(".teamName").inner_text()

    team_2_map_score = team_2.locator("xpath=/div")

    time_and_event = page.locator(".timeAndEvent")

    date = await time_and_event.locator(".time").get_attribute("data-unix")
    if date is None:
        raise ValueError("Date not found")

    event_link = time_and_event.get_by_role("link")
    event_href = await event_link.get_attribute("href")

    match = re.search(r"/events/(\d+)", event_href or "")

    if match is None:
        raise ValueError("Event ID not found in href")

    event_id = match.group(1)
    event_name = await event_link.get_attribute("title")

    match = re.search(r"/matches/(\d+)", page.url)
    if match is None:
        raise ValueError("Failed to find match id")

    match_id = match.group(1)

    return MatchResult(
        match_id=match_id,
        team_1_id=team_1_id,
        team_2_id=team_2_id,
        team_1_name=team_1_name,
        team_2_name=team_2_name,
        team_1_map_score=int(await team_1_map_score.inner_text()),
        team_2_map_score=int(await team_2_map_score.inner_text()),
        team_winner=team_1_id
        if int(await team_1_map_score.inner_text())
        > int(await team_2_map_score.inner_text())
        else team_2_id,
        event_name=event_name or "",
        event_id=event_id,
        date=datetime.fromtimestamp(float(date) / 1000),
    )
