import asyncio
import logging
from patchright.async_api import BrowserContext, async_playwright

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


async def process_vetos(pool: PagePool, url: str):
    async with pool.get_page() as page:
        vetos = await get_vetos(page, url)
        print(f"{vetos.model_dump_json()}")


async def process_maps(pool: PagePool, url: str):
    async with pool.get_page() as page:
        maps = await get_maps_stats(page, url)
        [print(f"{map_stat.model_dump_json()}") for map_stat in maps]


async def process_match(pool: PagePool, url: str) -> MatchResult:
    async with pool.get_page() as page:
        match_result = await get_match_result(page, url)
        print(f"{match_result.model_dump_json()}")
        return match_result


async def process_players_stats(pool: PagePool, url: str):
    player_stats = await get_players_maps_stats(pool, url)
    [print(f"{player_stat.model_dump_json()}") for player_stat in player_stats]


async def main():
    browser: None | BrowserContext = None

    pool: None | PagePool = None
    async with async_playwright() as p:
        try:
            b = await p.chromium.connect_over_cdp("http://localhost:9222")
            url = bo1_match

            start = asyncio.get_event_loop().time()
            pool = await create_page_pool(b)

            tasks = [
                process_match(pool, url),
                process_players_stats(pool, url),
                process_vetos(pool, url),
                process_maps(pool, url),
            ]

            await asyncio.gather(*tasks)
            await pool.close_all_pages()

            end = asyncio.get_event_loop().time()

            logger.info(
                f"Scraping completed in {end - start:.2f} seconds",
            )

            await b.close()

        except Exception as e:
            logger.exception(f"An error occurred: {e}")

        finally:
            if browser is not None:
                await browser.close()
            if pool is not None:
                await pool.close_all_pages()


def scrape():
    asyncio.run(main())


if __name__ == "__main__":
    scrape()
