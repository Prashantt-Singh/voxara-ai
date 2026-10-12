# Voxara AI — Phased Development Plan

This document outlines the phased roadmap for building Voxara AI into a production-grade, real-time Agentic Voice AI assistant.

---

## Phase Overview

| Phase | Milestone Name | Status | Summary |
| :---: | :--- | :---: | :--- |
| **Step 1** | **Project Foundation & UI Prototype** | **Current** | Setup React, TypeScript, Tailwind CSS, Framer Motion; implement responsive landing page, animated `AssistantOrb` with visual state machine, `MessageInput`, and documentation. |
| **Step 2** | **Audio Pipeline & Speech Interfaces** | Upcoming | Client-side audio capture (Web Audio API), audio visualizer integration, microphone permissions, audio playback streaming. |
| **Step 3** | **Backend Infrastructure & WebSocket Gateway** | Upcoming | FastAPI asynchronous server, low-latency WebSocket connection, bidirectional audio/text protocol. |
| **Step 4** | **Multimodal LLM & Voice Integration** | Upcoming | Gemini Live Multimodal API integration for real-time natural language dialogue with voice-to-voice streaming. |
| **Step 5** | **Agentic Orchestration & State Graphs** | Upcoming | LangGraph / workflow state machine for structured thinking, planning, and task execution loops. |
| **Step 6** | **Model Context Protocol (MCP) & Tool Execution** | Upcoming | MCP server integrations for external tool execution (browsing, file manipulation, API querying), accompanied by an animated execution dashboard. |
| **Step 7** | **Production Hardening, Polish & E2E Testing** | Upcoming | Latency optimization, error recovery, session persistence, accessible keyboard shortcuts, and deployment. |

---

## Step 1 Scope Checklist

- [x] React + TypeScript + Vite project initialization
- [x] Tailwind CSS and Framer Motion integration
- [x] Modular directory structure (`app/`, `components/assistant/`, `components/layout/`, `hooks/`, `types/`, `lib/`)
- [x] Minimalist landing page inspired by the reference design (warm yellow-orange gradient aesthetic)
- [x] `AssistantOrb` component with 6 visual demonstration states:
  - `idle`
  - `listening`
  - `thinking`
  - `executing`
  - `speaking`
  - `error`
- [x] `useAssistantState` hook managing state transitions
- [x] Accessible `MessageInput` component with plus, mic, and submit interactions
- [x] Local UI response / notice clarifying AI services will be connected in future steps (no fake backend responses)
- [x] Reduced motion accessibility (`prefers-reduced-motion`) support
- [x] TypeScript validation and production build checks
