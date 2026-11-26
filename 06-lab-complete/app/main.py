"""
Production AI Agent — Part 6 Final Project

Chạy: uvicorn app.main:app --workers 2
Chấm: python check_production_ready.py
"""
import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured (JSON) logging — tiêu chí 10 ──
# Mỗi dòng log của app phải là 1 JSON object hợp lệ, vd
# {"ts": "...", "lvl": "INFO", "event": "request", "path": "/ask", "status": 200, "ms": 12.3}
class _PassthroughFormatter(logging.Formatter):
    """Message được build sẵn bằng json.dumps() ở log_json() — formatter chỉ trả nguyên văn."""

    def format(self, record: logging.LogRecord) -> str:
        return record.getMessage()


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(_PassthroughFormatter())
    logger.addHandler(_handler)

# Giữ uvicorn's own loggers nguyên vẹn (log của uvicorn không tính vào tiêu chí 10).
logging.getLogger("uvicorn").setLevel(logging.INFO)


def log_json(level: int, **fields) -> None:
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "lvl": logging.getLevelName(level),
    }
    payload.update(fields)
    logger.log(level, json.dumps(payload, default=str))


# ── Lifespan — tiêu chí 11 (graceful shutdown hook) ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    log_json(logging.INFO, event="startup", environment=settings.environment, port=settings.port)
    yield
    log_json(logging.INFO, event="shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        ms = round((time.perf_counter() - start) * 1000, 2)
        log_json(
            logging.INFO,
            event="request",
            method=request.method,
            path=request.url.path,
            status=status_code,
            ms=ms,
        )


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: Optional[str] = None


# ── Health / Readiness — tiêu chí 4, 5 ──
@app.get("/health")
def health():
    """Liveness — luôn trả 200 khi process còn chạy, kể cả khi Redis chưa kết nối được."""
    return {"status": "ok"}


@app.get("/ready")
def ready():
    """Readiness — 200 khi sẵn sàng, 503 khi Redis (REDIS_URL) không kết nối được."""
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return {"status": "ready"}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    # tiêu chí 6: auth — Depends(verify_api_key) chạy trước, thiếu/sai key -> 401
    # tiêu chí 7: rate limit — vượt giới hạn -> 429
    check_rate_limit(api_key)
    # tiêu chí 8: cost guard — hết budget -> 402 (check TRƯỚC khi gọi LLM)
    check_budget()

    answer = llm_ask(body.question)

    input_tokens = max(1, len(body.question.split()))
    output_tokens = max(1, len(answer.split()))
    cost = record_cost(input_tokens, output_tokens)

    log_json(logging.INFO, event="ask", user_id=body.user_id, cost_usd=round(cost, 8))
    return {"question": body.question, "answer": answer}
