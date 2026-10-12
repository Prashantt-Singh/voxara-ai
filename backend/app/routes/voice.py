from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from app.config import settings
from app.services.token_service import TokenService

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TokenRequest(BaseModel):
    identity: str | None = Field(default=None, description="Optional unique participant ID")
    name: str | None = Field(default=None, description="Optional participant display name")
    room_name: str | None = Field(default=None, description="Optional target room name")


class TokenResponse(BaseModel):
    server_url: str = Field(description="LiveKit WebRTC Server URL")
    room_name: str = Field(description="Target room name")
    participant_identity: str = Field(description="Assigned participant identity")
    token: str = Field(description="Short-lived signed JWT access token")


class VoiceStatusResponse(BaseModel):
    status: str
    livekit_configured: bool
    livekit_server_url: str | None
    default_room: str
    details: str


@router.get("/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    """
    Returns current voice infrastructure health and LiveKit configuration readiness.
    """
    is_valid, reason = settings.validate_livekit_credentials()
    return VoiceStatusResponse(
        status="ready" if is_valid else "configuration_required",
        livekit_configured=is_valid,
        livekit_server_url=settings.livekit_url if is_valid else None,
        default_room=settings.livekit_default_room,
        details="LiveKit credentials ready." if is_valid else f"Configuration missing: {reason}",
    )


@router.post("/token", response_model=TokenResponse)
async def generate_connection_token(req: TokenRequest = TokenRequest()):
    """
    Generates a secure, short-lived JWT token for the client to connect directly
    to LiveKit WebRTC room.
    """
    is_valid, reason = settings.validate_livekit_credentials()
    if not is_valid:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "LIVEKIT_NOT_CONFIGURED",
                "message": (
                    "LiveKit server credentials are not configured on the backend. "
                    "Please set LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in backend/.env"
                ),
                "reason": reason,
            },
        )

    try:
        import uuid
        participant_identity = req.identity or f"user_{uuid.uuid4().hex[:8]}"
        room_name = req.room_name or settings.livekit_default_room

        token = TokenService.generate_token(
            identity=participant_identity,
            name=req.name,
            room_name=room_name,
        )

        return TokenResponse(
            server_url=settings.livekit_url,
            room_name=room_name,
            participant_identity=participant_identity,
            token=token,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "TOKEN_GENERATION_FAILED",
                "message": f"Failed to generate LiveKit access token: {str(e)}",
            },
        )
