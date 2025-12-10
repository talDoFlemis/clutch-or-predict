import asyncio
from patchright.async_api import BrowserContext, Page
from contextlib import asynccontextmanager
import logging


logger = logging.getLogger(__name__)


async def create_page_pool(
    browser: BrowserContext,
    max_amount_of_concurrent_pages: int = 10,
    initial_page_size: int = 5,
    minimum_page_size: int = 5,
    default_timeout: int = 10000,
):
    queue = asyncio.Queue(maxsize=max_amount_of_concurrent_pages)
    pages = [await browser.new_page() for _ in range(initial_page_size)]

    for page in pages:
        page.set_default_timeout(default_timeout)

    [await queue.put(page) for page in pages]

    return PagePool(
        browser,
        queue=queue,
        max_amount_of_concurrent_pages=max_amount_of_concurrent_pages,
        initial_page_size=initial_page_size,
        minimum_page_size=minimum_page_size,
    )


class PagePool:
    def __init__(
        self,
        browser: BrowserContext,
        queue: asyncio.Queue,
        max_amount_of_concurrent_pages: int = 10,
        initial_page_size: int = 5,
        minimum_page_size: int = 5,
        default_timeout: int = 5000,
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

        self.browser = browser
        self.max_amount_of_concurrent_pages = max_amount_of_concurrent_pages
        self.initial_page_size = initial_page_size
        self.minimum_page_size = minimum_page_size
        self.pages = queue
        self.current_page_count = initial_page_size
        self._lock = asyncio.Lock()
        self.default_timeout = default_timeout

    async def acquire(self) -> Page:
        assert self.pages.qsize() >= 0
        logger.debug(
            f"Acquiring page from pool. Current pool size: {self.pages.qsize()}"
        )

        # Try to get from queue first, but don't block if empty and we can create more
        try:
            page = self.pages.get_nowait()
            logger.debug(
                f"Acquired page from pool. Current pool size: {self.pages.qsize()}"
            )
            return page
        except asyncio.QueueEmpty:
            pass

        # If queue is empty and we haven't reached max capacity, create a new page
        async with self._lock:
            # Double-check after acquiring lock
            if not self.pages.empty():
                page = await self.pages.get()
                logger.debug(
                    f"Acquired page from pool. Current pool size: {self.pages.qsize()}"
                )
                return page

            if self.current_page_count < self.max_amount_of_concurrent_pages:
                logger.debug(
                    f"Pool empty, creating new page. Current count: {self.current_page_count}"
                )
                page = await self.browser.new_page()
                page.set_default_timeout(self.default_timeout)
                self.current_page_count += 1
                logger.debug(
                    f"Created new page. Current count: {self.current_page_count}"
                )
                return page

        # If we can't create more, wait for a page to be released
        page = await self.pages.get()
        logger.debug(
            f"Acquired page from pool. Current pool size: {self.pages.qsize()}"
        )
        return page

    async def release(self, page: Page):
        logger.debug(
            f"Releasing page back to pool. Current count: {self.current_page_count}, queue size: {self.pages.qsize()}"
        )

        # If we're above minimum size and queue is at initial capacity, close the page instead
        async with self._lock:
            if (
                self.current_page_count > self.minimum_page_size
                and self.pages.qsize() >= self.initial_page_size
            ):
                logger.debug(
                    f"Pool at capacity, closing excess page. Current count: {self.current_page_count}"
                )
                await page.close()
                self.current_page_count -= 1
                logger.debug(f"Closed page. Current count: {self.current_page_count}")
                return

        logger.debug("Returning page to pool")
        await self.pages.put(page)

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
