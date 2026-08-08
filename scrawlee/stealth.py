import json
import zlib

from .fingerprints import Identity

# Covers the device/rendering/software layers that are actually reachable
# from JS/CDP: navigator.webdriver, hardware/software properties, the
# WebGL vendor/renderer strings, and canvas/audio noise. Noise is seeded per
# identity (not per call) so a single persona stays internally consistent
# across a session — real hardware doesn't change its canvas hash mid-visit.
#
# Out of scope by construction: TLS/JA3/JA4, HTTP/2 frame ordering, and the
# installed-font list all come from Chromium's compiled network/font stack,
# below anything this script can touch. CDP-based automation tells (e.g. the
# Runtime.enable leak) also aren't fixable from inside the page — that needs
# a patched Chromium build (e.g. the `patchright` project) instead.
_TEMPLATE = r"""
(() => {
  const seed = __SEED__;
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rand = mulberry32(seed);

  Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
  Object.defineProperty(navigator, 'platform', { get: () => __PLATFORM__ });
  Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => __HW_CONCURRENCY__ });
  Object.defineProperty(navigator, 'deviceMemory', { get: () => __DEVICE_MEMORY__ });
  Object.defineProperty(navigator, 'languages', { get: () => __LANGUAGES__ });
  window.chrome = window.chrome || { runtime: {} };

  const fakePlugins = [
    { name: 'PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'Chromium PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'Microsoft Edge PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'WebKit built-in PDF', filename: 'internal-pdf-viewer' },
  ];
  Object.defineProperty(navigator, 'plugins', { get: () => fakePlugins });

  try {
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) => (
      parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters)
    );
  } catch (e) {}

  function patchGetParameter(ctor) {
    if (!ctor) return;
    const original = ctor.prototype.getParameter;
    ctor.prototype.getParameter = function (parameter) {
      if (parameter === 37445) return __WEBGL_VENDOR__;
      if (parameter === 37446) return __WEBGL_RENDERER__;
      return original.call(this, parameter);
    };
  }
  patchGetParameter(window.WebGLRenderingContext);
  patchGetParameter(window.WebGL2RenderingContext);

  function noisifyPixels(data) {
    for (let i = 0; i < data.length; i += 97) {
      data[i] = (data[i] ^ (Math.floor(rand() * 3) - 1)) & 0xff;
    }
  }

  try {
    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = function (...args) {
      const imgData = origGetImageData.apply(this, args);
      noisifyPixels(imgData.data);
      return imgData;
    };

    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function (...args) {
      const ctx = this.getContext('2d');
      if (ctx) {
        try {
          const imgData = ctx.getImageData(0, 0, this.width, this.height);
          noisifyPixels(imgData.data);
          ctx.putImageData(imgData, 0, 0);
        } catch (e) {}
      }
      return origToDataURL.apply(this, args);
    };
  } catch (e) {}

  try {
    const origGetChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function (...args) {
      const data = origGetChannelData.apply(this, args);
      for (let i = 0; i < data.length; i += 100) {
        data[i] = data[i] + (rand() - 0.5) * 1e-7;
      }
      return data;
    };
  } catch (e) {}

  try {
    Object.defineProperty(screen, 'width', { get: () => __SCREEN_W__ });
    Object.defineProperty(screen, 'height', { get: () => __SCREEN_H__ });
    Object.defineProperty(screen, 'availWidth', { get: () => __SCREEN_W__ });
    Object.defineProperty(screen, 'availHeight', { get: () => __SCREEN_H__ });
  } catch (e) {}
})();
"""


def build_stealth_script(identity: Identity) -> str:
    """
    Renders the stealth init script for one identity.
    Seeds canvas/audio noise deterministically from the identity key.
    Returns JS ready for context.add_init_script().
    """
    seed = zlib.crc32(identity.key.encode("utf-8"))
    replacements = {
        "__SEED__": str(seed),
        "__PLATFORM__": json.dumps(identity.platform),
        "__HW_CONCURRENCY__": str(identity.hardware_concurrency),
        "__DEVICE_MEMORY__": str(identity.device_memory),
        "__LANGUAGES__": json.dumps(list(identity.languages)),
        "__WEBGL_VENDOR__": json.dumps(identity.webgl_vendor),
        "__WEBGL_RENDERER__": json.dumps(identity.webgl_renderer),
        "__SCREEN_W__": str(identity.screen[0]),
        "__SCREEN_H__": str(identity.screen[1]),
    }
    script = _TEMPLATE
    for placeholder, value in replacements.items():
        script = script.replace(placeholder, value)
    return script
