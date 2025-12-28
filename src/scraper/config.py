"""
Configuration module for scraper using Dynaconf.
"""

from pathlib import Path
from dynaconf import Dynaconf

# Get the directory where this config file is located
settings_dir = Path(__file__).parent

settings = Dynaconf(
    envvar_prefix="SCRAPER",
    settings_files=[
        settings_dir / "settings.yaml",
        settings_dir / ".secrets.yaml",
    ],
    environments=True,
    load_dotenv=True,
    merge_enabled=True,
)


def get_broker_url() -> str:
    """
    Build the Redis broker URL from configuration.

    Returns:
        str: The complete Redis broker URL in the format:
             redis://[:password]@host:port/db
    """
    user = settings.get("redis.user", "")
    password = settings.get("redis.password", "")
    host = settings.get("redis.host", "localhost")
    port = settings.get("redis.port", 6379)
    db = settings.get("redis.db", 0)

    # Build auth part
    auth = ""
    if password:
        if user:
            auth = f"{user}:{password}@"
        else:
            auth = f":{password}@"
    elif user:
        auth = f"{user}@"

    return f"redis://{auth}{host}:{port}/{db}"


def get_celery_worker_concurrency() -> int:
    """Get the number of concurrent worker processes/threads."""
    return settings.get("celery.worker_concurrency", 4)


def get_celery_worker_log_level() -> str:
    """Get the worker log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)."""
    return settings.get("celery.worker_log_level", "DEBUG")


def get_page_pool_max_amount() -> int:
    """Get the maximum amount of concurrent pages for the page pool."""
    return settings.get("page_pool.max_amount", 30)

def get_maximum_operations_per_context() -> int:
    """Get the maximum number of operations per browser context."""
    return settings.get("page_pool.maximum_operations_per_context", 200)


def get_page_pool_initial_size() -> int:
    """Get the initial page size for the page pool."""
    return settings.get("page_pool.initial_size", 30)


def get_page_pool_minimum_amount() -> int:
    """Get the minimum amount of pages to maintain in the pool."""
    return settings.get("page_pool.minimum_amount", 30)


def get_page_pool_default_timeout() -> int:
    """Get the default timeout in milliseconds for page operations."""
    return settings.get("page_pool.default_timeout", 30000)


def get_browser_use_cdp() -> bool:
    """Get whether to use CDP to connect to a remote browser."""
    return settings.get("browser.use_cdp", False)


def get_browser_user_data_dir() -> str:
    """Get the user data directory for persistent browser context."""
    return settings.get("browser.user_data_dir", "/tmp/playwright")


def get_browser_channel() -> str:
    """Get the browser channel (e.g., 'chrome', 'msedge')."""
    return settings.get("browser.channel", "chrome")


def get_browser_headless() -> bool:
    """Get whether to run browser in headless mode."""
    return settings.get("browser.headless", False)


def get_browser_no_viewport() -> bool:
    """Get whether to disable viewport."""
    return settings.get("browser.no_viewport", True)


def get_debug_port() -> int:
    """Get the Chrome remote debugging port."""
    return settings.get("browser.debug_port", 9222)


def get_debug_address() -> str:
    """Get the Chrome remote debugging address."""
    return settings.get("browser.debug_address", "127.0.0.1")
