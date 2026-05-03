import random
import time
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from loguru import logger

VALID_ROTATION_STRATEGIES = {"round_robin", "random", "sticky"}

class ProxyManager:
    
    def __init__(self, rotation_strategy: str = "round_robin"):
        """
        Initializes the proxy manager object.
        Sets up the rotation strategy and proxy list.
        Prepares the quarantine tracking system.
        """
        if rotation_strategy not in VALID_ROTATION_STRATEGIES:
            raise ValueError(
                f"Invalid rotation_strategy '{rotation_strategy}'. "
                f"Use one of: {', '.join(sorted(VALID_ROTATION_STRATEGIES))}."
            )
        self.proxies: List[Dict[str, str]] = []
        self.rotation_strategy = rotation_strategy
        self._current_index = 0
        self._quarantined: Dict[str, float] = {}
        self.quarantine_time = 300
    
    def add_proxy(self, ip: str, port: str, username: str = "", password: str = ""):
        """
        Adds a new proxy to the pool.
        Formats proxy with authentication details.
        Skips the proxy if it already exists.
        """
        if username and password:
            user = quote_plus(username)
            pwd = quote_plus(password)
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{ip}:{port}"
            
        proxy_dict = {"http": proxy_url, "https": proxy_url}
        if proxy_dict not in self.proxies:
            self.proxies.append(proxy_dict)
            logger.debug("Added proxy to pool: {}", proxy_dict["http"])
        else:
            logger.debug("Skipped duplicate proxy: {}", proxy_dict["http"])
            
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Retrieves a proxy based on strategy.
        Filters out quarantined proxies automatically.
        Falls back to all proxies if none available.
        """
        if not self.proxies:
            logger.debug("Proxy pool is empty, using direct connection.")
            return None
            
        self._clean_quarantine()
        available_proxies = [p for p in self.proxies if p["http"] not in self._quarantined]
        
        if not available_proxies:
            logger.warning("All proxies are quarantined; temporarily reusing full proxy pool.")
            available_proxies = self.proxies
            
        if self.rotation_strategy == "random":
            selected = random.choice(available_proxies)
            logger.debug("Selected proxy using random strategy: {}", selected["http"])
            return selected
        elif self.rotation_strategy == "round_robin":
            proxy = available_proxies[self._current_index % len(available_proxies)]
            self._current_index += 1
            logger.debug("Selected proxy using round_robin strategy: {}", proxy["http"])
            return proxy
        elif self.rotation_strategy == "sticky":
            selected = available_proxies[0]
            logger.debug("Selected proxy using sticky strategy: {}", selected["http"])
            return selected

        return None

    def mark_failed(self, proxy_dict: Dict[str, str]):
        """
        Marks a specific proxy as failed.
        Places proxy into temporary quarantine.
        Prevents selection for the cooldown period.
        """
        url = proxy_dict.get("http")
        if url:
            self._quarantined[url] = time.time() + self.quarantine_time
            logger.warning("Proxy quarantined for {}s: {}", self.quarantine_time, url)

    def _clean_quarantine(self):
        """
        Scans for expired proxy quarantines.
        Rehabilitates recovered proxy connections.
        Makes proxies available for selection again.
        """
        now = time.time()
        expired = [url for url, time_limit in self._quarantined.items() if now > time_limit]
        for url in expired:
            del self._quarantined[url]
            logger.debug("Proxy removed from quarantine: {}", url)