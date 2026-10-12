# Voxara AI — System Architecture

Voxara AI is a real-time Agentic Voice AI assistant designed for multimodal, responsive voice-first interactions with tool execution and visual status feedback.

---

## High-Level Architecture (Current: Step 2)

```mermaid
flowchart TD
    subgraph Client["Frontend Client (React + TypeScript + Vite)"]
        UI["Landing Page UI"]
        Orb["AssistantOrb (Visual Feedback States)"]
        MicBtn["MessageInput & Mic Button"]
        Hook["useVoiceSession Hook"]
        VoiceService["voiceService (HTTP Client)"]
        LKClient["LiveKit WebRTC Client (livekit-client)"]
    end

    subgraph Backend["Backend Infrastructure (FastAPI + Python)"]
        API["FastAPI Gateway (/health, /api/voice/status)"]
        TokenGen["TokenService (/api/voice/token)"]
        Config["Config & Secret Validation (.env)"]
        LKAgent["LiveKit Voice Agent Worker (livekit-agents)"]
    end

    subgraph Cloud["LiveKit WebRTC Infrastructure"]
        LKCloud["LiveKit Cloud / WebRTC SFU Server"]
    end

    subgraph Future["Future AI Pipelines (Step 4+)"]
        Gemini["Multimodal LLM (Gemini Live)"]
        LangGraph["Agentic Orchestration (LangGraph)"]
        MCP["MCP Tools Engine"]
    end

    %% Frontend Interactions
    UI --> Orb
    UI --> MicBtn
    MicBtn -->|Toggle Voice| Hook
    Hook -->|Request Token| VoiceService
    VoiceService -->|POST /api/voice/token| TokenGen
    TokenGen --> Config
    Hook -->|Connect WebRTC Session| LKClient
    LKClient <==>|Bidirectional Audio Streaming| LKCloud
    LKAgent <==>|Room Worker Participation| LKCloud

    %% State Synchronization
    LKClient -.->|isSpeaking / ActiveSpeakers| Hook
    Hook -.->|idle / listening / speaking / error| Orb

    %% Future Connections
    LKAgent -.->|Planned Step 4| Gemini
    LKAgent -.->|Planned Step 5| LangGraph
    LKAgent -.->|Planned Step 6| MCP
```

---

## Directory Structure

```
voxara-ai/
├── docs/
│   ├── ARCHITECTURE.md          # System architecture and directory documentation
│   └── DEVELOPMENT_PLAN.md      # Phased development roadmap
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   └── voice.py         # /api/voice/token & /api/voice/status endpoints
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   └── token_service.py # LiveKit JWT AccessToken generation
│   │   ├── __init__.py
│   │   ├── agent.py             # LiveKit Voice Agent worker entrypoint
│   │   ├── config.py            # Pydantic Settings & environment variable validation
│   │   └── main.py              # FastAPI app setup, CORS, lifespan, and /health
│   ├── .env.example             # Template for required environment variables
│   ├── requirements.txt         # FastAPI, LiveKit SDK & Agent dependencies
│   ├── venv/                    # Python virtual environment
│   └── README.md                # Backend service documentation
├── frontend/
│   ├── public/                  # Static assets
│   ├── src/
│   │   ├── app/
│   │   │   └── LandingPage.tsx  # Main application view with voice controls
│   │   ├── components/
│   │   │   ├── assistant/
│   │   │   │   ├── AssistantOrb.tsx   # Animated visual state orb
│   │   │   │   ├── MessageInput.tsx   # Input bar & mic button
│   │   │   │   └── StateSelector.tsx  # Dev preview state selector
│   │   │   └── layout/
│   │   │       ├── Header.tsx         # Header with live state pill
│   │   │       └── Container.tsx      # Responsive container
│   │   ├── hooks/
│   │   │   ├── useAssistantState.ts   # State management hook
│   │   │   └── useVoiceSession.ts     # LiveKit WebRTC session hook
│   │   ├── lib/
│   │   │   └── voiceService.ts        # API client for backend voice endpoints
│   │   ├── types/
│   │   │   └── assistant.ts           # State, session, and error interfaces
│   │   ├── index.css                  # Global CSS & Tailwind directives
│   │   └── main.tsx                   # React root entrypoint
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   └── vite.config.ts
├── .gitignore                   # Root gitignore (env files, node_modules, venv, bytecode)
└── README.md                    # Project overview & startup instructions
```

---

## Voice Session State Machine

| Assistant State | Trigger / Source | Visual Representation |
| :--- | :--- | :--- |
| `idle` | Connected room with no active speakers, or standby. | Ambient warm golden breathing pulse. |
| `connecting` | Fetching token and negotiating WebRTC peer connection. | Radiant swirling transition. |
| `listening` | WebRTC participant's local audio track is unmuted and active. | Expanded radiant yellow wave. |
| `speaking` | Remote assistant participant is actively transmitting audio. | Vocal resonance modulation. |
| `thinking` | LLM reasoning / processing (future phase). | Swirling gradient rotation. |
| `executing` | Agentic workflow / tool execution (future phase). | Rhythmic operational oscillation. |
| `error` | Microphone permission denied or LiveKit configuration error. | Soft coral/crimson indicator with diagnostic alert. |

---

## Security Model

1. **Zero Secret Exposure**: LiveKit API secret (`LIVEKIT_API_SECRET`) resides solely on the backend inside environment variables and is never transmitted or exposed to the client.
2. **Short-Lived Access Tokens**: The backend issues signed JWT tokens with 15-minute time-to-live (`TTL`) granting restricted room access (`can_publish`, `can_subscribe`, `can_publish_data`).
3. **No Unauthenticated Secret Access**: Credentials and sensitive room parameters are strictly managed via Pydantic settings.
