from __future__ import annotations

from typing import Any, Dict

from scrawlee.client import ScrawleeClient

from ._log import log


class IPUtils:
    @staticmethod
    def get_ip() -> str:
        log.debug("IPUtils.get_ip")
        with ScrawleeClient() as client:
            res = client.get("https://api.ipify.org?format=json")
            return res.auto.get("ip", "") if isinstance(res.auto, dict) else ""

    @staticmethod
    def get_ip_info() -> Dict[str, Any]:
        log.debug("IPUtils.get_ip_info")
        with ScrawleeClient() as client:
            res = client.get("https://ipinfo.io/json")
            if isinstance(res.auto, dict):
                return res.auto
            return {}
