import asyncio
from types import SimpleNamespace
import httpx
from backend.app import main


def test_keyword_update_is_used_by_next_collection(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'jobs.db')
    monkeypatch.setattr(main, 'browser', SimpleNamespace(context=object(), logged_in=True, challenge=False,
                                                      is_open=True, message='已登录'))
    monkeypatch.setattr(main, '_collection_task', None)
    monkeypatch.setattr(main, '_worker', {'running': False, 'message': '', 'updated_at': None})
    captured = []
    async def fake_collection(config, blacklist):
        captured.append(config['keywords'])
    monkeypatch.setattr(main, 'run_collection', fake_collection)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            for keyword in ('FDE', 'Agent'):
                response = await client.put('/api/boss/config', json={'keywords': keyword})
                assert response.status_code == 200
                response = await client.post('/api/boss/collect')
                assert response.status_code == 200, response.text
                await main._collection_task
            assert captured == ['FDE', 'Agent']
    asyncio.run(check())
