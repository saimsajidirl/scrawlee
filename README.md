# Scrawlee

Scrawlee is a Python HTTP scraping client built on top of [`curl_cffi`](https://github.com/yifeikong/curl_cffi). It is designed to make reliable, stealthy web scraping simple — combining browser-level TLS impersonation, smart proxy rotation, automatic response parsing, cookie persistence, and exponential-backoff retries into a single, ergonomic API.

Both synchronous and fully asynchronous modes are supported out of the box.

---

## Table of Contents

- [Why Scrawlee](#why-scrawlee)
- [How It Works](#how-it-works)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [ScrawleeClient — Synchronous Client](#scrawleeclient--synchronous-client)
  - [Constructor Parameters](#constructor-parameters)
  - [Making Requests](#making-requests)
  - [Passing Extra Options](#passing-extra-options)
  - [Custom Headers](#custom-headers)
  - [Sending POST Data](#sending-post-data)
- [ScrawleeResponse — Working with Responses](#scrawleeresponse--working-with-responses)
  - [Standard Response Attributes](#standard-response-attributes)
  - [auto — Smart Auto-Parser](#auto--smart-auto-parser)
  - [data — JSON Responses](#data--json-responses)
  - [html — CSS Selector Parsing](#html--css-selector-parsing)
  - [lxml — XPath Parsing](#lxml--xpath-parsing)
- [AsyncScrawleeClient — Async Client](#asyncscrawleeclient--async-client)
  - [Running Requests Concurrently](#running-requests-concurrently)
- [ProxyManager — Proxy Rotation](#proxymanager--proxy-rotation)
  - [Rotation Strategies](#rotation-strategies)
  - [Adding Proxies](#adding-proxies)
  - [How Quarantine Works](#how-quarantine-works)
- [Cookie Persistence](#cookie-persistence)
- [Retry Behavior](#retry-behavior)
- [Browser Impersonation](#browser-impersonation)
- [Complete End-to-End Examples](#complete-end-to-end-examples)
  - [Scraping a JSON API](#scraping-a-json-api)
  - [Scraping an HTML Page](#scraping-an-html-page)
  - [High-Volume Async Scraper with Proxies](#high-volume-async-scraper-with-proxies)
  - [Resuming an Authenticated Session](#resuming-an-authenticated-session)
- [API Reference](#api-reference)
- [License](#license)

---

## Why Scrawlee

Most anti-bot systems fingerprint HTTP clients at the TLS/JA3 layer, not just by the `User-Agent` header. Standard `requests` and `httpx` clients expose a Python TLS signature that can be trivially blocked.

Scrawlee uses `curl_cffi` under the hood, which sends byte-for-byte identical TLS handshakes to real browsers (Chrome, Edge, Safari). Combined with matching browser headers that are generated dynamically on each session, it looks indistinguishable from a real browser to most bot detection systems.

On top of stealth, Scrawlee handles the tedious scaffolding every scraping project needs:

- Automatic retries so transient failures don't kill a long run
- Proxy rotation so a single IP is never hammered
- Response parsing built into the response object so you never `import BeautifulSoup` or `import json` manually
- Cookie save/load so you only solve challenges or log in once

---

## How It Works

```
Your code
   │
   ▼
ScrawleeClient.get(url)
   │
   ├─ Picks a browser fingerprint (chrome120, edge101, etc.)
   ├─ Generates matching browser headers (Accept-Language, Sec-Fetch-*, etc.)
   ├─ Selects a proxy from the ProxyManager (if configured)
   │
   ▼
curl_cffi AsyncSession / Session
   │   (sends a real browser TLS handshake)
   │
   ▼
Remote Server
   │
   ▼
ScrawleeResponse (wraps the raw response)
   ├─ response.auto    → dict (JSON) or HTMLParser (HTML)
   ├─ response.html    → selectolax HTMLParser for CSS selectors
   ├─ response.lxml    → lxml HtmlElement for XPath
   ├─ response.data    → dict (JSON only)
   └─ response.*       → anything from the original curl_cffi response
```

On any `429`, `500`, `502`, `503`, or `504`, Scrawlee automatically waits with exponential backoff and retries — up to `max_retries` times. Failed proxies are quarantined and removed from rotation for 5 minutes.

---

## Installation

```bash
pip install scrawlee
```

Python `3.8` or newer is required. All dependencies (`curl_cffi`, `selectolax`, `lxml`) are installed automatically.

---

## Quick Start

If you copy examples that use `logger.info(...)`, add `from loguru import logger`.

```python
from scrawlee import ScrawleeClient
from loguru import logger

with ScrawleeClient() as client:
    response = client.get("https://httpbin.org/get")
    logger.info(response.status_code)        # 200
    logger.info(response.auto["url"])        # https://httpbin.org/get
```

That is a complete working script. No sessions to manage, no headers to set — everything is handled automatically.

---

## ScrawleeClient — Synchronous Client

`ScrawleeClient` is the main synchronous scraping client. It manages a persistent `curl_cffi` session internally, which means cookies, connection pooling, and headers are all reused across multiple requests in the same `with` block.

### Constructor Parameters

```python
from scrawlee import ScrawleeClient

client = ScrawleeClient(
    proxy_manager=None,      # A ProxyManager instance. See ProxyManager section.
    max_retries=3,           # How many times to retry on transient failures before raising.
    impersonate="random",    # Browser fingerprint to impersonate. See Browser Impersonation.
    timeout=30,              # Per-request timeout in seconds.
    retry_status_codes={429, 500, 502, 503, 504},  # Which HTTP statuses should retry.
    retry_exceptions=(Exception,),                  # Which exception types should retry.
    retry_backoff_base=1.0,                         # Initial backoff delay in seconds.
    retry_jitter_max=1.0,                           # Random jitter upper bound in seconds.
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `proxy_manager` | `ProxyManager` or `None` | `None` | If `None`, requests are sent directly (no proxy). Pass a `ProxyManager` instance to enable rotation. |
| `max_retries` | `int` | `3` | Maximum number of retry attempts on transient HTTP errors (`429`, `5xx`). After exhausting retries, an exception is raised. |
| `impersonate` | `str` | `"random"` | Browser profile to impersonate. Valid values: `"chrome110"`, `"chrome120"`, `"edge101"`, `"safari15_5"`, `"random"`. When `"random"`, a profile is chosen at session creation time and held for the entire session. |
| `timeout` | `int` | `30` | Request timeout in seconds. Applies to each individual attempt (not the total across retries). |
| `retry_status_codes` | `Iterable[int]` or `None` | `{429, 500, 502, 503, 504}` | Status codes that trigger automatic retries. |
| `retry_exceptions` | `tuple[type[BaseException], ...]` or `None` | `(Exception,)` | Exception types that trigger retry attempts. |
| `retry_backoff_base` | `float` | `1.0` | Initial delay before retrying (then doubles each attempt). |
| `retry_jitter_max` | `float` | `1.0` | Random jitter added to each backoff delay (`0..jitter_max`). |

### Making Requests

Always use `ScrawleeClient` as a context manager. This ensures the underlying session is properly closed.

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    response = client.get("https://httpbin.org/get")
    response = client.post("https://httpbin.org/post", json={"key": "value"})
```

You can also manage the lifecycle manually, but you must call `client.close()` yourself:

```python
client = ScrawleeClient()
response = client.get("https://httpbin.org/get")
client.close()
```

### Passing Extra Options

`get()`, `post()`, `put()`, `patch()`, `delete()`, `head()`, `options()`, and `request()` accept any keyword arguments that `curl_cffi` supports. The most commonly used ones are:

```python
with ScrawleeClient() as client:
    # Query string parameters
    res = client.get("https://httpbin.org/get", params={"page": 2, "limit": 50})

    # Form-encoded POST body
    res = client.post("https://httpbin.org/post", data={"username": "bob", "password": "secret"})

    # JSON POST body
    res = client.post("https://httpbin.org/post", json={"token": "abc123"})

    # Custom per-request timeout (overrides the client timeout)
    res = client.get("https://slow-site.com", timeout=60)

    # Disable SSL verification (not recommended for production)
    res = client.get("https://self-signed.badssl.com", verify=False)
```

### Custom Headers

You can pass extra headers on individual requests or update the session headers so they apply to every request:

```python
with ScrawleeClient() as client:
    # Per-request headers
    res = client.get(
        "https://httpbin.org/headers",
        headers={"Authorization": "Bearer mytoken123"}
    )

    # Session-level headers (applied to all subsequent requests)
    client.session.headers.update({
        "X-Custom-Header": "my-value",
        "Referer": "https://google.com",
    })
    res = client.get("https://httpbin.org/headers")
```

### Sending POST Data

```python
with ScrawleeClient() as client:
    # JSON body
    res = client.post("https://httpbin.org/post", json={"search": "python"})
    logger.info(res.auto["json"])   # echoes back the parsed body

    # Form data
    res = client.post("https://httpbin.org/post", data={"field": "value"})
    logger.info(res.auto["form"])
```

---

## ScrawleeResponse — Working with Responses

Every request method returns a `ScrawleeResponse` object. It wraps the raw `curl_cffi` response and adds four parsing helpers, while still giving you full access to every standard response attribute.

### Standard Response Attributes

Because `ScrawleeResponse` transparently delegates to the underlying `curl_cffi` response, all standard attributes work exactly as you'd expect:

```python
with ScrawleeClient() as client:
    res = client.get("https://httpbin.org/get")

    res.status_code        # int, e.g. 200
    res.url                # str, the final URL after any redirects
    res.headers            # dict-like, response headers
    res.text               # str, decoded response body
    res.content            # bytes, raw response body
    res.cookies            # CookieJar
    res.elapsed            # timedelta, how long the request took
    res.encoding           # str, detected encoding
```

### `auto` — Smart Auto-Parser

`response.auto` is the most convenient property. It detects the `Content-Type` of the response and automatically returns the most useful representation:

| Response Content-Type | What `.auto` returns |
|---|---|
| `application/json` | A native Python `dict` (or `list`) parsed from the JSON body |
| `text/html` | A `selectolax` `HTMLParser` object ready for CSS queries |
| Anything else | The raw `response.text` string |

```python
with ScrawleeClient() as client:
    # JSON API endpoint
    res = client.get("https://httpbin.org/json")
    data = res.auto          # dict
    logger.info(data["slideshow"]["title"])

    # HTML page
    res = client.get("https://httpbin.org/html")
    parser = res.auto        # selectolax HTMLParser
    logger.info(parser.css_first("h1").text(strip=True))

    # Unknown content type (e.g. plain text)
    res = client.get("https://httpbin.org/robots.txt")
    logger.info(res.auto)          # raw string
```

`auto` is the recommended starting point for any request. Only use `html`, `lxml`, or `data` directly when you need a specific engine.

### `data` — JSON Responses

`response.data` is the parsed JSON body as a Python dict. It is `None` if the response is not JSON. Use this when you want to be explicit that you expect a JSON response.

```python
with ScrawleeClient() as client:
    res = client.get("https://httpbin.org/json")
    if res.data:
        logger.info(res.data["slideshow"]["author"])
```

### `html` — CSS Selector Parsing

`response.html` returns a `selectolax` `HTMLParser` instance. It is `None` for non-HTML responses.

`selectolax` is a C-extension parser — significantly faster than BeautifulSoup — and is ideal for CSS-based extraction.

**Selecting a single element:**

```python
with ScrawleeClient() as client:
    res = client.get("https://example.com")

    node = res.html.css_first("h1")
    if node:
        logger.info(node.text(strip=True))
```

**Selecting all matching elements:**

```python
with ScrawleeClient() as client:
    res = client.get("https://news.ycombinator.com")

    for item in res.html.css("span.titleline > a"):
        logger.info(item.text(strip=True), item.attributes.get("href"))
```

**Reading HTML attributes:**

```python
    link = res.html.css_first("a.my-link")
    href = link.attributes.get("href")
    data_id = link.attributes.get("data-id")
```

**Getting raw inner HTML of a node:**

```python
    node = res.html.css_first("div.content")
    logger.info(node.html)
```

**Checking if an element exists safely:**

```python
    node = res.html.css_first("div.optional-element")
    text = node.text(strip=True) if node else "not found"
```

### `lxml` — XPath Parsing

`response.lxml` returns a native `lxml` `HtmlElement` — the root element of the parsed document. It is `None` for non-HTML responses.

XPath is more powerful than CSS selectors when you need to traverse the document relationally (e.g. find a `<td>` based on its sibling's value, or navigate upward to a parent).

**Selecting text with a basic XPath:**

```python
with ScrawleeClient() as client:
    res = client.get("https://example.com")

    titles = res.lxml.xpath("//h1/text()")
    logger.info(titles[0] if titles else "not found")
```

**Selecting elements by attribute value:**

```python
    prices = res.lxml.xpath('//span[@class="price"]/text()')
    for price in prices:
        logger.info(price)
```

**Conditional XPath (in-stock items only):**

```python
    in_stock = res.lxml.xpath(
        '//div[@class="product" and @data-status="in-stock"]//span[@class="price"]/text()'
    )
```

**Navigating to a parent from a child:**

```python
    # Find the <tr> that contains the word "Revenue"
    row = res.lxml.xpath('//td[contains(text(), "Revenue")]/..')
```

**Combining `.html` and `.lxml` on the same response:**

Both parsers are built from the same response body, so you can freely mix them:

```python
with ScrawleeClient() as client:
    res = client.get("https://example.com/products")

    # Use selectolax for fast bulk list extraction
    names = [n.text(strip=True) for n in res.html.css("h2.product-name")]

    # Use lxml for a complex relational query
    special_price = res.lxml.xpath(
        '//div[@data-badge="sale"]//span[@class="price"]/text()'
    )
```

---

## AsyncScrawleeClient — Async Client

`AsyncScrawleeClient` is the asynchronous variant. It has an identical API to `ScrawleeClient`, but all request methods are coroutines and must be awaited. It uses `curl_cffi`'s `AsyncSession` internally.

Use it whenever you need to fire many requests in parallel. A single `asyncio.gather()` call can run dozens of requests concurrently with one client instance.

```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def main():
    async with AsyncScrawleeClient(impersonate="chrome120") as client:
        response = await client.get("https://httpbin.org/get")
        logger.info(response.status_code)
        logger.info(response.auto["url"])

asyncio.run(main())
```

### Running Requests Concurrently

```python
import asyncio
from scrawlee import AsyncScrawleeClient

URLS = [
    "https://httpbin.org/get",
    "https://httpbin.org/uuid",
    "https://httpbin.org/ip",
    "https://httpbin.org/user-agent",
]

async def main():
    async with AsyncScrawleeClient() as client:
        tasks = [client.get(url) for url in URLS]
        results = await asyncio.gather(*tasks)

        for res in results:
            logger.info(res.status_code, res.url)

asyncio.run(main())
```

All four requests fire simultaneously. The total time is roughly the time of the slowest single request, not the sum of all four.

**Async POST requests:**

```python
async def main():
    async with AsyncScrawleeClient() as client:
        res = await client.post(
            "https://httpbin.org/post",
            json={"query": "test"}
        )
        logger.info(res.data)
```

**Async with proxy rotation:**

```python
from scrawlee import AsyncScrawleeClient, ProxyManager

async def main():
    pm = ProxyManager(rotation_strategy="round_robin")
    pm.add_proxy(ip="12.34.56.78", port="8080", username="user", password="pwd")

    async with AsyncScrawleeClient(proxy_manager=pm) as client:
        res = await client.get("https://api.myip.com")
        logger.info(res.auto)
```

**Note on `save_cookies` / `load_cookies` in async mode:** these two methods are synchronous (they are just file I/O) and do not need to be awaited.

---

## ProxyManager — Proxy Rotation

`ProxyManager` maintains a pool of proxy servers and selects from them on every request according to a rotation strategy. It also tracks failures and automatically quarantines broken proxies.

### Rotation Strategies

| Strategy | Behaviour |
|---|---|
| `"round_robin"` | Cycles through proxies in order. Each request uses the next proxy in the list. |
| `"random"` | Picks a random proxy from the available pool for every request. |
| `"sticky"` | Always uses the first available proxy. Useful when you want session continuity through one IP. |

```python
from scrawlee import ProxyManager

pm_rr     = ProxyManager(rotation_strategy="round_robin")
pm_rand   = ProxyManager(rotation_strategy="random")
pm_sticky = ProxyManager(rotation_strategy="sticky")
```

The default strategy is `"round_robin"`.

### Adding Proxies

```python
from scrawlee import ProxyManager

pm = ProxyManager()

# Authenticated proxy
pm.add_proxy(ip="12.34.56.78", port="8080", username="myuser", password="mypassword")

# Unauthenticated proxy
pm.add_proxy(ip="98.76.54.32", port="3128")

# You can add as many as you want
pm.add_proxy(ip="11.22.33.44", port="8080", username="u2", password="p2")
```

Scrawlee encodes credentials safely using `urllib.parse.quote_plus`, so special characters in usernames or passwords are handled correctly.

Internally, each proxy is stored as:

```python
{"http": "http://user:pwd@ip:port", "https": "http://user:pwd@ip:port"}
```

This format is passed directly to `curl_cffi` on every request.

### How Quarantine Works

When a request fails (network error, or a retryable HTTP status after exhausting retries) and a proxy was in use, that proxy is automatically marked as failed:

```python
proxy_manager.mark_failed(proxy_dict)
```

A failed proxy is quarantined for **300 seconds (5 minutes)**. During that window it is excluded from rotation. After 5 minutes it is automatically re-admitted into the pool.

If **all** proxies are quarantined simultaneously, Scrawlee falls back to trying all of them anyway rather than sending direct traffic.

You do not need to call `mark_failed` yourself — the client handles it automatically on every exception.

---

## Cookie Persistence

Scrawlee stores cookies in the session automatically between requests (standard browser cookie jar behavior). You can also save the current cookie jar to a JSON file and reload it in a future script — useful for resuming authenticated sessions or bypassed bot challenges without repeating the login flow.

**Saving cookies:**

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    # Perform login or solve a challenge here
    client.post("https://example.com/login", data={"user": "bob", "pass": "secret"})

    # Save cookies to disk
    client.save_cookies("example_session.json")
    logger.info("Session saved.")
```

The file will contain a plain JSON object mapping cookie names to values:

```json
{
    "session_id": "abc123xyz",
    "csrf_token": "def456"
}
```

**Loading cookies in a later script:**

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    client.load_cookies("example_session.json")

    # Now authenticated immediately, no login needed
    res = client.get("https://example.com/dashboard")
    logger.info(res.status_code)
```

`load_cookies` silently does nothing if the file does not exist or is malformed, so it is safe to call unconditionally at the start of a script.

Both `save_cookies` and `load_cookies` are available on `AsyncScrawleeClient` as well, and are called the same way (no `await` needed).

---

## Retry Behavior

Scrawlee automatically retries requests on the following HTTP status codes:

| Status Code | Meaning |
|---|---|
| `429` | Too Many Requests (rate limited) |
| `500` | Internal Server Error |
| `502` | Bad Gateway |
| `503` | Service Unavailable |
| `504` | Gateway Timeout |

The retry loop uses **exponential backoff with jitter**:

- Wait time starts at `1.0` second
- After each failure, wait time doubles: `1s → 2s → 4s → ...`
- A random jitter of `0.0–1.0` seconds is added to prevent thundering-herd issues
- The proxy that was used on the failed attempt is quarantined

After `max_retries` (default: `3`) failed attempts, an exception is raised:

```
Exception: Max retries reached for https://example.com. Last error: ...
```

To increase resilience for long scraping jobs:

```python
client = ScrawleeClient(max_retries=5, timeout=60)
```

---

## Browser Impersonation

Scrawlee uses `curl_cffi` to send byte-accurate TLS handshakes matching real browsers. This means the JA3/JA4 fingerprint, cipher suite order, TLS extensions, and HTTP/2 settings all match the real browser — not a generic Python client.

Available fingerprints:

| Value | Browser |
|---|---|
| `"chrome110"` | Chrome 110 |
| `"chrome120"` | Chrome 120 |
| `"edge101"` | Edge 101 |
| `"safari15_5"` | Safari 15.5 |
| `"random"` | One of the above, chosen randomly at session creation |

In addition to the TLS fingerprint, Scrawlee also generates matching browser request headers automatically on each new session:

- `Accept-Language`: randomly chosen from common English locale strings
- `Sec-Fetch-Dest: document`
- `Sec-Fetch-Mode: navigate`
- `Sec-Fetch-Site: none`
- `Sec-Fetch-User: ?1`
- `Upgrade-Insecure-Requests: 1`

These headers are sent alongside `curl_cffi`'s built-in browser `Accept` and `User-Agent` for the chosen fingerprint, making the full request profile match a real browser session.

---

## Complete End-to-End Examples

### Scraping a JSON API

```python
from scrawlee import ScrawleeClient

def fetch_todos(limit=5):
    with ScrawleeClient(impersonate="chrome120") as client:
        res = client.get(
            "https://jsonplaceholder.typicode.com/todos",
            params={"_limit": limit}
        )

        if res.status_code != 200:
            raise RuntimeError(f"Request failed: {res.status_code}")

        todos = res.auto  # automatically a list of dicts
        for todo in todos:
            status = "done" if todo["completed"] else "pending"
            logger.info(f"[{status}] {todo['title']}")

fetch_todos()
```

### Scraping an HTML Page

```python
from scrawlee import ScrawleeClient

def scrape_quotes():
    with ScrawleeClient() as client:
        res = client.get("https://quotes.toscrape.com")

        for quote_div in res.html.css("div.quote"):
            text   = quote_div.css_first("span.text").text(strip=True)
            author = quote_div.css_first("small.author").text(strip=True)
            tags   = [t.text(strip=True) for t in quote_div.css("a.tag")]
            logger.info(f"{text}\n  — {author}  |  tags: {', '.join(tags)}\n")

scrape_quotes()
```

### High-Volume Async Scraper with Proxies

```python
import asyncio
from scrawlee import AsyncScrawleeClient, ProxyManager

PRODUCT_URLS = [
    "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
    "https://books.toscrape.com/catalogue/soumission_998/index.html",
    "https://books.toscrape.com/catalogue/sharp-objects_997/index.html",
]

async def scrape_product(client, url):
    res = await client.get(url)
    title = res.html.css_first("h1").text(strip=True)
    price = res.html.css_first("p.price_color").text(strip=True)
    stock = res.html.css_first("p.availability").text(strip=True)
    return {"url": url, "title": title, "price": price, "stock": stock}

async def main():
    pm = ProxyManager(rotation_strategy="round_robin")
    pm.add_proxy(ip="12.34.56.78", port="8080", username="user", password="pwd")
    pm.add_proxy(ip="98.76.54.32", port="8080", username="user2", password="pwd2")

    async with AsyncScrawleeClient(proxy_manager=pm, max_retries=5) as client:
        tasks = [scrape_product(client, url) for url in PRODUCT_URLS]
        products = await asyncio.gather(*tasks)

    for p in products:
        logger.info(f"{p['title']}  |  {p['price']}  |  {p['stock']}")

asyncio.run(main())
```

### Resuming an Authenticated Session

```python
import os
from scrawlee import ScrawleeClient

SESSION_FILE = "my_session.json"

def get_client_with_session():
    client = ScrawleeClient(impersonate="chrome120")
    if os.path.exists(SESSION_FILE):
        client.load_cookies(SESSION_FILE)
        logger.info("Loaded existing session.")
    else:
        logger.info("No session found, starting fresh.")
    return client

with get_client_with_session() as client:
    res = client.get("https://example.com/profile")

    if "login" in res.url:
        # Session expired or not present, log in again
        client.post("https://example.com/login", data={
            "username": "myuser",
            "password": "mypassword"
        })
        client.save_cookies(SESSION_FILE)
        logger.info("Logged in and session saved.")
        res = client.get("https://example.com/profile")

    logger.info("Profile page status: {}", res.status_code)
```

---

## API Reference

### `ScrawleeClient`

```python
class ScrawleeClient:
    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        max_retries: int = 3,
        impersonate: str = "random",
        timeout: int = 30,
    ): ...

    def request(self, method: str, url: str, **kwargs) -> ScrawleeResponse: ...
    def get(self, url: str, **kwargs) -> ScrawleeResponse: ...
    def post(self, url: str, **kwargs) -> ScrawleeResponse: ...
    def save_cookies(self, filepath: str) -> None: ...
    def load_cookies(self, filepath: str) -> None: ...
    def close(self) -> None: ...

    def __enter__(self) -> ScrawleeClient: ...
    def __exit__(self, ...) -> None: ...
```

### `AsyncScrawleeClient`

```python
class AsyncScrawleeClient:
    def __init__(
        self,
        proxy_manager: ProxyManager | None = None,
        max_retries: int = 3,
        impersonate: str = "random",
        timeout: int = 30,
    ): ...

    async def request(self, method: str, url: str, **kwargs) -> ScrawleeResponse: ...
    async def get(self, url: str, **kwargs) -> ScrawleeResponse: ...
    async def post(self, url: str, **kwargs) -> ScrawleeResponse: ...
    def save_cookies(self, filepath: str) -> None: ...
    def load_cookies(self, filepath: str) -> None: ...
    async def close(self) -> None: ...

    async def __aenter__(self) -> AsyncScrawleeClient: ...
    async def __aexit__(self, ...) -> None: ...
```

### `ScrawleeResponse`

```python
class ScrawleeResponse:
    # Parsing helpers
    auto   # dict | HTMLParser | str  — smart auto-detected parser
    data   # dict | None              — parsed JSON body
    html   # HTMLParser | None        — selectolax parser (HTML responses only)
    lxml   # HtmlElement | None       — lxml element (HTML responses only)

    # Delegated from the underlying curl_cffi response (all standard attributes work)
    status_code   # int
    url           # str
    headers       # dict-like
    text          # str
    content       # bytes
    cookies       # CookieJar
    elapsed       # timedelta
    encoding      # str
```

### `ProxyManager`

```python
class ProxyManager:
    def __init__(self, rotation_strategy: str = "round_robin"): ...
    #   rotation_strategy: "round_robin" | "random" | "sticky"

    def add_proxy(
        self,
        ip: str,
        port: str,
        username: str = "",
        password: str = "",
    ) -> None: ...

    def get_proxy(self) -> dict | None: ...
    def mark_failed(self, proxy_dict: dict) -> None: ...
```

---
