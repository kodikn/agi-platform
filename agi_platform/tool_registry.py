from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Final


@dataclass(frozen=True)
class ToolContract:
    name: str
    level: int
    purpose: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: tuple[str, ...]
    side_effects: bool
    risk: str
    mcp_kind: str = "tool"


TOOL_CONTRACTS: Final[tuple[ToolContract, ...]] = (
    ToolContract(
        name="memory.search",
        level=1,
        purpose="Retrieve ranked platform memories for agentic RAG context assembly.",
        input_schema={"query": "string", "limit": "integer"},
        output_schema={"results": "array"},
        permissions=("memory:read",),
        side_effects=False,
        risk="low",
    ),
    ToolContract(
        name="research.report",
        level=3,
        purpose="Build evidence-backed research reports with source trust metadata.",
        input_schema={"query": "string"},
        output_schema={"query": "string", "evidence": "array", "summary": "string"},
        permissions=("research:read", "network:restricted"),
        side_effects=False,
        risk="medium",
    ),
    ToolContract(
        name="analysis.code",
        level=5,
        purpose="Analyze source snippets for security and code-quality findings.",
        input_schema={"code": "string"},
        output_schema={"findings": "array", "summary": "object"},
        permissions=("analysis:run",),
        side_effects=False,
        risk="medium",
    ),
    ToolContract(
        name="sandbox.execute",
        level=7,
        purpose="Run approved commands inside a constrained sandbox profile.",
        input_schema={"command": "array", "timeout_seconds": "integer"},
        output_schema={"stdout": "string", "stderr": "string", "returncode": "integer"},
        permissions=("sandbox:execute",),
        side_effects=True,
        risk="high",
    ),
    ToolContract(
        name="governance.review",
        level=10,
        purpose="Record human approval decisions for risk-managed workflows.",
        input_schema={"decision_id": "integer", "approver": "string", "approved": "boolean"},
        output_schema={"decision": "object"},
        permissions=("governance:approve",),
        side_effects=True,
        risk="critical",
    ),
)


class ToolRegistry:
    def __init__(self, contracts: tuple[ToolContract, ...] = TOOL_CONTRACTS) -> None:
        self._contracts = {contract.name: contract for contract in contracts}

    def list_tools(self) -> dict[str, Any]:
        tools = [asdict(contract) for contract in self._contracts.values()]
        return {"count": len(tools), "tools": tools}

    def mcp_manifest(self) -> dict[str, Any]:
        return {
            "protocol": "mcp-compatible",
            "capabilities": {"tools": True, "resources": False, "prompts": False},
            "tools": [
                {
                    "name": contract.name,
                    "description": contract.purpose,
                    "input_schema": contract.input_schema,
                    "annotations": {
                        "level": contract.level,
                        "permissions": list(contract.permissions),
                        "side_effects": contract.side_effects,
                        "risk": contract.risk,
                    },
                }
                for contract in self._contracts.values()
            ],
        }
