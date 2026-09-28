import httpx

# Without auth header (like curl worked)
r1 = httpx.post("http://localhost:8000/api/v1/auth/register",
    json={"email":"noauth@example.com","password":"Password123","name":"No Auth"},
    headers={"Content-Type":"application/json"}, timeout=10)
print("NO AUTH HEADER:", r1.status_code, r1.json().get("message","")[:80])

# With a bogus auth header (like the browser interceptor sends)
r2 = httpx.post("http://localhost:8000/api/v1/auth/register",
    json={"email":"withauth@example.com","password":"Password123","name":"With Auth"},
    headers={"Authorization":"Bearer stale-token-xyz","Content-Type":"application/json"}, timeout=10)
print("WITH AUTH HEADER:", r2.status_code, r2.text[:200])