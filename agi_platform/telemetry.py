from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator

SENSITIVE_FIELDS = {
    "api_key",
    "authorization",
    "token",
    "password",
    "secret",
    "cookie",
    "set-cookie",
}
CORRELATION_FIELDS = (
    "request_id",
    "trace_id",
    "tenant_id",
    "actor_id",
    "agent_id",
    "workflow_id",
    "run_id",
    "task_id",
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for field_name in CORRELATION_FIELDS:
            value = getattr(record, field_name, None)
            if value:
                payload[field_name] = value
        for key, value in record.__dict__.items():
            if (
                key in payload
                or key.startswith("_")
                or key
                in {
                    "args",
                    "asctime",
                    "created",
                    "exc_info",
                    "exc_text",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "message",
                    "msg",
                    "name",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "thread",
                    "threadName",
                }
            ):
                continue
            if key.lower() in SENSITIVE_FIELDS:
                payload[key] = "[REDACTED]"
            elif isinstance(value, (str, int, float, bool)) or value is None:
                payload[key] = value
        if record.exc_info:
            exc_type = record.exc_info[0]
            if exc_type is not None:
                payload["exception_type"] = exc_type.__name__
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def configure_json_logging() -> None:
    root = logging.getLogger()
    if any(
        isinstance(handler.formatter, JsonLogFormatter) for handler in root.handlers
    ):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root.handlers = [handler]
    root.setLevel(os.getenv("AGI_LOG_LEVEL", "INFO"))


def trace_id() -> str:
    return uuid.uuid4().hex


@dataclass
class TelemetryRegistry:
    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    histograms: dict[str, list[float]] = field(
        default_factory=lambda: defaultdict(list)
    )
    gauges: dict[str, float] = field(default_factory=dict)

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self.counters[self._key(name, labels)] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.histograms[self._key(name, labels)].append(value)

    def set_gauge(self, name: str, value: float, **labels: str) -> None:
        self.gauges[self._key(name, labels)] = value

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
            self.increment(f"{name}_success_total", 1.0, **labels)
        except Exception:
            self.increment(f"{name}_error_total", 1.0, **labels)
            raise
        finally:
            self.observe(
                f"{name}_latency_ms",
                round((time.perf_counter() - started) * 1000, 3),
                **labels,
            )

    def prometheus(self) -> str:
        lines: list[str] = []
        for key, value in sorted(self.counters.items()):
            lines.append(f"{key} {value}")
        for key, value in sorted(self.gauges.items()):
            lines.append(f"{key} {value}")
        for key, values in sorted(self.histograms.items()):
            if values:
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_sum {round(sum(values), 3)}")
                lines.append(f"{key}_avg {round(sum(values) / len(values), 3)}")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _key(name: str, labels: dict[str, str]) -> str:
        if not labels:
            return name
        label_text = ",".join(
            f'{key}="{value}"' for key, value in sorted(labels.items())
        )
        return f"{name}{{{label_text}}}"
