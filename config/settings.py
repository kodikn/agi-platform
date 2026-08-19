"""Application settings and configuration"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class DatabaseSettings(BaseSettings):
    """Database configuration"""
    host: str = "localhost"
    port: int = 5432
    user: str = "agi_user"
    password: str = "agi_password"
    database: str = "agi_platform"
    echo: bool = False
    pool_size: int = 20
    max_overflow: int = 0

    class Config:
        env_prefix = "POSTGRES_"


class RedisSettings(BaseSettings):
    """Redis configuration"""
    host: str = "localhost"
    port: int = 6379
    db: int = 0
    password: Optional[str] = None

    class Config:
        env_prefix = "REDIS_"


class Neo4jSettings(BaseSettings):
    """Neo4j configuration"""
    host: str = "localhost"
    port: int = 7687
    user: str = "neo4j"
    password: str = "neo4j_password"
    database: str = "neo4j"

    class Config:
        env_prefix = "NEO4J_"


class QdrantSettings(BaseSettings):
    """Qdrant configuration"""
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "agi_memory"

    class Config:
        env_prefix = "QDRANT_"


class LLMSettings(BaseSettings):
    """LLM provider configuration"""
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"
    default_model: str = "gpt-4"
    fallback_model: str = "claude-3-opus"

    class Config:
        env_prefix = ""


class CelerySettings(BaseSettings):
    """Celery configuration"""
    broker_url: str = "amqp://guest:guest@localhost:5672//"
    result_backend: str = "redis://localhost:6379/0"
    task_serializer: str = "json"
    accept_content: list = ["json"]
    result_serializer: str = "json"
    timezone: str = "UTC"
    enable_utc: bool = True

    class Config:
        env_prefix = "CELERY_"


class SecuritySettings(BaseSettings):
    """Security configuration"""
    jwt_secret_key: str = "your-secret-key-here"
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 24

    class Config:
        env_prefix = "JWT_"


class Settings(BaseSettings):
    """Main application settings"""
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    api_title: str = "AGI Platform API"
    api_version: str = "0.1.0"

    # Sub-settings
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    neo4j: Neo4jSettings = Neo4jSettings()
    qdrant: QdrantSettings = QdrantSettings()
    llm: LLMSettings = LLMSettings()
    celery: CelerySettings = CelerySettings()
    security: SecuritySettings = SecuritySettings()

    # Environment
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
