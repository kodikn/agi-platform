from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agi_platform.agent_events import ActionEvent, EventLog, ObservationEvent


@dataclass
class SandboxLab:
    runs: list[dict[str, Any]] = field(default_factory=list)
    event_log: EventLog = field(default_factory=EventLog)

    def execute(self, command: list[str], timeout_seconds: int = 5) -> dict[str, Any]:
        action = self.event_log.append(ActionEvent(kind="sandbox.action", payload={"command": command, "timeout_seconds": timeout_seconds}, action="bash"))
        return self.execute_action(action, timeout_seconds).payload

    def execute_action(self, action: ActionEvent, timeout_seconds: int = 5) -> ObservationEvent:
        command = action.payload.get("command", [])
        started = time.perf_counter()
        if not command or command[0] not in {"python", "python3", "echo"}:
            observation = ObservationEvent(kind="sandbox.observation", payload={"error": "command is not allowed by sandbox policy", "command": command}, action_id=action.id, status="error")
            self.event_log.append(observation)
            raise ValueError(observation.payload["error"])
        with tempfile.TemporaryDirectory(prefix="agi-sandbox-") as workspace:
            completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=timeout_seconds, check=False)
            result = {"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "workspace_cleaned": not Path(workspace).exists(), "metrics": {"runtime_ms": round((time.perf_counter() - started) * 1000, 3)}}
        observation = ObservationEvent(kind="sandbox.observation", payload=result, action_id=action.id, status="ok" if completed.returncode == 0 else "error")
        self.runs.append(result)
        self.event_log.append(observation)
        return observation

    def events(self) -> list[dict[str, Any]]:
        return self.event_log.all()
