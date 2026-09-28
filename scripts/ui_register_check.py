"""Headless-Chrome CDP: register a brand-new user through the real UI form."""
import asyncio
import base64
import json
import os
import random
import string
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9349
BASE = "http://localhost:3000"
SUFFIX = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
EMAIL = f"ui.check.{SUFFIX}@agrigptdev.com"
PASSWORD = "UiCheck123!"
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
         "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-register-check"],
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

        print(f"== UI register ({EMAIL}) ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/register"})
        await asyncio.sleep(5)
        diag = await eval_js("""
          (() => {
            const inputs = [...document.querySelectorAll('input')].map(i => ({
              name: i.name, type: i.type, placeholder: i.placeholder, required: i.required,
            }));
            const btns = [...document.querySelectorAll('button')].map(b => b.textContent.trim());
            return { inputs, btns: btns.slice(0, 6) };
          })()
        """)
        print("  form:", json.dumps(diag)[:500])
        path = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const inputs = [...document.querySelectorAll('input')];
            for (const i of inputs) {
              const n = (i.name || '').toLowerCase();
              const ph = (i.placeholder || '').toLowerCase();
              if (i.type === 'email') setVal(i, %EMAIL%);
              else if (i.type === 'password') setVal(i, %PASSWORD%);
              else if (n.includes('name') || ph.includes('name')) setVal(i, 'UI Check');
              else if (n.includes('phone') || i.type === 'tel') setVal(i, '+91 98765 43210');
              else if (i.type === 'number') setVal(i, '2.5');
            }
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /create account|register|sign up|get started/i.test(b.textContent || ''));
            if (!btn) throw new Error('submit button not found');
            btn.click();
            await wait(8000);
            return location.pathname;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  after submit:", path)
        await asyncio.sleep(2)
        await shot("ui_register_result")
        try:
            href = await eval_js("location.href")
            body = await eval_js("(document.body && document.body.innerText || '').slice(0, 260)")
            print("  full url:", href)
            print("  page text:", json.dumps(body))
        except Exception as e:
            print("  (page still navigating:", e, ")")
        if "/dashboard" in path or "onboarding" in path:
            print("  RESULT: UI REGISTRATION WORKS ->", path)
        elif "already" in body.lower():
            print("  RESULT: rejected as already-registered")
        else:
            print("  RESULT: blocked or error — see page text above")


if __name__ == "__main__":
    asyncio.run(main())
