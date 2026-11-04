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

    async def open(self):
        async with self.lock:
            if self.context is not None:
                if self.context.pages:
                    if self.monitor is None or self.monitor.done():
                        self.monitor = asyncio.create_task(self._monitor())
                    return
                await self._close()
            from playwright.async_api import async_playwright
            try:
                self.profile.mkdir(parents=True, exist_ok=True)
                self.profile.chmod(0o700)
                self.driver = await async_playwright().start()
                self.context = await self.driver.chromium.launch_persistent_context(str(self.profile), headless=False)
                self.context.set_default_timeout(10000)
                page = self.context.pages[0] if self.context.pages else await self.context.new_page()
                await page.goto("https://www.zhipin.com", wait_until="domcontentloaded", timeout=30000)
                self.message = "浏览器已打开，请登录"
                self.monitor = asyncio.create_task(self._monitor())
            except BaseException:
                await self._close()
                raise

    async def _monitor(self):
        """Poll without owning the page or navigating it; one selector failure must not kill polling."""
        selectors = (
            ".nav-figure img",
            "#header a[href*='/web/geek/resume']", "#header a[href*='/web/geek/chat']",
            "header a[href*='/web/geek/resume']", "header a[href*='/web/geek/chat']",
        )
        while self.context:
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
                self.logged_in = logged_in
                self.message = "Boss 已登录" if logged_in else "浏览器已打开，请登录"
            except asyncio.CancelledError:
                raise
            except Exception:
                # Browser may briefly mutate its page list during navigation. Keep the monitor alive.
                self.logged_in = False
            await asyncio.sleep(3)

    async def _close(self):
        if self.monitor:
            self.monitor.cancel()
            await asyncio.gather(self.monitor, return_exceptions=True)
            self.monitor = None
        try:
            if self.context:
                await self.context.close()
        finally:
            self.context = None
            self.logged_in = False
            if self.driver:
                await self.driver.stop()
                self.driver = None

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
