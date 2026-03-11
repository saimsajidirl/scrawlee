# Scrawlee

An ultimate stealth scraping library built on top of `curl_cffi` with advanced proxy rotation, auto-parsing for JSON/HTML, and built-in rate-limiting retries. Fully supports both synchronous AND highly-concurrent asynchronous scraping.

## Key Features

- **Ultimate Stealth**: Rotates through real-world TLS/JA3 fingerprints (Chrome, Edge, Safari).
- **Asynchronous Engine**: Comes with `AsyncScrawleeClient` for blazing fast, highly-concurrent scraping using `asyncio`.
- **Auto-Parsing Response**: The `.auto` property automatically returns a parsed Python dictionary or a high-speed `selectolax` object depending on whether the response is JSON or HTML.
- **Dual-Parser Support**: Fetch lightning-fast CSS queries via `.html` (Selectolax) or utilize robust XPath querying via `.lxml` (lxml).
- **Cookie Persistence**: Instantly save and load authenticated sessions to disk so you never have to log in or solve Cloudflare challenges twice.
- **Smart Retries**: Built-in exponential backoff for common HTTP error codes (429, 50x).
- **Advanced Proxy Management**: Supports Random, Round-Robin, and Sticky session rotation with off-band automated health checks.

## Installation

```bash
pip install scrawlee
```
*(Requires Python 3.8+)*

## Usage Guide

### 1. Basic Synchronous Scraping
```python
from scrawlee import ScrawleeClient

with ScrawleeClient(impersonate="chrome120") as client:
    res = client.get("https://httpbin.org/get")
    
    # .auto magically returns a Dictionary for JSON API responses!
    print(res.auto['headers']['User-Agent'])
    
    res_html = client.get("https://httpbin.org/html")
    
    # Lightning fast CSS queries via selectolax
    print(res_html.html.css_first("h1").text(strip=True))
    
    # Powerful XPath queries via lxml
    print(res_html.lxml.xpath("//h1/text()")[0])
```

### 2. Deep Dive: Extracting Data from HTML
Scrawlee eliminates the need for external parsing libraries like BeautifulSoup. It comes natively packed with two blazing-fast, C-based parsing engines:

#### Extracting with CSS Selectors (via `.html`)
The `.html` property exposes the `selectolax` engine. It is the fastest way to parse data using standard CSS selectors.
```python
with ScrawleeClient() as client:
    res = client.get("https://example-store.com/products")
    
    # 1. Extract text from a single element
    title = res.html.css_first("h1.product-title").text(strip=True)
    
    # 2. Extract HTML attributes (e.g. data-id, href, src)
    product_id = res.html.css_first("div.product").attributes.get("data-product-id")
    
    # 3. Loop through lists of elements
    for feature_li in res.html.css("ul.features li"):
        print("Feature:", feature_li.text(strip=True))
```

#### Extracting with XPath Queries (via `.lxml`)
If you need complex DOM traversal (e.g., finding a parent element based on its child's value), CSS selectors fall short. The `.lxml` property provides industry-standard XPath extraction.
```python
with ScrawleeClient() as client:
    res = client.get("https://example-store.com/products")
    
    # Fetch an element exactly using an XPath query
    price = res.lxml.xpath('//div[@class="product-card" and @data-status="in-stock"]//span[@class="price"]/text()')[0]
    print(f"Price is: {price}")
```

### 3. High-Speed Asynchronous Scraping
If you need to scrape 1,000 pages concurrently, use `AsyncScrawleeClient`.
```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def run():
    async with AsyncScrawleeClient() as client:
        # Fire concurrent requests
        res1, res2 = await asyncio.gather(
            client.get("https://httpbin.org/get"),
            client.get("https://httpbin.org/html")
        )
        print("Async HTTPBin Status:", res1.status_code)

asyncio.run(run())
```

### 4. Persistent Sessions (Save/Load Cookies)
If you bypass a Datadome/Cloudflare wall or log into a website, save your cookies to disk so you can instantly resume the session tomorrow!
```python
from scrawlee import ScrawleeClient

# Script 1: Save the session
with ScrawleeClient() as client:
    # ... Login logic or bypass challenge ...
    client.save_cookies("twitter_session.json")

# Script 2: Load the session instantly
with ScrawleeClient() as client:
    client.load_cookies("twitter_session.json")
    res = client.get("https://api.twitter.com/protected_route")
```

### 5. Advanced Proxy Management
Automatically rotates Proxies and quarantines failing ones.
```python
from scrawlee import ScrawleeClient, ProxyManager

pm = ProxyManager(rotation_strategy="round_robin")
# Accepts raw proxy data
pm.add_proxy(ip="12.34.56.78", port="8080", username="user", password="pwd")

with ScrawleeClient(proxy_manager=pm) as client:
    res = client.get("https://api.myip.com")
    print("Masked IP:", res.auto['ip'])
```
