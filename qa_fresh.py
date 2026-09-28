"""Test fresh register + login after deleting all users."""
import httpx

EMAIL = "fresh-after-delete@example.com"
PW = "Password123"

# 1. Register
r = httpx.post("http://localhost:8000/api/v1/auth/register",
    json={"email": EMAIL, "password": PW, "name": "Fresh After Delete"},
    headers={"Content-Type": "application/json"}, timeout=15)
print(f"REGISTER: {r.status_code} {r.json().get('message','')[:80]}")

# 2. Login
r = httpx.post("http://localhost:8000/api/v1/auth/login",
    json={"email": EMAIL, "password": PW},
    headers={"Content-Type": "application/json"}, timeout=15)
print(f"LOGIN: {r.status_code}")
if r.status_code == 200:
    print(f"  access_token: {r.json().get('access_token','')[:30]}...")
else:
    print(f"  error: {r.json()}")

# 3. Try the credentials the user mentioned
r = httpx.post("http://localhost:8000/api/v1/auth/login",
    json={"email": "yashwanthgaddi57@gmail.com", "password": "9848430277"},
    headers={"Content-Type": "application/json"}, timeout=15)
print(f"\nUSER CRED LOGIN: {r.status_code} {r.json().get('error',{}).get('detail','')[:100]}")