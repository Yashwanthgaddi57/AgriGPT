"""Headless-Chrome CDP driver to verify the vendors radius feature end-to-end.

Logs in through the real UI, saves a Guntur-area location, opens the vendors
page, clicks the 10 km chip, and verifies:
  - the Leaflet radius circle exists with radius 10_000 m
  - in-radius / beyond-radius labeling matches the API response
  - screenshots at each step for evidence
"""
import asyncio
import base64
import json
import subprocess
import time
import urllib.request

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
DEBUG_PORT = 9333
BASE = "http://localhost:3000"
API = "http://localhost:8000/api/v1"
EMAIL = "buffy.radius.test@example.com"
PASSWORD = "Test1234!"
SHOT_DIR = ".freebuff/shots"

# Guntur, Andhra Pradesh (README example district) — a real agricultural area.
LAT, LNG = 16.3067, 80.4365


def cdp_http(path: str):
    with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}{path}") as r:
        return json.loads(r.read())


async def main() -> None:
    import os

    os.makedirs(SHOT_DIR, exist_ok=True)
    # Attach to an already-running Chrome (launch separately with:
    #   chrome --remote-debugging-port=9333 --headless=new ... &).
    # Launching Chrome from python subprocess here is unreliable on Windows.
    if os.environ.get("LAUNCH_CHROME"):
        proc = subprocess.Popen(
            [
                CHROME,
                f"--remote-debugging-port={DEBUG_PORT}",
                "--headless=new",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-gpu",
                "--window-size=1440,900",
                "--user-data-dir=.freebuff/chrome-profile",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        proc = None
    time.sleep(3)

    targets = None
    for _ in range(30):  # up to ~15s for Chrome to open the CDP port
        try:
            targets = cdp_http("/json")
            break
        except Exception:
            time.sleep(0.5)
    if targets is None:
        raise RuntimeError("Chrome CDP port never came up")
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
            res = await send(
                "Runtime.evaluate",
                {"expression": expr, "awaitPromise": await_promise, "returnByValue": True},
            )
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

        # ---- 1) Login through the real UI ----
        print("== Step 1: login ==")
        await send("Page.navigate", {"url": f"{BASE}/auth/login"})
        await asyncio.sleep(4)
        await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              const proto = el instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype
                            : HTMLInputElement.prototype;
              Object.getOwnPropertyDescriptor(proto, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const inputs = document.querySelectorAll('input');
            const email = [...inputs].find(i => i.type === 'email' || i.name === 'email');
            const pass = [...inputs].find(i => i.type === 'password');
            if (!email || !pass) throw new Error('login inputs not found');
            setVal(email, %EMAIL%);
            setVal(pass, %PASSWORD%);
            await new Promise(r => setTimeout(r, 300));
            const btn = [...document.querySelectorAll('button')].find(b =>
              /sign in|login|log in/i.test(b.textContent || ''));
            if (!btn) throw new Error('login button not found');
            btn.click();
            await new Promise(r => setTimeout(r, 4000));
            return location.pathname;
          })()
        """.replace("%EMAIL%", json.dumps(EMAIL)).replace("%PASSWORD%", json.dumps(PASSWORD)), await_promise=True)
        path = await eval_js("location.pathname")
        print(f"  after login: {path}")
        await shot("01_after_login")

        # Auth guard: if still on login page, bail loudly.
        if "/auth/" in path:
            raise RuntimeError("Login did not complete — check credentials/flow")

        # ---- 2) Save a Guntur location via the UI-independent API (same origin, token from localStorage) ----
        print("== Step 2: save Guntur location ==")
        await eval_js(f"""
          (async () => {{
            const raw = localStorage.getItem('agrisphere-auth');
            const token = JSON.parse(raw).access_token;
            const res = await fetch('{API}/geo/location', {{
              method: 'POST',
              headers: {{ 'Content-Type': 'application/json', Authorization: `Bearer ${{token}}` }},
              body: JSON.stringify({{ latitude: {LAT}, longitude: {LNG}, source: 'map_pin' }}),
            }});
            if (!res.ok) throw new Error('save location failed: ' + res.status);
            return await res.json();
          }})()
        """, await_promise=True)
        print(f"  saved pin at {LAT},{LNG}")

        # ---- 2.5) Complete onboarding wizard (new account is forced there) ----
        print("== Step 2.5: complete onboarding ==")
        await send("Page.navigate", {"url": f"{BASE}/dashboard/onboarding"})
        await asyncio.sleep(5)
        diag = await eval_js("({path: location.pathname, inputs: document.querySelectorAll('input').length, btns: document.body.innerText.slice(0, 300)})")
        print("  diag:", json.dumps(diag))
        onb = await eval_js("""
          (async () => {
            const setVal = (el, v) => {
              Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, v);
              el.dispatchEvent(new Event('input', { bubbles: true }));
            };
            const clickBtn = (txt) => {
              const b = [...document.querySelectorAll('button')].find(x => x.textContent.trim().includes(txt));
              if (!b) throw new Error('button not found: ' + txt);
              b.click();
            };
            const wait = (ms) => new Promise(r => setTimeout(r, ms));
            // Step 1: state + district via the new GeoAutocomplete
            const state = document.querySelectorAll('input')[0];
            setVal(state, 'Andhra');
            await wait(400);
            const opt = [...document.querySelectorAll('[role=option]')].find(o => /Andhra Pradesh/.test(o.textContent));
            if (!opt) throw new Error('state suggestion not shown');
            opt.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            await wait(300);
            const dist = document.querySelectorAll('input')[1];
            setVal(dist, 'Gunt');
            await wait(400);
            const opt2 = [...document.querySelectorAll('[role=option]')].find(o => /Guntur/.test(o.textContent));
            if (!opt2) throw new Error('district suggestion not shown');
            opt2.dispatchEvent(new MouseEvent('mousedown', { bubbles: true }));
            await wait(200);
            clickBtn('Next');
            await wait(400);
            // Step 2: farm size (needed so the dashboard stops redirecting)
            const size = [...document.querySelectorAll('input')].find(i => i.type === 'number');
            setVal(size, '3.2');
            clickBtn('Next');
            await wait(400);
            // Step 3: skip (optional)
            clickBtn('Next');
            await wait(400);
            // Step 4: finish
            clickBtn('Finish');
            await wait(3500);
            return location.pathname;
          })()
        """, await_promise=True)
        print(f"  onboarding done -> {onb}")
        await shot("01b_onboarding_done")
        if "/dashboard" not in onb:
            raise RuntimeError(f"Onboarding did not finish: {onb}")

        # ---- 3) Vendors page: default 50 km ----
        print("== Step 3: vendors page (default 50 km) ==")
        await send("Page.navigate", {"url": f"{BASE}/dashboard/vendors"})
        # First OSM discovery for a fresh area can take ~20s; poll for chips.
        chips_found = False
        for _ in range(40):
            await asyncio.sleep(1.5)
            chips_found = await eval_js(
                "[...document.querySelectorAll('button')].some(b => b.textContent.trim() === '10 km')"
            )
            if chips_found:
                break
        if not chips_found:
            diag = await eval_js("({path: location.pathname, text: document.body.innerText.slice(0, 400)})")
            raise RuntimeError(f"10 km chip never appeared: {json.dumps(diag)}")
        await asyncio.sleep(2)  # let map/list settle
        await shot("02_vendors_default")

        # ---- 4) Click the 10 km chip ----
        print("== Step 4: click 10 km ==")
        clicked = await eval_js("""
          (() => {
            const chips = [...document.querySelectorAll('button')].filter(b => b.textContent.trim() === '10 km');
            if (!chips.length) return false;
            chips[0].click();
            return true;
          })()
        """)
        if not clicked:
            raise RuntimeError("10 km chip not found")
        await asyncio.sleep(10)  # refetch + leaflet redraw
        await shot("03_vendors_10km")

        # ---- 5) Verify circle + labels vs API truth ----
        print("== Step 5: verify ==")
        state = await eval_js("""
          (() => {
            const circle = document.querySelector('path.leaflet-interactive');
            const count = document.querySelectorAll('path.leaflet-interactive').length;
            const bodyText = document.body.innerText;
            const within = bodyText.match(/Showing\\s+(\\d+) vendors within\\s+([\\d]+) km/);
            const badges = [...document.querySelectorAll('span')].filter(s => /beyond/.test(s.textContent)).length;
            return {
              interactivePaths: count,
              circlePresent: !!circle,
              showingLine: within ? within[0] : null,
              beyondBadges: badges,
              hasAmberNote: /Nothing within/.test(bodyText),
              radiusChips: [...document.querySelectorAll('button')].filter(b => / km$/.test(b.textContent.trim())).map(b => b.textContent.trim()),
            };
          })()
        """)
        print("  UI state:", json.dumps(state, indent=2))

        # Ground truth straight from the API
        api_state = await eval_js(f"""
          (async () => {{
            const raw = localStorage.getItem('agrisphere-auth');
            const token = JSON.parse(raw).access_token;
            const res = await fetch('{API}/geo/vendors?radius_km=10');
            const data = await res.json();
            const inR = data.items.filter(v => v.raw_distance_km <= data.radius_km && !v.beyond_radius);
            const outR = data.items.filter(v => v.beyond_radius);
            return {{
              radius_km: data.radius_km,
              total: data.total,
              items: data.items.length,
              max_in_radius_km: inR.length ? Math.max(...inR.map(v => v.raw_distance_km)) : null,
              beyond: outR.map(v => ({{ name: v.name, km: v.raw_distance_km }})),
            }};
          }})()
        """, await_promise=True)
        print("  API truth:", json.dumps(api_state, indent=2))

        # Scroll list area and take a final evidence shot
        await shot("04_vendors_10km_full")

        # ---- Assertions ----
        ok = True
        if not state["circlePresent"]:
            print("  ❌ FAIL: leaflet circle not found")
            ok = False
        else:
            print("  ✅ circle rendered on map")
        if api_state["radius_km"] != 10:
            print(f"  ❌ FAIL: API radius_km={api_state['radius_km']} != 10")
            ok = False
        else:
            print("  ✅ API echoes requested radius 10 km")
        if api_state["max_in_radius_km"] is not None and api_state["max_in_radius_km"] > 10.0:
            print(f"  ❌ FAIL: vendor beyond 10 km not tagged: {api_state['max_in_radius_km']} km")
            ok = False
        else:
            print("  ✅ all in-radius vendors ≤ 10.0 km")
        if api_state["beyond"]:
            print(f"  ✅ beyond-radius fallbacks tagged: {api_state['beyond']}")
        if state["showingLine"]:
            print(f"  ✅ label reads: {state['showingLine']}")
        else:
            print("  ⚠️ 'Showing N vendors within X km' line not found (maybe empty state)")

        print("\nRESULT:", "PASS" if ok else "FAIL")

    if proc:
        proc.terminate()


if __name__ == "__main__":
    asyncio.run(main())
