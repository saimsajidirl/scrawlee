import time
import random
import asyncio
import json
from typing import Optional, Dict, Any, Iterable, Tuple, Type
from curl_cffi import requests
from selectolax.parser import HTMLParser
from lxml import html as lxml_html
from loguru import logger
from .proxies import ProxyManager

class ScrawleeResponse:
    
    def __init__(self, original_response: requests.Response):
        """
        Initializes the enhanced response envelope.
        Stores the original requests response object.
        Triggers automatic content type parsing immediately.
        """
        self._response = original_response
        self._parsed_json = None
        self._parsed_html = None
        self._parsed_lxml = None
        self._auto_parse()

    def _auto_parse(self):
        """
        Detects content type from response headers.
        Attempts to parse JSON bodies automatically.
        Attempts to parse HTML bodies into DOM trees.
        """
        content_type = self._response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            try:
                self._parsed_json = self._response.json()
            except Exception:
                pass
        elif "text/html" in content_type:
            try:
                self._parsed_html = HTMLParser(self._response.text)
                self._parsed_lxml = lxml_html.fromstring(self._response.text)
            except Exception:
                pass

    @property
    def auto(self) -> Any:
        """
        Retrieves the most useful parsed version.
        Returns JSON dictionary if applicable.
        Falls back to HTMLParser or raw text.
        """
        if self._parsed_json is not None:
            return self._parsed_json
        if self._parsed_html is not None:
            return self._parsed_html
        return self._response.text

    @property
    def html(self) -> Optional[HTMLParser]:
        """
        Provides native selectolax HTMLParser.
        Enables fast CSS selector DOM traversal.
        Returns None if parsing previously failed.
        """
        return self._parsed_html

    @property
    def lxml(self):
        """
        Provides native lxml HtmlElement.
        Enables complex XPath data extraction.
        Returns None if parsing previously failed.
        """
        return self._parsed_lxml
        
    @property
    def data(self) -> Optional[Dict]:
        """
        Exposes parsed JSON body dictionary.
        Populated automatically for application/json responses.
        Returns None if parsing previously failed.
        """
        return self._parsed_json

    def __getattr__(self, name):
        """
        Delegates attribute access to original response.
        Ensures compatibility with standard requests objects.
        Allows accessing status_code, url, and headers directly.
        """
        return getattr(self._response, name)


