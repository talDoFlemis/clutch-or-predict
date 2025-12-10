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
        default_timeout=default_timeout,
    )


class PagePool:
    def __init__(
        self,
        browser: BrowserContext,
        queue: asyncio.Queue,
        max_amount_of_concurrent_pages: int,
        initial_page_size: int,
        minimum_page_size: int,
        default_timeout: int,
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

        if (
            self.pages.qsize() == 0
            and self.current_page_count < self.max_amount_of_concurrent_pages
        ):
            logger.debug("Creating a new page for the pool")
            page = await self.browser.new_page()
            page.set_default_timeout(self.default_timeout)
            self.current_page_count += 1
            return page

        # If we can't create more, wait for a page to be released
        page = await self.pages.get()
        logger.debug(
            f"Acquired page from pool. Current pool size: {self.pages.qsize()}"
        )
        return page

    async def release(self, page: Page):
        logger.debug(
            "Returning page to pool",
            extra={
                "pool_size": self.pages.qsize(),
                "current_page_count": self.current_page_count,
            },
        )

        if self.pages.qsize() >= self.minimum_page_size:
            logger.debug("Closing page as pool is above minimum size")
            await page.close()
            self.current_page_count -= 1
            return

        await self.pages.put(page)
        logger.debug(f"Page returned to pool. Current pool size: {self.pages.qsize()}")

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
