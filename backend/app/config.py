from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables and .env file.
    """
    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LiveKit credentials
    livekit_url: str = Field(
        default="",
        validation_alias="LIVEKIT_URL",
        description="LiveKit WebRTC Server URL (e.g. wss://project.livekit.cloud)",
    )
    livekit_api_key: str = Field(
        default="",
        validation_alias="LIVEKIT_API_KEY",
        description="LiveKit API Key",
    )
    livekit_api_secret: str = Field(
        default="",
        validation_alias="LIVEKIT_API_SECRET",
        description="LiveKit API Secret",
    )
    livekit_default_room: str = Field(
        default="voxara-voice-room",
        validation_alias="LIVEKIT_DEFAULT_ROOM",
        description="Default room name for voice interactions",
    )

    # Gemini / Google AI credentials
    google_api_key: str = Field(
        default="",
        validation_alias="GOOGLE_API_KEY",
        description="Google Gemini API Key for Gemini Live realtime audio",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash-native-audio-preview-12-2025",
        validation_alias="GEMINI_MODEL",
        description="Gemini Realtime Live API model ID",
    )
    gemini_voice: str = Field(
        default="Puck",
        validation_alias="GEMINI_VOICE",
        description="Gemini voice persona (e.g. Puck, Aoede, Fenrir, Leda)",
    )
    gemini_text_model: str = Field(
        default="gemini-3.7-flash",
        validation_alias="GEMINI_TEXT_MODEL",
        description="Google Gemini model ID for text generation and skill gap analysis",
    )

    # Database settings (PostgreSQL via asyncpg is the primary database)
    database_url: str = Field(
        default="",
        validation_alias="DATABASE_URL",
        description="SQLAlchemy PostgreSQL Database URL with asyncpg (e.g. postgresql+asyncpg://postgres:postgres@localhost:5432/voxara_ai)",
    )

    # Server settings
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def normalized_database_url(self) -> str:
        """
        Normalizes and strictly validates the database URL for PostgreSQL:
        - Ensures DATABASE_URL is configured (no silent fallback).
        - Rejects SQLite (PostgreSQL is required as the primary database).
        - Normalizes 'postgres://' and 'postgresql://' prefixes to 'postgresql+asyncpg://'.
        - Converts '?sslmode=require' to '?ssl=require' for asyncpg compatibility.
        """
        raw_url = (self.database_url or "").strip()
        if not raw_url:
            raise ValueError(
                "DATABASE_URL is not configured. PostgreSQL is the primary database for Voxara AI. "
                "Please configure DATABASE_URL in your environment or .env file "
                "(e.g., DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/voxara_ai or cloud PostgreSQL)."
            )

        if raw_url.startswith("sqlite"):
            raise ValueError(
                "SQLite is not supported as the primary database for Voxara AI. "
                "PostgreSQL with asyncpg is required. "
                "Please configure DATABASE_URL=postgresql+asyncpg://<username>:<password>@<host>:<port>/<dbname> "
                "or provide a PostgreSQL connection from Supabase / Neon."
            )

        url = raw_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and not url.startswith("postgresql+"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

        if not url.startswith("postgresql+asyncpg://"):
            raise ValueError(
                f"Unsupported database URL scheme in '{url}'. "
                "Voxara AI requires PostgreSQL with the asyncpg driver (postgresql+asyncpg://...)."
            )

        # Normalize query parameters for asyncpg compatibility:
        # 1. Convert 'sslmode=require' to 'ssl=require'
        # 2. Filter out parameters unsupported by asyncpg (e.g., Neon's 'channel_binding')
        from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
        parsed = urlparse(url)
        if parsed.query:
            query_tuples = parse_qsl(parsed.query, keep_blank_values=True)
            cleaned_tuples = []
            for k, v in query_tuples:
                if k == "sslmode":
                    cleaned_tuples.append(("ssl", "require" if v in ("require", "verify-ca", "verify-full") else v))
                elif k in ("channel_binding",):
                    # asyncpg handles SSL natively and rejects channel_binding
                    continue
                else:
                    cleaned_tuples.append((k, v))
            new_query = urlencode(cleaned_tuples)
            url = urlunparse(parsed._replace(query=new_query))

        return url

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    def validate_database_credentials(self) -> tuple[bool, str]:
        """
        Validates whether PostgreSQL database credentials are configured and not placeholders.
        Returns (is_valid, error_reason).
        """
        raw_url = (self.database_url or "").strip()
        if not raw_url:
            return False, "DATABASE_URL is not set."
        if raw_url.startswith("sqlite"):
            return False, "DATABASE_URL is set to SQLite, but PostgreSQL is required."
        if "<password>" in raw_url or "<username>" in raw_url or "user:password@ep-sample" in raw_url:
            return False, "DATABASE_URL contains placeholder values."
        try:
            _ = self.normalized_database_url
            return True, ""
        except ValueError as err:
            return False, str(err)

    def validate_livekit_credentials(self) -> tuple[bool, str]:
        """
        Validates whether LiveKit credentials are configured and not placeholders.
        Returns (is_valid, error_reason).
        """
        if not self.livekit_url or "your-project" in self.livekit_url:
            return False, "LIVEKIT_URL is not set or contains placeholder value."
        if not self.livekit_api_key or "your_livekit" in self.livekit_api_key:
            return False, "LIVEKIT_API_KEY is not set or contains placeholder value."
        if not self.livekit_api_secret or "your_livekit" in self.livekit_api_secret:
            return False, "LIVEKIT_API_SECRET is not set or contains placeholder value."
        return True, ""

    def validate_gemini_credentials(self) -> tuple[bool, str]:
        """
        Validates whether Google Gemini API credentials are configured.
        Returns (is_valid, error_reason).
        """
        if not self.google_api_key or "your_google" in self.google_api_key:
            return False, "GOOGLE_API_KEY is not set or contains placeholder value."
        return True, ""


# Cached settings instance
settings = Settings()
