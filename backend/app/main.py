import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import voice, workflows

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voxara-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_lk_valid, lk_reason = settings.validate_livekit_credentials()
    if is_lk_valid:
        logger.info("LiveKit credentials configured successfully.")
    else:
        logger.warning(
            "LiveKit credentials not configured or incomplete: %s. "
            "Token generation endpoint will return 503 until configured.",
            lk_reason,
        )

    is_gemini_valid, gemini_reason = settings.validate_gemini_credentials()
    if is_gemini_valid:
        logger.info("Google Gemini credentials configured successfully.")
    else:
        logger.warning(
            "Google Gemini credentials not configured or incomplete: %s. "
            "Gemini Live agent will require GOOGLE_API_KEY.",
            gemini_reason,
        )
    yield


app = FastAPI(
    title="Voxara AI Backend",
    description="Real-time Agentic Voice AI Assistant Backend Infrastructure",
    version="0.3.0",
    lifespan=lifespan,
)

# CORS Middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(voice.router)
app.include_router(workflows.router)


@app.get("/health")
async def health_check():
    is_livekit_ok, _ = settings.validate_livekit_credentials()
    is_gemini_ok, _ = settings.validate_gemini_credentials()
    return {
        "status": "healthy",
        "service": "voxara-ai-backend",
        "version": "0.4.0",
        "livekit_configured": is_livekit_ok,
        "gemini_configured": is_gemini_ok,
        "workflows_ready": True,
    }
