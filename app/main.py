from datetime import datetime, timezone
from uuid import uuid4
import sqlite3

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from app.schemas import MoodRequest
from app.ai_service import AIServiceError, SUPPORT_MESSAGE, analyze_text
from app.config import get_settings

from app.database import (
    clear_entries,
    create_entry,
    delete_entry,
    init_database,
    list_entries,
)


app = FastAPI(title="AI 心情搭子")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"])
init_database()


@app.middleware("http")
async def local_browser_boundary(request: Request, call_next):
    # 本机应用不开放跨站写操作；不是登录鉴权，也不能代替公网部署的安全设计。
    origin = request.headers.get("origin")
    expected_origin = f"{request.url.scheme}://{request.url.netloc}"
    if request.method in {"POST", "DELETE"} and origin and origin != expected_origin:
        return JSONResponse(status_code=403, content={"detail": {"message": "不允许跨站修改记录。"}})
    if request.url.path == "/api/analyze" and request.method == "POST":
        if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return JSONResponse(status_code=415, content={"detail": {"message": "请使用 JSON 提交心情。"}})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(sqlite3.Error)
async def database_error(request: Request, error: sqlite3.Error):
    # 不将数据库路径、SQL 或用户输入泄露给浏览器。
    return JSONResponse(status_code=503, content={"detail": {
        "code": "storage_unavailable",
        "message": "本地记录暂时无法读写，请稍后刷新历史确认结果，再重试。",
    }})


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/status")
def ai_status():
    # 只返回是否存在配置，不代表密钥和账户额度已经验证。
    try:
        settings = get_settings()
    except ValueError:
        return {"ai_configured": False, "error": "AI_PROVIDER 必须为 deepseek 或 openai。"}
    return {"ai_configured": bool(settings.api_key), "provider": settings.provider,
            "provider_label": settings.label, "key_variable": settings.key_variable}


@app.post("/api/analyze")
def analyze_mood(request: MoodRequest):
    try:
        analysis = analyze_text(request.text)
    except AIServiceError as error:
        raise HTTPException(status_code=error.status_code,
                            detail={"code": error.code, "message": error.message}) from None
    if analysis.safety == "support_needed":
        return {"status": "support_needed", "message": SUPPORT_MESSAGE, "saved": False}

    entry = {
        "id": str(uuid4()),
        "original_text": request.text.strip(),
        **analysis.model_dump(exclude={"safety"}),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return create_entry(entry)


@app.get("/api/entries")
def get_entries():
    return list_entries(limit=20)


@app.delete("/api/entries/{entry_id}", status_code=204)
def remove_entry(entry_id: str):
    if not delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="记录不存在")
    return Response(status_code=204)


@app.delete("/api/entries", status_code=204)
def remove_all_entries():
    clear_entries()
    return Response(status_code=204)


STATIC_DIR = Path(__file__).parent / "static"

# 放在 API 路由之后，且仅开放 static 文件夹，不开放 .env 或数据库。
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
