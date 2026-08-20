from __future__ import annotations

import os
import resource
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from agi_platform.security import TenantContext


_ALLOWED_COMMANDS = {"python", "python3", "echo"}
_SAFE_ENV = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"}


@dataclass(frozen=True)
class SandboxPolicy:
    allowed_commands: frozenset[str] = frozenset(_ALLOWED_COMMANDS)
    timeout_seconds: int = 5
    max_timeout_seconds: int = 10
    cpu_seconds: int = 2
    memory_bytes: int = 128 * 1024 * 1024
    max_output_bytes: int = 64 * 1024
    network: str = "host-disabled-by-policy"

    def validate(self, command: list[str], timeout_seconds: int) -> int:
        if not command or command[0] not in self.allowed_commands:
            raise ValueError("command is not allowed by sandbox policy")
        if timeout_seconds < 1:
            raise ValueError("timeout must be at least 1 second")
        return min(timeout_seconds, self.max_timeout_seconds)

    def as_dict(self) -> dict:
        return {
            "allowed_commands": sorted(self.allowed_commands),
            "max_timeout_seconds": self.max_timeout_seconds,
            "cpu_seconds": self.cpu_seconds,
            "memory_bytes": self.memory_bytes,
            "max_output_bytes": self.max_output_bytes,
            "network": self.network,
        }


@dataclass
class SandboxLab:
    runs: list[dict] = field(default_factory=list)
    policy: SandboxPolicy = field(default_factory=SandboxPolicy)

    def execute(self, command: list[str], timeout_seconds: int = 5, context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        timeout = self.policy.validate(command, timeout_seconds)
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix="agi-sandbox-") as workspace:
            workspace_path = Path(workspace)
            try:
                completed = subprocess.run(
                    command,
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                    check=False,
                    env=_SAFE_ENV,
                    preexec_fn=self._apply_process_limits,
                )
                stdout = completed.stdout[: self.policy.max_output_bytes]
                stderr = completed.stderr[: self.policy.max_output_bytes]
                result = {
                    "tenant_id": context.tenant_id,
                    "command": command,
                    "returncode": completed.returncode,
                    "stdout": stdout,
                    "stderr": stderr,
                    "timed_out": False,
                    "workspace_cleaned": not workspace_path.exists(),
                    "policy": self.policy.as_dict(),
                    "metrics": {"runtime_ms": round((time.perf_counter() - started) * 1000, 3)},
                }
            except subprocess.TimeoutExpired as exc:
                result = {
                    "tenant_id": context.tenant_id,
                    "command": command,
                    "returncode": 124,
                    "stdout": (exc.stdout or "")[: self.policy.max_output_bytes],
                    "stderr": (exc.stderr or "")[: self.policy.max_output_bytes],
                    "timed_out": True,
                    "workspace_cleaned": not workspace_path.exists(),
                    "policy": self.policy.as_dict(),
                    "metrics": {"runtime_ms": round((time.perf_counter() - started) * 1000, 3)},
                }
        result["workspace_cleaned"] = True
        self.runs.append(result)
        return result

    def capability_check(self) -> dict:
        from agi_platform.security import TenantContext

        result = self.execute(["echo", "sandbox-ready"], timeout_seconds=1, context=TenantContext("capability-check", "system", "capability-check", frozenset(), frozenset({"*"})))
        return {"status": "ready" if result["stdout"] == "sandbox-ready\n" else "not-ready", "result": result}

    def _apply_process_limits(self) -> None:
        os.setsid()
        resource.setrlimit(resource.RLIMIT_CPU, (self.policy.cpu_seconds, self.policy.cpu_seconds))
        resource.setrlimit(resource.RLIMIT_AS, (self.policy.memory_bytes, self.policy.memory_bytes))
        resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
        resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
