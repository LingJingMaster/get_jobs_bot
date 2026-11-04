import asyncio
from urllib.parse import urlsplit, parse_qs
from unittest.mock import AsyncMock
import pytest
from backend.app.collector import search_urls, ensure_available, CollectionBlocked, security_message
from backend.app.options import options


def test_search_filters_and_encoding():
    urls = search_urls({'keywords': '["Python & AI","Go"]', 'cityCode': '上海', 'degree': '[本科]', 'salary': '[20-50K]'})
    assert len(urls) == 2
    query = parse_qs(urlsplit(urls[0]).query)
    assert query['query'] == ['Python & AI']
    assert query['city'] == ['101020100']
    assert query['degree'] == ['204']
    assert query['salary'] == ['406']
    assert set(options()) == {'city', 'degree', 'industry', 'salary', 'experience', 'jobType', 'scale', 'stage'}
    with pytest.raises(ValueError):
        search_urls({'keywords': 'Python', 'cityCode': '不支持的城市名'})
    with pytest.raises(ValueError):
        search_urls({'keywords': '[]'})


def test_security_redirect_is_explicit():
    url = 'https://www.zhipin.com/web/geek/jobs?query=FDE&_security_check=5_1793812915239'
    assert security_message(url)
    assert '验证' in security_message(url)


def test_security_check_stops():
    async def check():
        page = AsyncMock()
        page.url = 'https://www.zhipin.com/web/common/security-check'
        with pytest.raises(CollectionBlocked):
            await ensure_available(page)
    asyncio.run(check())
