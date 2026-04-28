"""Scrawlee: An ultimate stealth scraping library for Python.
It integrates high-level TLS impersonation, dynamic header generation,
smart proxy rotation, and botasaurus-powered browser automation to
provide a seamless scraping experience."""

from .client import ScrawleeClient, AsyncScrawleeClient
from .proxies import ProxyManager
from .browser import BrowserClient, BrowserResponse

__all__ = [
    "ScrawleeClient",
    "AsyncScrawleeClient",
    "ProxyManager",
    "BrowserClient",
    "BrowserResponse",
]
