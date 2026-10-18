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

    # Server settings
    host: str = Field(default="0.0.0.0", validation_alias="HOST")
    port: int = Field(default=8000, validation_alias="PORT")
    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        validation_alias="CORS_ORIGINS",
    )

    @property
    def cors_origin_list(self) -> List[str]:
        if not self.cors_origins or self.cors_origins.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

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
