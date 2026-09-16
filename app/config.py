from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Gemini API Settings
    gemini_api_key: str = "mock"
    gemini_model: str = "gemini-2.5-flash"

    # Database Configuration (SQLite default, easily swappable with PostgreSQL URL)
    database_url: str = "sqlite:///./potholes.db"

    # Proximity matching radius in meters
    matching_radius_meters: float = 15.0

    # Local storage directory path
    storage_dir: str = "./uploads"

    # Server settings
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Allowed image MIME types
    allowed_image_types: List[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/jpg",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
