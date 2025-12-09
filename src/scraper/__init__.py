import asyncio
import logging
from patchright.async_api import BrowserContext, Page, async_playwright
import re
from pydantic import BaseModel
from datetime import datetime

logger = logging.getLogger(__name__)

url = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"


class MatchResult(BaseModel):
    team_1_name: str
    team_1_id: str
    team_1_map_score: int
    team_2_name: str
    team_2_map_score: int
    team_2_id: str
    team_winner: str
    event_name: str
    event_id: str
    date: datetime


# class MapStat(BaseModel):
#     map_stat_id: str
#     map_name: str
#
#     team_1_score: int
#     team_1_ct_score: int
#     team_1_tr_score: int
#
#     team_2_score: int
#     team_2_ct_score: int
#     team_2_tr_score: int
#
#     picked_by: str


async def get_match_result(page: Page) -> MatchResult:
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

    return MatchResult(
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


async def main():
    browser: None | BrowserContext = None

    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="/tmp/playwright",
                channel="chrome",
                headless=False,
                no_viewport=True,
            )
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            match_result = await get_match_result(page)
            print(f"{match_result.model_dump_json()}")
        except Exception as e:
            logger.exception(f"An error occurred: {e}")

        finally:
            if browser is not None:
                await browser.close()


def scrape():
    asyncio.run(main())


if __name__ == "__main__":
    scrape()
