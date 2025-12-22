import asyncio
from datetime import datetime, timedelta
from typing import List

import redis
import re
from scraper.config import get_broker_url
from scraper.celery import event as process_event
from patchright.async_api import async_playwright, Page
from parsel import Selector
import logging

from scraper.pool import create_page_pool

logger = logging.getLogger(__name__)

visited_key = "hltv:top_events_visited_urls"


async def __parse_links_on_page(page: Page, redis_client: redis.Redis):
    selector = Selector(await page.content())

    events = selector.css("td.name-col a::attr(href)").getall()
    events_ids: List[str] = []

    regex = re.compile(r"event=(\d+)")

    for event in events:
        event_id_match = regex.search(event)
        if event_id_match:
            events_ids.append(event_id_match.group(1))
        else:
            logger.warning(f"Could not extract event ID from URL: {event}")

    full_urls = [
        f"https://www.hltv.org/events/{event_id}/event" for event_id in events_ids
    ]

    amount_found = len(full_urls)
    new_events = 0

    for event_url in full_urls:
        if redis_client.sismember(visited_key, event_url):
            logger.info(f"Already visited event URL: {event_url}, skipping.")
            continue

        new_events += 1
        logger.info(f"Found event URL: {event_url}")
        process_event.delay(  # type: ignore
            event_url, top_event=True
        )  # Enqueue the event scraping task using celery's
        redis_client.sadd(visited_key, event_url)

    logger.info(f"Total event URLs found: {amount_found}, New events: {new_events}")


async def __parse_page(page: Page, redis_client: redis.Redis, url: str):
    await page.goto(url, wait_until="domcontentloaded")
    await __parse_links_on_page(page, redis_client)

    pagination_next_locator = page.locator(
        ".stats-headline-pagination .pagination-next"
    ).first
    pagination_next_class = await pagination_next_locator.get_attribute("class")

    while pagination_next_class is not None and "inactive" not in pagination_next_class:
        await pagination_next_locator.click()
        pagination_next_locator = page.locator(
            ".stats-headline-pagination .pagination-next"
        ).first
        pagination_next_class = await pagination_next_locator.get_attribute("class")
        await __parse_links_on_page(page, redis_client)


async def scrape(url: str, clear_visited: bool = False):
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="/tmp/playwright",
                channel="chrome",
                headless=False,
                no_viewport=True,
            )
            redis_client = redis.Redis.from_url(
                url=get_broker_url(),
            )
            pool = await create_page_pool(
                browser, max_amount_of_concurrent_pages=1, initial_page_size=1
            )

            if clear_visited:
                redis_client.delete(visited_key)

            async with pool.get_page() as page:
                await __parse_page(page, redis_client, url)

        except Exception as e:
            print(f"An error occurred: {e}")


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
        "--clear-visited",
        action="store_true",
        help="Clear visited URLs cache before crawling",
    )

    args = parser.parse_args()

    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d")

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d")

    url = f"https://www.hltv.org/stats/events?csVersion=CS2&startDate={start_date.strftime('%Y-%m-%d')}&endDate={end_date.strftime('%Y-%m-%d')}&rankingFilter=Top50"

    asyncio.run(scrape(url, args.clear_visited))


if __name__ == "__main__":
    main()
