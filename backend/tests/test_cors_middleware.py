def test_rate_limited_response_includes_cors_headers(client, monkeypatch):
    from app.core import middleware

    monkeypatch.setattr(middleware, "_allow", lambda _client_ip: False)
    response = client.post(
        "/api/v1/auth/resend-verification",
        headers={"Origin": "http://localhost:3000"},
        json={"email": "farmer@example.com"},
    )

    assert response.status_code == 429
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_preflight_bypasses_rate_limiter(client, monkeypatch):
    from app.core import middleware

    def unexpected_rate_check(_client_ip):
        raise AssertionError("CORS preflight should not consume rate-limit budget")

    monkeypatch.setattr(middleware, "_allow", unexpected_rate_check)
    response = client.options(
        "/api/v1/auth/resend-verification",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
