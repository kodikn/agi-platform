from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ResearchLayer:
    reports: list[dict[str, Any]] = field(default_factory=list)
    timeout_seconds: float = 20.0

    def query(self, query: str, sources: list[str] | None = None) -> dict[str, Any]:
        sources = sources or ["github", "osv"]
        evidence: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        with httpx.Client(timeout=self.timeout_seconds) as client:
            for source in sources:
                try:
                    evidence.extend(self._collect_source(client, source, query))
                except httpx.HTTPError as exc:
                    errors.append({"source": source, "error": str(exc)})
        iocs = sorted(set(re.findall(r"(?:\d{1,3}\.){3}\d{1,3}|[a-fA-F0-9]{32,64}|CVE-\d{4}-\d+", query, flags=re.IGNORECASE)))
        trust_score = round(sum(item["trust_score"] for item in evidence) / len(evidence), 3) if evidence else 0.0
        return {"query": query, "evidence": evidence, "iocs": iocs, "trust_score": trust_score, "errors": errors}

    def report(self, query: str) -> dict[str, Any]:
        result = self.query(query)
        report = {"query": query, "summary": self._summary(result), **result}
        self.reports.append(report)
        return report

    def _collect_source(self, client: httpx.Client, source: str, query: str) -> list[dict[str, Any]]:
        if source == "github":
            headers = {"Accept": "application/vnd.github+json"}
            token = os.getenv("GITHUB_TOKEN")
            if token:
                headers["Authorization"] = f"Bearer {token}"
            response = client.get("https://api.github.com/search/repositories", params={"q": query, "per_page": 3}, headers=headers)
            response.raise_for_status()
            return [
                {"source": "github", "title": item["full_name"], "url": item["html_url"], "trust_score": 0.7, "metadata": {"stars": item.get("stargazers_count", 0), "description": item.get("description")}}
                for item in response.json().get("items", [])
            ]
        if source == "osv":
            response = client.post("https://api.osv.dev/v1/query", json={"package": {"name": query}})
            response.raise_for_status()
            return [
                {"source": "osv", "title": vuln.get("id"), "url": vuln.get("database_specific", {}).get("url"), "trust_score": 0.9, "metadata": vuln}
                for vuln in response.json().get("vulns", [])[:3]
            ]
        raise ValueError(f"unsupported research source: {source}")

    @staticmethod
    def _summary(result: dict[str, Any]) -> str:
        if result["evidence"]:
            sources = sorted({item["source"] for item in result["evidence"]})
            return f"Found {len(result['evidence'])} evidence items from {', '.join(sources)}."
        return "No evidence returned by configured live sources."
