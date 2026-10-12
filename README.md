# Voxara AI — Real-time Agentic Voice Assistant

Voxara AI is a modern, real-time Agentic Voice AI assistant designed to deliver ultra-low-latency voice-to-voice interaction, multimodal intelligence, and dynamic agentic workflow execution.

---

## Current Status: Step 2 — Real-Time Voice Infrastructure

This repository implements **Step 2: Real-Time Voice Infrastructure**. In this phase, we integrated LiveKit's WebRTC infrastructure into both frontend and backend to enable genuine real-time bidirectional audio sessions without fabricating AI responses.

### Implemented in Step 2:
- **Frontend LiveKit WebRTC Client**: Integrated official `livekit-client` and `@livekit/components-react`.
- **`useVoiceSession` Hook**: Full lifecycle management covering `disconnected`, `connecting`, `connected`, and `error` states, plus active speaking detection.
- **`voiceService` Module**: Robust client communicating with backend token and status endpoints.
- **Microphone Connection Integration**: Clicking the mic button initiates token retrieval and WebRTC room connection; clicking again tears down the session and releases microphone tracks.
- **Live Visual State Binding**: The luminous `AssistantOrb` dynamically reacts to real WebRTC events:
  - `listening` when user microphone detects active vocal input
  - `speaking` when remote agent/participant emits audio
  - `idle` during ambient connected quietude
  - `thinking` during WebRTC connection negotiation
  - `error` with explanatory diagnostics if permissions or credentials fail
- **Clear Error Diagnostics**: In-UI alerts distinguish between browser microphone permission denials and backend credential configuration errors.
- **Backend FastAPI Service (`backend/app/`)**:
  - `GET /health`: Overall service health
  - `GET /api/voice/status`: LiveKit readiness verification
  - `POST /api/voice/token`: Secure short-lived JWT access token generation
- **Security & Secret Isolation**: LiveKit API secret never reaches the browser; all keys are validated through Pydantic settings from `.env`.
- **LiveKit Agent Entrypoint (`backend/app/agent.py`)**: Entrypoint skeleton for the agent worker to join rooms and handle audio streams.

### Explicit Scope Boundaries:
The following capabilities belong to upcoming phases and are **not yet implemented**:
- Speech recognition (ASR) transcription pipeline (Step 3/4)
- Gemini Live multimodal reasoning and conversational voice synthesis (Step 4)
- LangGraph orchestration and decision loops (Step 5)
- MCP tool execution engine and dashboard (Step 6)

---

## Prerequisites

- **Node.js**: v18.0.0 or higher
- **Python**: v3.10 or higher (v3.12 recommended)
- **LiveKit Account**: A free project at [LiveKit Cloud](https://cloud.livekit.io) (or a self-hosted LiveKit instance)

---

## Getting Started

### 1. Backend Setup

1. Open your terminal and navigate to the `backend` directory:
   ```bash
   cd backend
   ```

2. Create and activate a Python virtual environment:
   ```bash
   # Windows
   python -m venv venv
   .\venv\Scripts\activate

   # macOS / Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Open `backend/.env` and insert your LiveKit project credentials from [LiveKit Cloud](https://cloud.livekit.io):
   ```ini
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   LIVEKIT_DEFAULT_ROOM=voxara-voice-room
   HOST=0.0.0.0
   PORT=8000
   ```

5. Start the FastAPI development server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   The backend API will run on `http://localhost:8000`.

---

### 2. Frontend Setup

1. In a separate terminal, navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies (if not already installed):
   ```bash
   npm install
   ```

3. (Optional) Configure environment variables:
   ```bash
   cp .env.example .env
   ```
   Default `VITE_BACKEND_URL=http://localhost:8000`.

4. Start the Vite local development server:
   ```bash
   npm run dev
   ```

5. Open your browser and navigate to `http://localhost:5173`.

---

## How to Test the Voice Connection

1. Ensure the backend is running (`http://localhost:8000`).
2. Open the frontend at `http://localhost:5173`.
3. Click the **Microphone Button** in the input bar or click the **Orb**.
4. **If LiveKit credentials are configured in `backend/.env`**:
   - The browser prompts for microphone permission.
   - Upon granting permission, the pill changes to **"LiveKit Connected"**.
   - Speaking into your microphone triggers the luminous orb's radiant `listening` animation.
   - Clicking the mic button or "Leave" cleanly disconnects and releases the audio tracks.
5. **If LiveKit credentials are missing or unconfigured**:
   - The UI surfaces a clear diagnostic alert stating credentials need to be set in `backend/.env`.
   - The orb transitions to the soft coral `error` indicator without crashing.
6. **If microphone permission is denied by the browser**:
   - A descriptive "Microphone Permission Error" alert is presented guiding the user to grant access.

---

## Verification & Type Checking

To verify the frontend build:
```bash
npm --prefix frontend run build
npm --prefix frontend run lint
```

To verify the backend imports and configuration:
```bash
.\backend\venv\Scripts\python -c "from app.config import settings; print(settings.validate_livekit_credentials())"
```

---

## Architecture & Roadmap
- High-level system architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Development plan & milestones: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)
