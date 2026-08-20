from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    limit_per_minute: int
    windows: dict[str, deque[float]] = field(default_factory=lambda: defaultdict(deque))

    def allow(self, identity: str) -> bool:
        now = time.time()
        window = self.windows[identity]
        while window and now - window[0] >= 60:
            window.popleft()
        if len(window) >= self.limit_per_minute:
            return False
        window.append(now)
        return True


def security_headers() -> dict[str, str]:
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        "Cache-Control": "no-store",
    }


def apply_production_headers(response, service_name: str):
    for key, value in security_headers().items():
        response.headers[key] = value
    response.headers["X-Service-Name"] = service_name
    return response


def public_paths() -> set[str]:
    return {"/", "/health", "/live", "/ready", "/metrics", "/docs", "/openapi.json", "/redoc"}
