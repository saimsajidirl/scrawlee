from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup


def soupify(source: Any) -> BeautifulSoup:
    if source is None:
        return BeautifulSoup("", "html.parser")

    if hasattr(source, "text") and isinstance(getattr(source, "text"), str):
        return BeautifulSoup(source.text, "html.parser")

    if hasattr(source, "html"):
        html_obj = getattr(source, "html")
        if html_obj is not None and hasattr(html_obj, "html"):
            return BeautifulSoup(html_obj.html, "html.parser")

    if hasattr(source, "inner_html"):
        return BeautifulSoup(source.inner_html, "html.parser")

    if isinstance(source, str):
        return BeautifulSoup(source, "html.parser")

    return BeautifulSoup(str(source), "html.parser")
