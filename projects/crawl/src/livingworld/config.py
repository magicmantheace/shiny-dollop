from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LIVINGWORLD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./livingworld.db"
    admin_key: str = "change-me"
    host: str = "127.0.0.1"
    port: int = 8000

    world_seed: str = "living-world-001"
    world_name: str = "Eldara"
    target_population: int = 10_000
    persistent_npcs: int = 100
    towns: int = 5
    villages: int = 20

    tick_seconds: float = 5.0
    game_hours_per_tick: int = 1
    allow_origins: Annotated[list[str], NoDecode] = ["http://127.0.0.1:5173", "http://localhost:5173"]

    ai_provider: str = "none"
    ai_base_url: str = "http://127.0.0.1:11434/v1"
    ai_api_key: str = ""
    ai_model: str = ""

    @field_validator("allow_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("target_population", "persistent_npcs", "towns", "villages", "game_hours_per_tick")
    @classmethod
    def positive_ints(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("must be greater than zero")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
