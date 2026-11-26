"""
Config — 12-Factor: mọi cấu hình đọc từ biến môi trường.

TODO (tiêu chí 9 — Config từ environment variables):
  • Đọc các biến sau từ môi trường, có giá trị mặc định hợp lý khi chạy local:
      PORT, ENVIRONMENT, AGENT_API_KEY, REDIS_URL,
      RATE_LIMIT_PER_MINUTE, DAILY_BUDGET_USD (hoặc MONTHLY_BUDGET_USD)
  • Không hard-code secret (API key thật, mật khẩu...) trong code.
  • Liệt kê đủ các biến này trong .env.example.
"""
import os
from dataclasses import dataclass


def _getenv_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _getenv_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


@dataclass
class Settings:
    port: int = 8000
    environment: str = "development"
    agent_api_key: str = ""
    redis_url: str = "redis://localhost:6379/0"
    rate_limit_per_minute: int = 10
    daily_budget_usd: float = 1.0
    monthly_budget_usd: float = 0.0


def _load_settings() -> Settings:
    return Settings(
        port=_getenv_int("PORT", 8000),
        environment=os.getenv("ENVIRONMENT", "development"),
        agent_api_key=os.getenv("AGENT_API_KEY", ""),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        rate_limit_per_minute=_getenv_int("RATE_LIMIT_PER_MINUTE", 10),
        daily_budget_usd=_getenv_float("DAILY_BUDGET_USD", 1.0),
        monthly_budget_usd=_getenv_float("MONTHLY_BUDGET_USD", 0.0),
    )


settings = _load_settings()
