"""Typography benchmark: AgriGPT vs apple.com, Stripe, Linear, GitHub.

Measures computed font-size / weight / line-height / letter-spacing for
generic elements (body, h1-h3, p, nav a, button) on each site so the app's
type scale can be compared against real-world production sites.
"""
import asyncio
import json
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9351
SITES = [
    ("AgriGPT (landing)", "http://localhost:3000"),
    ("AgriGPT (dash)", "http://localhost:3000/dashboard"),
    ("apple.com/iphone", "https://www.apple.com/iphone/"),
    ("stripe.com", "https://stripe.com"),
    ("linear.app", "https://linear.app"),
    ("github.com", "https://github.com"),
]

PROBE = """
  (() => {
    const pick = (sel) => {
      const el = document.querySelector(sel);
      if (!el) return null;
      const cs = getComputedStyle(el);
      return `${cs.fontSize}|${cs.fontWeight}|${cs.lineHeight}|${cs.letterSpacing}`;
    };
    return {
      body: pick('body'),
      h1: pick('h1'),
      h2: pick('h2'),
      h3: pick('h3'),
      p: pick('main p, article p, p'),
      nav: pick('header a, nav a'),
      btn: pick('main button, a.button, button'),
    };
  })()
"""


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


def fmt(v, width=26):
    if not v:
        return "—".rjust(width)
    size, weight, lh, ls = (v.split("|") + ["", "", "", ""])[:4]
    return f"{size:>7} w{weight:<4} lh{lh[:11]:>11} ls{ls[:8]:>8}".rjust(width)


async def main():
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900",
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-typ-bench"],
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

        results = {}
        for label, url in SITES:
            try:
                await send("Page.navigate", {"url": url})
                await asyncio.sleep(7)
                res = await send("Runtime.evaluate",
                                 {"expression": PROBE, "awaitPromise": False, "returnByValue": True})
                results[label] = res.get("result", {}).get("value") or {}
            except Exception as e:
                results[label] = {"error": str(e)[:60]}

        print(f"{'site':<20}{'body':>34}{'h1':>34}{'h2':>34}")
        for label, r in results.items():
            print(f"{label:<20}{fmt(r.get('body')):>34}{fmt(r.get('h1')):>34}{fmt(r.get('h2')):>34}")
        print()
        print(f"{'site':<20}{'h3':>34}{'p':>34}{'nav':>34}")
        for label, r in results.items():
            print(f"{label:<20}{fmt(r.get('h3')):>34}{fmt(r.get('p')):>34}{fmt(r.get('nav')):>34}")
        print()
        print(f"{'site':<20}{'button':>34}")
        for label, r in results.items():
            print(f"{label:<20}{fmt(r.get('btn')):>34}")


asyncio.run(main())
