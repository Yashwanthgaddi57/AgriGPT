"""Capture exact console exception on /dashboard/subscription (single dispatch loop)."""
import asyncio
import json
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9359
BASE = "http://localhost:3000"
EMAIL = "e2e.5y0xey@agrigptdev.com"
PASSWORD = "E2eTest@2026"


def cdp_http(path):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main():
    subprocess.Popen(
        [CHROME, f"--remote-debugging-port={DEBUG_PORT}", "--headless=new",
         "--no-first-run", "--no-default-browser-check", "--disable-gpu",
         "--window-size=1440,900",
         f"--user-data-dir=C:/Users/2830433/Desktop/AgriGPT/.freebuff/chrome-sub-debug2"],
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
    pending = {}
    exceptions = []
    console = []

    async with ws as conn:
        async def recv_loop():
            async for raw in conn:
                m = json.loads(raw)
                mid_ = m.get("id")
                if mid_ in pending:
                    fut = pending.pop(mid_)
                    fut.set_result(m)
                elif m.get("method") == "Runtime.exceptionThrown":
                    d = m["params"]["exceptionDetails"]
                    exceptions.append({
                        "text": d.get("text"),
                        "desc": (d.get("exception") or {}).get("description"),
                        "stack": str((d.get("exception") or {}).get("stack"))[:1200],
                    })
                elif m.get("method") == "Runtime.consoleAPICalled":
                    p = m["params"]
                    txt = " ".join(str(a.get("value", a.get("description", "")))
                                   for a in p.get("args", []))
                    console.append(f"[{p.get('type')}] {txt}")

        listener = asyncio.get_event_loop().create_task(recv_loop())

        async def send(method, params=None):
            nonlocal mid
            mid += 1
            fut = asyncio.get_event_loop().create_future()
            pending[mid] = fut
            await conn.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
            res = await fut
            if "error" in res:
                raise RuntimeError(f"{method}: {res['error']}")
            return res.get("result", {})

        async def eval_js(expr, await_promise=False):
            res = await send("Runtime.evaluate",
                             {"expression": expr, "awaitPromise": await_promise,
                              "returnByValue": True})
            return res.get("result", {}).get("value")

        await send("Page.enable")
        await send("Runtime.enable")
        await send("Log.enable")

        await send("Page.navigate", {"url": BASE + "/auth/login"})
        await asyncio.sleep(4)
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

        exceptions.clear()
        console.clear()
        await send("Page.navigate", {"url": BASE + "/dashboard/subscription"})
        await asyncio.sleep(12)

        print("== page text ==")
        print(await eval_js("document.body.innerText.slice(0, 200)"))
        print("\n== exceptions ==")
        for e in exceptions:
            print(json.dumps(e, indent=1)[:2000])
        print("\n== console ==")
        for c in console:
            print(str(c)[:500])
        listener.cancel()


if __name__ == "__main__":
    asyncio.run(main())
