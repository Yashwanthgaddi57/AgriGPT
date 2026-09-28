"""Headless-Chrome CDP check: are all 13 sidebar nav items visible?"""
import asyncio
import json
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9339
BASE = "http://localhost:3000"
EMAIL = "e2e_auditor@test.com"
PASSWORD = "TestPass123!"
SHOT = ".freebuff/nav_check.png"


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main():
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900", "--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-nav-profile"],
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

        async def eval_js(expr):
            res = await send("Runtime.evaluate", {"expression": expr, "awaitPromise": True, "returnByValue": True})
            if res.get("exceptionDetails"):
                raise RuntimeError(f"JS error: {res['exceptionDetails']}")
            return res.get("result", {}).get("value")

        await send("Page.enable")
        await send("Runtime.enable")

        print("== login ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/login"})
        await asyncio.sleep(4)
        await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
              Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const inputs = document.querySelectorAll('input');
            const email = [...inputs].find(i => i.type === 'email' || i.name === 'email');
            const pass = [...inputs].find(i => i.type === 'password');
            if (!email || !pass) throw new Error('login inputs not found: ' + inputs.length);
            setVal(email, '%EMAIL%');
            setVal(pass, '%PASSWORD%');
            return 'filled';
          })()
        """.replace("%EMAIL%", EMAIL).replace("%PASSWORD%", PASSWORD))
        await eval_js("""
          (() => {
            const btn = [...document.querySelectorAll('button')].find(b => /sign in|login/i.test(b.textContent));
            if (!btn) throw new Error('submit button not found');
            btn.click();
            return 'clicked';
          })()
        """)
        await asyncio.sleep(5)
        print("url after login:", await eval_js("location.pathname"))

        print("== dashboard sidebar ==")
        await send("Page.navigate", {"url": f"{BASE}/dashboard"})
        await asyncio.sleep(6)

        info = await eval_js("""
          (() => {
            const aside = document.querySelector('aside');
            const asideLinks = aside ? [...aside.querySelectorAll('nav a')].map(a => a.textContent.trim()) : null;
            const links = [...document.querySelectorAll('a')].map(a => a.getAttribute('href'));
            const dashLinks = [...new Set(links.filter(h => h && h.startsWith('/dashboard')))];
            const bodyErr = document.body.innerText.slice(0, 400);
            return { asideFound: !!aside, asideLinks, dashLinks, asideVisible: aside ? getComputedStyle(aside).transform + ' | ' + getComputedStyle(aside).display : null, bodySample: bodyErr };
          })()
        """)
        print(json.dumps(info, indent=2)[:2500])

        res = await send("Page.captureScreenshot", {"format": "png"})
        import base64, os
        os.makedirs(os.path.dirname(SHOT), exist_ok=True)
        with open(SHOT, "wb") as f:
            f.write(base64.b64decode(res["data"]))
        print("shot:", SHOT)


asyncio.run(main())
