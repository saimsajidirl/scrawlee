from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

from ._log import log


class Profiles:
    _path = Path("profiles.json")

    @classmethod
    def _read(cls) -> Dict[str, Any]:
        if not cls._path.exists():
            return {}
        return json.loads(cls._path.read_text(encoding="utf-8"))

    @classmethod
    def _write(cls, data: Dict[str, Any]) -> None:
        cls._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def set_profile(cls, profile_name: str, data: Dict[str, Any]) -> None:
        payload = cls._read()
        payload[profile_name] = data
        cls._write(payload)
        log.debug("Profiles.set_profile {}", profile_name)

    @classmethod
    def get_profile(cls, profile_name: str) -> Optional[Dict[str, Any]]:
        return cls._read().get(profile_name)

    @classmethod
    def get_profiles(cls, random_order: bool = False) -> List[Dict[str, Any]]:
        values = list(cls._read().values())
        if random_order:
            random.shuffle(values)
        return values

    @classmethod
    def delete_profile(cls, profile_name: str) -> None:
        payload = cls._read()
        payload.pop(profile_name, None)
        cls._write(payload)
        log.debug("Profiles.delete_profile {}", profile_name)
