from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable, Iterable, List

from ._log import log


class Cache:
    REFRESH = "__refresh__"
    _root = Path("cache")

    @classmethod
    def _fn_dir(cls, function_name: str) -> Path:
        path = cls._root / function_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def _key(cls, item: Any) -> str:
        payload = json.dumps(item, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def put(cls, function_name: str, item: Any, result: Any) -> None:
        fp = cls._fn_dir(function_name) / f"{cls._key(item)}.json"
        fp.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    @classmethod
    def has(cls, function_name: str, item: Any) -> bool:
        fp = cls._fn_dir(function_name) / f"{cls._key(item)}.json"
        return fp.exists()

    @classmethod
    def get(cls, function_name: str, item: Any) -> Any:
        fp = cls._fn_dir(function_name) / f"{cls._key(item)}.json"
        if not fp.exists():
            return None
        return json.loads(fp.read_text(encoding="utf-8"))

    @classmethod
    def remove(cls, function_name: str, item: Any) -> None:
        fp = cls._fn_dir(function_name) / f"{cls._key(item)}.json"
        if fp.exists():
            fp.unlink()

    @classmethod
    def clear(cls, function_name: str) -> None:
        folder = cls._fn_dir(function_name)
        for file in folder.glob("*.json"):
            file.unlink()

    @classmethod
    def print_cached_items_count(cls, function_name: str) -> None:
        folder = cls._fn_dir(function_name)
        n = len(list(folder.glob("*.json")))
        log.info("{}: {} cached items", function_name, n)

    @classmethod
    def filter_items_in_cache(cls, function_name: str, items: Iterable[Any]) -> List[Any]:
        return [item for item in items if cls.has(function_name, item)]

    @classmethod
    def filter_items_not_in_cache(cls, function_name: str, items: Iterable[Any]) -> List[Any]:
        return [item for item in items if not cls.has(function_name, item)]

    @classmethod
    def delete_items(cls, function_name: str, items: Iterable[Any]) -> int:
        count = 0
        for item in items:
            fp = cls._fn_dir(function_name) / f"{cls._key(item)}.json"
            if fp.exists():
                fp.unlink()
                count += 1
        return count

    @classmethod
    def delete_items_by_filter(
        cls,
        function_name: str,
        should_delete_item: Callable[[Any, Any], bool],
        items: Iterable[Any],
    ) -> int:
        count = 0
        for item in items:
            if not cls.has(function_name, item):
                continue
            result = cls.get(function_name, item)
            if should_delete_item(item, result):
                cls.remove(function_name, item)
                count += 1
        return count
