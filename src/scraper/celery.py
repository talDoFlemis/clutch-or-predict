import asyncio
import ipaddress
import logging
import socket
import threading
from celery import Celery, signals
from parsel import Selector
from patchright.async_api import Browser, async_playwright, Playwright
from psycopg import AsyncConnection

from db import pool
from scraper.event import get_event
from scraper.pool import PagePool, create_page_pool
from scraper.match import get_match_result, get_match_result_from_selector
from scraper.vetos import get_vetos, get_vetos_from_selector
from scraper.map import get_maps_stats, get_map_stats_from_selector
from scraper.player import get_players_maps_stats
from scraper.models import VetoBoxNotFoundError, Event
from scraper.db_ops import (
    insert_event,
    insert_match_result,
    insert_vetos,
    insert_map_stats,
    insert_player_stats,
)
from scraper.config import (
    get_broker_url,
    get_celery_worker_concurrency,
    get_celery_worker_log_level,
    get_maximum_operations_per_context,
    get_page_pool_max_amount,
    get_page_pool_initial_size,
    get_page_pool_minimum_amount,
    get_page_pool_default_timeout,
    get_browser_use_cdp,
    get_browser_channel,
    get_browser_headless,
    get_debug_port,
    get_debug_address,
)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def is_ip_address(address: str) -> bool:
    """Check if the given string is a valid IP address."""
    try:
        ipaddress.ip_address(address)
        return True
    except ValueError:
        return False


# Global variables
browser: None | Browser = None
page_pool: None | PagePool = None
db_pool: None | pool.DatabasePool = None
playwright_instance: None | Playwright = None
event_loop: None | asyncio.AbstractEventLoop = None
loop_thread: None | threading.Thread = None

# Thread-safety controls
_init_lock = threading.Lock()
_is_initialized = False

# Get broker URL from config
broker_url = get_broker_url()

app = Celery(
    "clutch_or_predict",
    broker=broker_url,
)
app.conf.update(
    result_backend=broker_url,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=get_celery_worker_concurrency(),
    worker_log_level=get_celery_worker_log_level(),
)


def _start_background_loop(loop: asyncio.AbstractEventLoop):
    """Run the asyncio loop forever in a background thread."""
    asyncio.set_event_loop(loop)
    loop.run_forever()


def ensure_initialized():
    global \
        browser, \
        page_pool, \
        playwright_instance, \
        event_loop, \
        loop_thread, \
        _is_initialized, \
        db_pool

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
                global browser, page_pool, playwright_instance, db_pool
                logger.debug("Starting Playwright...")
                playwright_instance = await async_playwright().start()

                use_cdp = get_browser_use_cdp()

                if use_cdp:
                    # Connect to remote browser via CDP
                    # Resolve hostname to IP address (CDP requires IP or localhost)
                    debug_address = get_debug_address()
                    debug_port = get_debug_port()

                    # Resolve hostname to IP if not already an IP address
                    if not is_ip_address(debug_address):
                        try:
                            resolved_ip = socket.gethostbyname(debug_address)
                            logger.debug(f"Resolved {debug_address} to {resolved_ip}")
                            debug_address = resolved_ip
                        except socket.gaierror as e:
                            logger.warning(
                                f"Failed to resolve {debug_address}: {e}, using as-is"
                            )

                    cdp_url = f"http://{debug_address}:{debug_port}"
                    logger.debug(
                        f"Connecting to remote browser via CDP at {cdp_url}..."
                    )
                    browser = await playwright_instance.chromium.connect_over_cdp(
                        cdp_url
                    )
                    logger.debug("Connected to remote browser successfully")
                else:
                    # Launch persistent context locally
                    logger.debug("Launching Persistent Context...")
                    browser = await playwright_instance.chromium.launch(
                        channel=get_browser_channel(),
                        headless=get_browser_headless(),
                        args=["--no-sandbox", "--disable-setuid-sandbox"],
                    )
                    logger.debug("Persistent context launched successfully")

                logger.debug("Creating Page Pool...")
                page_pool = await create_page_pool(
                    browser,
                    max_amount_of_concurrent_pages=get_page_pool_max_amount(),
                    initial_page_size=get_page_pool_initial_size(),
                    minimum_page_size=get_page_pool_minimum_amount(),
                    default_timeout=get_page_pool_default_timeout(),
                    maximum_operations_per_context=get_maximum_operations_per_context(),
                )

                db_pool = pool.DatabasePool()
                await db_pool.open()

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
    try:
        ensure_initialized()
    except Exception:
        # If it fails here, it might retry in the task
        pass


