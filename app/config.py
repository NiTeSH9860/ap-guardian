"""
Central configuration. All model IDs and endpoints are defined here so that
swapping a Nebius Token Factory model is a one-line change, never a code change.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Nebius Token Factory (OpenAI-compatible endpoint)
    nebius_api_key: str = ""
    nebius_base_url: str = "https://api.tokenfactory.nebius.com/v1"

    # Model routing — cheap/high-volume model for extraction,
    # expensive/low-volume model for the reasoning that actually matters.
    nebius_extraction_model: str = "nvidia/Nemotron-3_5-Lightning"
    nebius_reconciliation_model: str = "nvidia/Nemotron-3-Ultra"
    nebius_embedding_model: str = "Qwen/Qwen3-Embedding-8B"

    # Optional vendor legitimacy check
    tavily_api_key: str = ""

    # App
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()