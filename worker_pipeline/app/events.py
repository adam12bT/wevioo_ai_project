import json
import time
from typing import Any

from app.config import settings
from app.redis_client import redis_connection


def event_stream_key(job_id: str) -> str:
    return f"rfp-worker:events:{job_id}"


def publish_event(job_id: str, event: str, data: dict[str, Any]) -> str:
    redis = redis_connection()
    event_id = redis.xadd(
        event_stream_key(job_id),
        {
            "event": event,
            "data": json.dumps(data, ensure_ascii=False, default=str),
            "created_at": str(time.time()),
        },
        maxlen=settings.redis_event_max_length,
        approximate=True,
    )
    redis.expire(event_stream_key(job_id), settings.redis_event_ttl_seconds)
    return event_id.decode() if isinstance(event_id, bytes) else str(event_id)


def read_events(job_id: str, after_id: str, block_ms: int = 15000) -> list[dict]:
    rows = redis_connection().xread(
        {event_stream_key(job_id): after_id},
        count=50,
        block=block_ms,
    )
    events: list[dict] = []
    for _, messages in rows:
        for raw_id, raw_fields in messages:
            fields = {
                (key.decode() if isinstance(key, bytes) else str(key)): (
                    value.decode() if isinstance(value, bytes) else str(value)
                )
                for key, value in raw_fields.items()
            }
            events.append(
                {
                    "id": raw_id.decode() if isinstance(raw_id, bytes) else str(raw_id),
                    "event": fields.get("event", "progress"),
                    "data": json.loads(fields.get("data", "{}")),
                }
            )
    return events