@signals.worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    global \
        browser, \
        page_pool, \
        playwright_instance, \
        event_loop, \
        loop_thread, \
        _is_initialized, \
        db_pool
    logger.info("Shutting down browser context and page pool")

    async def cleanup():
        global browser, playwright_instance
        if page_pool is not None:
            await page_pool.close_all_pages()
            logger.info("Page pool closed successfully")
        if browser is not None:
            await browser.close()
            logger.info("Browser context closed successfully")
        if playwright_instance is not None:
            await playwright_instance.stop()
            logger.info("Playwright instance stopped")
        if db_pool is not None:
            await db_pool.close()
            logger.info("Database pool closed successfully")

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


# Async processing functions
async def process_match_result(
    page_pool: PagePool, conn: AsyncConnection, match_url: str
):
    async with page_pool.get_page() as page:
        result = await get_match_result(page, match_url)
        await insert_match_result(conn, result)
        return result


async def process_vetos(page_pool: PagePool, conn: AsyncConnection, match_url: str):
    async with page_pool.get_page() as page:
        result = await get_vetos(page, match_url)
        await insert_vetos(conn, result)
        return result


async def process_maps(page_pool: PagePool, conn: AsyncConnection, match_url: str):
    async with page_pool.get_page() as page:
        result = await get_maps_stats(page, match_url)
        await insert_map_stats(conn, result)
        return result


async def process_player_stats(
    page_pool: PagePool, conn: AsyncConnection, match_url: str
):
    result = await get_players_maps_stats(page_pool, match_url)
    await insert_player_stats(conn, result)
    return result


async def process_full_match(
    page_pool: PagePool, conn: AsyncConnection, match_url: str
):
    try:
        async with page_pool.get_page() as page:
            await page.goto(match_url, wait_until="domcontentloaded")
            selector = Selector(await page.content())

            match_result = await get_match_result_from_selector(selector, match_url)
            await insert_match_result(conn, match_result)

            map_stats = await get_map_stats_from_selector(selector, match_url)
            await insert_map_stats(conn, map_stats)

            vetos = await get_vetos_from_selector(selector, match_url)
            await insert_vetos(conn, vetos)

        await process_player_stats(page_pool, conn, match_url)

        # If all succeed, commit the transaction
        await conn.commit()

        return {"status": "ok"}
    except Exception as e:
        # Rollback on any error
        await conn.rollback()
        logger.error(f"Transaction failed for {match_url}, rolled back: {e}")
        raise


async def process_event(
    page_pool: PagePool, conn: AsyncConnection, event_url: str, top_event: bool = False
) -> Event:
    async with page_pool.get_page() as page:
        event = await get_event(page, event_url)
        event.has_top_50_teams = top_event
        await insert_event(conn, event)
        return event


