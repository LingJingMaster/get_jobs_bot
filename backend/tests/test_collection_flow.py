import asyncio
from unittest.mock import AsyncMock
from backend.app import collector


class Element:
    def __init__(self, selector):
        self.selector = selector
        self.first = self
    async def wait_for(self, **kwargs):
        pass
    async def evaluate_all(self, expression):
        return ['https://www.zhipin.com/job_detail/example.html?source=search']
    async def count(self):
        return 0 if self.selector.startswith('.verify-wrap') else 1
    async def inner_text(self, **kwargs):
        return {' .unused': '', '.job-name h1, .name h1': 'Python',
                '.sider-company .company-info a, .company-info a': '公司',
                '.info-primary .salary': '20-30K'}.get(self.selector, '')


class Page:
    url = 'https://www.zhipin.com/web/geek/jobs'
    def __init__(self):
        self.closed = False
    def locator(self, selector):
        return Element(selector)
    async def goto(self, url, **kwargs):
        self.url = url
    async def close(self):
        self.closed = True


def test_collection_persists_without_chat_clicks():
    async def check():
        listing, detail = Page(), Page()
        context = AsyncMock()
        context.new_page.side_effect = [listing, detail]
        records = []
        await collector.collect(context, {'keywords': 'Python'}, [], records.append, lambda _: None, limit=1)
        assert records[0]['jobUrl'] == 'https://www.zhipin.com/job_detail/example.html'
        assert records[0]['deliveryStatus'] == '未投递'
        assert records[0]['jobName'] == 'Python'
        assert listing.closed and detail.closed
    asyncio.run(check())
