from datetime import datetime, timedelta
from typing import Any, Callable, Coroutine, Optional
from urllib.parse import urlencode
import logging
import asyncio
from patchright.async_api import async_playwright, Page
from scraper.celery import full_match

import redis

from scraper.pool import create_page_pool
from scraper.config import settings

logger = logging.getLogger(__name__)


class HLTVFrontier:
    BASE_URL = "https://www.hltv.org/results"
    VISITED_SET_KEY = "hltv:visited_urls"

    def __init__(self):
        # Get Redis configuration from dynaconf settings
        host = "2804:1a04:807d:8b00:be24:11ff:fe85:e66b"
        port = settings.get("redis.port", 6379)
        password = settings.get("redis.password", "")
        db = settings.get("redis.db", 0)

        self.redis_client = redis.Redis(
            host=host,
            port=port,
            password=password if password else None,
            db=db,
            decode_responses=True,
        )

    def build_url(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> str:
        if end_date is None:
            end_date = datetime.now()

        if start_date is None:
            start_date = end_date - timedelta(days=1)

        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "gameType": "CS2",
        }

        return f"{self.BASE_URL}?{urlencode(params)}"

    def is_visited(self, url: str) -> bool:
        return self.redis_client.sismember(self.VISITED_SET_KEY, url) == 1

    def mark_visited(self, url: str) -> None:
        self.redis_client.sadd(self.VISITED_SET_KEY, url)

    async def parse(
        self,
        url: str,
        parser: Callable[[str], Coroutine[Any, Any, None]],
        force: bool = False,
    ) -> bool:
        if not force and self.is_visited(url):
            print(f"Skipping already visited URL: {url}")
            return False

        self.mark_visited(url)

        await parser(url)

        return True

    async def crawl(
        self,
        parser: Callable[[str], Coroutine[Any, Any, None]],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        force: bool = False,
    ) -> None:
        url = self.build_url(start_date, end_date)
        await self.parse(url, parser, force=force)

    def clear_visited(self) -> None:
        self.redis_client.delete(self.VISITED_SET_KEY)
        logger.info("Cleared all visited URLs")

    def close(self) -> None:
        self.redis_client.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


async def __parse_links_on_page(page: Page, frontier: HLTVFrontier):
    links_locator = await page.locator(".result-con .a-reset").all()

    amount_of_links = 0

    for link_locator in links_locator:
        href = await link_locator.get_attribute("href")
        if href is not None:
            full_url = f"https://www.hltv.org{href}"
            if not frontier.is_visited(full_url):
                logger.info(f"Match URL: {full_url}")
                frontier.mark_visited(full_url)
                full_match.delay(full_url)  # type: ignore
                amount_of_links += 1
            else:
                logger.info(f"Skipping already visited match URL: {full_url}")

    logger.info(f"Found {amount_of_links} new match links on the page.")


async def __parse_results_page(page: Page, url: str, frontier: HLTVFrontier) -> None:
    logger.info(f"Parsing results page: {url}")
    await page.goto(url)
    await __parse_links_on_page(page, frontier)

    pagination_next_locator = page.locator(".results .pagination-next").first
    pagination_next_class = await pagination_next_locator.get_attribute("class")

    while pagination_next_class is not None and "inactive" not in pagination_next_class:
        await pagination_next_locator.click()
        pagination_next_locator = page.locator(".results .pagination-next").first
        pagination_next_class = await pagination_next_locator.get_attribute("class")
        await __parse_links_on_page(page, frontier)

    logger.info(f"Finished parsing results page: {url}")


async def run_frontier(
    args: Any, start_date: Optional[datetime], end_date: Optional[datetime]
) -> None:
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="/tmp/playwright",
                channel="chrome",
                headless=False,
                no_viewport=True,
            )

            start = asyncio.get_event_loop().time()
            pool = await create_page_pool(
                browser, max_amount_of_concurrent_pages=1, initial_page_size=1
            )

            with HLTVFrontier() as frontier:
                if args.clear_visited:
                    frontier.clear_visited()

                async def parser(url: str) -> None:
                    async with pool.get_page() as page:
                        await __parse_results_page(page, url, frontier)

                await frontier.crawl(
                    parser=parser,
                    start_date=start_date,
                    end_date=end_date,
                    force=args.force,
                )

            end = asyncio.get_event_loop().time()
            logger.info(
                f"Scraping completed in {end - start:.2f} seconds",
            )

        except Exception as e:
            logger.exception(f"An error occurred: {e}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Crawl HLTV results for a given date range"
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date in YYYY-MM-DD format (defaults to yesterday)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date in YYYY-MM-DD format (defaults to today)",
    )
    parser.add_argument(
        "--redis-host",
        type=str,
        default="localhost",
        help="Redis host (default: localhost)",
    )
    parser.add_argument(
        "--redis-port",
        type=int,
        default=6379,
        help="Redis port (default: 6379)",
    )
    parser.add_argument(
        "--redis-password",
        type=str,
        default="senha",
        help="Redis password (default: senha)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-fetch even if URL was previously visited",
    )
    parser.add_argument(
        "--clear-visited",
        action="store_true",
        help="Clear all visited URLs before crawling",
    )

    args = parser.parse_args()

    start_date = None
    end_date = None

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    asyncio.run(run_frontier(args, start_date, end_date))


if __name__ == "__main__":
    main()
