"""
DataGhost – application configuration.
Reads settings from environment variables or a .env file via pydantic-settings.
"""
import os
import tempfile
from typing import Optional, List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    DATABASE_URL: str = "sqlite:///./dataghost.db"
    REDIS_URL: str = "redis://localhost:6379"
    SECRET_KEY: str = "supersecretkey-change-in-production-at-least-32-chars"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    ENVIRONMENT: str = "development"

    @property
    def effective_database_url(self) -> str:
        url = self.DATABASE_URL
        if url.startswith("sqlite"):
            is_vercel = os.environ.get("VERCEL") == "1" or os.environ.get("VERCEL_ENV") is not None
            if is_vercel:
                tmp_db = os.path.join(tempfile.gettempdir(), "dataghost.db")
                return f"sqlite:///{tmp_db}"
            db_file_path = url.replace("sqlite:///", "")
            dir_path = os.path.dirname(db_file_path) or "."
            if not os.access(dir_path, os.W_OK):
                tmp_db = os.path.join(tempfile.gettempdir(), "dataghost.db")
                return f"sqlite:///{tmp_db}"
        return url

    # Multi-Device Management Configuration
    DEVICE_HEARTBEAT_TIMEOUT_SECONDS: int = 120
    ENROLLMENT_TOKEN_EXPIRE_MINUTES: int = 10
    SERVER_PUBLIC_URL: str = "http://localhost:8000"
    ANDROID_DPC_CERT_CHECKSUM: str = "oEK0v2z9Hsw3DZ8FzCP1m8XQAx4kymZ-uFSGS9Py7LY"

    # Frontend URLs for CORS
    FRONTEND_URL: Optional[str] = "http://localhost:3000"
    TUNNEL_FRONTEND_URL: Optional[str] = None

    # CORS Configuration
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "https://inc1.devtunnels.ms",
        "https://dataghost.vercel.app",
        "https://dataghost-git-main-nagesh17.vercel.app",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    parsed = json.loads(v)
                    if isinstance(parsed, list):
                        return [str(item).strip().rstrip("/") for item in parsed if str(item).strip()]
                except Exception:
                    pass
            return [item.strip().rstrip("/") for item in v.split(",") if item.strip()]
        elif isinstance(v, (list, tuple, set)):
            return [str(item).strip().rstrip("/") for item in v if str(item).strip()]
        return v

    @property
    def all_cors_origins(self) -> List[str]:
        origins = list(self.CORS_ORIGINS) if isinstance(self.CORS_ORIGINS, list) else []
        if self.FRONTEND_URL:
            origins.append(self.FRONTEND_URL.strip().rstrip("/"))
        if self.TUNNEL_FRONTEND_URL:
            origins.append(self.TUNNEL_FRONTEND_URL.strip().rstrip("/"))
        if self.SERVER_PUBLIC_URL:
            origins.append(self.SERVER_PUBLIC_URL.strip().rstrip("/"))
        return list(dict.fromkeys(origins))


    # Firebase Admin Configuration

    FIREBASE_CREDENTIALS_PATH: Optional[str] = None
    FIREBASE_CREDENTIALS_JSON: Optional[str] = None
    FIREBASE_PROJECT_ID: Optional[str] = "dataghost-9431f"


settings = Settings()


