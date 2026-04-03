from __future__ import annotations

import gzip
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from scrawlee.client import ScrawleeClient

from ._log import log


def _segment_count(url: str) -> int:
    path = re.sub(r"^https?://[^/]+/?", "", url)
    if not path:
        return 0
    return len([x for x in path.split("/") if x])


class Filters:
    @staticmethod
    def first_segment_equals(values):
        if isinstance(values, str):
            values = [values]
        values = set(values)
        return lambda url: (re.sub(r"^https?://[^/]+/?", "", url).split("/")[:1] or [""])[0] in values

    @staticmethod
    def first_segment_not_equals(values):
        if isinstance(values, str):
            values = [values]
        values = set(values)
        return lambda url: (re.sub(r"^https?://[^/]+/?", "", url).split("/")[:1] or [""])[0] not in values

    @staticmethod
    def has_exactly_1_segment():
        return lambda url: _segment_count(url) == 1


class Extractors:
    @staticmethod
    def extract_link_upto_second_segment():
        def _extract(url: str):
            m = re.match(r"^(https?://[^/]+)(/[^/]+)?(/[^/]+)?", url)
            if not m:
                return url
            return "".join([x for x in m.groups() if x is not None])

        return _extract


@dataclass
class Sitemap:
    url: str
    cache: Optional[str] = None

    def __post_init__(self):
        self._links = self._discover_links(self.url)

    def _fetch_text(self, url: str) -> str:
        log.debug("Sitemap fetch {}", url)
        with ScrawleeClient() as client:
            res = client.get(url)
            if url.endswith(".gz"):
                return gzip.decompress(res.content).decode("utf-8", errors="ignore")
            return res.text

    def _discover_links(self, url: str) -> List[str]:
        text = self._fetch_text(url)
        if "<?xml" in text or "<urlset" in text or "<sitemapindex" in text:
            root = ET.fromstring(text)
            out = []
            for loc in root.findall(".//{*}loc"):
                if loc.text:
                    out.append(loc.text.strip())
            log.info("Sitemap XML {} → {} <loc> entr(y/ies)", url, len(out))
            return out
        robots_url = url.rstrip("/") + "/robots.txt"
        robots = self._fetch_text(robots_url)
        found = [m.strip() for m in re.findall(r"(?im)^sitemap:\s*(.+)$", robots)]
        log.info("Sitemap from robots.txt {} → {} link(s)", robots_url, len(found))
        return found

    def filter(self, *conditions: Callable[[str], bool]) -> "Sitemap":
        links = self._links
        for condition in conditions:
            links = [link for link in links if condition(link)]
        self._links = links
        return self

    def extract(self, extractor: Callable[[str], str]) -> "Sitemap":
        self._links = [extractor(link) for link in self._links]
        return self

    def write_links(self, name: str) -> List[str]:
        from pathlib import Path

        out = Path("output")
        out.mkdir(exist_ok=True)
        fp = out / f"{name}.txt"
        fp.write_text("\n".join(self._links), encoding="utf-8")
        log.info("Sitemap wrote {} link(s) to {}", len(self._links), fp)
        return self._links

    def write_sitemaps(self, name: str) -> List[str]:
        return self.write_links(name)
