import asyncio
import json
import httpx
from backend.app import main, resume_workflow as workflow
from backend.app.jobs import save_job


def test_placeholder_resume_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'jobs.db')
    with main.connect() as db:
        job_id = save_job(db, {'jobUrl': 'https://www.zhipin.com/job_detail/p.html', 'jobName': '测试', 'companyName': '公司', 'jobDescription': 'Python', 'deliveryStatus': '未投递'})
    async def fake_ai(prompt, settings):
        return json.dumps({'resume': '# 姓名\n- **测试：** [待补充：项目成果]', 'notes': '请补充'}, ensure_ascii=False)
    monkeypatch.setattr(workflow, 'generate', fake_ai)
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            response = await client.post('/api/resume-workflow/generate', json={'jobId': job_id, 'resume': '测试用户有足够长度的原始简历材料，包含完整工作经历和教育背景。'})
            assert response.status_code == 502
            assert '占位符' in response.json()['detail']
    asyncio.run(check())
