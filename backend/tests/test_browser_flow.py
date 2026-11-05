"""Deterministic browser-port tests. No account, network or messages are used."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock
import pytest
from backend.app import delivery


class Locator:
    def __init__(self, page, selector):
        self.page, self.selector = page, selector
        self.first = self

    async def count(self):
        if self.selector.startswith('.verify-wrap'):
            return 0
        return 1

    async def inner_text(self, **kwargs):
        if self.selector.startswith('.job-name'):
            return 'Python开发'
        if self.selector.startswith('.sider-company'):
            return '测试公司'
        return '立即沟通'

    async def wait_for(self, **kwargs):
        pass

    async def click(self):
        if self.selector.startswith('div.send-message') and self.page.fail:
            raise RuntimeError('send interrupted')
        self.page.clicks.append(self.selector)

    async def fill(self, message):
        self.page.message = message

    def filter(self, **kwargs):
        return self

    def locator(self, selector):
        return Locator(self.page, selector)

    async def evaluate_all(self, script):
        return ['测试公司']

    async def evaluate(self, script):
        return '张某'

    async def is_visible(self):
        return False


class Page:
    def __init__(self, fail):
        self.fail, self.clicks, self.closed = fail, [], False
        self.url = 'https://www.zhipin.com/job_detail/test.html'

    def locator(self, selector, **kwargs):
        return Locator(self, selector)

    def get_by_text(self, text, **kwargs):
        return Locator(self, text)

    def is_closed(self):
        return self.closed

    async def bring_to_front(self):
        pass

    async def goto(self, url, **kwargs):
        self.url = url

    async def close(self):
        self.closed = True


@pytest.mark.parametrize('fail', [False, True])
def test_send_success_or_uncertain(fail):
    async def check():
        page = Page(fail)
        context = AsyncMock()
        context.new_page.return_value = page
        snapshots = []
        job = {'jobUrl': page.url, 'jobName': 'Python开发', 'companyName': '测试公司', 'deliveryStatus': '未投递'}
        async def message(repeat):
            assert not repeat
            return '您好，期待沟通'
        operation = delivery.send_one(context, job, {}, message, Path('unused'), lambda value: snapshots.append(dict(value)))
        if fail:
            with pytest.raises(RuntimeError):
                await operation
            assert snapshots[-1]['deliveryStatus'] == '发送待确认'
        else:
            await operation
            assert snapshots[-1]['deliveryStatus'] == '已投递'
        assert snapshots[0]['deliveryStatus'] == '发送待确认'
        assert not page.closed
    asyncio.run(check())
