
import pytest
from redis.exceptions import RedisError

from agi_platform.security import (
    DependencyError,
    RedisDistributedLock,
    RedisRateLimiter,
    RateLimitError,
    RateLimitRule,
)


class FakePipeline:
    def __init__(self, store):
        self.store = store
        self.ops = []

    def incr(self, key):
        self.ops.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.ops.append(("expire", key))
        return self

    def execute(self):
        out = []
        for op, key in self.ops:
            if op == "incr":
                self.store[key] = self.store.get(key, 0) + 1
                out.append(self.store[key])
            else:
                out.append(True)
        return out


class FakeRedis:
    def __init__(self, fail=False):
        self.store = {}
        self.fail = fail

    def pipeline(self):
        if self.fail:
            raise RedisError("redis://secret:pass@localhost/0 failed")
        return FakePipeline(self.store)

    def set(self, key, value, nx=False, px=None):
        if self.fail:
            raise RedisError("down")
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def eval(self, script, n, key, owner):
        if self.store.get(key) == owner:
            del self.store[key]
            return 1
        return 0


def test_redis_rate_limit_shared_across_replicas():
    redis_client = FakeRedis()
    replica_a = RedisRateLimiter("redis://unused", 2, client=redis_client)
    replica_b = RedisRateLimiter("redis://unused", 2, client=redis_client)
    rule = [RateLimitRule("tenant:t1", 2)]
    replica_a.check(rule, "r1")
    replica_b.check(rule, "r2")
    with pytest.raises(RateLimitError):
        replica_a.check(rule, "r3")


def test_security_sensitive_rate_limit_fails_closed_when_redis_unavailable():
    limiter = RedisRateLimiter("redis://unused", 10, client=FakeRedis(fail=True))
    with pytest.raises(DependencyError):
        limiter.check([RateLimitRule("api_key:k", 10, fail_closed=True)], "rid")


def test_non_sensitive_rate_limit_can_explicitly_fail_open():
    limiter = RedisRateLimiter("redis://unused", 10, client=FakeRedis(fail=True))
    limiter.check([RateLimitRule("ip:dev", 10, fail_closed=False)], "rid")


def test_distributed_lock_ownership_and_safe_release():
    client = FakeRedis()
    locks = RedisDistributedLock("redis://unused", client=client)
    handle = locks.acquire("github:index", ttl_ms=1000, timeout_ms=10)
    assert client.store["lock:github:index"] == handle.owner
    assert locks.release(handle) is True
    assert locks.release(handle) is False


def test_duplicate_worker_execution_is_prevented_by_lock_timeout():
    client = FakeRedis()
    first = RedisDistributedLock("redis://unused", client=client)
    second = RedisDistributedLock("redis://unused", client=client)
    first.acquire("job:1", ttl_ms=1000, timeout_ms=10)
    with pytest.raises(Exception):
        second.acquire("job:1", ttl_ms=1000, timeout_ms=25, retry_ms=5)
