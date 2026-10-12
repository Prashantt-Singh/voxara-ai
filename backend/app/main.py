import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.routes import voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("voxara-api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    is_valid, reason = settings.validate_livekit_credentials()
    if is_valid:
        logger.info("LiveKit credentials configured successfully.")
    else:
        logger.warning(
            "LiveKit credentials not configured or incomplete: %s. "
            "Token generation endpoint will return 503 until configured.",
            reason,
        )
    yield


app = FastAPI(
    title="Voxara AI Backend",
    description="Real-time Agentic Voice AI Assistant Backend Infrastructure",
    version="0.2.0",
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

# Register Voice API Router
app.include_router(voice.router)


@app.get("/health")
async def health_check():
    is_livekit_ok, _ = settings.validate_livekit_credentials()
    return {
        "status": "healthy",
        "service": "voxara-ai-backend",
        "version": "0.2.0",
        "livekit_configured": is_livekit_ok,
    }
