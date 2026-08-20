from __future__ import annotations

import importlib
from dataclasses import dataclass

from .catalog import PLATFORM_LEVELS


IMPLEMENTATION_MODULES = {
    0: "agi_platform.llm.core",
    1: "agi_platform.memory.core",
    2: "agi_platform.guardian.core",
    3: "agi_platform.research.core",
    4: "agi_platform.chinese_hub.core",
    5: "agi_platform.analysis.core",
    6: "agi_platform.github_intel.core",
    7: "agi_platform.sandbox.core",
    8: "agi_platform.knowledge_graph.core",
    9: "agi_platform.orchestration",
    10: "agi_platform.governance.core",
    11: "agi_platform.evolution.core",
}


@dataclass(frozen=True)
class ReadinessCriterion:
    name: str
    passed: bool
    detail: str


def level_readiness() -> list[dict]:
    results: list[dict] = []
    for level in PLATFORM_LEVELS:
        module_name = IMPLEMENTATION_MODULES[level.level]
        criteria = [
            _module_imports(module_name),
            ReadinessCriterion("api_surface", bool(level.api), ", ".join(level.api)),
            ReadinessCriterion("database_schema", bool(level.database), ", ".join(level.database)),
            ReadinessCriterion("observability", bool(level.metrics), ", ".join(level.metrics)),
            ReadinessCriterion("security_controls", bool(level.security), ", ".join(level.security)),
        ]
        results.append({"level": level.level, "name": level.name, "status": "ready" if all(item.passed for item in criteria) else "not-ready", "criteria": [item.__dict__ for item in criteria]})
    return results


def platform_ready() -> dict:
    levels = level_readiness()
    return {"status": "ready" if all(level["status"] == "ready" for level in levels) else "not-ready", "levels": levels}


def _module_imports(module_name: str) -> ReadinessCriterion:
    try:
        importlib.import_module(module_name)
    except Exception as exc:
        return ReadinessCriterion("implementation", False, str(exc))
    return ReadinessCriterion("implementation", True, module_name)
