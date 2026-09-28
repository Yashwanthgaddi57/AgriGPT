"""Headless-Chrome CDP: measure apple.com's real computed typography.

Loads apple.com (and a product-style section) and dumps computed font
size / weight / line-height / letter-spacing for key elements, so the app's
type scale can be matched to Apple's actual web usage.
"""
import asyncio
import json
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9345
URLS = ["https://www.apple.com/", "https://www.apple.com/iphone/"]

PROBE = """
  (() => {
    const pick = (sel, label) => {
      const el = document.querySelector(sel);
      if (!el) return { label, found: false };
      const cs = getComputedStyle(el);
      return {
        label,
        found: true,
        text: (el.textContent || '').trim().slice(0, 40),
        size: cs.fontSize,
        weight: cs.fontWeight,
        lh: cs.lineHeight,
        ls: cs.letterSpacing,
        family: cs.fontFamily.split(',')[0],
      };
    };
    return [
      pick('body', 'body'),
      pick('h1', 'h1'),
      pick('h2', 'h2'),
      pick('h3', 'h3'),
      pick('nav a', 'nav-link'),
      pick('.typography-hero-headline, .typography-headline-hero', 'hero-headline'),
      pick('.typography-headline, .typography-headline-elevated', 'headline'),
      pick('.typography-subhead, .typography-subhead-elevated', 'subhead'),
      pick('.typography-body, .typography-body-elevated', 'body-copy'),
      pick('.typography-eyebrow, .typography-eyebrow-elevated', 'eyebrow'),
      pick('.typography-caption, .typography-caption-elevated', 'caption'),
      pick('a.button, .button', 'button'),
      pick('p', 'first-p'),
      pick('li', 'first-li'),
    ];
  })()
"""


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main():
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900",
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-apple-probe"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3)
    targets = None
    for _ in range(30):
        try:
            targets = cdp_http("/json")
            break
        except Exception:
            time.sleep(0.5)
    page = next(t for t in targets if t["type"] == "page")
    ws = websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024)
    mid = 0

    async with ws as conn:
        async def send(method, params=None):
            nonlocal mid
            mid += 1
            await conn.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            while True:
                msg = json.loads(await conn.recv())
                if msg.get("id") == mid:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    return msg.get("result", {})

        await send("Page.enable")
        await send("Runtime.enable")

        for url in URLS:
            print(f"\n===== {url} =====")
            try:
                await send("Page.navigate", {"url": url})
                await asyncio.sleep(8)
                res = await send("Runtime.evaluate",
                                 {"expression": PROBE, "awaitPromise": False, "returnByValue": True})
                for item in res.get("result", {}).get("value", []):
                    if item.get("found"):
                        print(f"  {item['label']:<16} {item['size']:>8} w{item['weight']:<4} "
                              f"lh {item['lh']:>10} ls {item['ls']:>8}  «{item['text']}»")
                    else:
                        print(f"  {item['label']:<16} (not found)")
            except Exception as e:
                print("  error:", e)


asyncio.run(main())
