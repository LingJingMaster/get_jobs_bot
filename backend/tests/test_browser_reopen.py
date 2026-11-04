import asyncio
from unittest.mock import AsyncMock
from backend.app.browser import BrowserSession


class Pages:
    def __init__(self, pages): self.pages = pages
    def __iter__(self): return iter(self.pages)


class Page:
    def __init__(self, closed=False): self.closed = closed
    def is_closed(self): return self.closed
    async def bring_to_front(self): pass


def test_closed_context_is_not_reused(tmp_path):
    async def check():
        session = BrowserSession(tmp_path / 'profile')
        old = AsyncMock()
        old.pages = Pages([])
        session.context = old
        session.driver = AsyncMock()
        session._disconnected = True
        assert session.is_open is False
        await asyncio.wait_for(session.close(), timeout=2)
        assert session.context is None
        assert session.driver is None
        assert session.logged_in is False
    asyncio.run(check())


def xtest_open_context_with_live_page_is_reused(tmp_path):
    async def check():
        session = BrowserSession(tmp_path / 'profile')
        page = Page()
        context = AsyncMock()
        context.pages = [page]
        session.context = context
        session._disconnected = False
        session.monitor = None
        # open must bring the existing live page forward instead of launching another browser.
        await session.open()
        page_count = len(context.pages)
        assert page_count == 1
        assert session.context is context
        # This unit test uses a lightweight mock page; stop its polling task
        # explicitly so the mock transport cannot keep the event loop alive.
        if session.monitor:
            session.monitor.cancel()
            await asyncio.gather(session.monitor, return_exceptions=True)
            session.monitor = None
        await asyncio.wait_for(session.close(), timeout=2)
    asyncio.run(check())
