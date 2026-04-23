from pathlib import Path

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
    YamlConfigSettingsSource,
    PydanticBaseSettingsSource,
)
from pydantic import BaseModel

# Project root directory (where config.yaml and .env are located)
PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Secret settings loaded from .env file or environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        extra="ignore",
    )

    finnhub_api_key: str
    twelvedata_api_key: str


class StocksConfig(BaseModel):
    """Configuration for stocks: tickers to monitor and fetch intervals."""

    tickers: list[str]
    fetch_interval_seconds: int


class StreamConfig(BaseModel):
    """Configuration for data stream: window size and anomaly detection threshold."""

    rolling_window_size: int
    anomaly_z_threshold: float


class KafkaConfig(BaseModel):
    bootstrap_servers: str


class RawTickerProducerConfig(BaseModel):
    """Kafka producer configuration for raw ticker data."""

    client_id: str
    allow_auto_create_topics: bool


class RawTickerConsumerConfig(BaseModel):
    """Kafka consumer configuration for raw ticker data."""

    group_id: str
    client_id: str
    auto_offset_reset: str
    enable_auto_commit: bool
    allow_auto_create_topics: bool


class AnomalyProducerConfig(BaseModel):
    """Kafka producer configuration for anomaly data."""

    client_id: str
    allow_auto_create_topics: bool


class AnomalyConsumerConfig(BaseModel):
    """Kafka consumer configuration for anomaly data."""

    group_id: str
    client_id: str
    auto_offset_reset: str
    enable_auto_commit: bool
    allow_auto_create_topics: bool


class TopicConfig(BaseModel):
    """Kafka topic configuration."""

    num_partitions: int
    replication_factor: int


class AnomalyLlmConfig(BaseModel):
    """Configuration for the LLM used in anomaly analysis."""

    provider: str
    model: str


class AppConfig(BaseSettings):
    """Application configuration loaded from config.yaml."""

    model_config = SettingsConfigDict(
        yaml_file=str(PROJECT_ROOT / "config.yaml"),
        extra="ignore",
    )

    stocks: StocksConfig
    stream: StreamConfig
    kafka: KafkaConfig
    raw_ticker_producer: RawTickerProducerConfig
    raw_ticker_consumer: RawTickerConsumerConfig
    anomaly_producer: AnomalyProducerConfig
    anomaly_consumer: AnomalyConsumerConfig
    topics: dict[str, TopicConfig]
    anomaly_llm: AnomalyLlmConfig

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (YamlConfigSettingsSource(settings_cls),)


def get_config() -> tuple[AppConfig, Settings]:
    """Return the application config from YAML and secret settings from .env/env vars."""
    return (AppConfig(), Settings())


app_config, settings = get_config()