def _run_async_task(self, coro_func, match_url: str, serialize_list=False):
    global page_pool, event_loop, db_pool

    try:
        ensure_initialized()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        self.retry(exc=e)

    if page_pool is None or event_loop is None or db_pool is None:
        logger.error(
            f"Page pool {page_pool}, event loop {event_loop}, db pool {db_pool} not ready"
        )
        raise RuntimeError("Resources failed to initialize properly.")

    async def wrapper(page_pool, db_pool, match_url):
        async with db_pool.get_connection() as conn:
            return await coro_func(page_pool, conn, match_url)

    try:
        future = asyncio.run_coroutine_threadsafe(
            wrapper(page_pool, db_pool, match_url), event_loop
        )
        result = future.result()

        return result
    except Exception as e:
        logger.exception(f"Fatal error in task: {e}")
        self.retry(exc=e)


@app.task(bind=True, name="scraper.tasks.match_result", max_retries=3)
def match_result(self, match_url: str):
    """Scrape a CS:GO/CS2 match from HLTV."""
    return _run_async_task(self, process_match_result, match_url)


@app.task(bind=True, name="scraper.tasks.vetos", max_retries=3)
def vetos(self, match_url: str):
    """Pull only the vetos of a CS:GO/CS2 match from HLTV."""
    return _run_async_task(self, process_vetos, match_url)


@app.task(bind=True, name="scraper.tasks.maps", max_retries=3)
def maps(self, match_url: str):
    """Process only the maps stats of a CS:GO/CS2 match from HLTV."""
    return _run_async_task(self, process_maps, match_url, serialize_list=True)


@app.task(
    bind=True, name="scraper.tasks.player_stats", max_retries=3, default_retry_delay=10
)
def player_stats(self, match_url: str):
    """Process only the player stats of a CS:GO/CS2 match from HLTV."""
    result = _run_async_task(self, process_player_stats, match_url, serialize_list=True)
    logger.info(f"Successfully scraped match: {match_url}")
    return result


@app.task(bind=True, name="scraper.tasks.full_match", max_retries=3)
def full_match(self, match_url: str):
    """
    Scrape complete match data (match result, vetos, maps, player stats) in a single transaction.
    All data is committed atomically - if any part fails, nothing is saved.
    """
    global page_pool, event_loop, db_pool

    try:
        ensure_initialized()

        if page_pool is None or event_loop is None or db_pool is None:
            logger.error(
                f"Page pool {page_pool}, event loop {event_loop}, db pool {db_pool} not ready"
            )
            raise RuntimeError("Resources failed to initialize properly.")

        async def scrape(db_pool, page_pool, match_url):
            async with db_pool.get_connection() as conn:
                return await process_full_match(page_pool, conn, match_url)

        future = asyncio.run_coroutine_threadsafe(
            scrape(db_pool, page_pool, match_url), event_loop
        )

        result = future.result()
        logger.info(f"Successfully scraped full match: {match_url}")
        return result
    except VetoBoxNotFoundError as e:
        logger.warning(f"Veto box not found for match {match_url}: {e} - Not retrying")
        return None
    except Exception as e:
        logger.exception(f"Fatal error in full match scrape: {e}")
        self.retry(exc=e)


@app.task(bind=True, name="scraper.tasks.event", max_retries=3)
def event(self, event_url: str, top_event: bool = False):
    """Scrape Event from a CS:GO/CS2 event from HLTV."""
    global page_pool, event_loop, db_pool

    try:
        ensure_initialized()

        if page_pool is None or event_loop is None or db_pool is None:
            logger.error(
                f"Page pool {page_pool}, event loop {event_loop}, db pool {db_pool} not ready"
            )
            raise RuntimeError("Resources failed to initialize properly.")

        async def scrape(
            db_pool: pool.DatabasePool, page_pool: PagePool, event_url: str
        ):
            async with db_pool.get_connection() as conn:
                return await process_event(page_pool, conn, event_url, top_event)

        future = asyncio.run_coroutine_threadsafe(
            scrape(db_pool, page_pool, event_url), event_loop
        )

        result = future.result()
        logger.info(f"Successfully scraped event: {event_url}")
        return result.model_dump_json()
    except Exception as e:
        logger.exception(f"Fatal error in full event scrape: {e}")
        self.retry(exc=e)
