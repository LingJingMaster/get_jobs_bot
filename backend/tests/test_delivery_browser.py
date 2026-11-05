"""Local HTML fixtures exercise real browser events; no Boss requests or messages."""
import asyncio
from pathlib import Path

import pytest
from patchright.async_api import async_playwright
from backend.app.delivery import send_one

DETAIL = '''<div class="name"><h1>AI工程师</h1></div>
<div class="sider-company"><div class="company-info"><a title="招聘机构">招聘机构</a></div></div>
<div class="job-sec-text">Python 开发</div>
<div class="job-boss-info"><h2 class="name">张某<span>在线</span></h2></div>
<a class="btn-startchat" onclick="document.body.dataset.clicked='yes';document.querySelector('.dialog-container').hidden=false">立即沟通</a>
<div class="dialog-container" hidden><a class="close" onclick="this.parentElement.hidden=true">关闭</a>默认招呼已发送</div>
<a href="/web/geek/chat">消息</a>'''
CHAT = '''<div class="name-box" onclick="document.querySelector('main').hidden=false"><span class="name-text">张某</span>招聘机构</div>
<main hidden><span>AI工程师</span><div id="chat-input" contenteditable="true"></div>
<button type="send" onclick="const n=document.createElement('li');n.className='message-item item-myself';n.innerHTML='<i class=status-delivery>送达</i><p></p>';n.querySelector('p').textContent=document.querySelector('#chat-input').innerText;document.querySelector('ul').append(n)">发送</button>
<ul></ul><div aria-label="发送图片"><input type="file" onchange="const n=document.createElement('li');n.className='message-item item-myself';n.innerHTML='<i class=status-delivery>送达</i><img>';document.querySelector('ul').append(n)"></div></main>'''

@pytest.mark.parametrize('valid', [True, False])
def test_agency_delivery_and_failed_identity_keep_page(tmp_path, valid):
    async def run():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch(channel='chrome', headless=True)
            try:
                context = await browser.new_context()
                async def route(request):
                    await request.fulfill(body=CHAT if '/web/geek/chat' in request.request.url else DETAIL, content_type='text/html; charset=utf-8')
                await context.route('**/*', route)
                job = dict(jobUrl='https://www.zhipin.com/job_detail/test.html', jobName='AI工程师', companyName='匿名客户', hrPosition='招聘机构·主管', jobDescription='Python 开发' if valid else '完全不同岗位', deliveryStatus='未投递')
                saved = []
                image = tmp_path/'resume.png'
                image.write_bytes(b'fixture')
                async def message(repeat): return '您好，附上简历。'
                if valid:
                    await send_one(context, job, {'sendImgResume': 1}, message, image, lambda j: saved.append(dict(j)))
                    assert job['deliveryStatus'] == '已投递'
                    assert job['resumeStatus'] == '图片已送达'
                    assert saved[0]['deliveryStatus'] == '发送待确认'
                    assert await context.pages[0].locator('.item-myself').count() == 2
                else:
                    with pytest.raises(ValueError, match='岗位身份'):
                        await send_one(context, job, {}, message, image, lambda j: saved.append(dict(j)))
                    assert job['deliveryStatus'] == '未投递'
                    assert await context.pages[0].locator('body').get_attribute('data-clicked') is None
                assert not context.pages[0].is_closed()
            finally:
                await browser.close()
    asyncio.run(run())
