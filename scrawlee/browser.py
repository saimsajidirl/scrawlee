from typing import Any, Optional
from pathlib import Path
from urllib.parse import urlparse
import time
import json

from lxml import html as lxml_html
from loguru import logger
from selectolax.parser import HTMLParser

from . import fingerprints
from . import geoip
from .stealth import build_stealth_script

_BLOCK_MARKERS = (
    "just a moment",
    "attention required",
    "checking your browser",
    "access denied",
    "verify you are human",
    "cf-error-details",
    "captcha",
)


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

    # Kept for backward compatibility with code that reads `.impersonate`;
    # BrowserClient's actual fingerprint persona comes from `identity`
    # instead (see scrawlee.fingerprints), which is restricted to
    # Chromium-family personas for the reasons documented there.
    STEALTH_BROWSERS = fingerprints.identity_names()

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
        identity: Optional[str] = None,
        stealth: bool = True,
        geo_match: bool = True,
        auto_save_profile: bool = True,
        http2: bool = True,
        wait: int = 0,
    ):
        """
        Initializes the anti-detect browser client.
        Picks a self-consistent device/rendering identity to rotate stealth
        signals as one unit, rather than mismatching layers independently.
        Sets up the underlying Playwright browser lazily.
        """
        self.proxy = proxy
        self.headless = headless
        self.block_images = block_images
        self.block_images_and_css = block_images_and_css
        self.profile = profile
        self.tiny_profile = tiny_profile
        self.reuse_driver = reuse_driver
        self.bypass_cloudflare = bypass_cloudflare
        self.via_google = via_google
        self.stealth = stealth
        self.geo_match = geo_match
        self.auto_save_profile = auto_save_profile
        self.http2 = http2
        self.wait = wait

        self._identity = fingerprints.pick_identity(identity)
        self.impersonate = self._identity.key if impersonate == "random" else impersonate

        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._driver = None
        self._last_result: Any = None

    @property
    def identity(self) -> str:
        """
        Returns the key of the active fingerprint identity.
        Every stealth signal (UA, GPU strings, core count, viewport) is
        derived from this single persona, keeping layers internally
        consistent instead of mismatched.
        """
        return self._identity.key

    @staticmethod
    def available_identities():
        """
        Lists every identity persona available for pinning.
        Pass one of these keys as the `identity` constructor argument.
        """
        return fingerprints.identity_names()

    @staticmethod
    def _build_proxy_config(proxy: str) -> dict:
        """
        Parses a proxy URL into Playwright's proxy config.
        Separates embedded credentials from the server address.
        """
        parsed = urlparse(proxy)
        config = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
        if parsed.username:
            config["username"] = parsed.username
        if parsed.password:
            config["password"] = parsed.password
        return config

    @staticmethod
    def _route_block_images(route) -> None:
        if route.request.resource_type == "image":
            route.abort()
        else:
            route.continue_()

    @staticmethod
    def _route_block_images_and_css(route) -> None:
        if route.request.resource_type in ("image", "stylesheet", "font"):
            route.abort()
        else:
            route.continue_()

    def _profile_dir(self) -> Path:
        base = Path.home() / ".scrawlee" / "profiles"
        base.mkdir(parents=True, exist_ok=True)
        return base / self.profile

    def _tiny_profile_path(self) -> Path:
        base = Path.home() / ".scrawlee" / "profiles"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self.profile}.tiny.json"

    def _auto_profile_path(self) -> Path:
        base = Path.home() / ".scrawlee" / "profiles" / "_auto"
        base.mkdir(parents=True, exist_ok=True)
        return base / f"{self._identity.key}.json"

    def _load_cookies(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            cookies = json.loads(path.read_text(encoding="utf-8"))
            if cookies:
                self._context.add_cookies(cookies)
        except Exception:
            logger.debug("Failed to load cookies from {}", path)

    def _save_cookies(self, path: Path) -> None:
        try:
            path.write_text(json.dumps(self._context.cookies()), encoding="utf-8")
        except Exception:
            logger.debug("Failed to save cookies to {}", path)

    def _looks_blocked(self, page) -> bool:
        """
        Heuristically detects a challenge/block page.
        Checked before auto-saving a profile so a burned fingerprint's
        cookies never get reinforced as if the run had succeeded.
        """
        try:
            title = (page.title() or "").lower()
            if any(marker in title for marker in _BLOCK_MARKERS):
                return True
            snippet = page.evaluate(
                "document.body ? document.body.innerText.slice(0, 500) : ''"
            ).lower()
            return any(marker in snippet for marker in _BLOCK_MARKERS)
        except Exception:
            return False

    def _ensure_driver(self):
        """
        Lazily launches the Playwright Chromium instance.
        Reuses the existing page when reuse_driver is enabled.
        Returns the live Playwright Page for navigation.
        """
        if self.reuse_driver and self._page is not None:
            return self._page
        if self._page is not None:
            self._close_driver()

        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise ImportError(
                "playwright is required for BrowserClient. Install it with "
                "'pip install playwright' and then run 'playwright install chromium'."
            ) from exc

        self._playwright = sync_playwright().start()

        launch_kwargs: dict = {"headless": self.headless}
        if self.proxy:
            launch_kwargs["proxy"] = self._build_proxy_config(self.proxy)

        geo = geoip.resolve_geo(self.proxy) if (self.proxy and self.geo_match) else None
        identity = self._identity

        context_kwargs: dict = {
            "user_agent": identity.ua,
            "viewport": {"width": identity.viewport[0], "height": identity.viewport[1]},
            "screen": {"width": identity.screen[0], "height": identity.screen[1]},
            "device_scale_factor": identity.device_scale_factor,
            "is_mobile": identity.is_mobile,
            "has_touch": identity.has_touch,
            "locale": geo["locale"] if geo else identity.locale,
            "timezone_id": geo["timezone_id"] if geo else identity.timezone_id,
            "extra_http_headers": {
                "sec-ch-ua": identity.sec_ch_ua,
                "sec-ch-ua-mobile": identity.sec_ch_ua_mobile,
                "sec-ch-ua-platform": identity.sec_ch_ua_platform,
            },
        }
        if geo and geo.get("latitude") is not None and geo.get("longitude") is not None:
            context_kwargs["geolocation"] = {
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
            }
            context_kwargs["permissions"] = ["geolocation"]

        if self.profile and not self.tiny_profile:
            user_data_dir = str(self._profile_dir())
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir, **launch_kwargs, **context_kwargs
            )
            self._browser = None
        else:
            self._browser = self._playwright.chromium.launch(**launch_kwargs)
            self._context = self._browser.new_context(**context_kwargs)
            if self.profile and self.tiny_profile:
                self._load_cookies(self._tiny_profile_path())
            elif not self.profile and self.auto_save_profile:
                self._load_cookies(self._auto_profile_path())

        if self.stealth:
            self._context.add_init_script(build_stealth_script(identity))

        if self.block_images_and_css:
            self._context.route("**/*", self._route_block_images_and_css)
        elif self.block_images:
            self._context.route("**/*", self._route_block_images)

        self._page = self._context.new_page()
        self._driver = self._page
        logger.debug(
            "BrowserClient launched Chromium via Playwright (identity={}, headless={})",
            identity.key,
            self.headless,
        )
        return self._page

    def _close_driver(self) -> None:
        if self.profile and self.tiny_profile and self._context is not None:
            self._save_cookies(self._tiny_profile_path())
        for closable in (self._context, self._browser):
            if closable is not None:
                try:
                    closable.close()
                except Exception:
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._driver = None

    def attempt_cloudflare_bypass(self, page, timeout: int = 15000) -> None:
        """
        Attempts a best-effort Cloudflare Turnstile bypass.
        Clicks the challenge checkbox when one is present.
        Not a guaranteed solve, unlike a dedicated captcha solver.
        Public so custom run() flows can reuse it outside of get().
        """
        try:
            checkbox = page.frame_locator(
                "iframe[src*='challenges.cloudflare.com']"
            ).locator("input[type='checkbox']")
            checkbox.first.click(timeout=timeout)
        except Exception:
            logger.debug("No Cloudflare Turnstile challenge detected or bypass failed")

    @property
    def driver(self):
        """
        Provides direct access to the active Playwright Page.
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
        If poll_for_cookie is given, polls context cookies every poll_interval
        seconds up to wait_time seconds, exiting early once the cookie value
        remains unchanged for poll_stable consecutive checks.
        Auto-saves this identity's cookies locally when no explicit profile
        is set and the page doesn't look blocked, so a fingerprint that
        works keeps working on the next run.
        Returns a fully parsed browser response object.
        """
        use_google = via_google if via_google is not None else self.via_google
        use_bypass = (
            bypass_cloudflare
            if bypass_cloudflare is not None
            else self.bypass_cloudflare
        )
        wait_time = wait if wait is not None else self.wait

        def _task(page):
            if use_google:
                try:
                    page.goto("https://www.google.com/", wait_until="domcontentloaded")
                except Exception:
                    pass
                page.goto(url, wait_until="domcontentloaded", referer="https://www.google.com/")
            else:
                page.goto(url, wait_until="domcontentloaded")

            if use_bypass:
                self.attempt_cloudflare_bypass(page)

            if wait_time:
                if poll_for_cookie:
                    last_value = None
                    stable_count = 0
                    elapsed = 0.0
                    while elapsed < wait_time:
                        cookies = {c["name"]: c["value"] for c in page.context.cookies()}
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

            if not self.profile and self.auto_save_profile:
                if not self._looks_blocked(page):
                    self._save_cookies(self._auto_profile_path())
                else:
                    logger.debug("Page looks blocked; skipping auto profile save")

            return BrowserResponse(page.content(), page.url)

        return self.run(_task)

    def fetch(
        self,
        url: str,
        headers: Optional[dict] = None,
        include_credentials: bool = True,
    ) -> BrowserResponse:
        """
        Fetches the target URL via the browser's native fetch API.
        Reuses the current page's cookies and session state.
        Catches network/CORS failures in-page so a blocked or rejected
        request surfaces as a normal ConnectionError instead of an
        uncaught Playwright protocol error.
        Returns a parsed browser response containing HTML.
        """
        page = self._ensure_driver()
        result = page.evaluate(
            """async (args) => {
                try {
                    const response = await fetch(args.url, {
                        credentials: args.includeCredentials ? 'include' : 'omit',
                        headers: args.headers || {},
                    });
                    const text = await response.text();
                    return { text: text, status: response.status, error: null };
                } catch (error) {
                    return { text: '', status: null, error: String(error) };
                }
            }""",
            {"url": url, "headers": headers or {}, "includeCredentials": include_credentials},
        )
        if result["error"]:
            raise ConnectionError(f"Browser fetch to {url} failed: {result['error']}")
        return BrowserResponse(result["text"], url, result["status"])

    def run(self, task_fn) -> Any:
        """
        Executes a custom function using the Playwright page.
        Allows arbitrary interactions and form submissions.
        Returns the result of the provided callable task.
        """
        page = self._ensure_driver()
        try:
            self._last_result = task_fn(page)
        finally:
            if not self.reuse_driver:
                self._close_driver()
        return self._last_result

    def close(self) -> None:
        """
        Shuts down the underlying Chromium instance entirely.
        Releases all allocated system resources safely.
        Cleans up the internal execution context references.
        """
        self._close_driver()

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
