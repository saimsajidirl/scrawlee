from typing import Any, Optional

from lxml import html as lxml_html
from loguru import logger
from selectolax.parser import HTMLParser

class BrowserResponse:

    def __init__(self, html: str, url: str = "", status_code: int = 200):
        """
        Initializes the browser response object.
        Stores the raw HTML and URL strings.
        Sets up the parsing attributes natively.
        """
        self._html = html
        self._url = url
        self.status_code = status_code
        self._parsed_html: Optional[HTMLParser] = None
        self._parsed_lxml = None
        self._parse()

    def _parse(self) -> None:
        """
        Parses the raw HTML string automatically.
        Initializes the selectolax HTML parser.
        Initializes the lxml HTML element parser.
        """
        if not self._html:
            return
        try:
            self._parsed_html = HTMLParser(self._html)
            self._parsed_lxml = lxml_html.fromstring(self._html)
        except Exception:
            pass

    @property
    def html(self) -> Optional[HTMLParser]:
        """
        Returns the parsed selectolax HTMLParser.
        Allows fast CSS selector-based data extraction.
        Provides a native interface for DOM traversal.
        """
        return self._parsed_html

    @property
    def lxml(self):
        """
        Returns the parsed lxml HtmlElement.
        Allows powerful XPath-based data extraction.
        Provides a native interface for complex queries.
        """
        return self._parsed_lxml

    @property
    def text(self) -> str:
        """
        Returns the raw HTML string content.
        Represents the fully rendered page source.
        Useful for regex or manual string parsing.
        """
        return self._html

    @property
    def url(self) -> str:
        """
        Returns the visited page URL.
        Provides the source location of the response.
        Useful for tracking navigation and references.
        """
        return self._url

    @property
    def auto(self):
        """
        Returns the most useful parsed representation.
        Provides selectolax HTMLParser if successfully parsed.
        Falls back to raw HTML text otherwise.
        """
        return self._parsed_html if self._parsed_html is not None else self._html


class BrowserClient:

    def __init__(
        self,
        proxy: Optional[str] = None,
        headless: bool = False,
        block_images: bool = False,
        block_images_and_css: bool = False,
        profile: Optional[str] = None,
        tiny_profile: bool = False,
        reuse_driver: bool = True,
        bypass_cloudflare: bool = False,
        via_google: bool = True,
    ):
        """
        Initializes the anti-detect browser client.
        Configures connection and stealth settings.
        Sets up the underlying browser driver instance.
        """
        self.proxy = proxy
        self.headless = headless
        self.block_images = block_images
        self.block_images_and_css = block_images_and_css
        self.profile = profile
        self.tiny_profile = tiny_profile
        self.bypass_cloudflare = bypass_cloudflare
        self.via_google = via_google

        self._driver = None
        self._last_result: Any = None
        self._scrape_fn = None
        self._pending_task = None
        self._setup(reuse_driver)

    def _setup(self, reuse_driver: bool) -> None:
        """
        Configures the botasaurus browser driver.
        Applies proxies and performance optimizations.
        Initializes the core execution context wrapper.
        """
        from botasaurus.browser import Driver
        from botasaurus.browser import browser as _bot_browser

        kwargs: dict = {"reuse_driver": reuse_driver}
        if self.proxy:
            kwargs["proxy"] = self.proxy
        if self.headless:
            kwargs["headless"] = True
        if self.block_images_and_css:
            kwargs["block_images_and_css"] = True
        elif self.block_images:
            kwargs["block_images"] = True
        if self.profile:
            kwargs["profile"] = self.profile
            if self.tiny_profile:
                kwargs["tiny_profile"] = True

        @_bot_browser(**kwargs)
        def _execute(driver: Driver, data):
            self._driver = driver
            self._last_result = self._pending_task(driver)

        self._scrape_fn = _execute
        logger.debug("BrowserClient configured: {}", kwargs)

    @property
    def driver(self):
        """
        Provides direct access to the active driver.
        Allows low-level interactions and custom commands.
        Available only after the first navigation completes.
        """
        return self._driver

    def get(
        self,
        url: str,
        via_google: Optional[bool] = None,
        bypass_cloudflare: Optional[bool] = None,
    ) -> BrowserResponse:
        """
        Navigates to the specified target URL.
        Optionally uses a Google referrer for stealth.
        Returns a fully parsed browser response object.
        """
        use_google = via_google if via_google is not None else self.via_google
        use_bypass = (
            bypass_cloudflare
            if bypass_cloudflare is not None
            else self.bypass_cloudflare
        )

        def _task(driver):
            if use_google:
                driver.google_get(url, bypass_cloudflare=use_bypass)
            else:
                driver.get(url)
            return BrowserResponse(driver.page_html, url)

        self._pending_task = _task
        self._scrape_fn()
        return self._last_result

    def fetch(self, url: str) -> BrowserResponse:
        """
        Fetches the target URL via native requests.
        Bypasses full rendering to save significant bandwidth.
        Returns a parsed browser response containing HTML.
        """
        def _task(driver):
            resp = driver.requests.get(url)
            status = getattr(resp, "status_code", 200)
            return BrowserResponse(resp.text, url, status)

        self._pending_task = _task
        self._scrape_fn()
        return self._last_result

    def run(self, task_fn) -> Any:
        """
        Executes a custom function using the driver.
        Allows arbitrary interactions and form submissions.
        Returns the result of the provided callable task.
        """
        self._pending_task = task_fn
        self._scrape_fn()
        return self._last_result

    def close(self) -> None:
        """
        Shuts down the underlying Chrome instance entirely.
        Releases all allocated system resources safely.
        Cleans up the internal execution context references.
        """
        if self._scrape_fn is not None:
            try:
                self._scrape_fn.close()
            except Exception:
                pass

    def __enter__(self):
        """
        Enters the context manager block gracefully.
        Returns the current browser client instance directly.
        Enables automatic cleanup upon context exit.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context manager block gracefully.
        Ensures the underlying browser driver is closed.
        Releases all held resources automatically safely.
        """
        self.close()
