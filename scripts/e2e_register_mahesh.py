"""Register mahesh57@gmail.com through the real UI (post-delete verification)."""
import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9361
BASE = "http://localhost:3000"
EMAIL = "mahesh57@gmail.com"
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
         f"--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-mahesh-reg"],
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

        await send("Page.navigate", {"url": BASE + "/auth/register"})
        await asyncio.sleep(5)
        result = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            for (const i of document.querySelectorAll('input')) {
              const n = (i.name || '').toLowerCase();
              const ph = (i.placeholder || '').toLowerCase();
              if (i.type === 'email') setVal(i, %E%);
              else if (i.type === 'password') setVal(i, %P%);
              else if (n === 'name' || ph.includes('name')) setVal(i, 'Mahesh');
              else if (n === 'phone' || i.type === 'tel') setVal(i, '6281781459');
              else if (n.includes('state')) setVal(i, 'Telangana');
              else if (n.includes('district')) setVal(i, 'Nalgonda');
              else if (i.type === 'number') setVal(i, '1');
            }
            await wait(400);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /create account|register|sign up|get started/i.test(b.textContent || ''));
            if (!btn) throw new Error('submit button not found');
            btn.click();
            await wait(10000);
            return { url: location.href,
                     toast: (document.body.innerText.match(/[^\\n]*(failed|success|already)[^\\n]*/i) || [''])[0].slice(0, 160) };
          })()
        """.replace("%E%", json.dumps(EMAIL)).replace("%P%", json.dumps(PASSWORD)),
            await_promise=True)
        print("result:", json.dumps(result))
        await asyncio.sleep(2)
        await shot("mahesh_register_result")
        url = (result or {}).get("url", "")
        if "/dashboard" in url:
            print("SUCCESS: registered + signed in ->", url)
        else:
            print("CHECK TOAST:", (result or {}).get("toast"))


if __name__ == "__main__":
    asyncio.run(main())
