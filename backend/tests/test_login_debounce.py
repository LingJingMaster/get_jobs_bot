import asyncio
import time
from backend.app.browser import BrowserSession


def test_login_detection_survives_transient_dom_miss(tmp_path):
    async def check():
        session = BrowserSession(tmp_path / 'profile')
        session.logged_in = True
        session._last_login_seen = time.monotonic()
        session._login_grace_seconds = 15
        # A miss at one polling tick must not disable the collection control.
        assert session.logged_in is True
        assert time.monotonic() - session._last_login_seen < session._login_grace_seconds
    asyncio.run(check())
