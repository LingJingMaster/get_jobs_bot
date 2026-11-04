import asyncio
import httpx
from backend.app import main


def test_invalid_settings_and_no_login(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DB_PATH', tmp_path / 'db.sqlite')
    monkeypatch.setattr(main, 'browser', main.BrowserSession(tmp_path / 'profile'))
    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
            assert (await client.put('/api/boss/config', json={'enableAi': 2})).status_code == 422
            assert (await client.put('/api/boss/config', json={'expectedSalaryMin': 40, 'expectedSalaryMax': 20})).status_code == 422
            assert (await client.post('/api/boss/config/blacklist', json={'value': '   '})).status_code == 422
            assert (await client.post('/api/boss/config/blacklist', json={'type': 'other', 'value': 'x'})).status_code == 422
            assert (await client.post('/api/boss/start')).status_code == 409
            assert (await client.post('/api/boss/collect')).status_code == 409
            assert (await client.get('/api/liepin/config')).status_code == 404
    asyncio.run(check())
