"""Get Jobs Python API: Boss直聘 only."""
from __future__ import annotations
import json
import os
import sqlite3
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from contextlib import asynccontextmanager, contextmanager
from .browser import BrowserSession
from fastapi import FastAPI, HTTPException, UploadFile, File, Request, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = Path(os.getenv("GETJOBS_DB", ROOT / "db" / "getjobs.db"))
UPLOAD_DIR = ROOT / "data" / "uploads"

browser = BrowserSession(ROOT / "data" / "boss-profile")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await cancel_collection()
    await browser.close()

app = FastAPI(title="Get Jobs API", version="3.0.0", description="Boss直聘自动投递服务", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"], allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["Content-Type"])

_worker = {"running": False, "message": "未启动", "updated_at": None}
_collection_task: asyncio.Task | None = None

async def cancel_collection():
    if _collection_task and not _collection_task.done():
        _collection_task.cancel()
        await asyncio.gather(_collection_task, return_exceptions=True)

async def run_collection(config, blacklist):
    from .collector import collect
    from .jobs import save_job
    def save(job):
        with connect() as db:
            save_job(db, job)
    try:
        await collect(browser.context, config, blacklist, save, publish)
        publish("岗位采集完成，未发送招聘消息", False)
    except asyncio.CancelledError:
        publish("采集已停止", False)
        raise
    except Exception as exc:
        publish(f"采集停止：{exc}", False)

@app.post("/api/boss/collect")
async def collect_jobs():
    global _collection_task
    from .collector import search_urls
    if _collection_task and not _collection_task.done():
        raise HTTPException(status_code=409, detail="采集任务正在运行")
    if not browser.context or not browser.logged_in:
        raise HTTPException(status_code=409, detail="请先打开浏览器并登录 Boss")
    saved = get_boss_config()
    try:
        search_urls(saved["config"])
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    publish("开始采集岗位（不发送消息）", True)
    _collection_task = asyncio.create_task(run_collection(saved["config"], saved["blacklist"]))
    return {"success": True, **boss_status()}


def publish(message: str, running: bool | None = None) -> None:
    if running is not None:
        _worker["running"] = running
    _worker["message"] = message
    _worker["updated_at"] = datetime.now(timezone.utc).isoformat()

class BossConfig(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")
    id: int | None = None
    debugger: Literal[0, 1] = 0
    wait_time: int = Field(10, ge=0, le=120)
    keywords: str = "[]"
    city_code: str = ""
    industry: str = "[]"
    job_type: str = "不限"
    experience: str = "[]"
    degree: str = "[]"
    salary: str = "[]"
    scale: str = "[]"
    stage: str = "[]"
    say_hi: str = "您好，期待与您进一步沟通。"
    expected_salary_min: int | None = Field(None, ge=0)
    expected_salary_max: int | None = Field(None, ge=0)
    enable_ai: Literal[0, 1] = 0
    send_img_resume: Literal[0, 1] = 0
    allow_repeat_chat: Literal[0, 1] = 0
    repeat_chat_messages: str | None = None
    filter_dead_hr: Literal[0, 1] = 1
    dead_status: str = "[]"
    created_at: str | None = None
    updated_at: str | None = None

    @model_validator(mode="after")
    def validate_salary(self):
        if self.expected_salary_min is not None and self.expected_salary_max is not None and self.expected_salary_min > self.expected_salary_max:
            raise ValueError("薪资下限不能大于上限")
        return self

class BlacklistInput(BaseModel):
    type: Literal['company', 'job', 'recruiter'] = 'company'
    value: str = Field(min_length=1, max_length=200)

    @model_validator(mode='after')
    def strip_value(self):
        self.value = self.value.strip()
        if not self.value:
            raise ValueError('黑名单内容不能为空')
        return self


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.executescript("""
      CREATE TABLE IF NOT EXISTS boss_config (id INTEGER PRIMARY KEY AUTOINCREMENT, debugger INTEGER DEFAULT 0,
        wait_time INTEGER DEFAULT 10, keywords TEXT, city_code TEXT, industry TEXT, job_type TEXT, experience TEXT,
        degree TEXT, salary TEXT, scale TEXT, stage TEXT, say_hi TEXT, expected_salary_min INTEGER,
        expected_salary_max INTEGER, enable_ai INTEGER DEFAULT 0, send_img_resume INTEGER DEFAULT 0,
        allow_repeat_chat INTEGER DEFAULT 0, repeat_chat_messages TEXT, filter_dead_hr INTEGER DEFAULT 1,
        dead_status TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY AUTOINCREMENT, config_key TEXT UNIQUE, config_value TEXT,
        config_type TEXT, category TEXT, description TEXT, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
      CREATE TABLE IF NOT EXISTS boss_blacklist (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, value TEXT,
        UNIQUE(type, value));
      CREATE TABLE IF NOT EXISTS ai_config (id INTEGER PRIMARY KEY AUTOINCREMENT, introduce TEXT NOT NULL DEFAULT '', prompt TEXT NOT NULL DEFAULT '');
    """)
    if not db.execute("SELECT 1 FROM boss_config LIMIT 1").fetchone():
        item = BossConfig().model_dump(exclude={"id", "created_at", "updated_at"})
        cols = [k for k in item if k in {x[1] for x in db.execute('PRAGMA table_info(boss_config)')}]
        db.execute(f"INSERT INTO boss_config ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})", [item[k] for k in cols])
        db.commit()
    try:
        yield db
    finally:
        db.close()


def row_dict(row: sqlite3.Row | None) -> dict[str, Any]:
    return {to_camel(k): row[k] for k in row.keys()} if row else {}

@app.get("/api/health")
def health() -> dict[str, str]:
    with connect() as db: db.execute("SELECT 1")
    return {"status": "UP", "service": "get-jobs-python", "platform": "boss"}

@app.get("/api/boss/config")
def get_boss_config() -> dict[str, Any]:
    with connect() as db:
        config = row_dict(db.execute("SELECT * FROM boss_config ORDER BY id LIMIT 1").fetchone())
        blacklist = [row_dict(x) for x in db.execute("SELECT * FROM boss_blacklist ORDER BY id").fetchall()]
    from .options import options
    return {"config": config, "blacklist": blacklist, "options": options(), "resumeImage": resume_metadata()}

@app.put("/api/boss/config")
def save_boss_config(config: BossConfig) -> dict[str, Any]:
    data = config.model_dump(exclude={"id", "created_at", "updated_at"}, by_alias=False)
    with connect() as db:
        old = db.execute("SELECT id FROM boss_config ORDER BY id LIMIT 1").fetchone()
        if old:
            assignments = ",".join(f"{k}=?" for k in data)
            db.execute(f"UPDATE boss_config SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE id=?", [*data.values(), old[0]])
        else:
            db.execute(f"INSERT INTO boss_config ({','.join(data)}) VALUES ({','.join('?' for _ in data)})", list(data.values()))
        db.commit()
    return get_boss_config()["config"]

@app.get("/api/boss/config/blacklist")
def get_blacklist() -> list[dict[str, Any]]:
    with connect() as db: return [row_dict(x) for x in db.execute("SELECT * FROM boss_blacklist ORDER BY id")]

@app.post("/api/boss/config/blacklist")
def add_blacklist(payload: BlacklistInput) -> dict[str, Any]:
    item = payload.model_dump()
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO boss_blacklist(type,value) VALUES (?,?)", (item.get("type", "company"), item.get("value", "")))
        db.commit()
        return row_dict(db.execute("SELECT * FROM boss_blacklist WHERE type=? AND value=?", (item.get("type", "company"), item.get("value", ""))).fetchone())

@app.delete("/api/boss/config/blacklist/{item_id}")
def delete_blacklist(item_id: int) -> dict[str, bool]:
    with connect() as db:
        cursor = db.execute("DELETE FROM boss_blacklist WHERE id=?", (item_id,)); db.commit()
    return {"success": cursor.rowcount > 0}

@app.get("/api/ai/config")
def get_ai_config() -> dict[str, Any]:
    with connect() as db:
        row = db.execute("SELECT id,introduce,prompt FROM ai_config ORDER BY id LIMIT 1").fetchone()
    return {"success": True, "data": row_dict(row) if row else {"introduce": "", "prompt": ""}}

@app.post("/api/ai/config")
def save_ai_config(data: dict[str, str]) -> dict[str, Any]:
    if not isinstance(data.get("introduce"), str) or not isinstance(data.get("prompt"), str):
        raise HTTPException(status_code=400, detail="introduce 和 prompt 必须是字符串")
    with connect() as db:
        row = db.execute("SELECT id FROM ai_config ORDER BY id LIMIT 1").fetchone()
        if row:
            db.execute("UPDATE ai_config SET introduce=?,prompt=? WHERE id=?", (data["introduce"], data["prompt"], row[0]))
        else:
            db.execute("INSERT INTO ai_config(introduce,prompt) VALUES (?,?)", (data["introduce"], data["prompt"]))
        db.commit()
    return get_ai_config()

@app.get("/api/ai/chat")
async def ai_chat(content: str) -> dict[str, Any]:
    from .ai import generate, AIError
    if not content.strip() or len(content) > 20000:
        raise HTTPException(status_code=400, detail="内容不能为空且不能超过 20000 字符")
    try:
        reply = await generate(content, get_configs()["data"])
        return {"success": True, "data": reply, "message": "AI 请求成功"}
    except AIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

def analytics_filters(request: Request) -> dict[str, str]:
    values = dict(request.query_params)
    for key in ("minK", "maxK"):
        if values.get(key):
            import math
            try:
                number = float(values[key])
                if not math.isfinite(number) or number < 0:
                    raise ValueError()
            except ValueError:
                raise HTTPException(status_code=422, detail=f"{key} 必须是非负有限数值")
    if values.get("minK") and values.get("maxK") and float(values["minK"]) > float(values["maxK"]):
        raise HTTPException(status_code=422, detail="薪资下限不能大于上限")
    return values

@app.get("/api/boss/list")
def jobs_list(request: Request, page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=1000)) -> dict[str, Any]:
    from .jobs import selected_jobs
    with connect() as db:
        items = selected_jobs(db, analytics_filters(request))
    return {"items": items[(page-1)*size:page*size], "total": len(items), "page": page, "size": size}

@app.get("/api/boss/stats")
def jobs_stats(request: Request) -> dict[str, Any]:
    from .jobs import selected_jobs, statistics
    with connect() as db:
        return statistics(selected_jobs(db, analytics_filters(request)))

@app.get("/api/boss/reload")
def jobs_reload() -> dict[str, Any]:
    # SQLite is read on every request; no stale in-memory analytics cache.
    return {"success": True, "message": "统计数据已刷新"}

@app.get("/api/boss/status")
def boss_status() -> dict[str, Any]:
    return {"platform": "boss", **_worker, "browserOpen": browser.is_open, "isLoggedIn": browser.logged_in, "browserMessage": browser.message}

@app.get("/api/jobs/login-status/stream")
async def login_status_stream() -> StreamingResponse:
    async def stream():
        yield 'event: connected\ndata: ' + json.dumps({"bossLoggedIn": browser.logged_in}) + '\n\n'
        while True:
            yield 'event: login-status\ndata: ' + json.dumps({"platform": "boss", "isLoggedIn": browser.logged_in}) + '\n\n'
            await asyncio.sleep(3)
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.get("/api/boss/events")
async def boss_events() -> StreamingResponse:
    async def stream():
        last = None
        for _ in range(120):
            current = json.dumps({"platform": "boss", **_worker}, ensure_ascii=False)
            if current != last:
                yield f"data: {current}\n\n"
                last = current
            if not _worker["running"] and last is not None:
                break
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream")

@app.post("/api/cookie/save")
def save_cookie(platform: str = "boss") -> dict[str, Any]:
    if platform != "boss":
        raise HTTPException(status_code=404, detail="仅支持 Boss 直聘")
    raise HTTPException(status_code=501, detail="Cookie 手动保存尚未实现；浏览器使用持久化 profile")

def resume_metadata() -> dict[str, Any]:
    target = UPLOAD_DIR / "boss-resume.png"
    if not target.is_file():
        return {"exists": False}
    stat = target.stat()
    return {"exists": True, "fileName": target.name, "contentType": "image/png",
            "size": stat.st_size, "updatedAt": int(stat.st_mtime * 1000),
            "previewUrl": "/api/boss/config/resume-image/content"}

@app.get("/api/boss/config/resume-image/content")
def resume_content() -> FileResponse:
    if not resume_metadata()["exists"]:
        raise HTTPException(status_code=404, detail="尚未上传图片简历")
    return FileResponse(UPLOAD_DIR / "boss-resume.png", media_type="image/png", headers={"Cache-Control": "no-store"})

@app.post("/api/boss/config/resume-image")
async def upload_resume_image(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=400, detail="只支持 JPG、PNG 或 WebP 图片")
    content = await file.read(10 * 1024 * 1024 + 1)
    await file.close()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片大小不能超过 10MB")
    from PIL import Image, UnidentifiedImageError
    from io import BytesIO
    import tempfile
    try:
        with Image.open(BytesIO(content)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"} or image.width * image.height > 20_000_000:
                raise ValueError("图片格式或尺寸无效")
            image.load()
            output = BytesIO()
            image.convert("RGB").save(output, format="PNG")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        raise HTTPException(status_code=400, detail="无法读取图片或图片尺寸过大") from exc
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=UPLOAD_DIR, delete=False) as temp:
        temp.write(output.getvalue())
        temp_path = Path(temp.name)
    temp_path.replace(UPLOAD_DIR / "boss-resume.png")
    return {"success": True, "message": "图片简历上传成功", "resumeImage": resume_metadata()}

@app.get("/api/config")
def get_configs() -> dict[str, Any]:
    with connect() as db: return {"success": True, "data": {r["config_key"]: r["config_value"] for r in db.execute("SELECT config_key,config_value FROM config")}}

@app.post("/api/config")
def save_configs(values: dict[str, str]) -> dict[str, Any]:
    with connect() as db:
        for key, value in values.items(): db.execute("INSERT INTO config(config_key,config_value) VALUES (?,?) ON CONFLICT(config_key) DO UPDATE SET config_value=excluded.config_value", (key, value))
        db.commit()
    return {"success": True, "updateCount": len(values)}

async def run_delivery(saved, items, ai_config, settings):
    from .delivery import deliver
    from .jobs import save_job
    def save(job):
        with connect() as db:
            save_job(db, job)
    try:
        await deliver(browser.context, items, saved["config"], saved["blacklist"], ai_config, settings,
                      UPLOAD_DIR / "boss-resume.png", save, publish)
        publish("本次投递处理结束，请查看历史记录确认结果", False)
    except asyncio.CancelledError:
        publish("投递已停止，请检查发送待确认的记录", False)
        raise
    except Exception as exc:
        publish(f"投递停止：{exc}", False)

@app.post("/api/boss/start")
async def start_boss() -> dict[str, Any]:
    global _collection_task
    from .jobs import selected_jobs
    if _collection_task and not _collection_task.done():
        raise HTTPException(status_code=409, detail="已有任务正在运行")
    if not browser.context or not browser.logged_in:
        raise HTTPException(status_code=409, detail="请先打开浏览器登录")
    saved = get_boss_config()
    if saved["config"].get("sendImgResume") and not resume_metadata()["exists"]:
        raise HTTPException(status_code=422, detail="请先上传图片简历")
    with connect() as db:
        items = selected_jobs(db, {"statuses": "未投递"})
    if not items:
        raise HTTPException(status_code=409, detail="没有未投递记录，请先采集岗位")
    ai_config, settings = get_ai_config()["data"], get_configs()["data"]
    publish("开始处理未投递岗位（每次最多 20 个）", True)
    _collection_task = asyncio.create_task(run_delivery(saved, items, ai_config, settings))
    return {"success": True, **boss_status()}

@app.post("/api/boss/browser")
async def open_browser() -> dict[str, Any]:
    if _collection_task and not _collection_task.done():
        raise HTTPException(status_code=409, detail="请先停止当前任务")
    try:
        await browser.open()
        publish(browser.message, False)
        return {"success": True, **boss_status()}
    except Exception as exc:
        publish(f"Boss直聘浏览器启动失败：{exc}", False)
        raise HTTPException(status_code=503, detail="浏览器启动失败，请确认已安装 Playwright Chromium 且桌面可用") from exc

@app.post("/api/boss/stop")
async def stop_boss() -> dict[str, Any]:
    await cancel_collection()
    await browser.close()
    publish(browser.message, False)
    return {"success": True, **boss_status()}

@app.post("/api/boss/logout")
async def logout_boss() -> dict[str, Any]:
    await cancel_collection()
    await browser.logout()
    publish(browser.message, False)
    return {"success": True, **boss_status()}
