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
        await session.close()
        assert session.context is None
        assert session.driver is None
        assert session.logged_in is False
    asyncio.run(check())


def test_open_context_with_live_page_is_reused(tmp_path):
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
        await session.close()
    asyncio.run(check())
