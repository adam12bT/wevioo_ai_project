from functools import lru_cache

from redis import Redis

from app.config import settings


@lru_cache(maxsize=1)
def redis_connection() -> Redis:
    return Redis.from_url(settings.redis_url, decode_responses=False)

