from __future__ import annotations

import time
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class TelemetryRegistry:
    counters: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))

    def increment(self, name: str, value: float = 1.0, **labels: str) -> None:
        self.counters[self._key(name, labels)] += value

    def observe(self, name: str, value: float, **labels: str) -> None:
        self.histograms[self._key(name, labels)].append(value)

    @contextmanager
    def timer(self, name: str, **labels: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
            self.increment(f"{name}_success_total", **labels)
        except Exception:
            self.increment(f"{name}_error_total", **labels)
            raise
        finally:
            self.observe(f"{name}_latency_ms", round((time.perf_counter() - started) * 1000, 3), **labels)

    def prometheus(self) -> str:
        lines: list[str] = []
        for key, value in sorted(self.counters.items()):
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
        label_text = ",".join(f'{key}="{value}"' for key, value in sorted(labels.items()))
        return f"{name}{{{label_text}}}"
