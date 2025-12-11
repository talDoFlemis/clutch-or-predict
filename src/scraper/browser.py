import asyncio
import logging
from patchright.async_api import BrowserContext, async_playwright

logger = logging.getLogger(__name__)

browser: None | BrowserContext = None


async def start_browser():
    logger.info("Starting global browser server...")

    async with async_playwright() as p:
        global browser

        browser = await p.chromium.launch_persistent_context(
            user_data_dir="/tmp/playwright",
            channel="chrome",
            headless=False,
            no_viewport=True,
            args=["--remote-debugging-port=9222"],
        )
        await asyncio.Event().wait()


def main():
    asyncio.run(start_browser())


if __name__ == "__main__":
    logger.info("Initializing browser server...")
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Browser server stopped by user.")
    except Exception as e:
        logger.exception(f"An error occurred while starting the browser server: {e}")
    finally:
        if browser is not None:
            asyncio.run(browser.close())