class ScrawleeClient:
    
    STEALTH_BROWSERS = ["chrome110", "chrome120", "edge101", "safari15_5"]
    
    def __init__(
        self, 
        proxy_manager: Optional[ProxyManager] = None,
        max_retries: int = 3,
        impersonate: str = "random",
        timeout: int = 30,
        retry_status_codes: Optional[Iterable[int]] = None,
        retry_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
        retry_backoff_base: float = 1.0,
        retry_jitter_max: float = 1.0
    ):
        """
        Initializes the synchronous scraping engine client.
        Configures proxy rotation and automatic retry logic.
        Generates dynamic stealth headers for the session.
        """
        self.proxy_manager = proxy_manager or ProxyManager()
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_status_codes = set(retry_status_codes or [429, 500, 502, 503, 504])
        self.retry_exceptions = retry_exceptions or (Exception,)
        self.retry_backoff_base = retry_backoff_base
        self.retry_jitter_max = retry_jitter_max
        
        if impersonate == "random":
            self.impersonate = random.choice(self.STEALTH_BROWSERS)
        else:
            self.impersonate = impersonate
            
        self.session = requests.Session(impersonate=self.impersonate, timeout=self.timeout)
        self._generate_dynamic_headers()

    def _generate_dynamic_headers(self):
        """
        Constructs organic-looking browser request headers.
        Matches language and metadata to impersonated identity.
        Ensures perfect stealth against modern anti-bot systems.
        """
        languages = ["en-US,en;q=0.9", "en-GB,en;q=0.9,en-US;q=0.8", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"]
        self.session.headers.update({
            "Accept-Language": random.choice(languages),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    def request(self, method: str, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes high-level synchronous network request safely.
        Handles proxy rotation and exponential error backoff.
        Wraps final result in auto-parsing response envelope.
        """
        retries = 0
        backoff_time = self.retry_backoff_base

        while retries <= self.max_retries:
            current_proxy = self.proxy_manager.get_proxy()
            if current_proxy:
                kwargs["proxies"] = current_proxy
                logger.debug("Request {} {} via proxy {}", method, url, current_proxy.get("http"))
            else:
                logger.debug("Request {} {} without proxy", method, url)
            
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code in self.retry_status_codes:
                    raise requests.RequestsError(
                        f"Retryable status code {response.status_code} for {method} {url}"
                    )
                    
                return ScrawleeResponse(response)
                
            except self.retry_exceptions as e:
                if current_proxy:
                    self.proxy_manager.mark_failed(current_proxy)
                    
                retries += 1
                if retries > self.max_retries:
                    logger.error("Max retries reached for {} {}. Last error: {}", method, url, str(e))
                    raise Exception(f"Max retries reached for {url}. Last error: {str(e)}")
                logger.warning(
                    "Retry {}/{} for {} {} after error: {}",
                    retries,
                    self.max_retries,
                    method,
                    url,
                    str(e),
                )
                    
                sleep_for = backoff_time + random.uniform(0, self.retry_jitter_max)
                logger.debug("Sleeping {:.2f}s before retrying {} {}", sleep_for, method, url)
                time.sleep(sleep_for)
                backoff_time *= 2

    def get(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous GET HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("GET", url, **kwargs)
        
    def post(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous POST HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous PUT HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("PUT", url, **kwargs)

    def patch(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous PATCH HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("PATCH", url, **kwargs)

    def delete(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous DELETE HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("DELETE", url, **kwargs)

    def head(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous HEAD HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("HEAD", url, **kwargs)

    def options(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes a synchronous OPTIONS HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return self.request("OPTIONS", url, **kwargs)
        
    def save_cookies(self, filepath: str):
        """
        Saves current session cookies to file.
        Persists authentication state for future sessions.
        Writes data safely in JSON format locally.
        """
        cookies_dict = self.session.cookies.get_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cookies_dict, f, indent=4)

    def load_cookies(self, filepath: str):
        """
        Loads session cookies from saved file.
        Resumes previously authenticated scraping sessions.
        Fails silently if cookie file is missing.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cookies_dict = json.load(f)
            self.session.cookies.update(cookies_dict)
        except Exception:
            pass
        
    def close(self):
        """
        Terminates the underlying network session safely.
        Releases allocated file descriptors and sockets.
        Should be used when outside context managers.
        """
        self.session.close()

    def __enter__(self):
        """
        Enters the context manager block gracefully.
        Returns the current synchronous client instance.
        Enables automatic cleanup upon context exit.
        """
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the context manager block gracefully.
        Ensures the underlying network session closes.
        Releases all held resources automatically safely.
        """
        self.close()

class AsyncScrawleeClient:
    
    STEALTH_BROWSERS = ["chrome110", "chrome120", "edge101", "safari15_5"]
    
    def __init__(
        self, 
        proxy_manager: Optional[ProxyManager] = None,
        max_retries: int = 3,
        impersonate: str = "random",
        timeout: int = 30,
        retry_status_codes: Optional[Iterable[int]] = None,
        retry_exceptions: Optional[Tuple[Type[BaseException], ...]] = None,
        retry_backoff_base: float = 1.0,
        retry_jitter_max: float = 1.0
    ):
        """
        Initializes the asynchronous scraping engine client.
        Configures proxy rotation and automatic retry logic.
        Generates dynamic stealth headers for the session.
        """
        self.proxy_manager = proxy_manager or ProxyManager()
        self.max_retries = max_retries
        self.timeout = timeout
        self.retry_status_codes = set(retry_status_codes or [429, 500, 502, 503, 504])
        self.retry_exceptions = retry_exceptions or (Exception,)
        self.retry_backoff_base = retry_backoff_base
        self.retry_jitter_max = retry_jitter_max
        
        if impersonate == "random":
            self.impersonate = random.choice(self.STEALTH_BROWSERS)
        else:
            self.impersonate = impersonate
            
        self.session = requests.AsyncSession(impersonate=self.impersonate, timeout=self.timeout)
        self._generate_dynamic_headers()

    def _generate_dynamic_headers(self):
        """
        Constructs organic-looking browser request headers.
        Matches language and metadata to impersonated identity.
        Ensures perfect stealth against modern anti-bot systems.
        """
        languages = ["en-US,en;q=0.9", "en-GB,en;q=0.9,en-US;q=0.8", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"]
        self.session.headers.update({
            "Accept-Language": random.choice(languages),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    async def request(self, method: str, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes high-level asynchronous network request safely.
        Handles proxy rotation and exponential error backoff.
        Wraps final result in auto-parsing response envelope.
        """
        retries = 0
        backoff_time = self.retry_backoff_base

        while retries <= self.max_retries:
            current_proxy = self.proxy_manager.get_proxy()
            if current_proxy:
                kwargs["proxies"] = current_proxy
                logger.debug("Async request {} {} via proxy {}", method, url, current_proxy.get("http"))
            else:
                logger.debug("Async request {} {} without proxy", method, url)
            
            try:
                response = await self.session.request(method, url, **kwargs)
                
                if response.status_code in self.retry_status_codes:
                    raise requests.RequestsError(
                        f"Retryable status code {response.status_code} for {method} {url}"
                    )
                    
                return ScrawleeResponse(response)
                
            except self.retry_exceptions as e:
                if current_proxy:
                    self.proxy_manager.mark_failed(current_proxy)
                    
                retries += 1
                if retries > self.max_retries:
                    logger.error("Max retries reached for async {} {}. Last error: {}", method, url, str(e))
                    raise Exception(f"Max retries reached for {url}. Last error: {str(e)}")
                logger.warning(
                    "Async retry {}/{} for {} {} after error: {}",
                    retries,
                    self.max_retries,
                    method,
                    url,
                    str(e),
                )
                    
                sleep_for = backoff_time + random.uniform(0, self.retry_jitter_max)
                logger.debug("Async sleeping {:.2f}s before retrying {} {}", sleep_for, method, url)
                await asyncio.sleep(sleep_for)
                backoff_time *= 2

    async def get(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous GET HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("GET", url, **kwargs)
        
    async def post(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous POST HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous PUT HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous PATCH HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous DELETE HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous HEAD HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("HEAD", url, **kwargs)

    async def options(self, url: str, **kwargs) -> ScrawleeResponse:
        """
        Executes an asynchronous OPTIONS HTTP request.
        Utilizes underlying stealth and retry logic.
        Returns parsed ScrawleeResponse object natively.
        """
        return await self.request("OPTIONS", url, **kwargs)
        
    def save_cookies(self, filepath: str):
        """
        Saves current session cookies to file.
        Persists authentication state for future sessions.
        Writes data safely in JSON format locally.
        """
        cookies_dict = self.session.cookies.get_dict()
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cookies_dict, f, indent=4)

    def load_cookies(self, filepath: str):
        """
        Loads session cookies from saved file.
        Resumes previously authenticated scraping sessions.
        Fails silently if cookie file is missing.
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                cookies_dict = json.load(f)
            self.session.cookies.update(cookies_dict)
        except Exception:
            pass
        
    async def close(self):
        """
        Terminates the underlying asynchronous network session.
        Releases allocated file descriptors and sockets securely.
        Should be used when outside context managers.
        """
        await self.session.close()

    async def __aenter__(self):
        """
        Enters the async context manager block gracefully.
        Returns the current asynchronous client instance.
        Enables automatic cleanup upon context exit.
        """
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Exits the async context manager block gracefully.
        Ensures the underlying network session closes.
        Releases all held resources automatically safely.
        """
        await self.close()