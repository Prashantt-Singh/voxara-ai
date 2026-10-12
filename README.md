# Voxara AI — Real-time Agentic Voice Assistant

Voxara AI is a modern, real-time Agentic Voice AI assistant designed to deliver ultra-low-latency voice-to-voice interaction, multimodal intelligence, and dynamic agentic workflow execution.

---

## Current Status: Step 1 — Project Foundation

This repository currently implements **Step 1: Project Foundation**. In this phase, we established the clean frontend architecture, user experience baseline, and tactile animated visual state machine.

### What is implemented in Step 1:
- **Clean modular architecture**: Strict separation into `app/`, `components/assistant/`, `components/layout/`, `hooks/`, `types/`, and `lib/`.
- **Minimalist landing page**: Inspired by modern tactile interfaces with a warm luminous yellow-orange gradient palette, clean typography, and spacious layout.
- **`AssistantOrb` Component**: Luminous visual representation with support for 6 visual demonstration states:
  - `idle` (ambient warm breathing pulse)
  - `listening` (expanded radiant wave)
  - `thinking` (swirling gradient rotation)
  - `executing` (rhythmic operational oscillation)
  - `speaking` (vocal resonance modulation)
  - `error` (soft coral/crimson indicator)
- **`useAssistantState` Hook**: State management hook encapsulating assistant state transitions.
- **`MessageInput` Component**: Accessible pill input with plus action button, text input, microphone button, and keyboard submission (Enter).
- **Interactive State Preview**: Minimalist footer selector to preview each visual state.
- **Accessibility**: Semantic HTML, ARIA attributes, keyboard navigation, and full support for `prefers-reduced-motion`.
- **System Documentation**: High-level architectural specifications in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and phased milestones in [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md).

### Features NOT connected yet:
In accordance with Step 1 instructions, the following features are deliberately **not implemented** at this stage and will be developed in future phases:
- Real microphone audio capture and Web Audio streaming (Step 2)
- FastAPI backend server and WebSocket communication (Step 3)
- Gemini Live multimodal voice-to-voice LLM integration (Step 4)
- LangGraph agentic orchestration and state graphs (Step 5)
- Model Context Protocol (MCP) tool integrations (Step 6)
- Backend agent dashboards and telemetry (Step 6 & 7)

Submitting queries in the UI displays an explicit, honest local confirmation notice without fabricating AI responses.

---

## Getting Started

### Prerequisites
- Node.js (v18.0.0 or higher recommended)
- npm or pnpm

### Running the Application

1. Open your terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies (if not already installed):
   ```bash
   npm install
   ```

3. Start the Vite local development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to the local URL (typically `http://localhost:5173`).

### Building and Type Checking

To verify TypeScript types and create an optimized production build:
```bash
npm run build
```

To run TypeScript compiler verification standalone:
```bash
npx tsc --noEmit
```

---

## Roadmap & Architecture
- Detailed system design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- Step-by-step implementation plan: [docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)
