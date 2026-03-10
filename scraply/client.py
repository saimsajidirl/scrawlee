import time
import random
from typing import Optional, Dict, Any, Union
from curl_cffi import requests
from bs4 import BeautifulSoup
from .proxies import ProxyManager

class ScraplyResponse:
    """Enhanced response envelope that wraps a raw HTTP response.
    It automatically detects content types to provide pre-parsed JSON data
    or high-level BeautifulSoup objects directly on the response."""
    
    def __init__(self, original_response: requests.Response):
        self._response = original_response
        self._parsed_json = None
        self._parsed_html = None
        self._auto_parse()

    def _auto_parse(self):
        content_type = self._response.headers.get("Content-Type", "").lower()
        if "application/json" in content_type:
            try:
                self._parsed_json = self._response.json()
            except Exception:
                pass
        elif "text/html" in content_type:
            try:
                self._parsed_html = BeautifulSoup(self._response.text, "html.parser")
            except Exception:
                pass

    @property
    def auto(self) -> Any:
        """Dynamically retrieves the most useful version of the response.
        It returns a dictionary for JSON APIs and a BeautifulSoup object
        for HTML pages without any manual parsing required."""
        if self._parsed_json is not None:
            return self._parsed_json
        if self._parsed_html is not None:
            return self._parsed_html
        return self._response.text

    @property
    def html(self) -> Optional[BeautifulSoup]:
        """Provides a native BeautifulSoup tree for HTML responses.
        Perfect for quick DOM traversal and data extraction using
        standard CSS selectors or tag searches."""
        return self._parsed_html
        
    @property
    def data(self) -> Optional[Dict]:
        """Exposes the parsed JSON body as a native Python dictionary.
        This property is populated when the response headers indicate
        an application/json content type."""
        return self._parsed_json

    def __getattr__(self, name):
        """Seamlessly delegates attribute access to the underlying response.
        This ensures methods like status_code, url, and headers are
        still available exactly like a standard requests object."""
        return getattr(self._response, name)


class ScraplyClient:
    """The core scraping engine designed for maximum stealth and reliability.
    It combines advanced TLS fingerprinting with intelligent proxy rotation
    and automated retry logic to bypass modern anti-bot systems."""
    
    STEALTH_BROWSERS = ["chrome110", "chrome120", "edge101", "safari15_5"]
    
    def __init__(
        self, 
        proxy_manager: Optional[ProxyManager] = None,
        max_retries: int = 3,
        impersonate: str = "random",
        timeout: int = 30
    ):
        self.proxy_manager = proxy_manager or ProxyManager()
        self.max_retries = max_retries
        self.timeout = timeout
        
        if impersonate == "random":
            self.impersonate = random.choice(self.STEALTH_BROWSERS)
        else:
            self.impersonate = impersonate
            
        self.session = requests.Session(impersonate=self.impersonate, timeout=self.timeout)
        self._generate_dynamic_headers()

    def _generate_dynamic_headers(self):
        """Constructs organic-looking browser headers based on the active fingerprint.
        It ensures that critical signals like language and fetch metadata
        match the impersonated browser identity for perfect stealth."""
        languages = ["en-US,en;q=0.9", "en-GB,en;q=0.9,en-US;q=0.8", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"]
        self.session.headers.update({
            "Accept-Language": random.choice(languages),
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        })

    def request(self, method: str, url: str, **kwargs) -> ScraplyResponse:
        """Executes a high-level network request with integrated fail-safes.
        It handles automatic proxy selection, exponential backoff for
        transient errors, and wraps the final result in an auto-parsing layer."""
        retries = 0
        backoff_time = 1.0

        while retries <= self.max_retries:
            current_proxy = self.proxy_manager.get_proxy()
            if current_proxy:
                kwargs["proxies"] = current_proxy
            
            try:
                response = self.session.request(method, url, **kwargs)
                
                if response.status_code in [429, 500, 502, 503, 504]:
                    raise requests.RequestsError(f"Transient Error: Status code {response.status_code}")
                    
                return ScraplyResponse(response)
                
            except Exception as e:
                if current_proxy:
                    self.proxy_manager.mark_failed(current_proxy)
                    
                retries += 1
                if retries > self.max_retries:
                    raise Exception(f"Max retries reached for {url}. Last error: {str(e)}")
                    
                time.sleep(backoff_time + random.uniform(0, 1))
                backoff_time *= 2

    def get(self, url: str, **kwargs) -> ScraplyResponse:
        return self.request("GET", url, **kwargs)
        
    def post(self, url: str, **kwargs) -> ScraplyResponse:
        return self.request("POST", url, **kwargs)
        
    def close(self):
        """Safely terminates the underlying network session and resources.
        Best used when manual session management is required outside
        of a standard context manager block."""
        self.session.close()

    def __enter__(self):
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
