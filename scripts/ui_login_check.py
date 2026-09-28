"""Headless-Chrome CDP: log in through the real UI form and verify the dashboard."""
import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9347
BASE = "http://localhost:3000"
EMAIL = "yashwanthgaddi57@gmail.com"
PASSWORD = "AgriGPT@2026"
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
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-login-check"],
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

        print("== UI login ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/login"})
        await asyncio.sleep(5)
        path = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const inputs = document.querySelectorAll('input');
            const email = [...inputs].find(i => i.type === 'email' || i.name === 'email');
            const pass = [...inputs].find(i => i.type === 'password');
            if (!email || !pass) throw new Error('inputs not found');
            setVal(email, %EMAIL%);
            setVal(pass, %PASSWORD%);
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /sign in|login/i.test(b.textContent || ''));
            if (!btn) throw new Error('button not found');
            btn.click();
            await wait(7000);
            return location.pathname;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  landed on:", path)
        await shot("ui_login_result")
        if "/dashboard" in path:
            print("  ✅ LOGIN THROUGH UI WORKS")
        else:
            err = await eval_js("document.body.innerText.slice(0, 300)")
            print("  ❌ still on", path, "— page says:", json.dumps(err))


if __name__ == "__main__":
    asyncio.run(main())
