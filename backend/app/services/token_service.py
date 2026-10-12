import uuid
from datetime import timedelta
from livekit import api
from app.config import settings


class TokenService:
    """
    Secure LiveKit Access Token generator.
    Issues short-lived credentials for joining specific rooms with appropriate permissions.
    """

    @staticmethod
    def generate_token(
        identity: str | None = None,
        name: str | None = None,
        room_name: str | None = None,
        ttl_minutes: int = 15,
    ) -> str:
        """
        Generates a signed JWT token granting audio publish/subscribe access to a room.
        API secret is never returned or leaked to the client.
        """
        is_valid, reason = settings.validate_livekit_credentials()
        if not is_valid:
            raise ValueError(f"LiveKit configuration error: {reason}")

        participant_identity = identity or f"user_{uuid.uuid4().hex[:8]}"
        participant_name = name or "Voxara User"
        target_room = room_name or settings.livekit_default_room

        token = (
            api.AccessToken(
                api_key=settings.livekit_api_key,
                api_secret=settings.livekit_api_secret,
            )
            .with_identity(participant_identity)
            .with_name(participant_name)
            .with_ttl(timedelta(minutes=ttl_minutes))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=target_room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
        )

        return token.to_jwt()
