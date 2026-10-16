import time
import threading
from typing import Optional
import redis
from src.config import settings
from src.core.logging import logger


class InMemoryTokenBucket:
    """Thread-safe in-memory token bucket rate limiter."""

    def __init__(self, rate: float, capacity: float):
        self.rate = rate
        self.capacity = capacity
        self.tokens = capacity
        self.last_check = time.time()
        self._lock = threading.Lock()

    def acquire(self, tokens: float = 1.0, wait: bool = True) -> bool:
        while True:
            with self._lock:
                now = time.time()
                elapsed = now - self.last_check
                self.last_check = now
                self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True

                if not wait:
                    return False

                sleep_time = (tokens - self.tokens) / self.rate

            time.sleep(min(sleep_time, 1.0))


class DomainRateLimiter:
    """Per-domain rate limiter backed by Redis with local fallback."""

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis_client = redis_client
        self._local_buckets: dict[str, InMemoryTokenBucket] = {}
        self._lock = threading.Lock()

    def acquire(self, domain: str, rate: float = 5.0, capacity: float = 5.0, wait: bool = True) -> bool:
        if self.redis_client:
            try:
                return self._acquire_redis(domain, rate, capacity, wait)
            except Exception as e:
                logger.warning("Redis rate limiter failed, falling back to in-memory", domain=domain, error=str(e))

        return self._acquire_local(domain, rate, capacity, wait)

    def _acquire_local(self, domain: str, rate: float, capacity: float, wait: bool) -> bool:
        with self._lock:
            if domain not in self._local_buckets:
                self._local_buckets[domain] = InMemoryTokenBucket(rate=rate, capacity=capacity)
            bucket = self._local_buckets[domain]

        return bucket.acquire(1.0, wait=wait)

    def _acquire_redis(self, domain: str, rate: float, capacity: float, wait: bool) -> bool:
        key = f"ratelimit:{domain}"
        while True:
            now = time.time()
            # Redis pipeline to update tokens
            pipe = self.redis_client.pipeline()
            pipe.get(f"{key}:tokens")
            pipe.get(f"{key}:last")
            results = pipe.execute()

            raw_tokens, raw_last = results[0], results[1]
            if raw_tokens is None or raw_last is None:
                tokens = capacity
                last = now
            else:
                last = float(raw_last)
                elapsed = max(0.0, now - last)
                tokens = min(capacity, float(raw_tokens) + elapsed * rate)

            if tokens >= 1.0:
                tokens -= 1.0
                pipe = self.redis_client.pipeline()
                pipe.set(f"{key}:tokens", tokens, ex=3600)
                pipe.set(f"{key}:last", now, ex=3600)
                pipe.execute()
                return True

            if not wait:
                return False

            sleep_time = max(0.05, (1.0 - tokens) / rate)
            time.sleep(min(sleep_time, 1.0))


# Global rate limiter instance
try:
    _r = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_connect_timeout=1)
    rate_limiter = DomainRateLimiter(redis_client=_r)
except Exception:
    rate_limiter = DomainRateLimiter(redis_client=None)
