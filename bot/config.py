from pathlib import Path
from typing import List, Optional, Any

from pydantic import SecretStr, field_validator, BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

env_path = Path(__file__).parent.parent / ".env"

class Rewards(BaseModel):
    referral_bonus: int = 250
    add_car: int = 100
    add_reminder: int = 100
    fill_profile: int = 500
    mileage_allowance_per_day: int = 1000  # in km
    km_per_nut: int = 10

class Settings(BaseSettings):
    """Application settings."""
    bot_token: SecretStr
    admin_ids: Optional[List[int]] = None
    rewards: Rewards = Rewards()
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