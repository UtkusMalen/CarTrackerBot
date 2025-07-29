from pathlib import Path
from typing import List, Optional, Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

env_path = Path(__file__).parent.parent / ".env"

class Settings(BaseSettings):
    """Application settings."""
    bot_token: SecretStr
    admin_ids: Optional[List[int]] = None
    mileage_update_reminder_days: int = 1

    @field_validator("admin_ids", mode="before")
    @classmethod
    def split_admin_ids(cls, v: Any) -> Optional[List[int]]:
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        return v

    model_config = SettingsConfigDict(
        env_file=env_path,
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
    )

config = Settings()