import asyncio
from io import BytesIO
import httpx
from PIL import Image
from backend.app import main


def test_upload_validation_and_preview(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "DB_PATH", tmp_path / "db.sqlite")
    monkeypatch.setattr(main, "UPLOAD_DIR", tmp_path / "uploads")
    data = BytesIO()
    Image.new("RGB", (4, 4)).save(data, "PNG")

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
            config = (await client.get("/api/boss/config")).json()
            assert config["config"]["enableAi"] == 0
            assert config["config"]["sendImgResume"] == 0
            assert config["resumeImage"]["exists"] is False
            url = "/api/boss/config/resume-image"
            assert (await client.post(url, files={"file": ("bad.png", b"not an image", "image/png")})).status_code == 400
            response = await client.post(url, files={"file": ("../../resume.png", data.getvalue(), "image/png")})
            assert response.status_code == 200
            metadata = response.json()["resumeImage"]
            assert metadata["exists"] is True
            preview = await client.get(metadata["previewUrl"])
            assert preview.status_code == 200
            assert preview.headers["content-type"] == "image/png"
            assert (await client.get("/api/boss/config")).json()["resumeImage"] == metadata
            original = preview.content
            bad = await client.post(url, files={"file": ("bad.pdf", b"invalid pdf", "application/pdf")})
            assert bad.status_code == 400
            assert (await client.get(metadata["previewUrl"])).content == original
            pdf = BytesIO()
            Image.new("RGB", (100, 140), "white").save(pdf, "PDF")
            converted = await client.post(url, files={"file": ("resume.pdf", pdf.getvalue(), "application/pdf")})
            assert converted.status_code == 200
            result = Image.open(BytesIO((await client.get(metadata["previewUrl"])).content))
            assert result.format == "PNG" and result.width == 1440
            events = await client.get("/api/boss/events")
            assert events.text.startswith("data: ")
            assert events.text.endswith("\n\n")
            assert (await client.post("/api/cookie/save?platform=liepin")).status_code == 404
    asyncio.run(check())
