import asyncio
import ipaddress
import logging
import socket
import threading
from celery import Celery, signals
from patchright.async_api import BrowserContext, async_playwright, Playwright

from scraper.pool import PagePool, create_page_pool
from scraper.match import get_match_result
from scraper.vetos import get_vetos
from scraper.map import get_maps_stats
from scraper.player import get_players_maps_stats
from scraper.config import (
    get_broker_url,
    get_celery_worker_concurrency,
    get_celery_worker_log_level,
    get_page_pool_max_amount,
    get_page_pool_initial_size,
    get_page_pool_minimum_amount,
    get_page_pool_default_timeout,
    get_browser_use_cdp,
    get_browser_user_data_dir,
    get_browser_channel,
    get_browser_headless,
    get_browser_no_viewport,
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
browser: None | BrowserContext = None
page_pool: None | PagePool = None
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
                    browser_server = (
                        await playwright_instance.chromium.connect_over_cdp(cdp_url)
                    )
                    browser = browser_server.contexts[0]
                    logger.debug("Connected to remote browser successfully")
                else:
                    # Launch persistent context locally
                    logger.debug("Launching Persistent Context...")
                    browser = (
                        await playwright_instance.chromium.launch_persistent_context(
                            user_data_dir=get_browser_user_data_dir(),
                            channel=get_browser_channel(),
                            headless=get_browser_headless(),
                            no_viewport=get_browser_no_viewport(),
                            args=["--no-sandbox", "--disable-setuid-sandbox"],
                        )
                    )
                    logger.debug("Persistent context launched successfully")

                logger.debug("Creating Page Pool...")
                page_pool = await create_page_pool(
                    browser,
                    max_amount_of_concurrent_pages=get_page_pool_max_amount(),
                    initial_page_size=get_page_pool_initial_size(),
                    minimum_page_size=get_page_pool_minimum_amount(),
                    default_timeout=get_page_pool_default_timeout(),
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
    bind=True,
    name="scraper.tasks.match_result",
    max_retries=3,
)
def match_result(self, match_url: str):
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
        raise RuntimeError("Resources failed to initialize properly.")

    # Capture pool variable for closure
    pool = page_pool

    async def scrape():
        async with pool.get_page() as page:
            return await get_match_result(page, match_url)

    try:
        future = asyncio.run_coroutine_threadsafe(scrape(), event_loop)
        result = future.result()
        return result.model_dump_json()
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry(exc=e)


@app.task(
    bind=True,
    name="scraper.tasks.vetos",
    max_retries=3,
)
def vetos(self, match_url: str):
    """
    Pull only the vetos of a CS:GO/CS2 match from HLTV.
    """
    global page_pool, event_loop

    try:
        ensure_initialized()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        self.retry(exc=e)

    if page_pool is None or event_loop is None:
        raise RuntimeError("Resources failed to initialize properly.")

    # Capture pool variable for closure
    pool = page_pool

    async def scrape():
        async with pool.get_page() as page:
            return await get_vetos(page, match_url)

    try:
        future = asyncio.run_coroutine_threadsafe(scrape(), event_loop)
        result = future.result()
        return result.model_dump_json()
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry(exc=e)


@app.task(
    bind=True,
    name="scraper.tasks.maps",
    max_retries=3,
)
def maps(self, match_url: str):
    """
    Process only the maps stats of a CS:GO/CS2 match from HLTV.
    """
    global page_pool, event_loop

    try:
        ensure_initialized()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        self.retry(exc=e)

    if page_pool is None or event_loop is None:
        raise RuntimeError("Resources failed to initialize properly.")

    # Capture pool variable for closure
    pool = page_pool

    async def scrape():
        async with pool.get_page() as page:
            result = await get_maps_stats(page, match_url)
            return result

    try:
        future = asyncio.run_coroutine_threadsafe(scrape(), event_loop)
        result = future.result()
        return [map.model_dump_json() for map in result]
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry(exc=e)


@app.task(
    bind=True,
    name="scraper.tasks.player_stats",
    max_retries=3,
    default_retry_delay=10,
)
def player_stats(self, match_url: str):
    """
    Process only the player stats of a CS:GO/CS2 match from HLTV.
    """
    global page_pool, event_loop

    try:
        ensure_initialized()
    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        self.retry(exc=e)

    if page_pool is None or event_loop is None:
        raise RuntimeError("Resources failed to initialize properly.")

    # Capture pool variable for closure
    pool = page_pool

    try:
        future = asyncio.run_coroutine_threadsafe(
            get_players_maps_stats(pool, match_url), event_loop
        )
        result = future.result()
        logger.info(f"Successfully scraped match: {match_url}")
        return [player.model_dump_json() for player in result]
    except Exception as e:
        logger.exception(f"Fatal error in scrape: {e}")
        self.retry(exc=e)
