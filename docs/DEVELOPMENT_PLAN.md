# Voxara AI — Phased Development Plan

This document outlines the phased roadmap for building Voxara AI into a production-grade, real-time Agentic Voice AI assistant.

---

## Phase Overview

| Phase | Milestone Name | Status | Summary |
| :---: | :--- | :---: | :--- |
| **Step 1** | **Project Foundation & UI Prototype** | **Completed** | Setup React, TypeScript, Tailwind CSS, Framer Motion; implement responsive landing page, animated `AssistantOrb` with visual state machine, `MessageInput`, and documentation. |
| **Step 2** | **Real-Time Voice Infrastructure (LiveKit WebRTC)** | **Completed** | Integrate LiveKit WebRTC client, `useVoiceSession` hook, `voiceService`, FastAPI token generator, configuration validation, LiveKit agent entry point, and microphone controls. |
| **Step 3** | **Gemini Live Multimodal Voice AI Integration** | **Completed** | Official LiveKit Google plugin integration (`livekit-plugins-google`), Gemini Live bidirectional voice model (`RealtimeModel`), `AgentSession` loop, spoken greeting and conversation. |
| **Step 4** | **Agentic Orchestration & State Graphs** | Upcoming | LangGraph / workflow state machine for structured thinking, planning, and multi-turn task execution loops. |
| **Step 5** | **Model Context Protocol (MCP) & Tool Execution** | Upcoming | MCP server integrations for external tool execution (browsing, file manipulation, API querying), accompanied by an animated execution dashboard. |
| **Step 6** | **Production Hardening, Polish & E2E Testing** | Upcoming | Latency optimization, error recovery, session persistence, accessible keyboard shortcuts, and deployment. |

---

## Step 3 Scope Checklist

- [x] Install `livekit-plugins-google==1.8.6` supporting Gemini Live multimodal real-time API
- [x] Secure `GOOGLE_API_KEY`, `GEMINI_MODEL`, and `GEMINI_VOICE` configuration in backend
- [x] Update `backend/.env.example` with placeholder credentials
- [x] Configure `RealtimeModel` with native audio and custom system prompt
- [x] Implement `AgentSession` and `Agent` pipeline in `backend/app/agent.py`
- [x] Synchronize voice session state (`agentJoined`, `speaking`, `listening`, `idle`) with animated orb
- [x] FastAPI `/health` and `/api/voice/status` updated to report Gemini readiness
- [x] Verify frontend TypeScript compilation and production build (`0` errors)
- [x] Verify frontend linter (`oxlint` `0` errors)
- [x] Document connection architecture and interaction flows
