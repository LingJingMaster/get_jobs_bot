import asyncio
import httpx
from backend.app import main


def test_configuration_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(main, "browser", main.BrowserSession(tmp_path / "profile"))

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            assert (await client.get("/api/health")).json()["platform"] == "boss"
            response = await client.put("/api/boss/config", json={"cityCode": "上海", "keywords": "[Java]", "sayHi": "你好"})
            assert response.status_code == 200
            assert response.json()["cityCode"] == "上海"
            response = await client.post("/api/ai/config", json={"introduce": "x", "prompt": "y"})
            assert response.status_code == 200
            assert (await client.get("/api/ai/config")).json()["data"]["introduce"] == "x"
            assert (await client.get("/api/boss/status")).json()["running"] is False
            logout = await client.post("/api/boss/logout")
            assert logout.status_code == 200
            assert logout.json()["success"] is True
    asyncio.run(check())
