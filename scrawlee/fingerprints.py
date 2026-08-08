from dataclasses import dataclass
from typing import Optional, Tuple
import random


@dataclass(frozen=True)
class Identity:
    """
    A self-consistent device/browser persona.
    Every field describes the same imaginary machine so no
    single layer (UA, GPU, core count, viewport) contradicts another.
    """
    key: str
    platform: str
    ua: str
    sec_ch_ua: str
    sec_ch_ua_platform: str
    sec_ch_ua_mobile: str
    languages: Tuple[str, ...]
    viewport: Tuple[int, int]
    screen: Tuple[int, int]
    device_scale_factor: float
    is_mobile: bool
    has_touch: bool
    hardware_concurrency: int
    device_memory: int
    webgl_vendor: str
    webgl_renderer: str
    timezone_id: str
    locale: str


# All personas run on the real Chromium engine Playwright drives, so every
# entry here is Chrome/Edge-family. A Safari or Firefox UA layered on top of
# a Chromium renderer would itself be a cross-layer mismatch — exactly the
# kind of inconsistency that makes automation easier to fingerprint, not
# harder. TLS/JA3/JA4 and the installed-font list are not represented here:
# those come from Chromium's compiled network/font stack and cannot be
# rotated at the JS/CDP layer this module operates at.
IDENTITY_POOL = (
    Identity(
        key="chrome120_win_desktop",
        platform="Win32",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        sec_ch_ua='"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        sec_ch_ua_platform='"Windows"',
        sec_ch_ua_mobile="?0",
        languages=("en-US", "en"),
        viewport=(1920, 1080),
        screen=(1920, 1080),
        device_scale_factor=1.0,
        is_mobile=False,
        has_touch=False,
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        timezone_id="America/New_York",
        locale="en-US",
    ),
    Identity(
        key="chrome131_win_desktop",
        platform="Win32",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        sec_ch_ua='"Google Chrome";v="131", "Not_A Brand";v="8", "Chromium";v="131"',
        sec_ch_ua_platform='"Windows"',
        sec_ch_ua_mobile="?0",
        languages=("en-US", "en"),
        viewport=(2560, 1440),
        screen=(2560, 1440),
        device_scale_factor=1.0,
        is_mobile=False,
        has_touch=False,
        hardware_concurrency=16,
        device_memory=16,
        webgl_vendor="Google Inc. (NVIDIA)",
        webgl_renderer="ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        timezone_id="America/Chicago",
        locale="en-US",
    ),
    Identity(
        key="chrome124_win_laptop",
        platform="Win32",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        sec_ch_ua='"Chromium";v="124", "Not(A:Brand";v="99", "Google Chrome";v="124"',
        sec_ch_ua_platform='"Windows"',
        sec_ch_ua_mobile="?0",
        languages=("en-US", "en"),
        viewport=(1366, 768),
        screen=(1366, 768),
        device_scale_factor=1.25,
        is_mobile=False,
        has_touch=False,
        hardware_concurrency=4,
        device_memory=4,
        webgl_vendor="Google Inc. (Intel)",
        webgl_renderer="ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
        timezone_id="America/Los_Angeles",
        locale="en-US",
    ),
    Identity(
        key="edge120_win_desktop",
        platform="Win32",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        sec_ch_ua='"Not_A Brand";v="8", "Chromium";v="120", "Microsoft Edge";v="120"',
        sec_ch_ua_platform='"Windows"',
        sec_ch_ua_mobile="?0",
        languages=("en-US", "en"),
        viewport=(1920, 1080),
        screen=(1920, 1080),
        device_scale_factor=1.0,
        is_mobile=False,
        has_touch=False,
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (AMD)",
        webgl_renderer="ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        timezone_id="America/Denver",
        locale="en-US",
    ),
    Identity(
        key="edge131_win_desktop",
        platform="Win32",
        ua="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
        sec_ch_ua='"Not_A Brand";v="8", "Chromium";v="131", "Microsoft Edge";v="131"',
        sec_ch_ua_platform='"Windows"',
        sec_ch_ua_mobile="?0",
        languages=("en-GB", "en"),
        viewport=(1536, 864),
        screen=(1536, 864),
        device_scale_factor=1.25,
        is_mobile=False,
        has_touch=False,
        hardware_concurrency=6,
        device_memory=8,
        webgl_vendor="Google Inc. (Intel)",
        webgl_renderer="ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        timezone_id="Europe/London",
        locale="en-GB",
    ),
    Identity(
        key="chrome_android_mobile",
        platform="Linux armv8l",
        ua="Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        sec_ch_ua='"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        sec_ch_ua_platform='"Android"',
        sec_ch_ua_mobile="?1",
        languages=("en-US", "en"),
        viewport=(412, 915),
        screen=(412, 915),
        device_scale_factor=2.625,
        is_mobile=True,
        has_touch=True,
        hardware_concurrency=8,
        device_memory=8,
        webgl_vendor="Google Inc. (Qualcomm)",
        webgl_renderer="ANGLE (Qualcomm, Adreno (TM) 740, OpenGL ES 3.2)",
        timezone_id="America/New_York",
        locale="en-US",
    ),
)

_BY_KEY = {identity.key: identity for identity in IDENTITY_POOL}


def pick_identity(name: Optional[str] = None) -> Identity:
    """
    Resolves an explicit identity key or picks one at random.
    Falls back to a random pool entry for unknown or missing names.
    """
    if name and name in _BY_KEY:
        return _BY_KEY[name]
    return random.choice(IDENTITY_POOL)


def identity_names() -> Tuple[str, ...]:
    """
    Lists every identity key available in the pool.
    Useful for pinning a specific persona by name.
    """
    return tuple(_BY_KEY.keys())
