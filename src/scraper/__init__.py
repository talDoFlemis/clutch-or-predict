import asyncio
import logging
from patchright.async_api import BrowserContext, Page, async_playwright

from scraper.match import get_match_result
from scraper.models import MatchResult
from scraper.pool import PagePool, create_page_pool
from scraper.vetos import get_vetos
from scraper.map import get_maps_stats
from scraper.player import get_players_maps_stats

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

bo1_match = "https://www.hltv.org/matches/2388622/wild-vs-sentinels-digital-warriors-fall-cup-2025"
bo3_match = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"
bo5_match = (
    "https://www.hltv.org/matches/2380134/mouz-vs-vitality-blast-open-lisbon-2025"
)


async def process_vetos(pool: PagePool, url: str, team_1_name: str, team_2_name: str):
    async with pool.get_page() as page:
        vetos = await get_vetos(
            page,
            url,
            team_1_name,
            team_2_name,
        )
        print(f"{vetos.model_dump_json()}")


async def process_maps(pool: PagePool, url: str, team_1_name: str, team_2_name: str):
    async with pool.get_page() as page:
        maps = await get_maps_stats(
            page,
            url,
            team_1_name,
            team_2_name,
        )
        [print(f"{map_stat.model_dump_json()}") for map_stat in maps]


async def process_match(pool: PagePool, url: str) -> MatchResult:
    async with pool.get_page() as page:
        page.set_default_timeout(5000)
        await page.goto(url, wait_until="domcontentloaded")

        match_result = await get_match_result(page, url)
        print(f"{match_result.model_dump_json()}")
        return match_result


async def process_players_stats(pool: PagePool, url: str):
    player_stats = await get_players_maps_stats(pool, url)
    [print(f"{player_stat.model_dump_json()}") for player_stat in player_stats]


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
            url = bo5_match

            start = asyncio.get_event_loop().time()
            pool = await create_page_pool(browser)

            match_result = await process_match(pool, url)

            tasks = [
                process_players_stats(pool, url),
                process_vetos(
                    pool,
                    url,
                    match_result.team_1_name,
                    match_result.team_2_name,
                ),
                process_maps(
                    pool,
                    url,
                    match_result.team_1_name,
                    match_result.team_2_name,
                ),
            ]

            await asyncio.gather(*tasks)

            end = asyncio.get_event_loop().time()

            logger.info(
                f"Scraping completed in {end - start:.2f} seconds",
            )

        except Exception as e:
            logger.exception(f"An error occurred: {e}")

        finally:
            if browser is not None:
                await browser.close()


def scrape():
    asyncio.run(main())


if __name__ == "__main__":
    scrape()
