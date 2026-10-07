"""Test register + login after auto-confirm fix."""
import httpx

EMAIL = "auto-confirm@example.com"
PW = "Password123"

# 1. Register
r = httpx.post("http://localhost:8000/api/v1/auth/register",
    json={"email": EMAIL, "password": PW, "name": "Auto Confirm"},
    headers={"Content-Type": "application/json"}, timeout=15)
print(f"REGISTER: {r.status_code} {r.json().get('message','')[:80]}")

# 2. Login immediately after
r = httpx.post("http://localhost:8000/api/v1/auth/login",
    json={"email": EMAIL, "password": PW},
    headers={"Content-Type": "application/json"}, timeout=15)
print(f"LOGIN: {r.status_code}")
if r.status_code == 200:
    print(f"  token: {r.json().get('access_token','')[:30]}...")
else:
    print(f"  error: {r.json().get('error',{}).get('detail','')[:100]}")