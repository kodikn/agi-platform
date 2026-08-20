from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    environment: str
    service_name: str
    api_key: str | None
    rate_limit_per_minute: int
    database_url: str
    qdrant_url: str
    neo4j_uri: str
    redis_url: str
    tencentdb_memory_enabled: bool
    tencentdb_memory_base_url: str
    tencentdb_memory_api_key: str | None
    tencentdb_memory_team_id: str | None
    tencentdb_memory_timeout_seconds: int
    local_llm_base_url: str
    local_llm_model: str
    local_llm_api_key: str | None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("AGI_ENV", "production"),
            service_name=os.getenv("AGI_SERVICE_NAME", "agi-platform"),
            api_key=os.getenv("AGI_API_KEY"),
            rate_limit_per_minute=_int_env("AGI_RATE_LIMIT_PER_MINUTE", 120),
            database_url=os.getenv("DATABASE_URL", "postgresql://agi:agi@postgres:5432/agi"),
            qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            tencentdb_memory_enabled=os.getenv("TENCENTDB_MEMORY_ENABLED", "false").lower() in {"1", "true", "yes", "on"},
            tencentdb_memory_base_url=os.getenv("TENCENTDB_MEMORY_BASE_URL", ""),
            tencentdb_memory_api_key=os.getenv("TENCENTDB_MEMORY_API_KEY"),
            tencentdb_memory_team_id=os.getenv("TENCENTDB_MEMORY_TEAM_ID"),
            tencentdb_memory_timeout_seconds=_int_env("TENCENTDB_MEMORY_TIMEOUT_SECONDS", 3),
            local_llm_base_url=os.getenv("LOCAL_LLM_BASE_URL", ""),
            local_llm_model=os.getenv("LOCAL_LLM_MODEL", "local-model"),
            local_llm_api_key=os.getenv("LOCAL_LLM_API_KEY"),
        )


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


settings = Settings.from_env()
