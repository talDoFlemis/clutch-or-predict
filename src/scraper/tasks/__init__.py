import asyncio
import logging
import threading
from celery import Celery, signals
from patchright.async_api import BrowserContext, async_playwright, Playwright

from scraper.pool import PagePool, create_page_pool
from scraper.match import get_match_result
from scraper.vetos import get_vetos
from scraper.map import get_maps_stats
from scraper.player import get_players_maps_stats

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global variables
browser: None | BrowserContext = None
page_pool: None | PagePool = None
playwright_instance: None | Playwright = None
event_loop: None | asyncio.AbstractEventLoop = None
loop_thread: None | threading.Thread = None

# Thread-safety controls
_init_lock = threading.Lock()
_is_initialized = False

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


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """Run the asyncio loop forever in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def ensure_initialized():
    """
    Ensure the browser and page pool are initialized.
    This method is thread-safe and idempotent.
    """
    global \
        browser, \
        page_pool, \
        playwright_instance, \
        event_loop, \
        loop_thread, \
        _is_initialized

    # Fast check without lock
    if _is_initialized:
        return

    with _init_lock:
        # Double-check inside lock
        if _is_initialized:
            return

        logger.info("Initializing browser context and page pool...")

        try:
            # 1. Start the dedicated asyncio loop if not exists
            if event_loop is None:
                event_loop = asyncio.new_event_loop()
                loop_thread = threading.Thread(
                    target=_start_background_loop, args=(event_loop,), daemon=True
                )
                loop_thread.start()

            # 2. Define the setup coroutine
            async def setup():
                global browser, page_pool, playwright_instance
                logger.debug("Starting Playwright...")
                playwright_instance = await async_playwright().start()

                logger.debug("Launching Persistent Context...")
                browser = await playwright_instance.chromium.launch_persistent_context(
                    user_data_dir="/tmp/playwright",
                    channel="chrome",
                    headless=False,
                    no_viewport=True,
                    args=["--no-sandbox", "--disable-setuid-sandbox"],
                )

                logger.debug("Creating Page Pool...")
                page_pool = await create_page_pool(
                    browser,
                    max_amount_of_concurrent_pages=20,
                )

            # 3. Run setup on the background loop and wait for result
            future = asyncio.run_coroutine_threadsafe(setup(), event_loop)
            future.result()  # This will raise if setup fails

            _is_initialized = True
            logger.info("Browser context and page pool initialized successfully")

        except Exception as e:
            logger.exception("Failed to initialize worker resources")
            raise e


@signals.worker_process_init.connect
def init_worker(**kwargs):
    """Attempt initialization when worker process starts."""
    try:
        ensure_initialized()
    except Exception:
        # If it fails here, it might retry in the task
        pass


@signals.worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """Clean up browser and page pool when worker shuts down."""
    global \
        browser, \
        page_pool, \
        playwright_instance, \
        event_loop, \
        loop_thread, \
        _is_initialized
    logger.info("Shutting down browser context and page pool")

    async def cleanup():
        global browser, playwright_instance
        if browser is not None:
            await browser.close()
            logger.info("Browser context closed successfully")
        if playwright_instance is not None:
            await playwright_instance.stop()
            logger.info("Playwright instance stopped")

    try:
        if event_loop is not None and event_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(cleanup(), event_loop)
            future.result()
            event_loop.call_soon_threadsafe(event_loop.stop)
            if loop_thread is not None:
                loop_thread.join(timeout=5)
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        _is_initialized = False


@app.task(
    bind=True, name="scraper.tasks.scrape_match", max_retries=3, default_retry_delay=10
)
def scrape_match(self, match_url: str):
    """
    Scrape a CS:GO/CS2 match from HLTV.
    """
    global page_pool, event_loop

    # 1. Ensure resources are initialized (Lazy Load)
    try:
        ensure_initialized()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        # Retry the task if initialization failed (maybe temporary resource issue)
        self.retry(exc=e)

    if page_pool is None or event_loop is None:
        # Should not happen due to ensure_initialized raising, but purely for type safety
        raise RuntimeError("Resources failed to initialize properly.")

    logger.info(f"Starting to scrape match: {match_url}")

    # Capture pool variable for closure
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

        # Run all scraping sub-tasks concurrently
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
        # Submit the scraping coroutine to our dedicated event loop
        # This blocks the Celery thread but not the event loop
        future = asyncio.run_coroutine_threadsafe(scrape(), event_loop)
        result = future.result()
        logger.info(f"Successfully scraped match: {match_url}")
        return result
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry(exc=e)
