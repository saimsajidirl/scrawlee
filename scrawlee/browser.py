from typing import Any, Optional
import random
import time

from curl_cffi import requests
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

    STEALTH_BROWSERS = [
        "chrome120", "chrome124", "chrome129", "chrome131",
        "edge120", "edge122", "edge131",
        "safari17_0", "safari17_2", "safari17_5",
        "firefox109", "firefox115", "firefox120",
        "chrome99_android", "safari15_3_ios"
    ]

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
        impersonate: str = "random",
        http2: bool = True,
        wait: int = 0,
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
        self.http2 = http2
        self.wait = wait
        
        if impersonate == "random":
            self.impersonate = random.choice(self.STEALTH_BROWSERS)
        else:
            self.impersonate = impersonate

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
        wait: Optional[int] = None,
        poll_for_cookie: Optional[str] = None,
        poll_interval: float = 1.0,
        poll_stable: int = 2,
    ) -> BrowserResponse:
        """
        Navigates to the specified target URL.
        Optionally uses a Google referrer for stealth.
        Waits after navigation to allow JavaScript cookies to set.
        If poll_for_cookie is given, polls driver cookies every poll_interval
        seconds up to wait_time seconds, exiting early once the cookie value
        remains unchanged for poll_stable consecutive checks.
        Returns a fully parsed browser response object.
        """
        use_google = via_google if via_google is not None else self.via_google
        use_bypass = (
            bypass_cloudflare
            if bypass_cloudflare is not None
            else self.bypass_cloudflare
        )
        wait_time = wait if wait is not None else self.wait

        def _task(driver):
            if use_google:
                driver.google_get(url, bypass_cloudflare=use_bypass)
            else:
                driver.get(url)
            if wait_time:
                if poll_for_cookie:
                    last_value = None
                    stable_count = 0
                    elapsed = 0.0
                    while elapsed < wait_time:
                        cookies = {c["name"]: c["value"] for c in driver.get_cookies()}
                        current_value = cookies.get(poll_for_cookie)
                        if current_value is not None and current_value == last_value:
                            stable_count += 1
                            if stable_count >= poll_stable:
                                logger.debug(
                                    "Cookie '{}' stable after {:.1f}s, stopping wait",
                                    poll_for_cookie,
                                    elapsed,
                                )
                                break
                        else:
                            stable_count = 1 if current_value is not None else 0
                            last_value = current_value
                        time.sleep(poll_interval)
                        elapsed += poll_interval
                else:
                    logger.debug("Waiting {}s after navigation for cookies/JS to settle", wait_time)
                    time.sleep(wait_time)
            return BrowserResponse(driver.page_html, url)

        self._pending_task = _task
        self._scrape_fn()
        return self._last_result

    def _get_fingerprinting_headers(self) -> dict:
        """
        Generates browser fingerprinting headers for curl-cffi requests.
        Matches headers to the impersonated browser type.
        Ensures proper Sec-CH-UA and platform headers.
        """
        languages = [
            "en-US,en;q=0.9",
            "en-GB,en;q=0.9,en-US;q=0.8",
            "en-US,en;q=0.8,en-GB;q=0.6",
            "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
            "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7"
        ]
        
        sec_ch_ua = {
            "chrome120": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "chrome124": '"Not_A Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
            "chrome129": '"Google Chrome";v="129", "Not_A Brand";v="8", "Chromium";v="129"',
            "chrome131": '"Google Chrome";v="131", "Not_A Brand";v="8", "Chromium";v="131"',
            "edge120": '"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
            "edge122": '"Not_A Brand";v="8", "Chromium";v="122", "Microsoft Edge";v="122"',
            "edge131": '"Not_A Brand";v="8", "Chromium";v="131", "Microsoft Edge";v="131"',
            "safari17_0": '"Not_A Brand";v="8", "Safari";v="17.0"',
            "safari17_2": '"Not_A Brand";v="8", "Safari";v="17.2"',
            "safari17_5": '"Not_A Brand";v="8", "Safari";v="17.5"',
            "firefox109": '"Not_A Brand";v="8", "Firefox";v="109"',
            "firefox115": '"Not_A Brand";v="8", "Firefox";v="115"',
            "firefox120": '"Not_A Brand";v="8", "Firefox";v="120"',
            "chrome99_android": '"Chromium";v="99", "Not_A Brand";v="8", "Google Chrome";v="99"',
            "safari15_3_ios": '"Not_A Brand";v="8", "Safari";v="15.3"'
        }
        
        sec_ch_ua_platform = {
            "chrome120": '"Windows"',
            "chrome124": '"Windows"',
            "chrome129": '"Windows"',
            "chrome131": '"Windows"',
            "edge120": '"Windows"',
            "edge122": '"Windows"',
            "edge131": '"Windows"',
            "safari17_0": '"macOS"',
            "safari17_2": '"macOS"',
            "safari17_5": '"macOS"',
            "firefox109": '"Windows"',
            "firefox115": '"Windows"',
            "firefox120": '"Windows"',
            "chrome99_android": '"Android"',
            "safari15_3_ios": '"iOS"'
        }
        
        headers = {
            "Accept-Language": random.choice(languages),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Ch-Ua": sec_ch_ua.get(self.impersonate, '"Not_A Brand";v="8"'),
            "Sec-Ch-Ua-Mobile": "?0" if "android" not in self.impersonate and "ios" not in self.impersonate else "?1",
            "Sec-Ch-Ua-Platform": sec_ch_ua_platform.get(self.impersonate, '"Windows"'),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Cache-Control": "max-age=0"
        }
        
        return headers

    def fetch(self, url: str) -> BrowserResponse:
        """
        Fetches the target URL via native requests.
        Bypasses full rendering to save significant bandwidth.
        Returns a parsed browser response containing HTML.
        """
        kwargs = {
            "impersonate": self.impersonate
        }
        if self.proxy:
            kwargs["proxies"] = {"http": self.proxy, "https": self.proxy}
        
        headers = self._get_fingerprinting_headers()
        kwargs["headers"] = headers
        
        resp = requests.get(url, **kwargs)
        return BrowserResponse(resp.text, url, resp.status_code)

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
