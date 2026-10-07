import httpx
import pytest

from app.core.config import settings
from app.services import email_service


@pytest.mark.asyncio
async def test_resend_transport_failure_returns_false_and_logs(monkeypatch, caplog):
    original_client = httpx.AsyncClient

    def failing_client(**kwargs):
        async def fail_request(request):
            raise httpx.ConnectError("provider unreachable", request=request)

        return original_client(transport=httpx.MockTransport(fail_request), **kwargs)

    monkeypatch.setattr(email_service.httpx, "AsyncClient", failing_client)
    monkeypatch.setattr(settings, "RESEND_API_KEY", "test-key")

    sent = await email_service._send_resend(
        "farmer@example.com", "Test", "<p>Test</p>"
    )

    assert sent is False
    assert "Resend request failed: ConnectError" in caplog.text
