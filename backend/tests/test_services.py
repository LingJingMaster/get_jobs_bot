import asyncio
from unittest.mock import AsyncMock
import httpx
import pytest
from backend.app.ai import generate, AIError
from backend.app.browser import BrowserSession


def test_ai_protocol_and_error_redaction():
    settings = {"BASE_URL": "https://example.com/v1", "API_KEY": "secret", "MODEL": "test"}
    def handler(request):
        assert str(request.url) == "https://example.com/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好"}}]})
    async def check():
        assert await generate("hello", settings, httpx.MockTransport(handler)) == "你好"
        with pytest.raises(AIError) as error:
            await generate("hello", settings, httpx.MockTransport(lambda req: httpx.Response(401, text="secret")))
        assert "secret" not in str(error.value)
    asyncio.run(check())


def test_browser_close_before_logout(tmp_path):
    async def check():
        profile = tmp_path / "profile"
        profile.mkdir()
        (profile / "Cookies").write_text("private")
        session = BrowserSession(profile)
        context, driver = AsyncMock(), AsyncMock()
        session.context, session.driver = context, driver
        session.logged_in = True
        await session.logout()
        context.close.assert_awaited_once()
        driver.stop.assert_awaited_once()
        assert not profile.exists()
        assert session.context is None
        assert session.logged_in is False
        await session.close()
    asyncio.run(check())
