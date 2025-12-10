import asyncio
import logging
from celery import Celery, signals
from patchright.async_api import BrowserContext, async_playwright, Playwright

from scraper.pool import PagePool, create_page_pool
from scraper.match import get_match_result
from scraper.vetos import get_vetos
from scraper.map import get_maps_stats
from scraper.player import get_players_maps_stats

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global browser context and pool that persists across tasks
browser: None | BrowserContext = None
page_pool: None | PagePool = None
playwright_instance: None | Playwright = None
event_loop: None | asyncio.AbstractEventLoop = None

app = Celery(
    "clutch_or_predict",
    broker="redis://:senha@localhost:6379/0",
)
app.conf.update(
    result_backend="redis://:senha@localhost:6379/0",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@signals.worker_process_init.connect
def init_worker(**kwargs):
    """Initialize the browser and page pool when worker starts"""
    global browser, page_pool, playwright_instance, event_loop
    logger.info("Initializing browser context and page pool for worker")

    # Create a new event loop for this worker process
    event_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(event_loop)

    async def setup():
        global browser, page_pool, playwright_instance
        playwright_instance = await async_playwright().start()
        browser = await playwright_instance.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright",
            channel="chrome",
            headless=False,
            no_viewport=True,
        )
        page_pool = await create_page_pool(browser, max_amount_of_concurrent_pages=5)
        logger.info("Browser context and page pool initialized successfully")

    event_loop.run_until_complete(setup())


@signals.worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """Clean up browser and page pool when worker shuts down"""
    global browser, page_pool, playwright_instance, event_loop
    logger.info("Shutting down browser context and page pool")

    async def cleanup():
        global browser, playwright_instance
        if browser is not None:
            await browser.close()
            logger.info("Browser context closed successfully")
        if playwright_instance is not None:
            await playwright_instance.stop()
            logger.info("Playwright instance stopped")

    if event_loop is not None:
        event_loop.run_until_complete(cleanup())
        event_loop.close()


@app.task(
    bind=True, name="scraper.tasks.scrape_match", max_retries=3, default_retry_delay=10
)
def scrape_match(self, match_url: str):
    """
    Scrape a CS:GO/CS2 match from HLTV.

    Args:
        match_url: Full URL to the HLTV match page

    Returns:
        Dictionary containing match_result, players_stats, vetos, and maps_stats
    """
    global page_pool, event_loop

    if page_pool is None:
        raise RuntimeError(
            "Page pool not initialized. Worker may not have started properly."
        )

    if event_loop is None:
        raise RuntimeError(
            "Event loop not initialized. Worker may not have started properly."
        )

    logger.info(f"Starting to scrape match: {match_url}")

    # Type narrowing for the closure
    pool = page_pool

    async def scrape():
        logger.debug("Starting concurrent scraping tasks")

        async def process_match():
            logger.debug("Acquiring page for match processing")
            async with pool.get_page() as page:
                logger.debug(f"Processing match: {match_url}")
                result = await get_match_result(page, match_url)
                logger.debug("Match processing completed")
                return result

        async def process_players_stats():
            logger.debug("Starting player stats processing")
            result = await get_players_maps_stats(pool, match_url)
            logger.debug("Player stats processing completed")
            return result

        async def process_vetos():
            logger.debug("Acquiring page for vetos processing")
            async with pool.get_page() as page:
                logger.debug(f"Processing vetos: {match_url}")
                result = await get_vetos(page, match_url)
                logger.debug("Vetos processing completed")
                return result

        async def process_maps():
            logger.debug("Acquiring page for maps processing")
            async with pool.get_page() as page:
                logger.debug(f"Processing maps: {match_url}")
                result = await get_maps_stats(page, match_url)
                logger.debug("Maps processing completed")
                return result

        # Run all scraping tasks concurrently
        match_result, players_stats, vetos, maps_stats = await asyncio.gather(
            process_match(),
            process_players_stats(),
            process_vetos(),
            process_maps(),
        )

        return {
            "match_result": match_result.model_dump() if match_result else None,
            "players_stats": [p.model_dump() for p in players_stats]
            if players_stats
            else [],
            "vetos": vetos.model_dump() if vetos else None,
            "maps_stats": [m.model_dump() for m in maps_stats] if maps_stats else [],
        }

    try:
        result = event_loop.run_until_complete(scrape())
        logger.info(f"Successfully scraped match: {match_url}")
        return result
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry()
