def test_infer_job_fields_from_jd():
    from backend.app.jobs import infer_job_fields
    job = infer_job_fields({'jobName': 'AI应用工程师', 'jobDescription': '本科，3-5年经验，负责大模型和软件系统开发'})
    assert job['degree'] == '本科'
    assert job['experience'] == '3-5年'
    assert '人工智能' in job['industry']

import asyncio
import httpx
from backend.app import main
from backend.app.jobs import filter_reason, parse_list, salary_range, save_job


def test_filters():
    assert parse_list('[Java，Python]') == ['Java', 'Python']
    assert parse_list('["Java", "Go"]') == ['Java', 'Go']
    assert salary_range('20-30K·14薪') == (20, 30)
    assert salary_range('200-300元/天') is None
    assert salary_range('面议') is None
    assert filter_reason({'companyName': 'ABC科技'}, {}, [{'type': 'company', 'value': 'abc'}])
    assert filter_reason({'salary': '10-15K'}, {'expectedSalaryMin': 20}, [])
    assert filter_reason({'salary': '20-30K'}, {'expectedSalaryMin': 25}, []) is None
    assert filter_reason({'hrActiveStatus': '本月活跃'}, {'filterDeadHr': 1, 'deadStatus': '[本月活跃]'}, [])


def test_history_analytics(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'jobs.db')
    with main.connect() as db:
        job = {'jobUrl': 'https://www.zhipin.com/job_detail/test.html', 'jobName': 'Python开发',
               'companyName': '测试公司', 'salary': '20-30K', 'location': '上海', 'deliveryStatus': '已投递'}
        first = save_job(db, job)
        assert save_job(db, job) == first
        save_job(db, {**job, 'jobUrl': 'https://www.zhipin.com/job_detail/second.html', 'deliveryStatus': '已过滤', 'location': '北京'})

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            result = (await client.get('/api/boss/list?location=上海&size=1')).json()
            assert result['total'] == 1
            assert result['items'][0]['jobName'] == 'Python开发'
            stats = (await client.get('/api/boss/stats')).json()
            assert stats['kpi']['total'] == 2
            assert stats['kpi']['delivered'] == 1
            assert stats['kpi']['filtered'] == 1
            assert stats['kpi']['avgMonthlyK'] == 25
            assert (await client.get('/api/boss/list?minK=NaN')).status_code == 422
            assert (await client.get('/api/boss/list?page=0')).status_code == 422
            assert (await client.get('/api/boss/list?minK=40')).json()['total'] == 0
            assert (await client.get('/api/boss/stats?statuses=已投递')).json()['kpi']['total'] == 1
    asyncio.run(check())
