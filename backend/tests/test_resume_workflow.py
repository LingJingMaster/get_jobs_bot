import asyncio
from io import BytesIO
import json
import httpx
from PIL import Image
from backend.app import main, resume_workflow as workflow
from backend.app.jobs import save_job


def test_workflow_versions_and_delivery_guards(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'db.sqlite')
    monkeypatch.setattr(main, 'UPLOAD_DIR', tmp_path / 'uploads')
    with main.connect() as db:
        job_id = save_job(db, dict(jobUrl='https://www.zhipin.com/job_detail/test.html', jobName='后端开发', companyName='测试公司', jobDescription='Python 和 SQL 开发', deliveryStatus='未投递'))
    calls = []
    async def fake_ai(prompt, settings):
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps({'resume': '# 张三\n工作经历：测试公司，2020–2024，负责 Python 开发。\n教育：测试大学，本科。', 'notes': '补充联系方式，不编造业绩。'}, ensure_ascii=False)
        return '# 张三\n工作经历：测试公司，2020–2024，开发 Python 服务。\n教育：测试大学，本科。'
    monkeypatch.setattr(workflow, 'generate', fake_ai)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            response = await client.post('/api/resume-workflow/generate', json={'jobId': job_id, 'resume': '张三，在测试公司2020到2024负责Python开发；测试大学本科。', 'humanize': True})
            assert response.status_code == 200, response.text
            record = response.json()
            assert record['status'] == 'draft'
            assert record['builder'] != record['resume']
            assert len(calls) == 2 and 'Resume Builder' in calls[0] and 'Humanizer-zh' in calls[1]
            prefix = '/api/resume-workflow/' + record['id']
            assert (await client.post(prefix + '/deliver', json={'greeting': '您好'})).status_code == 409
            assert (await client.get(prefix + '/download/docx')).content.startswith(b'PK')
            assert len((await client.get('/api/resume-workflow')).json()['items']) == 1
            # Conversion is separately integration-tested; never use the real profile or send.
            image = BytesIO(); Image.new('RGB', (10, 10)).save(image, 'PNG')
            monkeypatch.setattr('backend.app.resume.render_resume', lambda *args: image.getvalue())
            approved = await client.post(prefix + '/approve', json={'resume': record['resume']})
            assert approved.status_code == 200
            assert approved.json()['status'] == 'approved'
            assert (await client.get(prefix + '/image')).content == image.getvalue()
            assert (await client.post(prefix + '/approve', json={'resume': record['resume']})).status_code == 409
            monkeypatch.setattr(main.browser, 'context', None)
            assert (await client.post(prefix + '/deliver', json={'greeting': '您好'})).status_code == 409
    asyncio.run(check())


def test_docx_roundtrip_and_safe_html(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'db.sqlite')
    text = '# 张三\n## 工作经历\n- **开发：**完成接口开发，保留原始事实。\n<script>alert(1)</script>'
    assert '保留原始事实' in workflow.extract(workflow.docx_bytes(text), 'resume.docx')
    workflow.save({'id': 'test', 'resume': text})
    html = workflow.download('test', 'html').body.decode()
    assert '<script>' not in html
    assert '&lt;script&gt;' in html
