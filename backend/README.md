# Voxara AI Backend

Python backend infrastructure for Voxara AI, providing secure LiveKit token issuance, session configuration, and the entrypoint for LiveKit Voice Agent workers.

---

## Directory Structure

```
backend/
├── app/
│   ├── routes/
│   │   ├── __init__.py
│   │   └── voice.py         # /api/voice/status and /api/voice/token endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   └── token_service.py # LiveKit JWT AccessToken generator with strict permissions
│   ├── __init__.py
│   ├── agent.py             # LiveKit Voice Agent entrypoint
│   ├── config.py            # Pydantic Settings & environment variable validation
│   └── main.py              # FastAPI app setup, CORS, lifespan, and /health
├── .env.example             # Template for required environment variables
├── requirements.txt         # FastAPI, LiveKit SDK & Agent dependencies
└── venv/                    # Python virtual environment
```

---

## Prerequisites

- Python 3.10+ (tested with Python 3.12)
- A LiveKit Cloud account or self-hosted LiveKit instance ([https://cloud.livekit.io](https://cloud.livekit.io))

---

## Setup & Running

### 1. Configure Environment Variables

Copy the example file to `.env`:

```bash
cp .env.example .env
```

Open `.env` and fill in your LiveKit project credentials:
```ini
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret
LIVEKIT_DEFAULT_ROOM=voxara-voice-room
HOST=0.0.0.0
PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> **Security Note:** Never commit `.env` or expose `LIVEKIT_API_SECRET` to the client.

### 2. Activate Virtual Environment & Install Dependencies

```bash
# Windows
.\venv\Scripts\activate
pip install -r requirements.txt

# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Start the FastAPI API Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The server will start at `http://localhost:8000`. You can test health at:
- `GET http://localhost:8000/health`
- `GET http://localhost:8000/api/voice/status`

### 4. Run the LiveKit Voice Agent Worker (Optional / Next Phase)

To start the agent worker process:

```bash
python -m app.agent dev
```

---

## Current Status (Step 2 Scope)

- **Implemented**: FastAPI application, credential validation, short-lived JWT token issuance, CORS policies, LiveKit Agent entrypoint skeleton, error handling when credentials are missing.
- **Next Phase (Step 3/4)**: Integration of speech recognition (ASR), LLM reasoning pipeline (Gemini Live), and speech synthesis (TTS).
