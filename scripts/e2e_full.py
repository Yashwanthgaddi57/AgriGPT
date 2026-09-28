"""AgriGPT full E2E UI test: real headless Chrome driving the actual forms.

Flow:
  1. Public pages load (landing, help, terms, privacy, not-found)
  2. Register brand-new account via /auth/register form
  3. Onboarding wizard (fill steps if present)
  4. Tour all dashboard pages, capture console errors
  5. Logout via UI, login again via UI
  6. Error paths: wrong password, duplicate email registration
"""
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
DEBUG_PORT = 9353
BASE = "http://localhost:3000"
SUFFIX = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
EMAIL = f"e2e.{SUFFIX}@agrigptdev.com"
PASSWORD = "E2eTest@2026"
SHOT_DIR = ".freebuff/shots"
console_errors = []
page_errors = []


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main():
    os.makedirs(SHOT_DIR, exist_ok=True)
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900",
         f"--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-e2e-full"],
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

        async def drain_console():
            """Read and clear collected console/page errors after each step."""
            errs = await eval_js("window.__e2eErrs ? window.__e2eErrs.splice(0) : []")
            for e in errs or []:
                console_errors.append(str(e)[:300])
            return errs or []

        async def install_capture():
            await send("Runtime.enable")
            await send("Page.enable")

        # Capture console + page errors via Runtime events
        loop = asyncio.get_event_loop()
        async def listen():
            async for msg in conn:
                m = json.loads(msg)
                if m.get("method") == "Runtime.consoleAPICalled":
                    p = m["params"]
                    if p.get("type") in ("error", "assert"):
                        txt = " ".join(
                            str(a.get("value", a.get("description", "")))
                            for a in p.get("args", []))
                        console_errors.append(txt[:300])
                elif m.get("method") == "Runtime.exceptionThrown":
                    d = m["params"]["exceptionDetails"]
                    page_errors.append(str(d.get("exception", {}).get("description",
                                       d.get("text", "")))[:300])

        listener = loop.create_task(listen())

        results = []

        def record(name, ok, detail=""):
            results.append((name, ok, detail))
            print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")

        # ---------- 1. Public pages ----------
        print("\n== 1. Public pages ==")
        for name, path in [("landing", "/"), ("help", "/help"),
                           ("terms", "/terms"), ("privacy", "/privacy")]:
            await goto(BASE + path, 3)
            status = await eval_js("document.readyState + '|' + document.body.innerText.length")
            record(f"public {path}", "complete" in str(status) and int(str(status).split("|")[1]) > 100,
                   f"({status})")

        # hydration check on landing
        await goto(BASE + "/", 4)
        await asyncio.sleep(2)
        recs = await eval_js("window.__e2eErrs ? window.__e2eErrs.length : -1")
        print(f"  landing console errors: {recs}")

        # 404 page
        await goto(BASE + "/this-page-does-not-exist", 3)
        body = await eval_js("document.body.innerText.slice(0, 120)")
        record("404 page renders", "not found" in body.lower() or "404" in body, json.dumps(body[:60]))

        # ---------- 2. Registration via UI ----------
        print(f"\n== 2. Register new account {EMAIL} ==")
        await goto(BASE + "/auth/register", 5)
        diag = await eval_js("""
          (() => ({ inputs: [...document.querySelectorAll('input')].map(i =>
                    ({ name: i.name, type: i.type, placeholder: i.placeholder })),
                   btns: [...document.querySelectorAll('button')].map(b => b.textContent.trim()).slice(0, 6) }))()
        """)
        print("  form:", json.dumps(diag)[:400])
        reg_path = await eval_js("""
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
              else if (n.includes('name') || ph.includes('name')) setVal(i, 'E2E Tester');
              else if (n.includes('phone') || i.type === 'tel') setVal(i, '+91 98765 43210');
              else if (i.type === 'number') setVal(i, '2.5');
            }
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /create account|register|sign up|get started/i.test(b.textContent || ''));
            if (!btn) throw new Error('submit button not found');
            btn.click();
            await wait(9000);
            return location.href;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  after submit:", reg_path)
        await shot("e2e_after_register")
        record("register via UI", "/dashboard" in reg_path, f"-> {reg_path}")

        # ---------- 3. Onboarding ----------
        print("\n== 3. Onboarding wizard ==")
        await asyncio.sleep(2)
        onb_url = await eval_js("location.href")
        if "/dashboard" in onb_url and "onboarding" in onb_url:
            for step in range(8):
                state = await eval_js("""
                  (() => ({
                    text: document.body.innerText.slice(0, 300),
                    inputs: [...document.querySelectorAll('input')].map(i =>
                      ({ name: i.name, type: i.type, placeholder: i.placeholder })),
                    btns: [...document.querySelectorAll('button')].map(b =>
                      ({ t: b.textContent.trim(), disabled: b.disabled })),
                  }))()
                """)
                btns = state["btns"]
                import re as _re
                def label_match(t):
                    return _re.search(r"continue|next|skip|finish|get started", t or "", _re.I)
                nxt = next((b for b in btns if label_match(b["t"]) and not b["disabled"]), None)
                if not nxt:
                    print(f"  step {step}: no continue/next button; stopping")
                    break
                # fill visible inputs generically
                await eval_js("""
                  (() => {
                    const setVal = (el, v) => {
                      const proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype
                                  : el.tagName === 'SELECT' ? HTMLSelectElement.prototype
                                  : HTMLInputElement.prototype;
                      Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
                      el.dispatchEvent(new Event('input', { bubbles: true }));
                      el.dispatchEvent(new Event('change', { bubbles: true }));
                    };
                    const inputs = [...document.querySelectorAll('input:not([type=hidden]), textarea')];
                    for (const i of inputs) {
                      if (i.type === 'number' || /acre|size|hectare/i.test(i.name + i.placeholder)) setVal(i, '2.5');
                      else if (i.type === 'text' && !i.value) setVal(i, 'E2E Farm');
                    }
                  })()
                """)
                await asyncio.sleep(0.5)
                # click the matched button by text
                clicked = await eval_js(f"""
                  (() => {{
                    const btn = [...document.querySelectorAll('button')]
                      .find(b => /{'continue|next|skip|finish|get started'}/i.test(b.textContent || '') && !b.disabled);
                    if (!btn) return 'not-found';
                    btn.click();
                    return btn.textContent.trim();
                  }})()
                """)
                await asyncio.sleep(3)
                url = await eval_js("location.href")
                print(f"  step {step}: clicked '{clicked}' -> {url}")
                await shot(f"e2e_onboarding_step{step}")
                if "/onboarding" not in url:
                    break
            final_url = await eval_js("location.href")
            record("onboarding completed", "/onboarding" not in final_url, f"-> {final_url}")
        else:
            record("onboarding completed", True, f"(not required; at {onb_url})")

        # ---------- 4. Dashboard tour ----------
        print("\n== 4. Dashboard tour ==")
        pages = [
            ("dashboard home", "/dashboard"),
            ("plan", "/dashboard/plan"),
            ("crops", "/dashboard/crops"),
            ("market", "/dashboard/market"),
            ("weather", "/dashboard/weather"),
            ("profit", "/dashboard/profit"),
            ("disease", "/dashboard/disease"),
            ("farm-log", "/dashboard/farm-log"),
            ("vendors", "/dashboard/vendors"),
            ("copilot", "/dashboard/copilot"),
            ("analytics", "/dashboard/analytics"),
            ("profile", "/dashboard/profile"),
            ("subscription", "/dashboard/subscription"),
        ]
        page_errs = {}
        for name, path in pages:
            before = len(page_errors) + len(console_errors)
            await goto(BASE + path, 6)
            await asyncio.sleep(2)
            after = len(page_errors) + len(console_errors)
            txt_len = await eval_js("(document.body.innerText || '').length")
            has_err = await eval_js("document.body.innerText.toLowerCase().includes('application error')")
            ok = txt_len > 100 and not has_err and after == before
            page_errs[name] = (before, after)
            record(f"page {path}", ok, f"(text={txt_len} newErrs={after - before})")
            await shot(f"e2e_{path.split('/')[-1] or 'home'}")

        # ---------- 5. Logout + login ----------
        print("\n== 5. Logout + Login ==")
        await goto(BASE + "/dashboard/profile", 5)
        logout = await eval_js("""
          (() => {
            const btn = [...document.querySelectorAll('button, a')]
              .find(b => /log ?out|sign ?out/i.test(b.textContent || ''));
            if (!btn) return 'not-found';
            btn.click();
            return 'clicked';
          })()
        """)
        await asyncio.sleep(5)
        url_after_logout = await eval_js("location.href")
        print(f"  logout: {logout} -> {url_after_logout}")
        record("logout via UI", "not-found" not in logout and "/dashboard" not in url_after_logout.split("?")[0].replace("/dashboard/onboarding", "") or "logout" in url_after_logout or "auth" in url_after_logout or "landing" in url_after_logout or "/" == url_after_logout[-1],
               f"-> {url_after_logout}")

        await goto(BASE + "/auth/login", 5)
        login_path = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const inputs = [...document.querySelectorAll('input')];
            for (const i of inputs) {
              if (i.type === 'email') setVal(i, %EMAIL%);
              else if (i.type === 'password') setVal(i, %PASSWORD%);
            }
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /log ?in|sign ?in/i.test(b.textContent || ''));
            if (!btn) throw new Error('login button not found');
            btn.click();
            await wait(9000);
            return location.href;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  after login:", login_path)
        record("login via UI (fresh account)", "/dashboard" in login_path, f"-> {login_path}")

        # ---------- 6. Error paths ----------
        print("\n== 6. Error paths ==")
        # wrong password
        await goto(BASE + "/auth/login", 4)
        wrong = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            const inputs = [...document.querySelectorAll('input')];
            for (const i of inputs) {
              if (i.type === 'email') setVal(i, %EMAIL%);
              else if (i.type === 'password') setVal(i, 'WrongPass@999');
            }
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /log ?in|sign ?in/i.test(b.textContent || ''));
            btn.click();
            await wait(6000);
            const t = document.body.innerText.toLowerCase();
            return { url: location.href, err: t.includes('invalid') || t.includes('incorrect')
                     || t.includes('wrong') || t.includes('failed') || t.includes('credential') };
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)), await_promise=True)
        print("  wrong password:", json.dumps(wrong))
        record("wrong password rejected", wrong and wrong.get("err") is True, str(wrong))

        # duplicate email registration (same EMAIL we just registered)
        await goto(BASE + "/auth/register", 4)
        dup = await eval_js("""
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
              else if (n.includes('name') || ph.includes('name')) setVal(i, 'E2E Dup');
              else if (n.includes('phone') || i.type === 'tel') setVal(i, '+91 98765 43210');
              else if (i.type === 'number') setVal(i, '2.5');
            }
            await wait(300);
            const btn = [...document.querySelectorAll('button')]
              .find(b => /create account|register|sign up|get started/i.test(b.textContent || ''));
            btn.click();
            await wait(8000);
            const t = document.body.innerText.toLowerCase();
            return { url: location.href, flagged: t.includes('already') || t.includes('exists')
                     || t.includes('registered') };
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)),
            await_promise=True)
        print("  duplicate email:", json.dumps(dup))
        record("duplicate email flagged", dup and dup.get("flagged") is True, str(dup))

        # ---------- Summary ----------
        print("\n================ SUMMARY ================")
        fails = [r for r in results if not r[1]]
        for name, ok, detail in results:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
        print(f"\nTotal: {len(results)}  Pass: {len(results) - len(fails)}  Fail: {len(fails)}")
        ce = [c for c in console_errors
              if not any(s in c.lower() for s in ("download the react devtools",))]
        print(f"\nConsole errors ({len(ce)}):")
        for c in ce[:15]:
            print(f"  - {c[:200]}")
        print(f"\nUncaught exceptions ({len(page_errors)}):")
        for p in page_errors[:10]:
            print(f"  - {p[:200]}")
        with open(".freebuff/e2e_results.json", "w") as f:
            json.dump({"results": results, "console_errors": ce[:50],
                       "page_errors": page_errors[:50]}, f, indent=2, default=str)
        print("\nSaved: .freebuff/e2e_results.json")
        listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())
