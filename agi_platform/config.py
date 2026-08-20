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

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            environment=os.getenv("AGI_ENV", "production"),
            service_name=os.getenv("AGI_SERVICE_NAME", "agi-platform"),
            api_key=os.getenv("AGI_API_KEY"),
            rate_limit_per_minute=int(os.getenv("AGI_RATE_LIMIT_PER_MINUTE", "120")),
            database_url=os.getenv("DATABASE_URL", "postgresql://agi:agi@postgres:5432/agi"),
            qdrant_url=os.getenv("QDRANT_URL", "http://qdrant:6333"),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://neo4j:7687"),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        )


settings = Settings.from_env()
