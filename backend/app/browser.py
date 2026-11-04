"""Single-owner local browser lifecycle; no background threads share Playwright objects."""
import asyncio
from pathlib import Path
from typing import Any


class BrowserSession:
    def __init__(self, profile: Path):
        self.profile = profile
        self.context: Any = None
        self.driver: Any = None
        self.lock = asyncio.Lock()
        self.monitor: asyncio.Task | None = None
        self.logged_in = False
        self.message = "浏览器未启动"
        self._disconnected = False
        self._last_login_seen = 0.0
        self._login_grace_seconds = 15.0
        self.navigation_times: list[float] = []
        self.navigation_paths: list[str] = []
        self.challenge = False

    @property
    def is_open(self):
        if self.context is None or self._disconnected:
            return False
        try:
            return any(not page.is_closed() for page in self.context.pages)
        except Exception:
            return False

    def _on_closed(self, context):
        # An event from an old context must never invalidate a newly opened one.
        if self.context is context:
            self._disconnected = True
            self.logged_in = False
            self.message = "浏览器窗口已关闭，请重新打开"

    async def open(self):
        async with self.lock:
            if self.context is not None:
                if self.is_open:
                    try:
                        page = next(p for p in self.context.pages if not p.is_closed())
                        # An explicit user click on "打开浏览器登录" is also a
                        # recovery action after a previous, already-resolved loop.
                        # Do not carry a stale diagnostic into the next collection.
                        if self.challenge and (page.url or '').startswith(('https://www.zhipin.com/', 'https://zhipin.com/')):
                            self.challenge = False
                            self.navigation_times.clear()
                            self.navigation_paths.clear()
                        if (page.url or "") in {"", "about:blank"}:
                            await page.goto("https://www.zhipin.com", wait_until="domcontentloaded", timeout=30000)
                        await page.bring_to_front()
                    except Exception:
                        self._disconnected = True
                    else:
                        if self.monitor is None or self.monitor.done():
                            self.monitor = asyncio.create_task(self._monitor())
                        return
                await self._close()
            from patchright.async_api import async_playwright
            try:
                self.profile.mkdir(parents=True, exist_ok=True)
                self.profile.chmod(0o700)
                self.driver = await async_playwright().start()
                self.context = await self.driver.chromium.launch_persistent_context(
                    str(self.profile), channel="chrome", headless=False, no_viewport=True
                )
                self._disconnected = False
                self._last_login_seen = 0.0
                context = self.context
                context.on("close", lambda *_: self._on_closed(context))
                if context.browser:
                    context.browser.on("disconnected", lambda *_: self._on_closed(context))
                self.context.set_default_timeout(10000)
                self.context.set_default_navigation_timeout(35000)
                page = self.context.pages[0] if self.context.pages else await self.context.new_page()
                page.on("framenavigated", lambda frame: self._record_navigation(frame.url) if frame == page.main_frame else None)
                await page.goto("https://www.zhipin.com", wait_until="domcontentloaded", timeout=30000)
                self.message = "浏览器已打开，请登录"
                self.monitor = asyncio.create_task(self._monitor())
            except BaseException:
                await self._close()
                raise

    def _record_navigation(self, url: str) -> None:
        import time
        from urllib.parse import urlsplit
        now = time.monotonic()
        path = urlsplit(url).path
        self.navigation_times = [t for t in self.navigation_times if now - t < 12]
        self.navigation_times.append(now)
        self.navigation_paths.append(path)
        self.navigation_paths = self.navigation_paths[-12:]
        # A normal homepage/search navigation can legitimately happen several
        # times. Escalate only when the current path is an actual security/blank
        # destination; never let ordinary navigation alone disable collection.
        security_path = ('security' in path or path == '/web/passport/zp/security.html' or path == '/web/geek/jobs')
        if security_path and (len(self.navigation_times) >= 6 or self.navigation_paths.count(path) >= 4):
            self.challenge = True
            self.logged_in = False
            self.message = "检测到页面反复刷新或安全验证，已暂停自动操作，请在浏览器中完成检查"

    async def _monitor(self):
        """Poll without owning the page or navigating it; one selector failure must not kill polling."""
        selectors = (
            ".nav-figure img",
            "#header a[href*='/web/geek/resume']", "#header a[href*='/web/geek/chat']",
            "header a[href*='/web/geek/resume']", "header a[href*='/web/geek/chat']",
        )
        while self.context:
            if not self.is_open:
                self.logged_in = False
                self.message = "浏览器窗口已关闭，请重新打开"
                return
            try:
                pages = list(self.context.pages)
                if not pages:
                    self.logged_in = False
                    self.message = "浏览器窗口已关闭，请重新打开"
                    await asyncio.sleep(3)
                    continue
                logged_in = False
                for page in pages:
                    from urllib.parse import urlsplit
                    host = urlsplit(page.url or '').hostname or ''
                    if host != 'zhipin.com' and not host.endswith('.zhipin.com'):
                        continue
                    # Do not reload or goto here: monitoring must never cause the user's tab to refresh.
                    for selector in selectors:
                        try:
                            candidate = page.locator(selector).first
                            if await candidate.count() and await candidate.is_visible():
                                logged_in = True
                                break
                        except Exception:
                            continue
                    if not logged_in:
                        # Current Boss markup may render the account area as plain text.
                        try:
                            logged_in = (await page.get_by_text("消息", exact=True).first.is_visible()
                                         and await page.get_by_text("简历", exact=True).first.is_visible())
                        except Exception:
                            pass
                    if logged_in:
                        break
                import time
                if logged_in:
                    self._last_login_seen = time.monotonic()
                self.logged_in = logged_in or (
                    self.logged_in and time.monotonic() - self._last_login_seen < self._login_grace_seconds
                )
                # A resolved verification/login page must clear an old loop
                # diagnostic; otherwise the UI stays blocked forever.
                if self.logged_in and any('/web/passport/zp/security' not in (p.url or '') and 'security' not in (p.url or '') for p in pages):
                    self.challenge = False
                    self.navigation_times.clear()
                    self.navigation_paths.clear()
                self.message = "Boss 已登录" if self.logged_in else "浏览器已打开，请登录"
            except asyncio.CancelledError:
                raise
            except Exception:
                # Browser may briefly mutate its page list during navigation.
                import time
                if time.monotonic() - self._last_login_seen >= self._login_grace_seconds:
                    self.logged_in = False
            await asyncio.sleep(3)

    async def _close(self):
        if self.monitor:
            self.monitor.cancel()
            await asyncio.gather(self.monitor, return_exceptions=True)
            self.monitor = None
        context, driver = self.context, self.driver
        self.context = None
        self.driver = None
        self.logged_in = False
        self._last_login_seen = 0.0
        self.challenge = False
        self.navigation_times.clear()
        self.navigation_paths.clear()
        self._disconnected = True
        # Closing an already-terminated Chromium must not prevent reopening.
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if driver:
            try:
                await driver.stop()
            except Exception:
                pass

    async def close(self):
        async with self.lock:
            await self._close()
            self.message = "浏览器已停止"

    async def logout(self):
        async with self.lock:
            # Close first so Chromium flushes state before it is removed.
            await self._close()
            import shutil
            if self.profile.exists():
                shutil.rmtree(self.profile)
            self.message = "本地登录态已清除"
