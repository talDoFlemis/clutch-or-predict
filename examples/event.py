import asyncio

from patchright.async_api import async_playwright, Page
import redis

from scraper.pool import create_page_pool
from scraper.event import get_event


async def scrape():
    url = "https://www.hltv.org/events/8870/wraith-tesfed-league-season-2"
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(
                channel="chrome",
                headless=False,
            )
            pool = await create_page_pool(
                browser, max_amount_of_concurrent_pages=1, initial_page_size=1
            )

            async with pool.get_page() as page:
                event = await get_event(page, url)
                print(f"{event.model_dump_json()}")

        except Exception as e:
            print(f"An error occurred: {e}")


def main():
    asyncio.run(scrape())


if __name__ == "__main__":
    main()
