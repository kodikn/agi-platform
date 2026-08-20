from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field

from agi_platform.security import TenantContext


@dataclass
class AnalysisLayer:
    runs: list[dict] = field(default_factory=list)

    def analyze_code(self, code: str, language: str = "python", context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        findings: list[dict] = []
        if language == "python":
            try:
                ast.parse(code)
            except SyntaxError as exc:
                findings.append({"severity": "high", "rule": "python.syntax", "message": str(exc)})
        patterns = ((r"eval\(", "high", "python.eval"), (r"subprocess\.Popen\(.*shell=True", "high", "python.shell"), (r"password\s*=\s*['\"]", "medium", "secret.literal"))
        for pattern, severity, rule in patterns:
            if re.search(pattern, code):
                findings.append({"severity": severity, "rule": rule, "message": f"Detected {rule}"})
        result = {"tenant_id": context.tenant_id, "language": language, "findings": findings, "metrics": {"lines": len(code.splitlines()), "findings_count": len(findings)}}
        self.runs.append(result)
        return result

    def analyze_repository(self, files: dict[str, str], context: TenantContext | None = None) -> dict:
        if context is None:
            raise ValueError("tenant context is required")
        file_results = {path: self.analyze_code(content, "python" if path.endswith(".py") else "text", context) for path, content in files.items()}
        return {"files": file_results, "summary": {"files_analyzed": len(files), "findings_count": sum(result["metrics"]["findings_count"] for result in file_results.values())}}
