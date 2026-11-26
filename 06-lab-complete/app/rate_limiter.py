"""
Rate limiting (tiêu chí 7).

Yêu cầu:
  • Mỗi API key tối đa RATE_LIMIT_PER_MINUTE request trong 60 giây (sliding window)
  • Vượt giới hạn → HTTP 429, nên kèm header Retry-After
  • State lưu trong Redis để mọi worker / instance dùng chung và vẫn còn sau khi
    restart agent (script chấm sẽ restart agent để kiểm tra)
"""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    """Sliding window dùng Redis sorted set: ZREMRANGEBYSCORE -> ZCARD -> ZADD -> EXPIRE.

    Vượt RATE_LIMIT_PER_MINUTE request / 60s cho `key` -> raise HTTPException(429).
    """
    limit = settings.rate_limit_per_minute
    now = time.time()
    window_start = now - WINDOW_SECONDS
    redis_key = f"ratelimit:{key}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(redis_key, 0, window_start)
    pipe.zcard(redis_key)
    pipe.execute()

    count = r.zcard(redis_key)
    if count >= limit:
        # thời điểm request cũ nhất còn trong window sẽ hết hạn — dùng để tính Retry-After
        oldest = r.zrange(redis_key, 0, 0, withscores=True)
        retry_after = WINDOW_SECONDS
        if oldest:
            retry_after = max(1, int(oldest[0][1] + WINDOW_SECONDS - now) + 1)
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )

    member = f"{now}:{uuid.uuid4().hex}"
    pipe = r.pipeline()
    pipe.zadd(redis_key, {member: now})
    pipe.expire(redis_key, WINDOW_SECONDS)
    pipe.execute()
