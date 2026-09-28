"""Headless-Chrome CDP: screenshot the landing page + dashboard and probe the
Luro glow treatment (computed box-shadows, fonts, colors) for fine-tuning.

Outputs:
  .freebuff/shots/theme_landing_view.png   (viewport)
  .freebuff/shots/theme_landing_full.png   (full page)
  .freebuff/shots/theme_dashboard.png      (dashboard, if login works)
Style-probe results + pixel analysis are printed to stdout.
"""
import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9341
BASE = "http://localhost:3000"
EMAIL = "e2e_auditor@test.com"
PASSWORD = "TestPass123!"
SHOT_DIR = ".freebuff/shots"


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900",
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-theme-profile"],
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

        async def eval_js(expr, await_promise=False):
            res = await send("Runtime.evaluate",
                             {"expression": expr, "awaitPromise": await_promise,
                              "returnByValue": True})
            if res.get("exceptionDetails"):
                raise RuntimeError(f"JS error: {res['exceptionDetails']}")
            return res.get("result", {}).get("value")

        async def shot(name, full=False):
            res = await send("Page.captureScreenshot",
                             {"format": "png", "captureBeyondViewport": full})
            with open(f"{SHOT_DIR}/{name}.png", "wb") as f:
                f.write(base64.b64decode(res["data"]))
            print(f"  [shot] {SHOT_DIR}/{name}.png")

        await send("Page.enable")
        await send("Runtime.enable")

        # ---------- 1) Landing page ----------
        print("== landing page ==")
        await send("Page.navigate", {"url": BASE})
        await asyncio.sleep(6)
        await shot("theme_landing_view")
        await shot("theme_landing_full", full=True)

        probe = await eval_js("""
          (() => {
            const cs = el => getComputedStyle(el);
            const body = document.body;
            const card = document.querySelector('.rounded-3xl.bg-card');
            const btnPrimary = [...document.querySelectorAll('a,button')]
              .find(b => /get started/i.test(b.textContent || ''));
            const h1 = document.querySelector('h1');
            const badge = document.querySelector('.rounded-full.border');
            const fmtShadow = el => el ? cs(el).boxShadow : null;
            return {
              bodyBg: cs(body).backgroundColor,
              bodyColor: cs(body).color,
              bodyFont: cs(body).fontFamily.slice(0, 60),
              h1Font: h1 ? cs(h1).fontFamily.slice(0, 60) : null,
              h1Weight: h1 ? cs(h1).fontWeight : null,
              h1Size: h1 ? cs(h1).fontSize : null,
              h1Tracking: h1 ? cs(h1).letterSpacing : null,
              cardFound: !!card,
              cardBg: card ? cs(card).backgroundColor : null,
              cardRadius: card ? cs(card).borderRadius : null,
              cardShadow: fmtShadow(card),
              btnBg: btnPrimary ? cs(btnPrimary).backgroundColor : null,
              btnRadius: btnPrimary ? cs(btnPrimary).borderRadius : null,
              btnWeight: btnPrimary ? cs(btnPrimary).fontWeight : null,
              btnShadow: fmtShadow(btnPrimary),
              glowCards: document.querySelectorAll('[class*="shadow-glow"],[class*="glow-"]').length,
            };
          })()
        """)
        print("LANDING PROBE:", json.dumps(probe, indent=2))

        # ---------- 2) Dashboard (login first) ----------
        print("== dashboard ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/login"})
        await asyncio.sleep(4)
        try:
            await eval_js("""
              (async () => {
                const setVal = (el, v) => {
                  const proto = el instanceof HTMLTextAreaElement
                    ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
                  Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                };
                const inputs = document.querySelectorAll('input');
                const email = [...inputs].find(i => i.type === 'email' || i.name === 'email');
                const pass = [...inputs].find(i => i.type === 'password');
                if (!email || !pass) throw new Error('login inputs not found');
                setVal(email, '%EMAIL%');
                setVal(pass, '%PASSWORD%');
                await new Promise(r => setTimeout(r, 300));
                const btn = [...document.querySelectorAll('button')]
                  .find(b => /sign in|login/i.test(b.textContent || ''));
                if (!btn) throw new Error('login button not found');
                btn.click();
                await new Promise(r => setTimeout(r, 4000));
                return location.pathname;
              })()
            """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
                await_promise=True)
        except Exception as e:
            print("  login attempt failed (will probe dashboard shell anyway):", e)

        await send("Page.navigate", {"url": f"{BASE}/dashboard"})
        await asyncio.sleep(7)
        path = await eval_js("location.pathname")
        print("  dashboard path:", path)
        await shot("theme_dashboard")

        dash_probe = await eval_js("""
          (() => {
            const cs = el => getComputedStyle(el);
            const cards = [...document.querySelectorAll('.rounded-3xl.bg-card')].slice(0, 5);
            const h1 = document.querySelector('h1');
            const aside = document.querySelector('aside');
            return {
              path: location.pathname,
              h1: h1 ? { font: cs(h1).fontFamily.slice(0, 50), weight: cs(h1).fontWeight,
                         tracking: cs(h1).letterSpacing } : null,
              cardCount: cards.length,
              cards: cards.map(c => ({
                bg: cs(c).backgroundColor,
                radius: cs(c).borderRadius,
                shadow: cs(c).boxShadow.slice(0, 90),
              })),
              asideVisible: aside ? cs(aside).display !== 'none' : false,
              bodyText: document.body.innerText.slice(0, 200),
            };
          })()
        """)
        print("DASHBOARD PROBE:", json.dumps(dash_probe, indent=2))

        # ---------- 3) Pixel analysis of the glow on the landing hero card ----------
        res = await send("Page.captureScreenshot", {"format": "png"})
        with open(f"{SHOT_DIR}/probe_raw.png", "wb") as f:
            f.write(base64.b64decode(res["data"]))

    # Analyze glow falloff around cards with PIL (run in the venv)
    analyze_glow()


def analyze_glow():
    """Sample pixels around a card edge to quantify the glow halo spread."""
    import sys
    try:
        from PIL import Image
    except ImportError:
        print("(PIL not available for pixel analysis)")
        return
    path = os.path.join(SHOT_DIR, "theme_landing_view.png")
    if not os.path.exists(path):
        return
    img = Image.open(path).convert("RGB")
    w, h = img.size
    # Scan a horizontal strip mid-page and measure green-channel lift vs the void.
    void = (5, 19, 9)
    best = 0
    rows_with_glow = 0
    for y in range(0, h, 6):
        row_glow = 0
        for x in range(0, w, 6):
            r, g, b = img.getpixel((x, y))
            if g > void[1] + 18 and g > r:  # green lift above the void
                row_glow += 1
        if row_glow > 3:
            rows_with_glow += 1
        best = max(best, row_glow)
    print(f"GLOW PIXEL SCAN: {rows_with_glow} rows show green halo lift; peak row samples={best} (of {w//6})")


if __name__ == "__main__":
    asyncio.run(main())
