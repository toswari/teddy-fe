"""Configuration helpers for VideoLogoDetection."""
from __future__ import annotations

import os
from dataclasses import dataclass


def get_config(name: str | None) -> type[BaseConfig]:
    lookup = {
        "development": DevelopmentConfig,
        "production": ProductionConfig,
        "test": TestConfig,
    }
    if name is None:
        name = os.getenv("APP_ENV", "development")
    return lookup.get(name.lower(), DevelopmentConfig)


@dataclass
class BaseConfig:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "videologo-dev")
    SQLALCHEMY_DATABASE_URI: str = os.getenv(
        "DATABASE_URL",
        "postgresql://videologo_user:videologo_pass@localhost:35432/videologo_db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
    AUTO_CREATE_SCHEMA: bool = os.getenv("AUTO_CREATE_SCHEMA", "true").lower() == "true"
    PROJECT_MEDIA_ROOT: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "media"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")
    LMSTUDIO_BASE_URL: str = os.getenv("LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    LMSTUDIO_API_KEY: str = os.getenv("LMSTUDIO_API_KEY", "lm-studio")


class DevelopmentConfig(BaseConfig):
    DEBUG: bool = True


class ProductionConfig(BaseConfig):
    DEBUG: bool = False
    AUTO_CREATE_SCHEMA: bool = False


class TestConfig(BaseConfig):
    TESTING: bool = True
    AUTO_CREATE_SCHEMA: bool = True
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
