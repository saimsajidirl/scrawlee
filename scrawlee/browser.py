"""Browser automation for scrawlee backed by the botasaurus anti-detect Driver.

BrowserClient wraps the botasaurus @browser decorator to give scrawlee users
a clean, class-based API for driving a real Chrome instance while keeping the
same BrowserResponse parsing interface (selectolax CSS / lxml XPath) that
ScrawleeResponse already provides for HTTP-based scraping.
"""

from typing import Any, Optional

from lxml import html as lxml_html
from loguru import logger
from selectolax.parser import HTMLParser


class BrowserResponse:
    """Rendered-page response with selectolax CSS and lxml XPath parsers built in.

    Mirrors the ScrawleeResponse interface so the same parsing code works
    regardless of whether the page was fetched via HTTP or a full browser visit.

    Attributes:
        status_code: HTTP status of the underlying request (200 for browser navigations).
        url:         The URL that was visited.
    """

    def __init__(self, html: str, url: str = "", status_code: int = 200):
        self._html = html
        self._url = url
        self.status_code = status_code
        self._parsed_html: Optional[HTMLParser] = None
        self._parsed_lxml = None
        self._parse()

    def _parse(self) -> None:
        if not self._html:
            return
        try:
            self._parsed_html = HTMLParser(self._html)
            self._parsed_lxml = lxml_html.fromstring(self._html)
        except Exception:
            pass

    @property
    def html(self) -> Optional[HTMLParser]:
        """selectolax HTMLParser for fast CSS selector-based extraction.

        Example::

            title = response.html.css_first("h1").text()
            links = [a.attrs["href"] for a in response.html.css("a[href]")]
        """
        return self._parsed_html

    @property
    def lxml(self):
        """lxml HtmlElement for XPath-based extraction.

        Example::

            prices = response.lxml.xpath('//span[@class="price"]/text()')
        """
        return self._parsed_lxml

    @property
    def text(self) -> str:
        """Raw HTML string of the fully rendered page."""
        return self._html

    @property
    def url(self) -> str:
        """URL of the page that was visited."""
        return self._url

    @property
    def auto(self):
        """Most useful pre-parsed form: selectolax HTMLParser, or raw text as fallback."""
        return self._parsed_html if self._parsed_html is not None else self._html


