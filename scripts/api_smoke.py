"""Authenticated backend API smoke test using the E2E account's real session."""
import json
import sys
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api/v1"
EMAIL = sys.argv[1] if len(sys.argv) > 1 else None
PASSWORD = sys.argv[2] if len(sys.argv) > 2 else None

if not EMAIL:
    sys.exit("usage: python api_smoke.py <email> <password>")


def req(method, path, body=None, token=None, form=False):
    data = None
    headers = {"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    if body is not None:
        data = (urllib.parse.urlencode(body) if form else json.dumps(body)).encode()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:300]}


import urllib.parse  # noqa: E402

results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {str(detail)[:140]}")


# --- login ---
st, login = req("POST", "/auth/login", {"email": EMAIL, "password": PASSWORD})
token = login.get("access_token") if isinstance(login, dict) else None
record("POST /auth/login", st == 200 and bool(token), f"({st})")
if not token:
    sys.exit("cannot continue without token")
H = token

# --- core reads ---
st, me = req("GET", "/profile", token=H)
record("GET /profile", st == 200, f"({st})")
st, farms = req("GET", "/farms", token=H)
record("GET /farms", st == 200, f"({st} n={len(farms) if isinstance(farms, list) else '?'})")

# create a farm if none (so geo-dependent endpoints have data)
if isinstance(farms, list) and not farms:
    st, farm = req("POST", "/farms", token=H, body={
        "name": "Smoke Farm", "area_acres": 2.5,
        "state": "Maharashtra", "district": "Nashik",
    })
    record("POST /farms", st in (200, 201), f"({st})")
else:
    record("POST /farms", True, "(skipped, farm exists)")

st, dash = req("GET", "/dashboard", token=H)
record("GET /dashboard", st == 200, f"({st})")
st, subs = req("GET", "/subscription/plans", token=H)
record("GET /subscription/plans", st == 200 and bool(subs), f"({st})")
st, mysub = req("GET", "/subscription", token=H)
record("GET /subscription", st == 200, f"({st})")
st, weather = req("GET", "/weather", token=H)
record("GET /weather", st == 200, f"({st})")
st, tick = req("GET", "/market/ticker", token=H)
record("GET /market/ticker", st == 200, f"({st})")
st, mandis = req("GET", "/geo/mandis?state=Maharashtra", token=H)
record("GET /geo/mandis", st == 200, f"({st})")
st, vendors = req("GET", "/geo/vendors?latitude=19.99&longitude=73.79", token=H)
record("GET /geo/vendors", st == 200, f"({st})")
st, search = req("GET", "/geo/search?q=nash", token=H)
record("GET /geo/search", st == 200, f"({st})")
st, notif = req("GET", "/notifications", token=H)
record("GET /notifications", st == 200, f"({st})")
st, today = req("GET", "/farm/today", token=H)
record("GET /farm/today", st == 200, f"({st})")

# --- writes ---
st, exp = req("POST", "/farm/expenses", token=H, body={
    "category": "seed", "amount_inr": 1200,
    "description": "smoke test", "spent_on": "2026-09-27"})
record("POST /farm/expenses", st in (200, 201), f"({st})")
st, harv = req("POST", "/farm/harvests", token=H, body={
    "crop": "wheat", "quantity_quintals": 10.5})
record("POST /farm/harvests", st in (200, 201), f"({st})")

# --- AI-ish endpoints (may need keys; accept 200 or documented 4xx/5xx-with-detail) ---
st, rec = req("POST", "/crops/recommend", token=H, body={
    "location": "Nashik, Maharashtra", "farm_size_acres": 2.5,
    "budget_inr": 50000, "season": "kharif"})
record("POST /crops/recommend", st == 200, f"({st} {str(rec)[:100]})")
st, pred = req("POST", "/profit/predict", token=H, body={
    "crop": "wheat", "farm_size_acres": 2.5, "season": "rabi",
    "seed_cost": 3000, "labor_cost": 8000, "fertilizer_cost": 4000,
    "irrigation_cost": 2000, "transportation_cost": 1500, "other_cost": 500})
record("POST /profit/predict", st == 200, f"({st} {str(pred)[:100]})")
st, chat = req("POST", "/chat/messages", token=H, body={
    "content": "Hello, what should I sow in Nashik kharif?"})
record("POST /chat/messages", st == 200, f"({st} {str(chat)[:100]})")
st, cmp = req("GET", "/market/compare?crop=wheat", token=H)
record("GET /market/compare", st == 200, f"({st})")

# --- subscription checkout (known to be stubbed / payments soon) ---
st, co = req("POST", "/subscription/checkout", token=H, body={"plan": "pro"})
record("POST /subscription/checkout", st in (200, 201, 400, 501, 503),
       f"({st} {str(co)[:90]})")

print("\n================ API SUMMARY ================")
fails = [r for r in results if not r[1]]
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nTotal: {len(results)}  Pass: {len(results) - len(fails)}  Fail: {len(fails)}")
