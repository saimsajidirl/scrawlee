# Scraply

An ultimate stealth scraping library built on top of `curl_cffi` with advanced proxy rotation, auto-parsing for JSON/HTML, and built-in rate-limiting retries.

## Features

- **Ultimate Stealth**: Rotates through real-world TLS/JA3 fingerprints (Chrome, Edge, Safari).
- **Auto-Parsing Response**: The `.auto` property automatically returns a parsed Python dictionary or a `BeautifulSoup` object depending on whether the response is JSON or HTML.
- **Smart Retries**: Built-in exponential backoff for common HTTP error codes (429, 50x).
- **Advanced Proxy Management**: Supports Random, Round-Robin, and Sticky session rotation with off-band automated health checks.

## Installation

```bash
pip install .
```

## Usage

Check out the `demo.py` script for a quick start!
