import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.app.browser import BrowserSession


def test_dead_browser_relaunches_with_same_profile(tmp_path, monkeypatch):
    async def check():
        session = BrowserSession(tmp_path / 'profile')
        session.profile.mkdir()
        (session.profile / 'session-marker').write_text('keep')
        old = MagicMock()
        old.pages = []
        old.close = AsyncMock(side_effect=RuntimeError('already closed'))
        old_driver = MagicMock()
        old_driver.stop = AsyncMock(side_effect=RuntimeError('transport closed'))
        session.context, session.driver = old, old_driver
        page = MagicMock()
        page.is_closed.return_value = False
        page.goto = AsyncMock()
        fresh = MagicMock()
        fresh.pages = [page]
        fresh.close = AsyncMock()
        driver = MagicMock()
        driver.chromium.launch_persistent_context = AsyncMock(return_value=fresh)
        driver.stop = AsyncMock()
        factory = MagicMock()
        factory.start = AsyncMock(return_value=driver)
        import playwright.async_api
        monkeypatch.setattr(playwright.async_api, 'async_playwright', lambda: factory)
        await session.open()
        assert session.context is fresh
        assert session.is_open
        assert (session.profile / 'session-marker').read_text() == 'keep'
        session._on_closed(old)
        assert session.is_open  # stale callback cannot invalidate the replacement
        session._on_closed(fresh)
        assert not session.is_open
        assert not session.logged_in
        await session.close()
    asyncio.run(check())
