# Voxara AI — Phased Development Plan

This document outlines the phased roadmap for building Voxara AI into a production-grade, real-time Agentic Voice AI assistant.

---

## Phase Overview

| Phase | Milestone Name | Status | Summary |
| :---: | :--- | :---: | :--- |
| **Step 1** | **Project Foundation & UI Prototype** | **Completed** | Setup React, TypeScript, Tailwind CSS, Framer Motion; implement responsive landing page, animated `AssistantOrb` with visual state machine, `MessageInput`, and documentation. |
| **Step 2** | **Real-Time Voice Infrastructure (LiveKit WebRTC)** | **Completed** | Integrate LiveKit WebRTC client, `useVoiceSession` hook, `voiceService`, FastAPI token generator, configuration validation, LiveKit agent entry point, and microphone controls. |
| **Step 3** | **Audio Pipeline & Speech Processing** | Upcoming | Client-side audio processing, VAD calibration, noise suppression fine-tuning, and audio level visualization. |
| **Step 4** | **Multimodal LLM & Conversational Voice Agent** | Upcoming | Gemini Live Multimodal API integration for bidirectional voice-to-voice conversation with interruption support. |
| **Step 5** | **Agentic Orchestration & State Graphs** | Upcoming | LangGraph / workflow state machine for structured thinking, planning, and task execution loops. |
| **Step 6** | **Model Context Protocol (MCP) & Tool Execution** | Upcoming | MCP server integrations for external tool execution (browsing, file manipulation, API querying), accompanied by an animated execution dashboard. |
| **Step 7** | **Production Hardening, Polish & E2E Testing** | Upcoming | Latency optimization, error recovery, session persistence, accessible keyboard shortcuts, and deployment. |

---

## Step 2 Scope Checklist

- [x] Integrate official LiveKit React client libraries (`livekit-client`, `@livekit/components-react`)
- [x] Implement frontend `useVoiceSession` hook with lifecycle management
- [x] Implement frontend `voiceService` module for backend token requests
- [x] Connect microphone button to real voice session lifecycle
- [x] Display accurate states for `disconnected`, `connecting`, `connected`, `listening`, `speaking`, `error`
- [x] Surface connection and permission errors cleanly in the UI
- [x] Clean session teardown and duplicate connection protection
- [x] FastAPI backend under `backend/app/` with `/api/voice/status` and `/api/voice/token`
- [x] Secure short-lived token generation via official LiveKit Python SDK
- [x] Strict secret isolation (secrets never exposed to client or logged)
- [x] Configuration validation with descriptive error reporting
- [x] LiveKit Agent worker entrypoint skeleton (`backend/app/agent.py`)
- [x] Full TypeScript type-checking and Vite production build verified
