from typing import Optional
from loguru import logger

_LOCALE_BY_COUNTRY = {
    "US": "en-US", "GB": "en-GB", "CA": "en-CA", "AU": "en-AU",
    "DE": "de-DE", "FR": "fr-FR", "ES": "es-ES", "IT": "it-IT",
    "NL": "nl-NL", "BR": "pt-BR", "PT": "pt-PT", "JP": "ja-JP",
    "IN": "en-IN", "MX": "es-MX", "RU": "ru-RU", "PK": "en-PK",
}


def _locale_from_country(country_code: Optional[str]) -> str:
    if not country_code:
        return "en-US"
    return _LOCALE_BY_COUNTRY.get(country_code.upper(), "en-US")


def resolve_geo(proxy: Optional[str] = None, timeout: float = 5.0) -> Optional[dict]:
    """
    Resolves timezone/locale/coordinates for a proxy's exit IP.
    Queries ipwho.is through the given proxy (or directly if none).
    Returns None on any failure so callers can proceed without geo-matching.
    """
    try:
        from curl_cffi import requests
    except ImportError:
        return None

    kwargs: dict = {"timeout": timeout}
    if proxy:
        kwargs["proxies"] = {"http": proxy, "https": proxy}

    try:
        response = requests.get("https://ipwho.is/", **kwargs)
        data = response.json()
    except Exception as exc:
        logger.debug("GeoIP lookup failed, continuing without geo-match: {}", exc)
        return None

    if not data.get("success", True):
        return None

    timezone_id = (data.get("timezone") or {}).get("id")
    if not timezone_id:
        return None

    return {
        "ip": data.get("ip"),
        "timezone_id": timezone_id,
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "locale": _locale_from_country(data.get("country_code")),
        "country_code": data.get("country_code"),
    }
