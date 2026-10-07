"""One-shot live deployment probe for the Render URLs. Read-only."""
import re

import httpx

API = "https://agrigpt-api-6nkh.onrender.com"
WEB = "https://agrigpt-web.onrender.com"


def main() -> None:
    # 1. Backend health + environment
    r = httpx.get(f"{API}/health", timeout=60)
    print(f"1. backend /health        -> {r.status_code} {r.text[:100]}")

    # 2. CORS preflight with the real frontend origin
    r = httpx.request(
        "OPTIONS",
        f"{API}/api/v1/subscription/plans",
        headers={"Origin": WEB, "Access-Control-Request-Method": "GET"},
        timeout=60,
    )
    print(
        f"2. CORS preflight         -> {r.status_code}"
        f" | allow-origin: {r.headers.get('access-control-allow-origin')}"
    )

    # 3. Plans endpoint body
    r = httpx.get(f"{API}/api/v1/subscription/plans", timeout=60)
    try:
        body = r.json()
        print(
            f"3. plans endpoint         -> {r.status_code}"
            f" payments_enabled={body.get('payments_enabled')}"
            f" plans={[p['id'] for p in body.get('plans', [])]}"
        )
    except Exception:
        print(f"3. plans endpoint         -> {r.status_code} {r.text[:100]}")

    # 4. What API URL is baked into the deployed frontend bundle?
    try:
        html = httpx.get(f"{WEB}/", timeout=60).text
        chunks = sorted(set(re.findall(r'/_next/static/chunks/[^"\']+\.js', html)))
        print(f"4. frontend js chunks     -> {len(chunks)} found")
        baked: set[str] = set()
        for chunk in chunks[:20]:
            try:
                js = httpx.get(f"{WEB}{chunk}", timeout=60).text
                baked.update(re.findall(r"https://[a-z0-9-]+\.onrender\.com", js))
                if "localhost:8000" in js:
                    baked.add("http://localhost:8000")
            except Exception:
                continue
        print(f"   onrender URLs in bundle -> {sorted(baked) if baked else 'none in first 20 chunks'}")
    except Exception as e:
        print(f"4. frontend bundle probe FAILED: {type(e).__name__}: {str(e)[:80]}")


if __name__ == "__main__":
    main()
