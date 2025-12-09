import asyncio
import logging
from patchright.async_api import BrowserContext, Page, async_playwright

from scraper.match import get_match_result
from scraper.vetos import get_vetos

logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

bo1_match = "https://www.hltv.org/matches/2388622/wild-vs-sentinels-digital-warriors-fall-cup-2025"
bo3_match = "https://www.hltv.org/matches/2388119/g2-vs-the-mongolz-starladder-budapest-major-2025"
bo5_match = (
    "https://www.hltv.org/matches/2380134/mouz-vs-vitality-blast-open-lisbon-2025"
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
            await page.goto(bo5_match, wait_until="domcontentloaded")
            match_result = await get_match_result(page)
            print(f"{match_result.model_dump_json()}")
            vetos = await get_vetos(
                page, match_result.team_1_name, match_result.team_2_name
            )
            print(f"{vetos.model_dump_json()}")
        except Exception as e:
            logger.exception(f"An error occurred: {e}")

        finally:
            if browser is not None:
                await browser.close()


def scrape():
    asyncio.run(main())


if __name__ == "__main__":
    scrape()
