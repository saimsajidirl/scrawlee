from __future__ import annotations

import functools
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Iterable, List, Optional, Sequence, Union

from scrawlee.client import ScrawleeClient, ScrawleeResponse

from ._log import log

DataItem = Any


@dataclass
class RuntimeConfig:
    profile: Optional[str] = None
    proxy: Optional[Union[str, dict]] = None
    headless: bool = False
    block_images: bool = False
    block_images_and_css: bool = False


def _resolve(value: Any, data: Any) -> Any:
    if callable(value):
        return value(data)
    return value


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return [None]
    if isinstance(value, list):
        return value
    return [value]


class Driver:
    """Lightweight Botasaurus-like driver backed by ScrawleeClient."""

    def __init__(self, client: ScrawleeClient, config: RuntimeConfig):
        self.client = client
        self.config = config
        self.last_response: Optional[ScrawleeResponse] = None

    def get(self, url: str, **kwargs) -> ScrawleeResponse:
        log.debug("Driver.get {}", url)
        self.last_response = self.client.get(url, **kwargs)
        return self.last_response

    def get_text(self, selector: str) -> Optional[str]:
        if not self.last_response or not self.last_response.html:
            return None
        node = self.last_response.html.css_first(selector)
        return node.text(strip=True) if node else None

    def select(self, selector: str):
        if not self.last_response or not self.last_response.html:
            return None
        return self.last_response.html.css_first(selector)

    def select_all(self, selector: str):
        if not self.last_response or not self.last_response.html:
            return []
        return self.last_response.html.css(selector)

    def prompt(self):
        return None


def _build_proxy_manager(proxy_value: Optional[Union[str, dict, Sequence[str]]]):
    if not proxy_value:
        return None
    from scrawlee.proxies import ProxyManager

    pm = ProxyManager(rotation_strategy="round_robin")
    if isinstance(proxy_value, dict):
        value = proxy_value.get("http") or proxy_value.get("https")
        if value:
            proxy_value = [value]
    if isinstance(proxy_value, str):
        proxy_value = [proxy_value]
    if isinstance(proxy_value, list):
        log.debug("ProxyManager registering {} proxy entr(y/ies)", len(proxy_value))
    for proxy in proxy_value:
        # Accept full proxy URL for compatibility.
        if "://" in proxy:
            raw = proxy.split("://", 1)[1]
            if "@" in raw:
                creds, host = raw.split("@", 1)
                username, password = creds.split(":", 1)
                ip, port = host.split(":", 1)
                pm.add_proxy(ip=ip, port=port, username=username, password=password)
            else:
                ip, port = raw.split(":", 1)
                pm.add_proxy(ip=ip, port=port)
    return pm


def _run_one_browser(fn: Callable, item: DataItem, kwargs: dict, defaults: dict):
    profile = _resolve(kwargs.get("profile", defaults.get("profile")), item)
    proxy = _resolve(kwargs.get("proxy", defaults.get("proxy")), item)
    runtime_config = RuntimeConfig(
        profile=profile,
        proxy=proxy,
        headless=bool(kwargs.get("headless", defaults.get("headless", False))),
        block_images=bool(kwargs.get("block_images", defaults.get("block_images", False))),
        block_images_and_css=bool(
            kwargs.get("block_images_and_css", defaults.get("block_images_and_css", False))
        ),
    )
    pm = _build_proxy_manager(runtime_config.proxy)
    with ScrawleeClient(proxy_manager=pm) as client:
        driver = Driver(client=client, config=runtime_config)
        return fn(driver, item)


def _run_one_request(fn: Callable, item: DataItem, kwargs: dict, defaults: dict):
    proxy = _resolve(kwargs.get("proxy", defaults.get("proxy")), item)
    pm = _build_proxy_manager(proxy)
    with ScrawleeClient(proxy_manager=pm) as client:
        response = fn(client, item)
        return response


def _execute(
    runner: Callable[[Callable, DataItem, dict, dict], Any],
    fn: Callable,
    data: Any,
    call_kwargs: dict,
    defaults: dict,
    parallel: int,
):
    items = _as_list(data)
    log.debug("execute {} item(s) parallel={} fn={}", len(items), parallel, getattr(fn, "__name__", repr(fn)))
    if parallel <= 1 or len(items) <= 1:
        return [runner(fn, item, call_kwargs, defaults) for item in items]

    outputs: List[Any] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=parallel) as ex:
        futures = {ex.submit(runner, fn, item, call_kwargs, defaults): idx for idx, item in enumerate(items)}
        for future in as_completed(futures):
            idx = futures[future]
            outputs[idx] = future.result()
    return outputs


def browser(_fn: Optional[Callable] = None, **decorator_kwargs):
    def deco(fn: Callable):
        @functools.wraps(fn)
        def wrapper(data=None, **call_kwargs):
            parallel = int(call_kwargs.pop("parallel", decorator_kwargs.get("parallel", 1)))
            results = _execute(_run_one_browser, fn, data, call_kwargs, decorator_kwargs, parallel)
            return results[0] if not isinstance(data, list) else results

        return wrapper

    if _fn is not None and callable(_fn):
        return deco(_fn)
    return deco


def request(_fn: Optional[Callable] = None, **decorator_kwargs):
    def deco(fn: Callable):
        @functools.wraps(fn)
        def wrapper(data=None, **call_kwargs):
            parallel = int(call_kwargs.pop("parallel", decorator_kwargs.get("parallel", 1)))
            results = _execute(_run_one_request, fn, data, call_kwargs, decorator_kwargs, parallel)
            return results[0] if not isinstance(data, list) else results

        return wrapper

    if _fn is not None and callable(_fn):
        return deco(_fn)
    return deco


def task(_fn: Optional[Callable] = None, **decorator_kwargs):
    def deco(fn: Callable):
        @functools.wraps(fn)
        def wrapper(data=None, **call_kwargs):
            items = _as_list(data)
            parallel = int(call_kwargs.pop("parallel", decorator_kwargs.get("parallel", 1)))
            log.debug("task {} item(s) parallel={} fn={}", len(items), parallel, getattr(fn, "__name__", repr(fn)))
            if parallel <= 1 or len(items) <= 1:
                results = [fn(item) for item in items]
            else:
                results = [None] * len(items)
                with ThreadPoolExecutor(max_workers=parallel) as ex:
                    futures = {ex.submit(fn, item): idx for idx, item in enumerate(items)}
                    for future in as_completed(futures):
                        idx = futures[future]
                        results[idx] = future.result()
            return results[0] if not isinstance(data, list) else results

        return wrapper

    if _fn is not None and callable(_fn):
        return deco(_fn)
    return deco
