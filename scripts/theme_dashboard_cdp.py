"""Headless-Chrome CDP: register a fresh user, complete onboarding, then
screenshot the real dashboard + probe its Luro glow treatment.
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
DEBUG_PORT = 9343
BASE = "http://localhost:3000"
EMAIL = "buffy.radius.test@example.com"
PASSWORD = "Test1234!"
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
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-theme-profile-2"],
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

        async def shot(name):
            res = await send("Page.captureScreenshot", {"format": "png"})
            with open(f"{SHOT_DIR}/{name}.png", "wb") as f:
                f.write(base64.b64decode(res["data"]))
            print(f"  [shot] {SHOT_DIR}/{name}.png")

        await send("Page.enable")
        await send("Runtime.enable")

        # ---- 1) Login with the existing on-boarded test account ----
        print("== login ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/login"})
        await asyncio.sleep(4)
        path = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              const proto = el instanceof HTMLTextAreaElement
                ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
              Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const inputs = document.querySelectorAll('input');
            const email = [...inputs].find(i => i.type === 'email' || i.name === 'email');
            const pass = [...inputs].find(i => i.type === 'password');
            if (!email || !pass) throw new Error('login inputs not found');
            setVal(email, %EMAIL%);
            setVal(pass, %PASSWORD%);
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /sign in|login/i.test(b.textContent || ''));
            if (!btn) throw new Error('login button not found');
            btn.click();
            await wait(6000);
            return location.pathname;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  after login:", path)
        if "/auth/" in path:
            err = await eval_js("document.body.innerText.slice(0, 300)")
            print("  LOGIN ERROR STATE:", json.dumps(err))

        # ---- 2) If pushed to onboarding, complete it ----
        if "onboarding" in path:
            print("== onboarding ==")
            onb = await eval_js("""
              (async () => {
                const setVal = (el, v) => {
                  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
                  el.dispatchEvent(new Event('input', { bubbles: true }));
                };
                const clickBtn = (txt) => {
                  const b = [...document.querySelectorAll('button')]
                    .find(x => x.textContent.trim().includes(txt));
                  if (!b) throw new Error('button not found: ' + txt);
                  b.click();
                };
                const wait = (ms) => new Promise(r => setTimeout(r, ms));
                // Step 1: state + district via GeoAutocomplete
                const state = document.querySelectorAll('input')[0];
                setVal(state, 'Andhra');
                await wait(600);
                let opt = [...document.querySelectorAll('[role=option]')]
                  .find(o => /Andhra Pradesh/.test(o.textContent));
                if (opt) {
                  opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                  await wait(400);
                  const dist = document.querySelectorAll('input')[1];
                  setVal(dist, 'Gunt');
                  await wait(600);
                  const opt2 = [...document.querySelectorAll('[role=option]')]
                    .find(o => /Guntur/.test(o.textContent));
                  if (opt2) {
                    opt2.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
                    await wait(300);
                  }
                }
                clickBtn('Next');
                await wait(600);
                // Step 2: farm size
                const size = [...document.querySelectorAll('input')].find(i => i.type === 'number');
                if (size) setVal(size, '3.2');
                clickBtn('Next');
                await wait(600);
                // Step 3 (optional)
                clickBtn('Next');
                await wait(600);
                // Step 4: finish
                clickBtn('Finish');
                await wait(4000);
                return location.pathname;
              })()
            """, await_promise=True)
            print("  after onboarding:", onb)

        # ---- 3) Dashboard screenshot + glow probe ----
        print("== dashboard ==")
        await send("Page.navigate", {"url": f"{BASE}/dashboard"})
        await asyncio.sleep(8)
        path = await eval_js("location.pathname")
        print("  path:", path)
        await shot("theme_dashboard_authed")

        probe = await eval_js("""
          (() => {
            const cs = el => getComputedStyle(el);
            const cards = [...document.querySelectorAll('.rounded-3xl.bg-card')].slice(0, 4);
            const h1 = document.querySelector('h1');
            const aside = document.querySelector('aside');
            const ticker = document.querySelector('[class*="overflow-x-auto"]');
            return {
              path: location.pathname,
              h1: h1 ? { font: cs(h1).fontFamily.slice(0, 44), weight: cs(h1).fontWeight,
                         tracking: cs(h1).letterSpacing, size: cs(h1).fontSize } : null,
              cardCount: document.querySelectorAll('.rounded-3xl.bg-card').length,
              cards: cards.map(c => ({ bg: cs(c).backgroundColor, radius: cs(c).borderRadius,
                                       shadow: cs(c).boxShadow.slice(0, 72) })),
              asideVisible: aside ? cs(aside).display !== 'none' : false,
              bodySample: document.body.innerText.slice(0, 180),
            };
          })()
        """)
        print("DASHBOARD PROBE:", json.dumps(probe, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
