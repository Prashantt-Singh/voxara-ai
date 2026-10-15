# Voxara AI — Phased Development Plan

This document outlines the phased roadmap for building Voxara AI into a production-grade, real-time Agentic Voice AI assistant.

---

## Phase Overview

| Phase | Milestone Name | Status | Summary |
| :---: | :--- | :---: | :--- |
| **Step 1** | **Project Foundation & UI Prototype** | **Completed** | Setup React, TypeScript, Tailwind CSS, Framer Motion; implement responsive landing page, animated `AssistantOrb` with visual state machine, `MessageInput`, and documentation. |
| **Step 2** | **Real-Time Voice Infrastructure (LiveKit WebRTC)** | **Completed** | Integrate LiveKit WebRTC client, `useVoiceSession` hook, `voiceService`, FastAPI token generator, configuration validation, LiveKit agent entry point, and microphone controls. |
| **Step 3** | **Gemini Live Multimodal Voice AI Integration** | **Completed** | Official LiveKit Google plugin integration (`livekit-plugins-google`), Gemini Live bidirectional voice model (`RealtimeModel`), `AgentSession` loop, spoken greeting and conversation. |
| **Step 4A** | **Agentic Workflow Foundation (LangGraph)** | **Completed** | Introduce LangGraph StateGraph orchestration layer, typed execution state, sequential nodes (`receive_request` -> `validate_request` -> `produce_result`), execution lifecycle events with true durations, and POST `/api/workflows/demo`. |
| **Step 4B** | **Voice Agent & LangGraph Integration** | Upcoming | Invoke LangGraph workflows from LiveKit voice agent without persistent competing loops. |
| **Step 5** | **Model Context Protocol (MCP) & Tool Execution** | Upcoming | MCP server integrations for external tool execution (browsing, file manipulation, API querying), accompanied by an animated execution dashboard. |
| **Step 6** | **Production Hardening, Polish & E2E Testing** | Upcoming | Latency optimization, error recovery, session persistence, accessible keyboard shortcuts, and deployment. |

---

## Step 4A Scope Checklist

- [x] Install `langgraph>=1.2.0` in backend environment and add to `requirements.txt`
- [x] Implement typed workflow state in `backend/app/workflows/state.py` with `operator.add` event reducer
- [x] Implement discrete workflow nodes in `backend/app/workflows/nodes.py`: `receive_request`, `validate_request`, `produce_result`
- [x] Construct and compile `StateGraph` in `backend/app/workflows/graph.py` with async `run_workflow` runner
- [x] Implement FastAPI router in `backend/app/routes/workflows.py` (`POST /api/workflows/demo`, `GET /api/workflows/status`)
- [x] Emit real lifecycle execution events (`node_start`, `node_finish`, `node_error`) with actual durations
- [x] Register router in `backend/app/main.py` without modifying voice infrastructure (`agent.py`)
- [x] Maintain backward compatibility for `/health`, `/api/voice/status`, and `/api/voice/token`
- [x] Add comprehensive test suite in `backend/tests/test_workflows.py` (12 passing tests)

