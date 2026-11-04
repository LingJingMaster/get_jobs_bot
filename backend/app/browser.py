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
                return
            from playwright.async_api import async_playwright
            try:
                self.profile.mkdir(parents=True, exist_ok=True)
                self.profile.chmod(0o700)
                self.driver = await async_playwright().start()
                self.context = await self.driver.chromium.launch_persistent_context(str(self.profile), headless=False)
                self.context.set_default_timeout(10000)
                page = self.context.pages[0] if self.context.pages else await self.context.new_page()
                await page.goto("https://www.zhipin.com/web/geek/job", wait_until="domcontentloaded", timeout=30000)
                self.message = "浏览器已打开，请登录；自动投递尚未迁移"
                self.monitor = asyncio.create_task(self._monitor())
            except BaseException:
                await self._close()
                raise

    async def _monitor(self):
        try:
            while self.context:
                pages = self.context.pages
                # Visible signed-in navigation, not merely browser existence or a stale cookie.
                self.logged_in = any([await page.locator("li.nav-figure img").first.is_visible() for page in pages if "zhipin.com" in page.url])
                await asyncio.sleep(3)
        except asyncio.CancelledError:
            raise
        except Exception:
            self.logged_in = False
            self.message = "浏览器已关闭或页面状态不可用，请停止后重新打开"

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
