import asyncio
from patchright.async_api import BrowserContext, Page, Browser
from contextlib import asynccontextmanager
import logging

from scraper.config import get_browser_no_viewport


logger = logging.getLogger(__name__)


async def create_page_pool(
    browser: Browser,
    max_amount_of_concurrent_pages: int = 10,
    initial_page_size: int = 5,
    minimum_page_size: int = 5,
    default_timeout: int = 30000,
    maximum_operations_per_context: int = 200,
):
    browser_context = await browser.new_context(no_viewport=get_browser_no_viewport())

    pages = [await browser_context.new_page() for _ in range(initial_page_size)]

    for page in pages:
        page.set_default_timeout(default_timeout)

    return PagePool(
        browser=browser,
        browser_context=browser_context,
        pages=pages,
        max_amount_of_concurrent_pages=max_amount_of_concurrent_pages,
        initial_page_size=initial_page_size,
        minimum_page_size=minimum_page_size,
        default_timeout=default_timeout,
        maximum_operations_per_context=maximum_operations_per_context,
    )


class PagePool:
    def __init__(
        self,
        browser: Browser,
        browser_context: BrowserContext,
        pages: list[Page],
        max_amount_of_concurrent_pages: int,
        initial_page_size: int,
        minimum_page_size: int,
        default_timeout: int,
        maximum_operations_per_context: int,
    ):
        if initial_page_size > max_amount_of_concurrent_pages:
            raise ValueError(
                "Initial page size cannot be greater than max amount of concurrent pages."
            )
        if initial_page_size <= 0:
            initial_page_size = 1
        if max_amount_of_concurrent_pages <= 0:
            max_amount_of_concurrent_pages = 1
        if minimum_page_size <= 0 or minimum_page_size > initial_page_size:
            minimum_page_size = minimum_page_size

        self.browser_context = browser_context
        self.max_amount_of_concurrent_pages = max_amount_of_concurrent_pages
        self.initial_page_size = initial_page_size
        self.minimum_page_size = minimum_page_size
        self.free_pages = asyncio.Queue(maxsize=max_amount_of_concurrent_pages)
        self.current_page_count = initial_page_size
        self._lock = asyncio.Lock()
        self.default_timeout = default_timeout
        self.max_operations_per_context = maximum_operations_per_context
        self.operation_amount_in_current_context = 0
        self.browser = browser

        for page in pages:
            self.free_pages.put_nowait(page)

    async def acquire(self) -> Page:
        assert self.free_pages.qsize() >= 0

        logger.debug(
            f"Acquiring page from pool. Current pool size: {self.free_pages.qsize()}"
        )

        await self.__create_new_context_if_needed()

        async with self._lock:
            if (
                self.free_pages.qsize() == 0
                and self.current_page_count < self.max_amount_of_concurrent_pages
            ):
                logger.debug("Creating a new page for the pool")
                page = await self.browser_context.new_page()
                page.set_default_timeout(self.default_timeout)
                self.current_page_count += 1
                return page

            # If we can't create more, wait for a page to be released
            page = await self.free_pages.get()
            logger.debug(
                f"Acquired page from pool. Current pool size: {self.free_pages.qsize()}"
            )

            return page

    async def __create_new_context_if_needed(self) -> None:
        async with self._lock:
            if (
                self.operation_amount_in_current_context
                < self.max_operations_per_context
            ):
                self.operation_amount_in_current_context += 1
                return

            logger.info(
                "Maximum operations per context reached. Creating a new browser context."
            )

            await self.close_all_pages()

            self.operation_amount_in_current_context = 0
            await self.browser_context.close()

            self.browser_context = await self.browser.new_context(
                no_viewport=get_browser_no_viewport()
            )

            pages = [
                await self.browser_context.new_page()
                for _ in range(self.initial_page_size)
            ]

            self.current_page_count = len(pages)

            for page in pages:
                page.set_default_timeout(self.default_timeout)
                logger.info(
                    f"Populating new browser context with pages. {self.free_pages.qsize()}"
                )
                await self.free_pages.put(page)

            logger.info("New browser context created.")

    async def release(self, page: Page):
        logger.debug(
            "Returning page to pool",
            extra={
                "pool_size": self.free_pages.qsize(),
                "current_page_count": self.current_page_count,
            },
        )

        async with self._lock:
            if self.free_pages.qsize() > self.minimum_page_size:
                logger.debug("Closing page as pool is above minimum size")
                await page.close()
                self.current_page_count -= 1
                return

            await page.goto("about:blank")
            await self.free_pages.put(page)

            logger.debug(
                f"Page returned to pool. Current pool size: {self.free_pages.qsize()}"
            )

    @asynccontextmanager
    async def get_page(self):
        page = None
        try:
            page = await self.acquire()
            yield page
        except Exception as e:
            logger.exception(f"An error occurred while using the page: {e}")
            raise e
        finally:
            if page is not None:
                await self.release(page)

    async def close_all_pages(self):
        logger.info("Closing all pages in the pool...")

        while not self.free_pages.empty():
            logger.info(f"Closing page. Pages left to close: {self.free_pages.qsize()}")
            page = await self.free_pages.get()
            await page.close()

        logger.info("All pages in the pool have been closed.")
