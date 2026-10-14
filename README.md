# Voxara AI — Real-time Agentic Voice Assistant

Voxara AI is a modern, real-time Agentic Voice AI assistant designed to deliver ultra-low-latency voice-to-voice interaction, multimodal intelligence, and dynamic agentic workflow execution.

---

## Current Status: Step 3 — Gemini Live API Voice Integration

This repository implements **Step 3: Gemini Live API Integration**. Voxara is powered by Google's Gemini Live real-time audio pipeline via LiveKit Agents, enabling natural, full-duplex spoken conversations with immediate voice responses.

### Implemented in Step 3:
- **Google Gemini Live Multimodal Integration**: Integrated official `livekit-plugins-google==1.8.6` using `RealtimeModel` with native bidirectional audio streaming.
- **Conversational LiveKit Agent Worker (`backend/app/agent.py`)**:
  - Connects to the room, auto-subscribes to user audio, and pairs with `AgentSession`.
  - Streams microphone input directly into Gemini Live over real-time WebSockets.
  - Returns low-latency synthesized speech using Gemini's natural conversational voice (`Puck`, `Aoede`, etc.).
  - Greets the user naturally upon entry.
- **System Instructions**: Customized prompt tuned for voice dialogue (concise, warm, avoiding awkward formatting or markdown reading).
- **Assistant State Synchronization**:
  - `idle`: Standby with ambient golden glow.
  - `listening`: User microphone actively speaking.
  - `speaking`: Voxara agent actively delivering synthesized speech.
  - `thinking`: Connecting and negotiating session.
  - `error`: Clearly surfaces missing credentials or permission rejections.
- **Frontend Real-Time Experience (`LandingPage.tsx`, `useVoiceSession.ts`)**:
  - Active detection when the Voxara AI agent joins the room.
  - Status pill distinguishes between *"LiveKit Connected (Waiting for Agent)"* and *"Voxara AI Active (Gemini Live)"*.
- **Security & Secret Isolation**: Neither `LIVEKIT_API_SECRET` nor `GOOGLE_API_KEY` are exposed to the frontend; tokens are signed exclusively by the backend.

### Explicit Scope Boundaries:
The following capabilities belong to future phases and are **not yet implemented**:
- LangGraph multi-step task planning and state loops (Step 4)
- Model Context Protocol (MCP) tool execution engine (Step 5)
- Execution dashboard and UI telemetry widgets (Step 5)

---

## Prerequisites

- **Node.js**: v18.0.0 or higher
- **Python**: v3.10 or higher (v3.12 recommended)
- **LiveKit Account**: A free project at [LiveKit Cloud](https://cloud.livekit.io)
- **Google Gemini API Key**: From [Google AI Studio](https://aistudio.google.com/apikey)

---

## Getting Started

### 1. Backend Setup

1. Open a terminal and navigate to the `backend` directory:
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
   Open `backend/.env` and insert your credentials:
   ```ini
   LIVEKIT_URL=wss://your-project.livekit.cloud
   LIVEKIT_API_KEY=your_livekit_api_key
   LIVEKIT_API_SECRET=your_livekit_api_secret
   LIVEKIT_DEFAULT_ROOM=voxara-voice-room

   # Google Gemini Live API Key
   GOOGLE_API_KEY=your_google_gemini_api_key
   GEMINI_MODEL=gemini-2.5-flash-native-audio-preview-12-2025
   GEMINI_VOICE=Puck

   HOST=0.0.0.0
   PORT=8000
   CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   ```

5. Start the FastAPI API Server:
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   The backend API will run on `http://localhost:8000`.

6. In a **second terminal**, start the Gemini Live Agent worker:
   ```bash
   cd backend
   .\venv\Scripts\activate
   python -m app.agent dev
   ```

---

### 2. Frontend Setup

1. In a **third terminal**, navigate to the `frontend` directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the Vite local development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:5173`.

---

## How to Test the Voice Interaction

1. Ensure both the **FastAPI backend** (`uvicorn app.main:app`) and the **LiveKit Agent worker** (`python -m app.agent dev`) are running.
2. Open `http://localhost:5173` in Chrome, Edge, or Safari.
3. Click the **Microphone Button** in the input bar or click the **Orb**.
4. Grant microphone access when prompted.
5. The status pill will display **"Voxara AI Active (Gemini Live)"**.
6. Voxara will greet you aloud (*"Hello! I am Voxara. How can I help you today?"*).
7. Speak into your microphone — the orb will pulse in `listening` mode. When Voxara speaks back, the orb shifts into its vocal `speaking` wave.
8. Click the mic button again to cleanly leave the room and release the microphone.

---

## Verification & Type Checking

To verify the frontend:
```bash
npm --prefix frontend run build
npm --prefix frontend run lint
```

To verify backend configuration and imports:
```bash
.\backend\venv\Scripts\python -c "from app.config import settings; print(settings.validate_livekit_credentials(), settings.validate_gemini_credentials())"
```

---

## Architecture & Roadmap
- Detailed voice pipeline and architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Development plan & milestones: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)
