import asyncio
import logging
import os
import sys
from patchright.async_api import BrowserContext, async_playwright

from scraper.config import get_debug_port, get_debug_address

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

browser: None | BrowserContext = None


async def start_browser():
    logger.info("Starting global browser server...")
    logger.info(f"DISPLAY environment variable: {os.environ.get('DISPLAY')}")

    global browser

    # Get the debugging port and address from configuration
    debug_port = get_debug_port()
    debug_address = get_debug_address()
    logger.info(f"Chrome remote debugging port: {debug_port}")
    logger.info(f"Chrome remote debugging address: {debug_address}")

    try:
        async with async_playwright() as p:
            logger.info("Launching Chrome browser...")
            browser = await p.chromium.launch_persistent_context(
                user_data_dir="/tmp/chrome-profile",
                channel="chrome",
                headless=False,
                no_viewport=True,
                args=[
                    f"--remote-debugging-port={debug_port}",
                    f"--remote-debugging-address={debug_address}",
                ],
            )

            logger.info("Browser launched successfully!")
            logger.info(f"Remote debugging available at http://{debug_address}:{debug_port}")
            logger.info("Press Ctrl+C to stop the browser server")
            sys.stdout.flush()

            await asyncio.Event().wait()

    except Exception as e:
        logger.error(f"Failed to start browser: {e}")
        raise


def main():
    logger.info("Initializing browser server...")
    try:
        asyncio.run(start_browser())
    except KeyboardInterrupt:
        logger.info("Browser server stopped by user.")
    except Exception as e:
        logger.exception(f"An error occurred while starting the browser server: {e}")
    finally:
        if browser:
            asyncio.run(browser.close())


if __name__ == "__main__":
    main()
