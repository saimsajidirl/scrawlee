# Scraply

An ultimate stealth scraping library built on top of `curl_cffi` with advanced proxy rotation, auto-parsing for JSON/HTML, and built-in rate-limiting retries. Fully supports both synchronous AND highly-concurrent asynchronous scraping.

## Key Features

- **Ultimate Stealth**: Rotates through real-world TLS/JA3 fingerprints (Chrome, Edge, Safari).
- **Asynchronous Engine**: Comes with `AsyncScraplyClient` for blazing fast, highly-concurrent scraping using `asyncio`.
- **Auto-Parsing Response**: The `.auto` property automatically returns a parsed Python dictionary or a `BeautifulSoup` object depending on whether the response is JSON or HTML.
- **Cookie Persistence**: Instantly save and load authenticated sessions to disk so you never have to log in or solve Cloudflare challenges twice.
- **Smart Retries**: Built-in exponential backoff for common HTTP error codes (429, 50x).
- **Advanced Proxy Management**: Supports Random, Round-Robin, and Sticky session rotation with off-band automated health checks.

## Installation

```bash
pip install .
```
*(Requires Python 3.8+)*

## Usage Guide

### 1. Basic Synchronous Scraping
```python
from scraply import ScraplyClient

with ScraplyClient(impersonate="chrome120") as client:
    res = client.get("https://httpbin.org/get")
    
    # .auto magically returns a Dictionary for JSON API responses!
    print(res.auto['headers']['User-Agent'])
    
    res_html = client.get("https://httpbin.org/html")
    # .auto magically returns a BeautifulSoup object for HTML responses!
    print(res_html.auto.find("h1").text)
```

### 2. High-Speed Asynchronous Scraping
If you need to scrape 1,000 pages concurrently, use `AsyncScraplyClient`.
```python
import asyncio
from scraply import AsyncScraplyClient

async def run():
    async with AsyncScraplyClient() as client:
        # Fire concurrent requests
        res1, res2 = await asyncio.gather(
            client.get("https://httpbin.org/get"),
            client.get("https://httpbin.org/html")
        )
        print("Async HTTPBin Status:", res1.status_code)

asyncio.run(run())
```

### 3. Persistent Sessions (Save/Load Cookies)
If you bypass a Datadome/Cloudflare wall or log into a website, save your cookies to disk so you can instantly resume the session tomorrow!
```python
from scraply import ScraplyClient

# Script 1: Save the session
with ScraplyClient() as client:
    # ... Login logic or bypass challenge ...
    client.save_cookies("twitter_session.json")

# Script 2: Load the session instantly
with ScraplyClient() as client:
    client.load_cookies("twitter_session.json")
    res = client.get("https://api.twitter.com/protected_route")
```

### 4. Advanced Proxy Management
Automatically rotates Proxies and quarantines failing ones.
```python
from scraply import ScraplyClient, ProxyManager

pm = ProxyManager(rotation_strategy="round_robin")
# Accepts raw proxy data
pm.add_proxy(ip="12.34.56.78", port="8080", username="user", password="pwd")

with ScraplyClient(proxy_manager=pm) as client:
    res = client.get("https://api.myip.com")
    print("Masked IP:", res.auto['ip'])
```
