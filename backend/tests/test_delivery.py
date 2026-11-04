import asyncio
from unittest.mock import AsyncMock
from backend.app import delivery, main
from backend.app.jobs import save_job, selected_jobs


def test_greetings(monkeypatch):
    async def check():
        assert await delivery.greeting({}, {'sayHi': '你好'}, {}, {}) == '你好'
        assert await delivery.greeting({}, {'repeatChatMessages': '\n再次问候\n'}, {}, {}, True) == '再次问候'
        monkeypatch.setattr(delivery, 'generate', AsyncMock(return_value='false'))
        assert await delivery.greeting({}, {'enableAi': 1}, {}, {}) is None
    asyncio.run(check())


def test_unknown_send_not_reset_by_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'jobs.db')
    with main.connect() as db:
        job = {'jobUrl': 'https://www.zhipin.com/job_detail/id.html', 'deliveryStatus': '发送待确认'}
        save_job(db, job)
        save_job(db, {**job, 'deliveryStatus': '未投递'})
        assert selected_jobs(db, {})[0]['deliveryStatus'] == '发送待确认'


def test_debugger_and_uncertain_records_never_sent(tmp_path, monkeypatch):
    send = AsyncMock()
    monkeypatch.setattr(delivery, 'send_one', send)
    async def check():
        await delivery.deliver(None, [{'deliveryStatus': '发送待确认'}], {}, [], {}, {}, tmp_path / 'image', lambda _: None, lambda _: None)
        await delivery.deliver(None, [{'deliveryStatus': '未投递'}], {'debugger': 1}, [], {}, {}, tmp_path / 'image', lambda _: None, lambda _: None)
        send.assert_not_awaited()
    asyncio.run(check())
