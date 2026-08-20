from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field


@dataclass
class AnalysisLayer:
    runs: list[dict] = field(default_factory=list)

    def analyze_code(self, code: str, language: str = "python") -> dict:
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
        result = {"language": language, "findings": findings, "metrics": {"lines": len(code.splitlines()), "findings_count": len(findings)}}
        self.runs.append(result)
        return result

    def analyze_repository(self, files: dict[str, str]) -> dict:
        file_results = {path: self.analyze_code(content, "python" if path.endswith(".py") else "text") for path, content in files.items()}
        return {"files": file_results, "summary": {"files_analyzed": len(files), "findings_count": sum(result["metrics"]["findings_count"] for result in file_results.values())}}
