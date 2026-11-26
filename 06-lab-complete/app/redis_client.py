"""
Kết nối Redis dùng chung cho rate limiter và cost guard.

Yêu cầu:
  • Đọc REDIS_URL từ config
  • App vẫn phải KHỞI ĐỘNG ĐƯỢC khi Redis chưa sẵn sàng (đừng ping Redis lúc import)
  • redis_healthy() dùng cho GET /ready: Redis không kết nối được → False
"""
import redis

from app.config import settings

# Tạo client lazy — redis.from_url() KHÔNG mở connection ngay (chỉ ping mới mở),
# nên app vẫn import/khởi động được ngay cả khi Redis chưa sẵn sàng.
r = redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_connect_timeout=1.5,
    socket_timeout=1.5,
)


def redis_healthy() -> bool:
    """Ping Redis; lỗi kết nối → False. Không bao giờ raise."""
    try:
        return bool(r.ping())
    except redis.RedisError:
        return False
    except Exception:
        return False
