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
| **Step 4B** | **Gemini-Powered Skill Analysis Workflow** | **Completed** | Implement dedicated LangGraph workflow (`validate_input` -> `compare_skills` -> `analyze_skill_gaps` -> `validate_analysis`), deterministic Python set math, isolated Google GenAI text service, structured Pydantic schemas, and `POST /api/workflows/skill-analysis`. |
| **Step 4C** | **Voice Agent & LangGraph Integration** | **Completed** | Connect LiveKit voice agent (Gemini Live) to LangGraph workflows via function tools (`analyze_skills_demonstration`, `run_demo_workflow`) without competing loops; async non-blocking execution, execution store tracking, and voice-friendly spoken responses. |
| **Step 5** | **Opportunity Hunter & Research Watcher** | **Completed** | Production-ready Agentic AI capabilities: SQLite persistence with WAL mode, Opportunity Hunter workflow (Devpost/programs ingestion, deadlines, scoring), Research Watcher workflow (arXiv, Hugging Face, GitHub Releases), independent background scheduler, human-in-the-loop confirmation gate, and frontend activity & telemetry drawer. |
| **Step 6** | **Model Context Protocol (MCP) & Extensible Tools** | Upcoming | MCP server integrations for external tool execution (browsing, file manipulation, custom API querying). |
| **Step 7** | **Production Hardening, Polish & Deployment** | Upcoming | Latency optimization, error recovery, session persistence, accessible keyboard shortcuts, and cloud deployment. |

---

## Step 5 Scope Checklist

- [x] Persistent SQLite database layer with WAL mode and foreign keys in `backend/app/db/`
- [x] Typed Pydantic models and CRUD repositories for preferences, opportunities, research items, notifications, and executions
- [x] Real data source ingestion without fabrication:
  - Opportunity Hunter: Devpost Hackathons API, verified tech fellowship & internship programs
  - Research Watcher: Hugging Face Daily Papers API, GitHub Framework Releases API (LangGraph, MCP, LiveKit), arXiv CS.AI RSS
- [x] Deduplication engine with SHA-256 content hashing preventing redundant processing or alert spam
- [x] LangGraph Opportunity Hunter StateGraph (`load_hunt_criteria` -> `ingest_and_score` -> `track_deadlines_and_briefing`)
- [x] LangGraph Research Watcher StateGraph (`load_topics` -> `ingest_and_deduplicate` -> `generate_digest_and_briefing`)
- [x] LiveKit Voice Agent Tools: `hunt_opportunities_tool` and `check_research_updates_tool` with natural speech briefings
- [x] Proactive voice greetings on session connection when pending notifications exist
- [x] Autonomous background monitoring scheduler running in FastAPI lifespan independently of active voice sessions
- [x] Human-in-the-loop confirmation gate for consequential actions with verification tokens
- [x] Frontend Activity Drawer & Telemetry Panel with tabbed views for Opportunities, Research, Live Telemetry, and Alerts
- [x] Comprehensive automated test suite: 58 tests collected, 57 passed, 1 skipped

---

## Step 4C Scope Checklist

- [x] Inspect existing LiveKit agent, Gemini Live configuration, LangGraph graphs, and FastAPI endpoints
- [x] Select Approach A: Tool-based invocation via LiveKit `@llm.function_tool` preserving real-time audio duplex
- [x] Create LiveKit Agent tools in `backend/app/agent_tools.py`:
  - `analyze_skills_demonstration`: Step 4B Gemini-powered skill analysis LangGraph workflow
  - `run_demo_workflow`: Step 4A sequential state transition demonstration workflow
- [x] Enforce strict input validation, timeouts (`asyncio.wait_for`), and structured voice-friendly summaries
- [x] Implement thread-safe execution event store in `backend/app/workflows/execution_store.py`
- [x] Register tools with `Agent(tools=VOICE_AGENT_TOOLS)` in `backend/app/agent.py`
- [x] Update `VOXARA_SYSTEM_PROMPT` to protect ordinary conversational turns and prevent hallucinations
- [x] Expose execution retrieval endpoints (`GET /api/workflows/executions`, `GET /api/workflows/executions/{id}`)
- [x] Preserve existing token generation (`POST /api/voice/token`) and `/health` endpoints
- [x] Add comprehensive integration test suite in `backend/tests/test_agent_workflow_integration.py` (14 passing tests)

---

## Step 4B Scope Checklist

- [x] Configure supported Gemini text generation model in `backend/app/config.py` (`gemini_text_model`)
- [x] Add explicit `google-genai>=2.29.0` to `backend/requirements.txt`
- [x] Implement isolated Gemini text-generation service in `backend/app/services/gemini_service.py`
- [x] Define typed `SkillAnalysisState` with `operator.add` event reducer in `backend/app/workflows/state.py`
- [x] Define Pydantic models `SkillAnalysisRequest` and `SkillAnalysisResponse` with rigorous validation
- [x] Implement discrete workflow nodes in `backend/app/workflows/skill_nodes.py`:
  - `validate_input`: checks non-empty lists and trims whitespace
  - `compare_skills`: deterministic Python set comparison with case & whitespace normalization
  - `analyze_skill_gaps`: Gemini text model semantic gap analysis & priority ranking
  - `validate_analysis`: strict schema validation of returned output
- [x] Build and compile LangGraph `StateGraph` in `backend/app/workflows/skill_graph.py` with async runner
- [x] Implement `POST /api/workflows/skill-analysis` endpoint in `backend/app/routes/workflows.py`
- [x] Emit real lifecycle execution events (`node_start`, `node_finish`, `node_error`) with actual durations
- [x] Maintain 100% backward compatibility for `/health`, `/api/voice/*`, and `/api/workflows/demo`
- [x] Add comprehensive test suite in `backend/tests/test_skill_analysis.py` (26 tests covering all edge cases)

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

