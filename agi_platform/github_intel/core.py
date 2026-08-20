from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from agi_platform.outbound import OutboundPolicy, SecureHTTPClient


@dataclass
class GitHubIntelligence:
    repositories: dict[str, dict[str, Any]] = field(default_factory=dict)
    timeout_seconds: float = 20.0

    def index_repository(self, url: str, dependencies: list[str] | None = None) -> dict[str, Any]:
        parsed = urlparse(url)
        parts = parsed.path.strip("/").removesuffix(".git").split("/")
        if parsed.netloc not in {"github.com", "www.github.com"} or len(parts) < 2:
            raise ValueError("expected a GitHub repository URL")
        full_name = f"{parts[0]}/{parts[1]}"
        headers = {"Accept": "application/vnd.github+json"}
        token = os.getenv("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        client = SecureHTTPClient(OutboundPolicy(allowed_domains=frozenset({"api.github.com"})))
        repo_response = client.get(f"https://api.github.com/repos/{full_name}", headers=headers)
        repo_response.raise_for_status()
        contributors_response = client.get(f"https://api.github.com/repos/{full_name}/contributors", params={"per_page": 10}, headers=headers)
        contributors_response.raise_for_status()
        repo = repo_response.json()
        record = {
            "full_name": repo["full_name"],
            "url": repo["html_url"],
            "description": repo.get("description"),
            "default_branch": repo.get("default_branch"),
            "stars": repo.get("stargazers_count", 0),
            "forks": repo.get("forks_count", 0),
            "open_issues": repo.get("open_issues_count", 0),
            "dependencies": dependencies or [],
            "contributors": [item.get("login") for item in contributors_response.json()],
        }
        self.repositories[full_name] = record
        return record

    def analyze(self, full_name: str) -> dict[str, Any]:
        repo = self.repositories[full_name]
        return {
            "repository": full_name,
            "dependency_count": len(repo["dependencies"]),
            "stars": repo["stars"],
            "open_issues": repo["open_issues"],
            "contributors": repo["contributors"],
            "knowledge": [
                f"{full_name} default branch is {repo['default_branch']}",
                f"{full_name} currently has {repo['stars']} stars and {repo['open_issues']} open issues",
            ],
        }
