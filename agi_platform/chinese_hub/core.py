from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from agi_platform.outbound import SecureHTTPClient


@dataclass
class ChineseResearchHub:
    articles: list[dict[str, Any]] = field(default_factory=list)
    timeout_seconds: float = 20.0

    def ingest(self, title: str, body: str, script: str = "simplified") -> dict[str, Any]:
        translation = self._translate(body)
        classification = self._classify(body)
        iocs = re.findall(r"(?:\d{1,3}\.){3}\d{1,3}|[a-fA-F0-9]{32,64}|CVE-\d{4}-\d+", body, flags=re.IGNORECASE)
        article = {
            "id": len(self.articles) + 1,
            "title": title,
            "script": script,
            "original": body,
            "translated": translation["text"],
            "translation_provider": translation["provider"],
            "translation_status": translation["status"],
            "classification": classification,
            "iocs": iocs,
        }
        self.articles.append(article)
        return article

    def _translate(self, text: str) -> dict[str, str]:
        endpoint = os.getenv("LIBRETRANSLATE_URL")
        api_key = os.getenv("LIBRETRANSLATE_API_KEY")
        if not endpoint:
            return {"text": text, "provider": "none-configured", "status": "untranslated"}
        payload = {"q": text, "source": "zh", "target": "en", "format": "text"}
        if api_key:
            payload["api_key"] = api_key
        client = SecureHTTPClient()
        response = client.post(f"{endpoint.rstrip('/')}/translate", json=payload)
        response.raise_for_status()
        return {"text": response.json()["translatedText"], "provider": "libretranslate", "status": "translated"}

    @staticmethod
    def _classify(text: str) -> str:
        threat_terms = ("威胁", "漏洞", "攻击", "木马", "恶意软件", "后门", "勒索", "CVE")
        return "threat-intelligence" if any(term in text for term in threat_terms) else "general-research"
