import random
import time
from typing import List, Dict, Optional
from urllib.parse import quote_plus

class ProxyManager:
    """A robust proxy controller that maintains pool health and rotation logic.
    It manages multiple credential sets and automatically identifies
    unreliable proxies to keep your scraping sessions uninterrupted."""
    
    def __init__(self, rotation_strategy: str = "round_robin"):
        """
        rotation_strategy: "round_robin", "random", or "sticky"
        """
        self.proxies: List[Dict[str, str]] = []
        self.rotation_strategy = rotation_strategy
        self._current_index = 0
        self._quarantined: Dict[str, float] = {}  
        self.quarantine_time = 300  
    
    def add_proxy(self, ip: str, port: str, username: str = "", password: str = ""):
        """Registers a new proxy server into the rotation pool.
        It handles credential formatting and URL encoding so you can
        provide raw connection details without worrying about internal syntax."""
        if username and password:
            user = quote_plus(username)
            pwd = quote_plus(password)
            proxy_url = f"http://{user}:{pwd}@{ip}:{port}"
        else:
            proxy_url = f"http://{ip}:{port}"
            
        proxy_dict = {"http": proxy_url, "https": proxy_url}
        if proxy_dict not in self.proxies:
            self.proxies.append(proxy_dict)
            
    def get_proxy(self) -> Optional[Dict[str, str]]:
        """Retrieves an optimal proxy based on the configured rotation pattern.
        This method filters out recently failed proxies and maintains
        sticky sessions or random selection according to your script's needs."""
        if not self.proxies:
            return None
            
        self._clean_quarantine()
        available_proxies = [p for p in self.proxies if p["http"] not in self._quarantined]
        
        if not available_proxies:
            available_proxies = self.proxies
            
        if self.rotation_strategy == "random":
            return random.choice(available_proxies)
        elif self.rotation_strategy == "round_robin":
            proxy = available_proxies[self._current_index % len(available_proxies)]
            self._current_index += 1
            return proxy
        elif self.rotation_strategy == "sticky":
            return available_proxies[0]
            
        return None

    def mark_failed(self, proxy_dict: Dict[str, str]):
        """Blacklists a failing proxy by moving it into temporary quarantine.
        This prevents subsequent requests from attempting to use broken
        nodes until a cooldown period has successfully passed."""
        url = proxy_dict.get("http")
        if url:
            self._quarantined[url] = time.time() + self.quarantine_time

    def _clean_quarantine(self):
        """Scans and rehabilitates proxies whose quarantine timers have expired.
        Ensures the rotation pool remains as large as possible by
        re-integrating nodes that may have recovered from transient network issues."""
        now = time.time()
        expired = [url for url, time_limit in self._quarantined.items() if now > time_limit]
        for url in expired:
            del self._quarantined[url]