class BrowserClient:
    """Anti-detect browser automation client powered by the botasaurus Driver.

    Launches a real Chrome instance with human-like TLS fingerprints capable of
    bypassing Cloudflare WAF, Datadome, FingerprintJS, and Turnstile CAPTCHAs.
    All page visits return BrowserResponse objects with selectolax (CSS) and lxml
    (XPath) parsers already initialised.

    Botasaurus is a core dependency of Scrawlee and is installed automatically.
    Node.js is also bundled via ``nodejs-bin`` and installed automatically with
    ``pip install scrawlee`` — no separate system-level Node.js install is needed::

        pip install scrawlee

    Basic usage::

        with BrowserClient() as client:
            resp = client.get("https://example.com")
            print(resp.html.css_first("h1").text())

    Stealth usage with Google referrer + Cloudflare bypass::

        with BrowserClient(bypass_cloudflare=True, block_images=True) as client:
            resp = client.get("https://protected-site.com")
            prices = resp.lxml.xpath('//span[@class="price"]/text()')

    Low-bandwidth bulk scraping via browser fetch API::

        with BrowserClient(block_images=True) as client:
            # Full load once to establish session / cookies
            client.get("https://finance.yahoo.com/quote/AAPL/")
            # Subsequent pages use browser fetch — up to 97% less bandwidth
            for ticker in ["GOOG", "MSFT", "AMZN"]:
                resp = client.fetch(f"https://finance.yahoo.com/quote/{ticker}/")
                price = resp.html.css_first('[data-testid="qsp-price"]').text()
    """

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
        Args:
            proxy:               Proxy URL, e.g. ``"http://user:pass@host:port"``.
            headless:            Run Chrome headlessly. **Not recommended** for
                                 Cloudflare/Datadome-protected sites — they detect it.
            block_images:        Block image requests to reduce proxy bandwidth.
            block_images_and_css: Block images *and* CSS for maximum bandwidth savings.
            profile:             Named Chrome profile for session/cookie persistence.
            tiny_profile:        Cookie-only lightweight profile (~1 KB vs ~100 MB).
                                 Recommended when managing hundreds of profiles.
            reuse_driver:        Keep the same Chrome instance across multiple calls
                                 instead of launching a new one each time.
            bypass_cloudflare:   Apply botasaurus JS+Captcha Cloudflare bypass on every
                                 ``get()`` call. Use for Turnstile / JS-challenge pages.
            via_google:          Visit pages via Google referrer by default for stealth.
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
        self._setup(reuse_driver)

    # ------------------------------------------------------------------
    # Internal setup
    # ------------------------------------------------------------------

    def _setup(self, reuse_driver: bool) -> None:
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
        def _execute(driver: Driver, task_fn):
            # Capture driver reference for .driver property
            self._driver = driver
            # Run the user-supplied task and store result via closure.
            # We deliberately do NOT return the value here so botasaurus
            # does not attempt to serialise it into an output/*.json file.
            self._last_result = task_fn(driver)

        self._scrape_fn = _execute
        logger.debug("BrowserClient configured: {}", kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def driver(self):
        """Direct access to the botasaurus Driver after the first navigation.

        Use this when you need low-level control that is not exposed through
        ``get()``, ``fetch()``, or ``run()``::

            client.get("https://example.com")
            client.driver.click("button.load-more")
            resp = BrowserResponse(client.driver.page_html)
        """
        return self._driver

    def get(
        self,
        url: str,
        via_google: Optional[bool] = None,
        bypass_cloudflare: Optional[bool] = None,
    ) -> BrowserResponse:
        """Navigate to *url* with a full Chrome page load and return a BrowserResponse.

        By default the page is visited via a Google referrer for maximum stealth.
        Pass ``bypass_cloudflare=True`` to enable the botasaurus Cloudflare JS+Captcha
        solver for pages that serve a Turnstile or JS-computation challenge.

        Args:
            url:               Target URL.
            via_google:        Override instance-level ``via_google`` setting.
            bypass_cloudflare: Override instance-level ``bypass_cloudflare`` setting.

        Returns:
            BrowserResponse with ``.html`` (selectolax), ``.lxml``, and ``.text``.
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

        self._scrape_fn(_task)
        return self._last_result

    def fetch(self, url: str) -> BrowserResponse:
        """Fetch *url* via the browser's native fetch API without a full navigation.

        Only the HTML body is transferred — no images, stylesheets, or fonts —
        which can reduce proxy bandwidth by up to 97 % compared to ``get()``.
        Requires at least one prior ``get()`` call to establish a valid session
        and cookies on the target domain.

        Args:
            url: Target URL (same domain as the previously visited page recommended).

        Returns:
            BrowserResponse with ``.html``, ``.lxml``, and ``.text``.
        """
        def _task(driver):
            resp = driver.requests.get(url)
            status = getattr(resp, "status_code", 200)
            return BrowserResponse(resp.text, url, status)

        self._scrape_fn(_task)
        return self._last_result

    def run(self, task_fn) -> Any:
        """Execute *task_fn* with the raw botasaurus Driver and return its result.

        Use this for interactions that go beyond ``get()`` and ``fetch()``:
        form submission, JS execution, shadow-DOM traversal, iframe interaction,
        drag-and-drop, request interception, CDP commands, etc.

        Args:
            task_fn: Callable ``(driver: Driver) -> Any``.

        Returns:
            Whatever *task_fn* returns.

        Example::

            def search(driver):
                driver.type("input[name='q']", "scrawlee python")
                driver.click("button[type='submit']")
                driver.short_random_sleep()
                return BrowserResponse(driver.page_html, driver.current_url)

            resp = client.run(search)
            results = resp.html.css(".result-title")
        """
        self._scrape_fn(task_fn)
        return self._last_result

    def close(self) -> None:
        """Shut down the Chrome instance and release all resources."""
        if self._scrape_fn is not None:
            try:
                self._scrape_fn.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
