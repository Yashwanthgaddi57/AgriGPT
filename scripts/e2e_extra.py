"""Extra E2E UI checks: subscription page data, duplicate-register error, forgot-password, copilot chat."""
import asyncio
import base64
import json
import os
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9355
BASE = "http://localhost:3000"
EMAIL = "e2e.5y0xey@agrigptdev.com"
PASSWORD = "E2eTest@2026"
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
         f"--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-e2e-extra"],
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

        async def goto(url, wait_s=4):
            await send("Page.navigate", {"url": url})
            await asyncio.sleep(wait_s)

        await send("Page.enable")
        await send("Runtime.enable")

        results = []

        def record(name, ok, detail=""):
            results.append((name, ok, detail))
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} {str(detail)[:160]}")

        # ---- 0. Login via UI ----
        print("== 0. Login ==")
        await goto(BASE + "/auth/login", 4)
        await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            for (const i of document.querySelectorAll('input')) {
              if (i.type === 'email') setVal(i, %E%);
              else if (i.type === 'password') setVal(i, %P%);
            }
            await wait(300);
            [...document.querySelectorAll('button')]
              .find(b => /log ?in|sign ?in/i.test(b.textContent || '')).click();
            await wait(8000);
          })()
        """.replace("%E%", json.dumps(EMAIL)).replace("%P%", json.dumps(PASSWORD)),
            await_promise=True)
        url = await eval_js("location.href")
        record("login", "/dashboard" in url, url)

        # ---- 1. Subscription page with data ----
        print("== 1. Subscription page ==")
        await goto(BASE + "/dashboard/subscription", 6)
        await asyncio.sleep(4)
        sub_txt = await eval_js("(document.body.innerText || '')")
        has_plans = ("Kisan Free" in sub_txt) or ("Pro Farmer" in sub_txt) or ("Free" in sub_txt and "Pro" in sub_txt)
        print("  text len:", len(sub_txt), "| first 300:", json.dumps(sub_txt[:300]))
        await shot("e2e_extra_subscription")
        record("subscription page shows plans", has_plans and len(sub_txt) > 300, f"len={len(sub_txt)}")

        # ---- 2. Copilot chat via UI ----
        print("== 2. Copilot chat ==")
        await goto(BASE + "/dashboard/copilot", 5)
        chat_result = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
              Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const ta = document.querySelector('textarea') ||
                       document.querySelector('input[placeholder*="sk" i], input[placeholder*="ask" i], input[type=text]');
            if (!ta) return { sent: false, reason: 'no input found' };
            setVal(ta, 'What crop suits Nashik in kharif?');
            await wait(400);
            const btn = [...document.querySelectorAll('button')].find(b =>
              /send/i.test(b.textContent || '') || b.querySelector('svg.lucide-send, svg.lucide-arrow-up'));
            if (btn) btn.click(); else {
              ta.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));
            }
            await wait(20000);
            return { sent: true, body: document.body.innerText.slice(0, 1500) };
          })()
        """, await_promise=True)
        body_txt = (chat_result or {}).get("body", "") or ""
        got_reply = len(body_txt) > 400 and ("copilot" in body_txt.lower() or "answer" in body_txt.lower() or len(body_txt) > 700)
        print("  sent:", (chat_result or {}).get("sent"), "| reply len:", len(body_txt))
        await shot("e2e_extra_copilot")
        record("copilot replies in UI", bool((chat_result or {}).get("sent")) and got_reply,
               f"len={len(body_txt)}")

        # ---- 3. Logout, then duplicate register w/ different password ----
        print("== 3. Duplicate register (different password) ==")
        await goto(BASE + "/dashboard/profile", 4)
        await eval_js("""
          (() => { const b = [...document.querySelectorAll('button, a')]
            .find(x => /log ?out|sign ?out/i.test(x.textContent || ''));
            if (b) b.click(); })()
        """)
        await asyncio.sleep(4)
        await goto(BASE + "/auth/register", 4)
        dup = await eval_js("""
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
              else if (i.type === 'password') setVal(i, 'Different@2026');
              else if (n.includes('name') || ph.includes('name')) setVal(i, 'E2E Dup');
              else if (n.includes('phone') || i.type === 'tel') setVal(i, '+91 98765 43210');
              else if (i.type === 'number') setVal(i, '2.5');
            }
            await wait(300);
            [...document.querySelectorAll('button')]
              .find(b => /create account|register|sign up|get started/i.test(b.textContent || '')).click();
            await wait(8000);
            const t = document.body.innerText.toLowerCase();
            return { url: location.href,
                     msg: (t.match(/[^\\n]*(already|exists|registered)[^\\n]*/) || [''])[0].slice(0, 160) };
          })()
        """.replace("%E%", json.dumps(EMAIL)), await_promise=True)
        print("  dup:", json.dumps(dup))
        await shot("e2e_extra_duplicate")
        record("duplicate + diff password shows friendly error",
               dup and bool(dup.get("msg")), dup.get("msg") if dup else "")

        # ---- 4. Forgot password ----
        print("== 4. Forgot password ==")
        await goto(BASE + "/auth/forgot-password", 4)
        forgot = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const i = document.querySelector('input[type=email]') || document.querySelector('input');
            if (!i) return { ok: false, msg: 'no input' };
            setVal(i, %E%);
            await wait(300);
            const btn = [...document.querySelectorAll('button')].find(b =>
              /reset|send|recover|forgot/i.test(b.textContent || ''));
            if (!btn) return { ok: false, msg: 'no button: ' +
              [...document.querySelectorAll('button')].map(b => b.textContent.trim()).join('|').slice(0, 120) };
            btn.click();
            await wait(7000);
            return { ok: true, msg: document.body.innerText.replace(/\\s+/g, ' ').slice(0, 300) };
          })()
        """.replace("%E%", json.dumps(EMAIL)), await_promise=True)
        print("  forgot:", json.dumps(forgot))
        await shot("e2e_extra_forgot")
        record("forgot-password flow responds", forgot and forgot.get("ok") is True,
               (forgot or {}).get("msg", "")[:100])

        print("\n================ EXTRA SUMMARY ================")
        fails = [r for r in results if not r[1]]
        for name, ok, detail in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print(f"\nTotal: {len(results)}  Pass: {len(results) - len(fails)}  Fail: {len(fails)}")


if __name__ == "__main__":
    asyncio.run(main())
