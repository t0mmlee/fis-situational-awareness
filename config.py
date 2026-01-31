"""
FIS Situational Awareness System - Configuration Module

Manages all configuration via environment variables and provides
type-safe configuration objects.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn, RedisDsn


class DatabaseSettings(BaseSettings):
    """PostgreSQL database configuration."""

    url: PostgresDsn = Field(
        default="postgresql://fis_user:fis_pass@localhost:5432/fis_awareness",
        description="PostgreSQL connection string"
    )
    pool_size: int = Field(default=10, description="Connection pool size")
    max_overflow: int = Field(default=20, description="Max overflow connections")
    echo: bool = Field(default=False, description="Echo SQL queries (debug mode)")

    model_config = SettingsConfigDict(env_prefix="DATABASE_")


class RedisSettings(BaseSettings):
    """Redis cache configuration."""

    url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="Redis connection string"
    )
    ttl_seconds: int = Field(default=3600, description="Default cache TTL")

    model_config = SettingsConfigDict(env_prefix="REDIS_")


class TemporalSettings(BaseSettings):
    """Temporal workflow engine configuration."""

    host: str = Field(default="localhost:7233", description="Temporal server host")
    namespace: str = Field(default="fis-awareness", description="Temporal namespace")
    task_queue: str = Field(default="fis-ingestion", description="Task queue name")
    api_key: Optional[str] = Field(default=None, description="Temporal Cloud API key")

    model_config = SettingsConfigDict(env_prefix="TEMPORAL_")


class MCPSettings(BaseSettings):
    """Tribe MCP server configuration."""

    server_path: str = Field(
        default="uvx",
        description="Path to MCP server executable"
    )
    server_args: list[str] = Field(
        default=["mcp-server-tribe"],
        description="MCP server arguments"
    )

    model_config = SettingsConfigDict(env_prefix="MCP_")


class IngestionSettings(BaseSettings):
    """Data ingestion configuration."""

    interval_days: int = Field(
        default=3,
        description="Days between ingestion cycles"
    )
    batch_size: int = Field(
        default=100,
        description="Batch size for processing items"
    )
    max_retries: int = Field(
        default=3,
        description="Max retry attempts for failed operations"
    )

    # Slack configuration
    slack_channels: list[str] = Field(
        default=[],
        description="Specific Slack channels to monitor (empty = search all)"
    )
    slack_search_query: str = Field(
        default="FIS",
        description="Slack search query"
    )

    # Notion configuration
    notion_main_hub_id: str = Field(
        default="2c04f38daa208021ae9efbab622bc6d9",
        description="FIS Strategic Enterprise AI Delivery Plan page ID"
    )
    notion_stakeholders_id: str = Field(
        default="2d84f38daa20807eaa0df706cf5438de",
        description="FIS Stakeholders Database page ID"
    )
    notion_search_tag: str = Field(
        default="FIS",
        description="Notion search tag"
    )

    # External sources configuration
    news_sources: list[str] = Field(
        default=[
            "bloomberg.com",
            "reuters.com",
            "wsj.com",
            "ft.com"
        ],
        description="Prioritized news sources"
    )
    sec_cik: str = Field(
        default="0001136893",
        description="FIS SEC CIK number"
    )

    model_config = SettingsConfigDict(env_prefix="INGESTION_")


class AlertingSettings(BaseSettings):
    """Alerting configuration."""

    channel_id: str = Field(
        ...,
        description="Slack channel ID for alerts (#fis-situational-awareness)"
    )
    significance_threshold: int = Field(
        default=75,
        description="Minimum significance score to trigger alert (CRITICAL only)"
    )
    dedup_window_hours: int = Field(
        default=24,
        description="Hours to check for duplicate alerts"
    )
    max_alerts_per_day: int = Field(
        default=20,
        description="Maximum alerts to send per day (rate limit)"
    )

    model_config = SettingsConfigDict(env_prefix="ALERT_")


class AISettings(BaseSettings):
    """AI/LLM configuration for entity extraction."""

    provider: str = Field(
        default="anthropic",
        description="AI provider (openai or anthropic)"
    )
    model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Model to use for entity extraction"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for AI provider"
    )
    azure_endpoint: Optional[str] = Field(
        default=None,
        description="Azure OpenAI endpoint (if using Azure)"
    )
    temperature: float = Field(
        default=0.0,
        description="Temperature for AI responses"
    )
    max_tokens: int = Field(
        default=4000,
        description="Max tokens for AI responses"
    )

    model_config = SettingsConfigDict(env_prefix="AI_")


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""

    prometheus_port: int = Field(
        default=9090,
        description="Prometheus metrics port"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)"
    )
    log_format: str = Field(
        default="json",
        description="Log format (json or text)"
    )

    model_config = SettingsConfigDict(env_prefix="MONITORING_")


class Config(BaseSettings):
    """Main application configuration."""

    # Environment
    environment: str = Field(
        default="development",
        description="Environment (development, staging, production)"
    )
    debug: bool = Field(
        default=False,
        description="Debug mode"
    )

    # Sub-configurations
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    temporal: TemporalSettings = Field(default_factory=TemporalSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    ingestion: IngestionSettings = Field(default_factory=IngestionSettings)
    alerting: AlertingSettings = Field(default_factory=AlertingSettings)
    ai: AISettings = Field(default_factory=AISettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


# Global configuration instance
config = Config()
