"""Render approved text directly with installed Chrome and system CJK fonts."""
from .markdown import to_html


async def render_text_image(text: str) -> bytes:
    from patchright.async_api import async_playwright
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>
    *{box-sizing:border-box}body{margin:0;background:white;color:#222;font:20px/1.65 "Source Han Sans CN","Noto Sans CJK SC","Hiragino Sans GB",sans-serif}
    main{width:1100px;padding:48px 64px}h1{font-size:36px;margin:0 0 18px}h2{font-size:25px;margin:26px 0 12px;border-bottom:1px solid #ccc;padding-bottom:6px}h3{font-size:21px;margin:20px 0 10px}
    p{margin:10px 0}ul{padding-left:26px;margin:10px 0}li{margin:6px 0}main{overflow-wrap:anywhere}
    </style><main>''' + to_html(text) + '</main></html>'
    async with async_playwright() as driver:
        browser = await driver.chromium.launch(channel='chrome', headless=True)
        try:
            page = await browser.new_page(viewport={'width': 1100, 'height': 900}, device_scale_factor=1.5)
            await page.route('**/*', lambda route: route.abort())
            await page.set_content(html, wait_until='load')
            await page.evaluate('document.fonts.ready')
            height = await page.locator('main').evaluate('(node) => node.scrollHeight')
            if 1650 * height * 1.5 > 20_000_000:
                raise ValueError('简历过长，请精简后再生成投递图片')
            image = await page.locator('main').screenshot(type='png', timeout=30000)
            if len(image) > 10 * 1024 * 1024:
                raise ValueError('图片超过 10MB，请精简简历')
            return image
        finally:
            await browser.close()
