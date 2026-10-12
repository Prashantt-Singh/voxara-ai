"""
Voxara AI - LiveKit Voice Agent Worker Entrypoint (Step 2 Baseline)

IMPORTANT NOTICE REGARDING STEP 2 SCOPE:
In this phase (Step 2: Real-Time Voice Infrastructure), this module establishes
the LiveKit Agent worker connection protocol and room event handlers.

Conversational AI pipelines (ASR / Gemini Multimodal Live / TTS) are scheduled
for subsequent phases (Step 3/4). This worker connects to the room, publishes
participant state metadata, and logs WebRTC session activity without simulating
or fabricating AI speech until a full LLM pipeline is configured.
"""

import logging
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
)
from app.config import settings

logger = logging.getLogger("voxara-voice-agent")
logging.basicConfig(level=logging.INFO)


async def entrypoint(ctx: JobContext):
    """
    Entrypoint executed when an agent job is dispatched for a room.
    """
    logger.info("Connecting to LiveKit room: %s (job_id: %s)", ctx.room.name, ctx.job.id)

    # Connect to room with audio-only auto-subscription
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Wait for the first human participant to join
    participant = await ctx.wait_for_participant()
    logger.info("Participant joined room %s: %s (%s)", ctx.room.name, participant.identity, participant.name)

    # Listen to participant audio publication
    @ctx.room.on("participant_connected")
    def on_participant_connected(p):
        logger.info("Participant connected: %s", p.identity)

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(p):
        logger.info("Participant disconnected: %s", p.identity)

    @ctx.room.on("track_subscribed")
    def on_track_subscribed(track, publication, p):
        logger.info("Subscribed to track %s (%s) from participant %s", track.sid, track.kind, p.identity)

    logger.info(
        "Agent is active in room %s. Ready for voice interaction pipeline integration (Step 3/4).",
        ctx.room.name,
    )


def run_agent():
    """
    CLI runner for starting the LiveKit Agent worker process.
    Validates configuration before starting.
    """
    is_valid, reason = settings.validate_livekit_credentials()
    if not is_valid:
        logger.error(
            "Cannot start LiveKit Voice Agent: %s. "
            "Please configure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in backend/.env",
            reason,
        )
        return

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    )


if __name__ == "__main__":
    run_agent()
