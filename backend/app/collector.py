"""Bounded, cancellable Boss collection. Never clicks chat or sends messages."""
import asyncio
from urllib.parse import urlencode, urljoin, urlsplit
from .jobs import parse_list, filter_reason
from .options import codes


class CollectionBlocked(Exception):
    pass


def search_urls(config):
    keywords = parse_list(config.get('keywords', ''))
    if not keywords:
        raise ValueError('请先保存至少一个搜索关键词')
    if len(keywords) > 20:
        raise ValueError('每次最多搜索 20 个关键词')
    params = {key: codes(key, config.get('cityCode' if key == 'city' else key, '')) for key in
              ('city', 'jobType', 'salary', 'experience', 'degree', 'scale', 'stage', 'industry')}
    return ['https://www.zhipin.com/web/geek/jobs?' + urlencode({**{k: v for k, v in params.items() if v}, 'query': word}) for word in keywords]


async def text(page, selector):
    locator = page.locator(selector).first
    return (await locator.inner_text(timeout=3000)).strip() if await locator.count() else ''


async def ensure_available(page):
    if any(part in page.url for part in ('/web/user/', '/web/common/security', 'captcha')):
        raise CollectionBlocked('请手动完成登录或安全验证后重新采集')
    if await page.locator('.verify-wrap, .captcha-container, .error-content').count():
        raise CollectionBlocked('平台要求验证或页面不可用，已停止采集')


async def collect(context, config, blacklist, save, report, limit=100):
    """Uses independent pages; context owner must cancel this before closing the browser."""
    urls = search_urls(config)
    listing = await context.new_page()
    detail = await context.new_page()
    seen = set()
    try:
        for url in urls:
            await listing.goto(url, wait_until='domcontentloaded', timeout=30000)
            await ensure_available(listing)
            await listing.locator('li.job-card-box').first.wait_for(timeout=15000)
            for _ in range(10):
                await ensure_available(listing)
                links = await listing.locator('li.job-card-box a[href*="/job_detail/"]').evaluate_all('(nodes) => nodes.map(n => n.href)')
                fresh = [link for link in links if link not in seen]
                if not fresh:
                    break
                for link in fresh:
                    parsed = urlsplit(link)
                    if parsed.scheme != 'https' or parsed.hostname != 'www.zhipin.com' or not parsed.path.startswith('/job_detail/'):
                        continue
                    canonical = urljoin('https://www.zhipin.com', parsed.path)
                    if canonical in seen:
                        seen.add(link)
                        continue
                    seen.add(link)
                    seen.add(canonical)
                    await detail.goto(link, wait_until='domcontentloaded', timeout=30000)
                    await ensure_available(detail)
                    await detail.locator('.job-name h1, .name h1').first.wait_for(timeout=10000)
                    job = {
                        'jobUrl': canonical,
                        'jobName': await text(detail, '.job-name h1, .name h1'),
                        'companyName': await text(detail, '.sider-company .company-info a, .company-info a'),
                        'salary': await text(detail, '.info-primary .salary'),
                        'location': await text(detail, '.text-city'),
                        'hrName': await text(detail, '.boss-info-attr .name'),
                        'hrPosition': await text(detail, '.boss-info-attr'),
                        'hrActiveStatus': await text(detail, '.boss-active-time'),
                        'jobDescription': await text(detail, '.job-sec-text'),
                    }
                    if not job['jobName'] or not job['companyName']:
                        raise CollectionBlocked('岗位页面结构变化，无法确认公司或职位，已停止')
                    reason = filter_reason(job, config, blacklist)
                    job['deliveryStatus'] = '已过滤' if reason else '未投递'
                    job['filterReason'] = reason
                    save(job)
                    limit -= 1
                    report('已采集：' + job['jobName'])
                    if limit <= 0:
                        return
                    await asyncio.sleep(max(2, config.get('waitTime', 10)))
                await listing.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(2)
    finally:
        await asyncio.gather(listing.close(), detail.close(), return_exceptions=True)
