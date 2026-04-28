# Scrawlee

> **Most scrapers get blocked. Scrawlee doesn't.**
>
> While every other HTTP client announces itself through its TLS handshake, Scrawlee impersonates Chrome, Edge, and Safari at the network layer — the exact fingerprints anti-bot systems trust. It rotates and self-heals proxy pools, survives rate limits with exponential back-off, and hands you parsed data the instant a response lands. Hit a JavaScript wall or a Cloudflare challenge? One flag flips it to a full anti-detect Chrome instance that has bypassed Cloudflare, Datadome, and FingerprintJS in production. Built for engineers who are done fighting infrastructure and just want the data.

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI version](https://img.shields.io/badge/version-0.1.0-green)](pyproject.toml)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [How It Works](#2-how-it-works)
3. [Tech Stack & Dependencies](#3-tech-stack--dependencies)
4. [Core Features](#4-core-features)
5. [Installation](#5-installation)
6. [Technical How-To Guide](#6-technical-how-to-guide)
   - [Basic HTTP Requests](#61-basic-http-requests)
   - [Working with Responses](#62-working-with-responses)
   - [Async Requests](#63-async-requests)
   - [Proxy Rotation](#64-proxy-rotation)
   - [Browser Automation](#65-browser-automation)
   - [Advanced Configuration](#66-advanced-configuration)
   - [Cookie Persistence](#67-cookie-persistence)
7. [FAQ](#7-faq)
8. [Contributing](#8-contributing)
9. [License](#9-license)

---

## 1. Project Overview

Modern websites defend themselves with a layered stack of bot-detection systems: TLS fingerprinting checks, HTTP/2 frame analysis, browser-feature detection, Cloudflare Turnstile, Datadome, FingerprintJS, and IP reputation databases. A plain `requests` call fails every single one of these checks before the server even reads the URL.

**Scrawlee** is designed to win those checks by default.

It is a stealth-focused Python scraping library that impersonates real browser TLS fingerprints at the network level, generates matching browser-grade HTTP headers, rotates and quarantines proxies automatically, retries transient failures with exponential back-off, and wraps every response in an auto-parsing layer so you get typed JSON dictionaries or live DOM objects — never raw strings — without writing any parsing glue code yourself.

When HTTP-level stealth is not enough, Scrawlee can drive a **real Chrome instance** through its `BrowserClient`, backed by the botasaurus anti-detect driver. This unlocks full JavaScript rendering, human-like interactions, Cloudflare JS-challenge solving, cookie persistence across sessions, and low-bandwidth fetch-API scraping — all through the same clean response interface.

### Problems Scrawlee solves

| Problem | Scrawlee's answer |
|---|---|
| TLS fingerprint blocklists | `curl_cffi` impersonates Chrome/Edge/Safari at the TLS layer |
| Bot-detection HTTP headers | Dynamically generated `Sec-Fetch-*` + `Accept-Language` headers keyed to the active fingerprint |
| IP bans and rate-limiting | `ProxyManager` with quarantine, automatic fail-over, and three rotation strategies |
| Transient server errors | Configurable retry loop with exponential back-off and random jitter |
| Manual JSON / HTML parsing | `ScrawleeResponse.auto` returns the right object for the content type |
| JavaScript-rendered pages | `BrowserClient` drives a real Chrome with botasaurus anti-detect |
| Cloudflare / Datadome WAFs | `BrowserClient(bypass_cloudflare=True)` engages botasaurus JS + Captcha solver |
| Bandwidth costs at scale | `BrowserClient.fetch()` uses the browser's native fetch API (up to 97% less data) |

---

## 2. How It Works

### 2.1 HTTP request lifecycle (`ScrawleeClient` / `AsyncScrawleeClient`)

```
ScrawleeClient.get(url)
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  1. ProxyManager.get_proxy()                             │
│     • Checks quarantine list (5-minute cooldown default) │
│     • Applies round_robin / random / sticky strategy     │
│     • Falls back to direct connection if pool is empty   │
└────────────────────────┬─────────────────────────────────┘
                         │ proxy dict (or None)
                         ▼
┌──────────────────────────────────────────────────────────┐
│  2. curl_cffi Session.request()                          │
│     • Sends request with active TLS fingerprint          │
│       (chrome110 / chrome120 / edge101 / safari15_5)     │
│     • Attaches forged Sec-Fetch-* + Accept-Language      │
│       headers that match the chosen fingerprint          │
└────────────────────────┬─────────────────────────────────┘
                         │ raw Response
                         ▼
┌──────────────────────────────────────────────────────────┐
│  3. Retry / back-off logic                               │
│     • If status_code ∈ retry_status_codes → re-raise     │
│     • If retry_exceptions raised → mark proxy failed     │
│       and quarantine it; sleep exponential + jitter      │
│     • Repeat up to max_retries times                     │
└────────────────────────┬─────────────────────────────────┘
                         │ successful raw Response
                         ▼
┌──────────────────────────────────────────────────────────┐
│  4. ScrawleeResponse auto-parse                          │
│     • Content-Type: application/json → .data (dict)      │
│     • Content-Type: text/html        → .html (selectolax)│
│                                        .lxml (lxml)       │
│     • .auto returns the most useful parsed form          │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Browser request lifecycle (`BrowserClient`)

```
BrowserClient.get(url)
       │
       ▼
┌──────────────────────────────────────────────────────────┐
│  1. botasaurus @browser decorator                        │
│     • Spawns or reuses a Chrome instance                 │
│     • Applies anti-detect patches (WebGL, Canvas,        │
│       navigator.webdriver = false, etc.)                 │
│     • Configures proxy, profile, image blocking          │
└────────────────────────┬─────────────────────────────────┘
                         │ Driver ready
                         ▼
┌──────────────────────────────────────────────────────────┐
│  2. Driver.google_get(url) / Driver.get(url)             │
│     • Navigates via Google referrer for stealth OR       │
│       directly — depending on via_google flag            │
│     • Optionally solves Turnstile / JS-challenge         │
│       when bypass_cloudflare=True                        │
└────────────────────────┬─────────────────────────────────┘
                         │ driver.page_html (fully rendered)
                         ▼
┌──────────────────────────────────────────────────────────┐
│  3. BrowserResponse construction                         │
│     • Passes rendered HTML to selectolax HTMLParser      │
│     • Passes rendered HTML to lxml.html.fromstring       │
│     • .html, .lxml, .text, .auto ready for extraction    │
└──────────────────────────────────────────────────────────┘
```

---

## 3. Tech Stack & Dependencies

### Core dependencies

| Library | Version | Role | Why it was chosen |
|---|---|---|---|
| **[curl_cffi](https://github.com/yifeikong/curl-cffi)** | `>=0.7.1` | TLS impersonation + HTTP client | Binds to `libcurl` with BoringSSL to produce byte-exact TLS `ClientHello` messages that match real browser fingerprints. Standard `requests` / `httpx` use OpenSSL and produce a distinct fingerprint that anti-bot systems recognise immediately. |
| **[selectolax](https://github.com/rushter/selectolax)** | `>=0.3.17` | Fast CSS selector HTML parsing | Written in C via Cython; benchmarks 10–50× faster than BeautifulSoup for DOM traversal. The natural choice for high-throughput HTML extraction. |
| **[lxml](https://lxml.de/)** | `>=5.1.0` | XPath HTML parsing | The de-facto standard for complex XPath queries in Python. Complements selectolax by exposing the full XPath axis model for cases where CSS selectors are insufficient. |
| **[loguru](https://github.com/Delgan/loguru)** | `>=0.7.2` | Structured logging | Zero-config, coloured, structured logging with no boilerplate. Provides debug, warning, and error output across proxy rotation and retry events without requiring users to configure Python's `logging` module. |botsaruruss is no toptional depencies its part of scrawlee as main
| **[botasaurus](https://github.com/omkarcloud/botasaurus)** | `>=4.0.0` | Anti-detect Chrome automation | Wraps Playwright-managed Chrome with comprehensive anti-detection patches (Canvas, WebGL, navigator props, TLS JA3/JA4 normalization). Provides a `@browser` decorator that handles driver lifecycle, Google-referrer navigation, and built-in Cloudflare / Datadome bypass — far beyond what vanilla Playwright or Selenium offer. Part of Scrawlee's core — not optional. |
| **[nodejs-bin](https://pypi.org/project/nodejs-bin/)** | `>=18.0.0` | Bundled Node.js runtime | Ships pre-compiled Node.js LTS binaries as a Python wheel. Installs the `node` executable directly into the virtualenv — no system-level Node.js install required. Botasaurus uses Node.js for its JavaScript-based Cloudflare challenge solver; bundling it here means `pip install scrawlee` is the only command a user ever needs. |

### Build tools

| Tool | Role |
|---|---|
| **hatchling** | PEP 517 build backend |
| **pytest** | Test runner |
| **build + twine** | Package distribution |

### Runtime requirements

- Python **3.8+**
- Node.js — installed automatically via `nodejs-bin` (bundled as a Python wheel; no separate system install required)

---

## 4. Core Features

### HTTP / TLS layer
- **TLS fingerprint impersonation** — Impersonates `chrome110`, `chrome120`, `edge101`, or `safari15_5` at the TLS `ClientHello` level via `curl_cffi`, making requests indistinguishable from a real browser at the network layer.
- **Random fingerprint selection** — Passing `impersonate="random"` (the default) picks a different browser fingerprint on each `ScrawleeClient` instantiation to prevent fingerprint entropy clustering.
- **Dynamic organic headers** — `_generate_dynamic_headers()` automatically attaches `Accept-Language`, `Sec-Fetch-Dest`, `Sec-Fetch-Mode`, `Sec-Fetch-Site`, `Sec-Fetch-User`, and `Upgrade-Insecure-Requests` values that are consistent with the chosen browser identity.
- **Persistent session** — A single `curl_cffi.requests.Session` is reused across all calls, preserving cookies and connection pools exactly as a browser would.
- **Full HTTP method support** — `get()`, `post()`, `put()`, `patch()`, `delete()`, `head()`, `options()`.

### Proxy management
- **Three rotation strategies** — `round_robin` (default), `random`, and `sticky` via `ProxyManager(rotation_strategy=...)`.
- **Automatic proxy quarantine** — Failed proxies are removed from the active pool for a configurable cooldown period (default 300 seconds) via `mark_failed()` / `_clean_quarantine()`.
- **Full-pool fallback** — If all proxies are quarantined, `get_proxy()` temporarily re-admits the full pool rather than hanging.
- **Credential URL encoding** — `add_proxy()` URL-encodes usernames and passwords with `quote_plus` to handle special characters in credentials.
- **Duplicate detection** — Re-adding an identical proxy to the pool is silently ignored.

### Reliability
- **Configurable retry loop** — `max_retries` (default 3) controls how many times a failing request is re-attempted.
- **Configurable retry triggers** — `retry_status_codes` (default: `{429, 500, 502, 503, 504}`) and `retry_exceptions` (default: any `Exception`) determine what constitutes a retriable failure.
- **Exponential back-off with jitter** — Sleep time doubles on every retry (`retry_backoff_base * 2^n`) plus a random `uniform(0, retry_jitter_max)` offset to prevent thundering-herd on shared proxy pools.

### Response auto-parsing (`ScrawleeResponse`)
- **Auto-detection** — Inspects the `Content-Type` response header and parses the body automatically.
- **`.auto` property** — Returns a Python `dict` for JSON APIs or a `selectolax.parser.HTMLParser` for HTML pages; falls back to the raw text string.
- **`.data` property** — Exposes the parsed JSON body as a native Python `dict`.
- **`.html` property** — Exposes a live `selectolax.parser.HTMLParser` for CSS selector-based DOM traversal.
- **`.lxml` property** — Exposes an `lxml.html.HtmlElement` for XPath-based extraction.
- **Transparent delegation** — All other attributes (`status_code`, `url`, `headers`, `cookies`, `text`, `content`, etc.) are transparently delegated to the underlying `curl_cffi` response object.

### Async support (`AsyncScrawleeClient`)
- **`asyncio`-native** — Uses `curl_cffi.requests.AsyncSession` so thousands of concurrent requests can be dispatched with `asyncio.gather()` without thread-pool overhead.
- **Identical API** — Every method mirrors `ScrawleeClient` with `async/await`; `asyncio.sleep()` is used in place of `time.sleep()` during back-off.
- **Async context manager** — `async with AsyncScrawleeClient() as client:` correctly closes the `AsyncSession` with `await`.

### Browser automation (`BrowserClient`)
- **Real Chrome, anti-detect patched** — Launches an actual Chrome instance via botasaurus with all standard bot-detection vectors suppressed (`navigator.webdriver`, Canvas noise, WebGL renderer masking, etc.).
- **`get(url)`** — Full Chrome navigation; returns a `BrowserResponse` with selectolax and lxml parsers already populated.
- **Google-referrer stealth** — `via_google=True` (default) routes the initial visit through a Google search referrer, passing referrer-policy checks on many sites.
- **Cloudflare / Datadome bypass** — `bypass_cloudflare=True` engages botasaurus's JS + Captcha solver for Turnstile and JS-computation challenges.
- **`fetch(url)`** — Uses the browser's built-in fetch API to retrieve subsequent pages without full navigation (up to 97% bandwidth reduction); inherits the established session and cookies.
- **`run(task_fn)`** — Accepts any `(driver: Driver) -> Any` callable for arbitrary browser interactions: form submission, clicking, typing, scrolling, JS execution, iframe access, CDP commands, etc.
- **Chrome profile persistence** — `profile="my_profile"` persists the full Chrome profile (~100 MB) or, with `tiny_profile=True`, a cookie-only lightweight variant (~1 KB).
- **Driver reuse** — `reuse_driver=True` (default) keeps the Chrome instance alive between calls, eliminating per-request browser startup cost.
- **Resource blocking** — `block_images=True` or `block_images_and_css=True` suppress unnecessary network requests to reduce bandwidth and speed up loads.

### Cookie persistence
- **`save_cookies(filepath)`** — Serialises all current session cookies to a JSON file.
- **`load_cookies(filepath)`** — Rehydrates a session from a previously saved JSON cookie file, enabling authenticated session resumption.

---

## 5. Installation

```bash
pip install scrawlee
```

Everything Scrawlee needs — including botasaurus and a bundled Node.js runtime — is installed automatically. No separate system-level installs are required. `BrowserClient` is ready to use immediately after `pip install scrawlee`.

### From source

```bash
git clone https://github.com/<your-username>/scrawlee.git
cd scrawlee
pip install -e ".[dev]"
```

---

## 6. Technical How-To Guide

### 6.1 Basic HTTP requests

Scrawlee's HTTP client is `ScrawleeClient`. Every request goes through TLS fingerprint impersonation, automatic proxy rotation (if configured), exponential back-off retries, and auto-response parsing — all invisibly.

```python
from scrawlee import ScrawleeClient

# Context manager ensures the session is closed and connections are released.
with ScrawleeClient() as client:
    response = client.get("https://httpbin.org/get")
    print(response.status_code)   # 200
    print(response.url)           # https://httpbin.org/get
    print(response.headers)       # dict of response headers
```

#### All HTTP methods

```python
with ScrawleeClient() as client:
    # GET — retrieve a resource
    r = client.get("https://api.example.com/items")

    # POST — create a resource, send a JSON body
    r = client.post("https://api.example.com/items", json={"name": "widget", "price": 9.99})

    # POST — submit HTML form data
    r = client.post("https://example.com/login", data={"username": "me", "password": "secret"})

    # PUT — full replacement of a resource
    r = client.put("https://api.example.com/items/42", json={"name": "updated widget"})

    # PATCH — partial update
    r = client.patch("https://api.example.com/items/42", json={"active": False})

    # DELETE
    r = client.delete("https://api.example.com/items/42")

    # HEAD — fetch headers only, no body (useful for checking if a URL exists)
    r = client.head("https://example.com/large-file.zip")
    print(r.headers.get("Content-Length"))

    # OPTIONS — discover allowed methods
    r = client.options("https://api.example.com/items")
    print(r.headers.get("Allow"))
```

#### Passing extra `curl_cffi` options

Any keyword argument accepted by `curl_cffi.requests.Session.request()` passes straight through — query parameters, custom headers, timeouts, redirect control, and more:

```python
with ScrawleeClient() as client:
    response = client.get(
        "https://api.example.com/search",
        params={"q": "scrawlee", "page": 2, "limit": 50},
        headers={
            "Authorization": "Bearer eyJhbGci...",
            "X-Request-ID": "abc-123",
        },
        timeout=90,
        allow_redirects=False,
    )
    print(response.status_code)  # 301 if redirect was not followed
```

#### Inspecting the impersonated fingerprint

The active TLS fingerprint is chosen randomly at instantiation time (from `chrome110`, `chrome120`, `edge101`, `safari15_5`). You can read or pin it:

```python
client = ScrawleeClient()
print(client.impersonate)   # e.g. "chrome120"

# Pin a specific fingerprint
client = ScrawleeClient(impersonate="safari15_5")
print(client.impersonate)   # always "safari15_5"
```

---

### 6.2 Working with responses

`ScrawleeClient` returns a `ScrawleeResponse`. On construction it inspects the `Content-Type` header and eagerly parses the body — you never call a separate parse step.

#### Scraping an HTML page — CSS selectors via `selectolax`

selectolax uses a C-backed Lexbor parser. CSS selector queries are 10–50× faster than BeautifulSoup.

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    response = client.get("https://news.ycombinator.com/")
    page = response.html  # selectolax HTMLParser

    # css_first returns the first match, or None
    top_story = page.css_first(".titleline > a")
    print(top_story.text())          # article title
    print(top_story.attrs["href"])   # article URL

    # css returns a list of all matching nodes
    titles = [el.text() for el in page.css(".titleline > a")]
    scores = [el.text() for el in page.css(".score")]
    authors = [el.text() for el in page.css(".hnuser")]

    for title, score, author in zip(titles, scores, authors):
        print(f"{score:>8}  {author:<20}  {title}")
```

#### Navigating the DOM tree

selectolax lets you walk parent / sibling / child relationships without building a full tree:

```python
with ScrawleeClient() as client:
    response = client.get("https://books.toscrape.com/")
    page = response.html

    books = []
    for article in page.css("article.product_pod"):
        title  = article.css_first("h3 > a").attrs["title"]
        price  = article.css_first(".price_color").text()
        rating = article.css_first("p.star-rating").attrs["class"].split()[-1]
        in_stock = article.css_first(".availability").text().strip()
        books.append({"title": title, "price": price, "rating": rating, "in_stock": in_stock})

    # Sort by price descending
    books.sort(key=lambda b: float(b["price"].replace("Â£", "").replace("£", "")), reverse=True)
    for book in books[:5]:
        print(book)
```

#### Scraping an HTML page — XPath via `lxml`

lxml XPath is the right tool for axes (`ancestor::`, `following-sibling::`, `preceding::`) and text node extraction:

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    response = client.get("https://books.toscrape.com/")
    tree = response.lxml  # lxml HtmlElement

    # XPath axis: find the <p> price inside each article
    prices = tree.xpath('//article[@class="product_pod"]//p[@class="price_color"]/text()')
    # XPath string functions
    titles = tree.xpath('//article//h3/a/@title')
    # Conditional XPath: books with 5-star rating only
    five_star = tree.xpath('//p[contains(@class,"star-rating Five")]/following-sibling::h3/a/@title')

    print("All prices:", prices[:5])
    print("5-star titles:", five_star)
```

#### Consuming a JSON API

```python
from scrawlee import ScrawleeClient

with ScrawleeClient() as client:
    # Single resource
    response = client.get("https://jsonplaceholder.typicode.com/posts/1")
    post = response.data   # plain Python dict
    print(post["title"], post["userId"])

    # Collection
    response = client.get("https://jsonplaceholder.typicode.com/posts")
    posts = response.data  # list of dicts
    print(f"{len(posts)} posts fetched")

    # Nested JSON — just use normal dict/list access
    response = client.get("https://jsonplaceholder.typicode.com/users/1")
    user = response.data
    print(user["address"]["city"])
    print(user["company"]["name"])
```

#### Posting JSON and reading the echo

```python
with ScrawleeClient() as client:
    response = client.post(
        "https://jsonplaceholder.typicode.com/posts",
        json={"title": "Scrawlee rocks", "body": "stealth scraping", "userId": 1},
    )
    created = response.data
    print(created["id"])     # the server-assigned ID
    print(created["title"])  # echoed back
```

#### Using `.auto` for content-agnostic code

`.auto` returns a `dict` for JSON, an `HTMLParser` for HTML, or raw text as a fallback — useful for utility functions that handle multiple endpoint types:

```python
from scrawlee import ScrawleeClient

def fetch_and_dump(url: str):
    with ScrawleeClient() as client:
        response = client.get(url)
        result = response.auto
        if isinstance(result, dict):
            # JSON endpoint
            return result
        else:
            # HTML endpoint — selectolax HTMLParser
            return {"text": result.text()}

print(fetch_and_dump("https://jsonplaceholder.typicode.com/posts/1"))
print(fetch_and_dump("https://example.com"))
```

#### Accessing raw response properties

`ScrawleeResponse` transparently delegates every attribute not explicitly defined to the underlying `curl_cffi` response:

```python
with ScrawleeClient() as client:
    r = client.get("https://httpbin.org/response-headers?X-Powered-By=Scrawlee")

    print(r.status_code)                         # 200
    print(r.url)                                 # final URL after redirects
    print(r.headers["Content-Type"])             # "application/json"
    print(r.headers.get("X-Powered-By"))         # "Scrawlee"
    print(r.elapsed.total_seconds())             # request round-trip time
    print(len(r.content))                        # raw bytes length
    print(r.encoding)                            # detected charset
    print(dict(r.cookies))                       # cookie jar as plain dict
```

---

### 6.3 Async requests

`AsyncScrawleeClient` is powered by `curl_cffi.requests.AsyncSession` — backed by `libcurl`'s multi-handle non-blocking interface. Every method mirrors `ScrawleeClient` exactly, only with `async/await`. The exponential back-off uses `await asyncio.sleep()` so the event loop is never blocked during retries.

#### Fire-and-gather pattern

```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def scrape_all(urls: list[str]):
    async with AsyncScrawleeClient() as client:
        tasks = [client.get(url) for url in urls]
        responses = await asyncio.gather(*tasks)
    return responses

urls = [
    "https://httpbin.org/get",
    "https://httpbin.org/ip",
    "https://httpbin.org/headers",
    "https://httpbin.org/user-agent",
    "https://httpbin.org/uuid",
]
responses = asyncio.run(scrape_all(urls))
for r in responses:
    print(r.status_code, r.url)
```

#### Controlled concurrency with `asyncio.Semaphore`

When scraping hundreds or thousands of URLs, unbounded `gather()` will exhaust file descriptors and proxy bandwidth. Use a semaphore to cap the number of in-flight requests:

```python
import asyncio
from scrawlee import AsyncScrawleeClient, ProxyManager

async def scrape_with_limit(urls: list[str], concurrency: int = 25):
    pm = ProxyManager(rotation_strategy="random")
    pm.add_proxy("10.0.0.1", "3128", "user", "pass")
    pm.add_proxy("10.0.0.2", "3128", "user", "pass")

    sem = asyncio.Semaphore(concurrency)

    async with AsyncScrawleeClient(proxy_manager=pm) as client:
        async def bounded_get(url: str):
            async with sem:
                return await client.get(url)

        return await asyncio.gather(*[bounded_get(u) for u in urls])

urls = [f"https://example.com/page/{i}" for i in range(200)]
results = asyncio.run(scrape_with_limit(urls, concurrency=30))
print(f"Fetched {len(results)} pages")
```

#### Async POST requests

```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def submit_forms(payloads: list[dict]):
    async with AsyncScrawleeClient() as client:
        tasks = [
            client.post("https://api.example.com/submit", json=payload)
            for payload in payloads
        ]
        responses = await asyncio.gather(*tasks)
    return [r.data for r in responses]

results = asyncio.run(submit_forms([
    {"query": "apple"},
    {"query": "banana"},
    {"query": "cherry"},
]))
print(results)
```

#### Producer-consumer pattern for large crawls

For very large link graphs, a queue-based producer-consumer avoids building the full URL list in memory:

```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def crawl_queue(seed_urls: list[str], concurrency: int = 20):
    queue: asyncio.Queue = asyncio.Queue()
    results = []
    visited = set()

    for url in seed_urls:
        await queue.put(url)
        visited.add(url)

    async with AsyncScrawleeClient() as client:
        async def worker():
            while True:
                url = await queue.get()
                try:
                    r = await client.get(url)
                    results.append((url, r.status_code))
                    # discover more links
                    if r.html:
                        for a in r.html.css("a[href]"):
                            href = a.attrs.get("href", "")
                            if href.startswith("https://example.com") and href not in visited:
                                visited.add(href)
                                await queue.put(href)
                finally:
                    queue.task_done()

        workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
        await queue.join()
        for w in workers:
            w.cancel()

    return results

results = asyncio.run(crawl_queue(["https://example.com"]))
print(f"Crawled {len(results)} pages")
```

---

### 6.4 Proxy rotation

`ProxyManager` maintains a pool of proxies, routes requests through them according to the chosen strategy, and automatically quarantines proxies that cause failures.

#### Adding proxies and choosing a rotation strategy

```python
from scrawlee import ScrawleeClient, ProxyManager

pm = ProxyManager(rotation_strategy="round_robin")  # the default
pm.add_proxy("192.168.1.10", "8080")                          # unauthenticated
pm.add_proxy("10.0.0.1",    "3128", "user", "p@$$w0rd")      # with credentials
pm.add_proxy("203.0.113.5", "9999", "alice", "hunter2")

with ScrawleeClient(proxy_manager=pm) as client:
    r = client.get("https://httpbin.org/ip")
    print(r.data["origin"])  # shows the proxy's exit IP
```

#### Strategy comparison

```python
# Round-robin — cycles 1→2→3→1→2→3 regardless of which requests succeed
pm_rr = ProxyManager(rotation_strategy="round_robin")

# Random — picks any healthy proxy at random on every request
# Best for large pools where any IP works equally well
pm_rand = ProxyManager(rotation_strategy="random")

# Sticky — always uses the first healthy proxy
# Use when the target site tracks sessions by IP (e.g., shopping carts, login pages)
pm_sticky = ProxyManager(rotation_strategy="sticky")
```

#### Verifying which proxy was used

```python
from scrawlee import ScrawleeClient, ProxyManager

pm = ProxyManager(rotation_strategy="round_robin")
pm.add_proxy("198.51.100.1", "3128")
pm.add_proxy("198.51.100.2", "3128")
pm.add_proxy("198.51.100.3", "3128")

with ScrawleeClient(proxy_manager=pm) as client:
    for i in range(6):
        r = client.get("https://httpbin.org/ip")
        print(f"Request {i+1}: exit IP = {r.data['origin']}")
# Output alternates through the three proxies: 1, 2, 3, 1, 2, 3
```

#### Automatic quarantine and self-healing

When a request raises a retryable exception while a proxy is active, `ProxyManager.mark_failed()` is called automatically. The proxy is moved to quarantine with a deadline of `quarantine_time` seconds from now. `get_proxy()` calls `_clean_quarantine()` internally on every invocation to re-admit proxies whose cooldown has elapsed.

```python
# Default quarantine is 300 seconds (5 minutes).
# Extend it for stricter IP health requirements:
pm = ProxyManager()
pm.quarantine_time = 900  # 15 minutes

# Reduce it during development / testing:
pm.quarantine_time = 30
```

If every proxy is simultaneously quarantined, `get_proxy()` temporarily re-admits the full pool rather than returning `None` and blocking the request:

```python
# This behaviour is automatic — no code needed on your side.
# Scrawlee logs a warning:
# "All proxies are quarantined; temporarily reusing full proxy pool."
```

#### Adding many proxies from a list

```python
from scrawlee import ProxyManager

proxy_lines = [
    "203.0.113.10:3128:alice:pass1",
    "203.0.113.11:3128:alice:pass2",
    "203.0.113.12:3128",  # no auth
]

pm = ProxyManager(rotation_strategy="random")
for line in proxy_lines:
    parts = line.split(":")
    if len(parts) == 4:
        ip, port, user, pwd = parts
        pm.add_proxy(ip, port, user, pwd)
    else:
        ip, port = parts
        pm.add_proxy(ip, port)
```

#### Combining proxy rotation with async

```python
import asyncio
from scrawlee import AsyncScrawleeClient, ProxyManager

async def run():
    pm = ProxyManager(rotation_strategy="random")
    pm.add_proxy("10.0.0.1", "3128", "u", "p")
    pm.add_proxy("10.0.0.2", "3128", "u", "p")

    async with AsyncScrawleeClient(proxy_manager=pm) as client:
        tasks = [client.get(f"https://httpbin.org/ip") for _ in range(10)]
        results = await asyncio.gather(*tasks)

    exit_ips = [r.data["origin"] for r in results]
    print(set(exit_ips))  # should show multiple IPs

asyncio.run(run())
```

---

### 6.5 Browser automation

`BrowserClient` drives a real Chrome instance through the botasaurus anti-detect driver. It suppresses all standard bot-detection vectors — `navigator.webdriver`, Canvas fingerprinting, WebGL renderer leaks, font enumeration, TLS JA3/JA4 — before the page even loads. `BrowserClient` is a **core part of Scrawlee** and requires no extra install.

#### Basic browser navigation

```python
from scrawlee import BrowserClient

with BrowserClient() as client:
    response = client.get("https://example.com")

    # Identical parsing interface to ScrawleeResponse
    heading = response.html.css_first("h1").text()
    links   = [a.attrs["href"] for a in response.html.css("a[href]")]
    print(heading)
    print(links)
```

#### Bypassing Cloudflare JS challenge and Turnstile

`bypass_cloudflare=True` engages botasaurus's built-in JS + Captcha solver. It handles Turnstile challenges, JS computation challenges, and `cf_clearance` cookie acquisition automatically:

```python
from scrawlee import BrowserClient

with BrowserClient(bypass_cloudflare=True, block_images=True) as client:
    response = client.get("https://cloudflare-protected-site.com")
    print(response.html.css_first("h1").text())

    # lxml XPath works identically
    prices = response.lxml.xpath('//span[contains(@class,"price")]/text()')
    print(prices)
```

#### Google-referrer stealth

By default (`via_google=True`) every `get()` call routes the initial navigation through a Google search referrer. This passes referrer-policy checks on sites that verify `document.referrer` or inspect the `Referer` HTTP header:

```python
# Default: via_google=True — navigates via Google referrer
with BrowserClient() as client:
    r = client.get("https://example.com/article")

# Disable when you need a direct navigation (e.g., internal tools, APIs)
with BrowserClient(via_google=False) as client:
    r = client.get("https://intranet.example.com/dashboard")

# Override per-call
with BrowserClient(via_google=True) as client:
    r = client.get("https://example.com/", via_google=False)
```

#### Low-bandwidth bulk scraping with `fetch()`

`fetch()` uses the browser's **native fetch API** to retrieve subsequent pages without triggering a full navigation. No new page load, no DNS resolution, no TLS handshake — only the HTTP request body is transferred. Benchmarks show up to 97% bandwidth reduction compared to repeated `get()` calls.

`fetch()` inherits the current session's cookies, CSRF tokens, and authenticated state, making it the fastest way to iterate through many pages of a logged-in site:

```python
from scrawlee import BrowserClient

tickers = ["GOOG", "MSFT", "AMZN", "NVDA", "META", "TSLA", "AAPL"]

with BrowserClient(block_images=True) as client:
    # The first get() loads the full page and establishes cookies
    client.get("https://finance.yahoo.com/quote/AAPL/")

    for ticker in tickers:
        # Subsequent calls use browser fetch — only raw HTML transferred
        resp = client.fetch(f"https://finance.yahoo.com/quote/{ticker}/")
        price = resp.html.css_first('[data-testid="qsp-price"]').text()
        change = resp.html.css_first('[data-testid="qsp-price-change"]').text()
        print(f"{ticker:6s}  {price:>10}  {change}")
```

#### Arbitrary interactions with `run()`

`run()` accepts any `(driver: Driver) -> Any` callable. Use it when you need to type text, click buttons, scroll, hover, submit forms, execute JavaScript, interact with iframes, intercept requests at the CDP layer, or chain multi-step flows:

```python
from scrawlee import BrowserClient, BrowserResponse

# --- Example 1: search form submission ---
def search_google(driver):
    driver.type('textarea[name="q"]', "scrawlee python scraping")
    driver.press_key('textarea[name="q"]', "Enter")
    driver.short_random_sleep()           # human-like pause before reading DOM
    return BrowserResponse(driver.page_html, driver.current_url)

with BrowserClient() as client:
    result = client.run(search_google)
    for a in result.html.css("h3"):
        print(a.text())

# --- Example 2: infinite scroll ---
def scroll_to_bottom(driver):
    prev_height = 0
    while True:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        driver.long_random_sleep()
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == prev_height:
            break
        prev_height = new_height
    return BrowserResponse(driver.page_html, driver.current_url)

with BrowserClient() as client:
    client.get("https://example-infinite-scroll.com/feed")
    result = client.run(scroll_to_bottom)
    items = result.html.css(".feed-item")
    print(f"Found {len(items)} items after full scroll")

# --- Example 3: login then scrape dashboard ---
def login(driver):
    driver.type('#username', 'myuser@example.com')
    driver.type('#password', 'mysecretpassword')
    driver.click('button[type="submit"]')
    driver.wait_for_element('.dashboard-header', wait=15)  # wait up to 15s
    return BrowserResponse(driver.page_html, driver.current_url)

with BrowserClient(tiny_profile=True, profile="my_account") as client:
    result = client.run(login)
    username_display = result.html.css_first(".welcome-user").text()
    print(f"Logged in as: {username_display}")
    # Profile is saved — next run skips login entirely
```

#### JavaScript execution

```python
from scrawlee import BrowserClient, BrowserResponse

with BrowserClient() as client:
    client.get("https://example.com")
    driver = client.driver

    # Execute arbitrary JS and read the return value
    scroll_height = driver.execute_script("return document.body.scrollHeight")
    print(f"Page height: {scroll_height}px")

    # Manipulate the DOM
    driver.execute_script(
        "document.querySelectorAll('.cookie-banner').forEach(el => el.remove())"
    )

    # Extract data via JS (useful for values not in the HTML source)
    local_storage = driver.execute_script(
        "return JSON.stringify(Object.entries(localStorage))"
    )
    print(local_storage)

    response = BrowserResponse(driver.page_html, driver.current_url)
    items = response.html.css(".item")
    print(f"{len(items)} items after DOM manipulation")
```

#### Chrome profile persistence

Profiles allow you to persist authenticated state across script runs. On the first run you log in; on all subsequent runs Scrawlee picks up the saved session:

```python
# Full profile (~100 MB per profile)
# Stores cookies, localStorage, IndexedDB, sessionStorage, browser history.
with BrowserClient(profile="amazon_account") as client:
    r = client.get("https://www.amazon.com/gp/css/order-history")
    # If the profile was already logged in, orders load immediately.
    orders = r.html.css(".order-info")
    print(f"{len(orders)} orders found")

# Tiny profile (~1 KB per profile)
# Stores cookies only. Recommended when managing hundreds of accounts.
with BrowserClient(profile="account_042", tiny_profile=True) as client:
    r = client.get("https://example.com/dashboard")
    print(r.html.css_first(".user-greeting").text())
```

#### Blocking images and CSS to reduce bandwidth

```python
# block_images — suppresses image requests only
with BrowserClient(block_images=True) as client:
    r = client.get("https://example.com")   # 40–60% less bandwidth, same HTML

# block_images_and_css — suppresses images and stylesheets
# Best for pure data extraction where visual rendering is irrelevant
with BrowserClient(block_images_and_css=True) as client:
    r = client.get("https://example.com")   # up to 80% less bandwidth
```

#### Accessing the raw botasaurus Driver

For capabilities not exposed by `get()`, `fetch()`, or `run()` — request interception, CDP commands, network condition simulation, cookie injection, etc. — access the `Driver` object directly after the first navigation:

```python
from scrawlee import BrowserClient, BrowserResponse

with BrowserClient() as client:
    client.get("https://example.com")
    driver = client.driver  # botasaurus Driver instance

    # Scroll
    driver.scroll_down()
    driver.scroll_to_bottom()

    # Interact
    driver.click(".load-more-button")
    driver.hover('.tooltip-trigger')

    # Wait for dynamic content
    driver.wait_for_element('.dynamic-results', wait=10)

    # Read updated DOM
    response = BrowserResponse(driver.page_html, driver.current_url)
    results = response.html.css(".result-card")
    print(f"{len(results)} results loaded")
```

---

### 6.6 Advanced configuration

#### Custom TLS fingerprint

Scrawlee supports four browser identities for TLS impersonation. The default (`"random"`) picks one at random per client instance to prevent fingerprint entropy clustering across many scrapers:

```python
from scrawlee import ScrawleeClient

# Pin a specific fingerprint
for identity in ["chrome110", "chrome120", "edge101", "safari15_5"]:
    with ScrawleeClient(impersonate=identity) as client:
        r = client.get("https://httpbin.org/headers")
        # JA3/JA4 hash will match the named browser
        print(identity, r.data["headers"].get("User-Agent", "")[:40])
```

#### Tuning retry behaviour

The default retry settings are conservative. For mission-critical scrapers against flaky APIs, increase `max_retries` and tune the back-off curve:

```python
from scrawlee import ScrawleeClient
from curl_cffi.requests import RequestsError

# Aggressive retry with wide jitter to avoid thundering-herd against shared proxies
with ScrawleeClient(
    max_retries=7,
    retry_status_codes={403, 429, 500, 502, 503, 504, 520, 524},
    retry_exceptions=(RequestsError, ConnectionError, TimeoutError, OSError),
    retry_backoff_base=1.5,   # 1.5s → 3s → 6s → 12s → 24s → 48s → 96s
    retry_jitter_max=5.0,     # add up to 5s of uniform random noise
    timeout=60,
) as client:
    response = client.get("https://unstable-api.example.com/expensive-endpoint")
    print(response.data)
```

#### Understanding the back-off formula

On retry number `n` (1-indexed), Scrawlee sleeps for:

$$
t_n = (\text{retry\_backoff\_base} \times 2^{n-1}) + \text{uniform}(0,\ \text{retry\_jitter\_max})
$$

With defaults (`base=1.0`, `jitter_max=1.0`) and 3 retries:

| Retry | Base sleep | + jitter (max) | Total (max) |
|-------|-----------|----------------|-------------|
| 1     | 1.0 s     | 1.0 s          | 2.0 s       |
| 2     | 2.0 s     | 1.0 s          | 3.0 s       |
| 3     | 4.0 s     | 1.0 s          | 5.0 s       |

#### Merging custom headers with the organic header set

Scrawlee generates a full `Sec-Fetch-*` + `Accept-Language` header set on every client instantiation. You can add to (not replace) these headers per-request:

```python
with ScrawleeClient() as client:
    # The Sec-Fetch-* headers are already present; the dict is merged
    r = client.get(
        "https://api.example.com/private",
        headers={
            "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9...",
            "X-API-Version": "2",
            "Accept": "application/json",
        },
    )
    print(r.data)
```

#### Disabling TLS certificate verification (internal / dev servers)

```python
with ScrawleeClient() as client:
    r = client.get("https://dev-server.internal", verify=False)
    print(r.status_code)
```

#### Setting a global timeout vs per-request timeout

```python
# Global timeout for all requests made by this client
with ScrawleeClient(timeout=10) as client:
    try:
        r = client.get("https://slow-server.example.com")
    except Exception as e:
        print("Timed out:", e)

# Per-request override (overrides the global)
with ScrawleeClient(timeout=30) as client:
    r = client.get("https://normally-slow.example.com", timeout=5)
```

#### Headless Chrome with proxy

```python
from scrawlee import BrowserClient

with BrowserClient(
    proxy="http://user:pass@proxy-host:8080",
    headless=True,               # run without a visible window
    block_images_and_css=True,   # maximum bandwidth saving
    via_google=False,
) as client:
    response = client.get("https://example.com")
    print(response.html.css_first("h1").text())
```

> **Warning:** Many anti-bot systems detect headless Chrome through browser feature probes (missing `chrome.app`, `chrome.runtime`, window dimensions, media device enumeration). For Cloudflare or Datadome-protected sites, prefer `headless=False` (the default) and use `bypass_cloudflare=True` instead.

#### Per-call override of `via_google` and `bypass_cloudflare`

Instance-level defaults can be overridden for individual calls without creating a new client:

```python
with BrowserClient(via_google=True, bypass_cloudflare=False) as client:
    # Most pages: via Google referrer, no Cloudflare bypass
    r_normal = client.get("https://example.com/news")

    # Hardened page: skip Google referrer, enable Cloudflare bypass
    r_cf = client.get(
        "https://hardened.example.com/products",
        via_google=False,
        bypass_cloudflare=True,
    )

    print(r_normal.html.css_first("h1").text())
    print(r_cf.html.css_first(".product-title").text())
```

#### Disabling loguru output

```python
from loguru import logger
logger.disable("scrawlee")  # silences all Scrawlee log messages
```

To re-enable for debugging:

```python
logger.enable("scrawlee")
logger.add("scrawlee_debug.log", level="DEBUG", rotation="10 MB")
```

---

### 6.7 Cookie persistence

Save the cookie jar from one session and reload it in a future run to maintain authenticated state without re-logging in. Cookies are serialised as a plain JSON file.

```python
from scrawlee import ScrawleeClient

# --- Run 1: authenticate and save ---
with ScrawleeClient() as client:
    client.post(
        "https://example.com/login",
        data={"username": "me@example.com", "password": "hunter2"},
        allow_redirects=True,
    )
    # Confirm login succeeded
    profile = client.get("https://example.com/api/me")
    print("Logged in as:", profile.data["name"])

    client.save_cookies("session_cookies.json")
    # session_cookies.json now contains all cookies set by the server
```

```python
# --- Run 2: resume session without logging in again ---
with ScrawleeClient() as client:
    client.load_cookies("session_cookies.json")

    response = client.get("https://example.com/dashboard")
    print(response.html.css_first(".welcome-message").text())

    # Refresh the cookie file so expiry is pushed forward
    client.save_cookies("session_cookies.json")
```

#### Async cookie persistence

The same `save_cookies()` / `load_cookies()` interface is available on `AsyncScrawleeClient`:

```python
import asyncio
from scrawlee import AsyncScrawleeClient

async def login_and_scrape():
    async with AsyncScrawleeClient() as client:
        await client.post(
            "https://example.com/login",
            data={"username": "me", "password": "secret"},
        )
        client.save_cookies("async_cookies.json")

async def resume_scrape():
    async with AsyncScrawleeClient() as client:
        client.load_cookies("async_cookies.json")
        r = await client.get("https://example.com/members-only")
        print(r.html.css_first(".members-content").text())

asyncio.run(login_and_scrape())
asyncio.run(resume_scrape())
```

#### Inspecting the saved cookie file

The JSON file is human-readable and editable:

```json
{
    "sessionid": "abc123xyz789",
    "csrftoken": "def456uvw012",
    "_ga": "GA1.2.1234567890.1714000000"
}
```

You can merge cookies from multiple sources, remove expired entries, or inject test cookies by editing this file directly before passing it to `load_cookies()`.

---

## 7. FAQ

**Q: Does Scrawlee guarantee bypassing every anti-bot system?**

No tool can make that guarantee. Bot detection is an arms race. Scrawlee's HTTP client (`ScrawleeClient`) is effective against TLS fingerprinting, IP bans, and rate-limiting. `BrowserClient` with `bypass_cloudflare=True` is effective against Cloudflare JS challenges and Turnstile CAPTCHAs. Highly sophisticated defences (image-based CAPTCHAs requiring human vision, fully dynamic JS obfuscation changed per-request) may require additional measures outside the scope of this library.

**Q: When should I use `ScrawleeClient` vs `BrowserClient`?**

Use `ScrawleeClient` when the target page's content is available in the raw HTTP response (i.e., it does not require JavaScript execution to render). It is 10–100× faster and uses far less memory than running Chrome. Switch to `BrowserClient` when the page renders its content with JavaScript, requires cookie/session state from an interactive flow, or is protected by a Cloudflare JS challenge.

**Q: How do I handle rate limiting effectively?**

Combine several strategies: set `retry_status_codes` to include `429`, tune `retry_backoff_base` to a higher value (e.g., `2.0`), add multiple proxies to `ProxyManager` so failed IPs are automatically cycled out, and consider adding per-domain request delays in your own scraping loop.

**Q: Can I use `BrowserClient.fetch()` from the first request?**

No. `fetch()` re-uses the browser's existing session context (cookies, authentication headers, TLS state). It requires at least one prior `get()` call to the target domain to establish that context. Calling `fetch()` first will likely receive a redirect or login page.

**Q: How does proxy quarantine work?**

When a request fails and the failure is attributed to a proxy, `ProxyManager.mark_failed()` records the proxy's URL with a timestamp offset by `quarantine_time` seconds (default: 300). On each subsequent `get_proxy()` call, `_clean_quarantine()` removes entries whose timeout has elapsed, automatically re-admitting the proxy to the pool.

**Q: Is `AsyncScrawleeClient` truly non-blocking?**

Yes. It uses `curl_cffi.requests.AsyncSession`, which is backed by `libcurl`'s multi-handle async interface. All I/O is non-blocking. The exponential back-off also uses `await asyncio.sleep()` rather than `time.sleep()`, so the event loop is never blocked during retries.

**Q: Can I change the proxy quarantine duration?**

Yes, directly on the `ProxyManager` instance:

```python
pm = ProxyManager()
pm.quarantine_time = 60  # 60 seconds
```

**Q: How do I suppress the loguru output?**

```python
from loguru import logger
logger.disable("scrawlee")
```

**Q: Can I scrape HTTPS sites with self-signed certificates?**

Pass `verify=False` through `**kwargs`:

```python
client.get("https://internal-dev-server.local", verify=False)
```

**Q: How do I scale to thousands of concurrent requests?**

Use `AsyncScrawleeClient` with `asyncio.gather()` or `asyncio.Semaphore` for rate control:

```python
import asyncio
from scrawlee import AsyncScrawleeClient, ProxyManager

async def scrape(urls, concurrency=50):
    pm = ProxyManager(rotation_strategy="random")
    # ... add proxies ...
    sem = asyncio.Semaphore(concurrency)

    async with AsyncScrawleeClient(proxy_manager=pm) as client:
        async def bounded_get(url):
            async with sem:
                return await client.get(url)

        return await asyncio.gather(*[bounded_get(u) for u in urls])
```

---

## 8. Contributing

Contributions are welcome. Please follow these steps:

1. **Fork** the repository and create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Install dev dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```
3. **Write tests** in the `tests/` directory covering your change.
4. **Run the test suite:**
   ```bash
   pytest
   ```
5. **Open a Pull Request** against `main` with a clear description of the problem your change solves.

### Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/).
- Keep docstrings consistent with the existing style in `client.py` and `browser.py`.
- Do not introduce new mandatory dependencies without a compelling reason.

### Reporting issues

Open an issue on GitHub. Include the Python version, OS, relevant code snippet, and the full traceback.

---

## 9. License

Scrawlee is released under the [MIT License](LICENSE).

```
MIT License

Copyright (c) 2026 Saim Sajid

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
