"""Scraply: An ultimate stealth scraping library for Python.
It integrates high-level TLS impersonation, dynamic header generation,
and smart proxy rotation to provide a seamless scraping experience."""

from .client import ScraplyClient
from .proxies import ProxyManager

__all__ = ["ScraplyClient", "ProxyManager"]
