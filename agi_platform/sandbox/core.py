from __future__ import annotations

import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SandboxLab:
    runs: list[dict] = field(default_factory=list)

    def execute(self, command: list[str], timeout_seconds: int = 5) -> dict:
        if not command or command[0] not in {"python", "python3", "echo"}:
            raise ValueError("command is not allowed by sandbox policy")
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="agi-sandbox-") as workspace:
            completed = subprocess.run(command, cwd=workspace, capture_output=True, text=True, timeout=timeout_seconds, check=False)
            result = {"command": command, "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr, "workspace_cleaned": not Path(workspace).exists(), "metrics": {"runtime_ms": round((time.perf_counter() - started) * 1000, 3)}}
        self.runs.append(result)
        return result
