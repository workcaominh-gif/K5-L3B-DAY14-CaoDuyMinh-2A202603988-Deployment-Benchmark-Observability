"""
Cost guard (tiêu chí 8).

Yêu cầu:
  • Cộng dồn chi phí LLM (tính theo token) vào Redis
  • Tổng chi phí vượt DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD) → HTTP 402
"""
from datetime import datetime, timezone

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _budget_limit() -> float:
    if settings.monthly_budget_usd and settings.monthly_budget_usd > 0:
        return settings.monthly_budget_usd
    return settings.daily_budget_usd


def _period_key() -> str:
    now = datetime.now(timezone.utc)
    if settings.monthly_budget_usd and settings.monthly_budget_usd > 0:
        return f"cost:month:{now.strftime('%Y-%m')}"
    return f"cost:day:{now.strftime('%Y-%m-%d')}"


def _current_spend() -> float:
    val = r.get(_period_key())
    try:
        return float(val) if val is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → raise HTTPException(status_code=402)."""
    limit = _budget_limit()
    spent = _current_spend()
    if spent >= limit:
        raise HTTPException(
            status_code=402,
            detail=f"Daily/monthly budget exceeded: spent ${spent:.6f} of ${limit:.6f}",
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí của request vào tổng, trả về chi phí request."""
    cost = (input_tokens / 1000.0) * PRICE_INPUT_PER_1K + (output_tokens / 1000.0) * PRICE_OUTPUT_PER_1K
    key = _period_key()
    pipe = r.pipeline()
    pipe.incrbyfloat(key, cost)
    # TTL dư dả để key tự dọn — 35 ngày đủ cho cả daily và monthly window
    pipe.expire(key, 35 * 24 * 60 * 60)
    pipe.execute()
    return cost
