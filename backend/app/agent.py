"""
Voxara AI - LiveKit Voice Agent Worker Entrypoint (Step 3: Gemini Live API Integration)

This module implements the full real-time conversational voice pipeline using Google's
Gemini Live API via the official livekit-plugins-google RealtimeModel and livekit-agents.

Pipeline Overview:
1. Agent connects to the LiveKit WebRTC room.
2. A human participant connects and speaks through their microphone.
3. Audio streams directly via WebRTC into the AgentSession.
4. Gemini Live processes bidirectional multimodal audio in real time.
5. Synthesized audio responses are streamed back to the room and played to the user.
6. Local assistant state and audio activity events are automatically synchronized.
"""

import logging
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    AgentSession,
    Agent,
    cli,
)
from livekit.plugins.google.realtime import RealtimeModel
from app.config import settings
from app.agent_tools import VOICE_AGENT_TOOLS

logger = logging.getLogger("voxara-voice-agent")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

VOXARA_SYSTEM_PROMPT = """You are Voxara, a modern, intelligent, and empathetic real-time AI voice assistant.
Your goal is to provide helpful, concise, and natural spoken answers.

Core Capabilities:
1. Opportunity Hunter: Discovers real internships, hackathons, and tech programs, verifies details against original sources, tracks deadlines, and matches candidate preferences.

Guidelines for voice conversation:
- Keep your answers natural, conversational, and relatively brief so the dialogue flows smoothly.
- Avoid markdown tables, bullet points, asterisks, or formatting that sounds awkward when spoken aloud.
- Speak warmly with clarity and enthusiasm.
- For ordinary conversation, greetings, and questions, reply directly and naturally without calling tools.
- Specialized Agentic Workflow Tools:
  * 'hunt_opportunities_tool': Call when the user asks to find hackathons, internships, scholarships, tech opportunities, or check deadlines.
  * 'analyze_skills_demonstration': Demonstration tool for skill gap analysis when explicitly requested.
  * 'run_demo_workflow': Demonstration tool for testing graph execution.
- When you invoke a tool, briefly inform the user that you are checking the feeds or analyzing their request.
- Once the tool returns, summarize the findings naturally in your own conversational words based on the results.
- If the user asks for tasks outside your available tools, politely explain that the capability is not yet supported.
- If you don't know something or an action fails, state it honestly and politely.
"""


async def entrypoint(ctx: JobContext):
    """
    Entrypoint executed when an agent job is dispatched for a room.
    Integrates Gemini Live real-time audio pipeline into the room session.
    """
    logger.info("Initializing Voxara Voice Agent for room: %s (job_id: %s)", ctx.room.name, ctx.job.id)

    # 1. Validate Gemini credentials
    is_gemini_valid, gemini_reason = settings.validate_gemini_credentials()
    if not is_gemini_valid:
        logger.error(
            "Cannot start voice conversation pipeline: %s. "
            "Please ensure GOOGLE_API_KEY is set in backend/.env",
            gemini_reason,
        )
        # Connect to room and inform user of missing configuration if possible
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        return

    # 2. Connect to the LiveKit room with audio subscription
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info("Agent connected to LiveKit room: %s", ctx.room.name)

    # 3. Wait for the participant to enter
    participant = await ctx.wait_for_participant()
    logger.info("Active human participant joined room: %s (%s)", participant.identity, participant.name)

    # 4. Instantiate Google Gemini Live Realtime Model
    try:
        model = RealtimeModel(
            model=settings.gemini_model,
            api_key=settings.google_api_key,
            voice=settings.gemini_voice,
            instructions=VOXARA_SYSTEM_PROMPT,
        )
        logger.info(
            "Gemini RealtimeModel initialized with model '%s' and voice '%s'.",
            settings.gemini_model,
            settings.gemini_voice,
        )
    except Exception as e:
        logger.error("Failed to initialize Gemini RealtimeModel: %s", e, exc_info=True)
        return

    # 5. Create LiveKit Agent with registered workflow tools and AgentSession
    agent = Agent(
        instructions=VOXARA_SYSTEM_PROMPT,
        tools=VOICE_AGENT_TOOLS,
    )

    session = AgentSession(
        llm=model,
    )

    # Log session and agent events for monitoring and troubleshooting
    @session.on("agent_state_changed")
    def on_agent_state_changed(event):
        logger.info("Agent state transition: %s", getattr(event, "state", event))

    @session.on("user_state_changed")
    def on_user_state_changed(event):
        logger.info("User speaking state: %s", getattr(event, "state", event))

    @session.on("error")
    def on_session_error(event):
        logger.error("Session runtime error: %s", getattr(event, "error", event))

    # 6. Start the voice agent session attached to the room
    try:
        logger.info("Starting AgentSession for room %s...", ctx.room.name)
        await session.start(agent=agent, room=ctx.room)
        logger.info("Voxara Voice Agent is live and listening in room %s!", ctx.room.name)

        # Proactive greeting: Check if there are pending notifications in database
        greeting = "Hello! I am Voxara. How can I help you today?"
        try:
            from app.db import repository
            pending = await repository.list_user_notifications(user_id="default_user", unread_only=True, limit=1)
            if pending:
                notif = pending[0]
                spoken = notif.spoken_summary or notif.title
                greeting = f"Hello! I am Voxara. Welcome back! By the way, {spoken} How can I help you today?"
                await repository.mark_notification_read(user_id="default_user", notification_id=notif.id)
        except Exception as notif_err:
            logger.debug("Could not query proactive notifications on entry: %s", notif_err)

        session.say(greeting)
    except Exception as e:
        logger.error("Error starting AgentSession: %s", e, exc_info=True)


def run_agent():
    """
    CLI runner for starting the LiveKit Agent worker process.
    Validates LiveKit and Gemini configuration before starting.
    """
    is_lk_valid, lk_reason = settings.validate_livekit_credentials()
    if not is_lk_valid:
        logger.error(
            "Cannot start LiveKit Voice Agent worker: %s. "
            "Please configure LIVEKIT_URL, LIVEKIT_API_KEY, and LIVEKIT_API_SECRET in backend/.env",
            lk_reason,
        )
        return

    is_gemini_valid, gemini_reason = settings.validate_gemini_credentials()
    if not is_gemini_valid:
        logger.warning(
            "Google Gemini credentials warning: %s. "
            "Voice agent will connect to LiveKit but cannot stream Gemini speech until GOOGLE_API_KEY is configured in backend/.env",
            gemini_reason,
        )

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
