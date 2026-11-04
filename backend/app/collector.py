"""Bounded, cancellable Boss collection. Never clicks chat or sends messages."""
import asyncio
from urllib.parse import urlencode, urljoin, urlsplit
from .jobs import parse_list, filter_reason
from .options import codes


class CollectionBlocked(Exception):
    pass


SECURITY_HOSTS = {'zhipin.com', 'www.zhipin.com'}


def security_message(url: str) -> str | None:
    """Return a user-facing message for Boss security redirects; never bypass them."""
    parsed = urlsplit(url or '')
    if parsed.hostname not in SECURITY_HOSTS:
        return None
    if '_security_check' in (parsed.query or '') or '/passport/zp/security' in (parsed.path or '') or 'captcha' in (parsed.path or ''):
        return 'Boss 触发了安全验证，请在浏览器中完成验证；验证完成后等待 10 秒再重新采集'
    return None


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


async def first_text(page, selectors):
    for selector in selectors:
        try:
            value = await text(page, selector)
            if value:
                return value
        except Exception:
            continue
    return ''


async def ensure_available(page):
    blocked = security_message(page.url)
    if blocked:
        raise CollectionBlocked(blocked)
    if any(part in page.url for part in ('/web/user/', '/web/common/security', 'captcha')):
        raise CollectionBlocked('请手动完成登录或安全验证后重新采集')
    if await page.locator('.verify-wrap, .captcha-container, .error-content').count():
        raise CollectionBlocked('平台要求验证或页面不可用，已停止采集')


async def open_search(page, keyword, config):
    """Use Boss's normal homepage search interaction instead of a cold direct list URL."""
    await page.goto('https://www.zhipin.com/', wait_until='domcontentloaded', timeout=30000)
    await ensure_available(page)
    input_box = page.locator('input.ipt-search, input[placeholder*="搜索职位"], input[placeholder*="搜索职位、公司"]').first
    await input_box.wait_for(timeout=15000)
    await input_box.fill(keyword)
    button = page.locator('button.btn-search, button:has-text("搜索")').first
    if await button.count():
        await button.click()
    else:
        await input_box.press('Enter')
    await page.wait_for_load_state('domcontentloaded', timeout=30000)
    await ensure_available(page)
    # The UI search controls keyword and current city. Do not cold-jump through
    # an encoded URL; filters are applied later only when the page exposes them.
    await page.locator('li.job-card-box').first.wait_for(timeout=15000)


async def collect(context, config, blacklist, save, report, limit=100):
    """Uses one listing page and one detail page; no parallel tabs or direct list navigation."""
    keywords = parse_list(config.get('keywords', ''))
    if not keywords:
        raise ValueError('请先保存至少一个搜索关键词')
    if getattr(context, 'challenge', False) is True:
        raise CollectionBlocked("浏览器检测到刷新循环，请人工检查后再采集")
    listing = await context.new_page()
    detail = await context.new_page()
    seen = set()
    try:
        for keyword in keywords:
            await open_search(listing, keyword, config)
            try:
                await listing.locator('li.job-card-box').first.wait_for(timeout=15000)
            except Exception as exc:
                blocked = security_message(listing.url)
                if blocked:
                    raise CollectionBlocked(blocked) from exc
                raise CollectionBlocked('岗位列表未加载，可能需要在 Boss 页面完成验证；请稍后重试') from exc
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
                    # Boss may render a simplified detail page after a normal
                    # search. Missing detail fields must not discard the whole
                    # batch; the listing card remains a safe, user-visible record.
                    job = {
                        'jobUrl': canonical,
                        'jobName': await first_text(detail, ('.job-name h1', '.name h1', '.job-name', 'h1.name')),
                        'companyName': await first_text(detail, ('.sider-company .company-info a', '.company-info a', '.company-name')),
                        'salary': await first_text(detail, ('.info-primary .salary', '.job-primary .salary', '.salary')),
                        'location': await first_text(detail, ('.text-city', '.job-location', '.location')),
                        'hrName': await first_text(detail, ('.boss-info-attr .name', '.boss-name')),
                        'hrPosition': await first_text(detail, ('.boss-info-attr', '.boss-info')),
                        'hrActiveStatus': await first_text(detail, ('.boss-active-time', '.active-time')),
                        'jobDescription': await first_text(detail, ('.job-sec-text', '.job-description')),
                    }
                    if not job['jobName'] or not job['companyName']:
                        report('跳过一条无法确认职位/公司的页面：' + canonical)
                        continue
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
