# SunChat System Requirements Document

## 1. Introduction
SunChat is a personal AI assistant that runs locally (or optionally in a cloud‑enabled mode) and provides conversational capabilities powered by large language models (LLMs). The system integrates persistent memory, a knowledge base (RAG), and free‑tier web search to deliver context‑aware answers while keeping user data private.

## 2. System Overview
The architecture is layered (see `architecture/overview.md`):
- **User Interaction Layer** – Web (React), Desktop (Tauri), Mobile (Flutter), CLI, Mini‑Program.
- **Security Gateway** – JWT‑based auth (local mode), input sanitisation, rate limiting, audit logging.
- **Intelligent Core** – Chat routing, LLM inference, Memory Service, Knowledge Service, Search Service.
- **Data Storage Layer** – SQLite for relational data, Chroma for vector embeddings, filesystem for uploaded documents, AES‑256‑GCM encrypted local storage.

## 3. Functional Requirements
### 3.1 Memory Management Service
1. **Create / Update / Delete Memory** – Store semantic, episodic, and working‑memory entries with metadata (type, category, tags, importance, confidence).
2. **Vectorisation** – Automatically generate embeddings via the configured embedding model and store the vector ID in Chroma.
3. **Semantic Retrieval** – Provide top‑k similarity search over user memories.
4. **Emotion Tagging** – Record valence, arousal, and dominant emotion linked to a memory.
5. **Retention Policies** – Configurable auto‑purge based on `memory_retention_days`.

### 3.2 Knowledge Base Service
1. **File Upload** – Accept PDF, DOCX, PPT, TXT, MD; store metadata and persist raw file.
2. **Chunking & Embedding** – Split documents into logical chunks, embed each chunk, and persist vectors in Chroma.
3. **RAG Query** – Retrieve relevant chunks for a user query and combine with LLM to generate answers.
4. **Status Tracking** – Track upload/processing/ready states and expose via API.

### 3.3 Search Integration Service
1. **Free‑Tier Search** – Use DuckDuckGo (and optional SearXNG) to fetch web results without API keys.
2. **Intent Routing** – Classify queries (news, academic, commerce, code, general) and augment with user memory context.
3. **Result Normalisation** – Return a unified JSON schema with title, URL, snippet, source, and confidence score.

### 3.4 Chat Routing & Conversation Service
1. **Session Management** – Create, list, rename, and delete chat sessions.
2. **Message Persistence** – Store each user and assistant message with timestamps and token usage.
3. **Dynamic Prompt Construction** – Inject system prompt, memory context, and search results before calling the LLM.
4. **Streaming / Non‑Streaming Responses** – Support both modes via Ollama API.
5. **Memory Extraction** – After each assistant reply, run a specialised LLM prompt to extract new memories and persist them.

### 3.5 API Endpoints (FastAPI)
- **Auth** – `/auth/register`, `/auth/login`, `/auth/me` (local mock implementation).
- **Chat** – `/chat/sessions`, `/chat/messages`, `/chat/sessions/{id}/messages`.
- **Memories** – CRUD and search endpoints (`/memories`, `/memories/search`).
- **Knowledge** – `/kb/upload`, `/kb/files`, `/kb/qa`.
- **Search** – `/search`, `/search/suggest`.
- **Health & Models** – `/health`, `/models`.

### 3.6 Front‑End UI Features
1. **Conversation View** – Real‑time streaming display, message editing, copy, and export.
2. **Memory Browser** – List, filter, and view memory details with importance weighting.
3. **Knowledge Explorer** – Upload documents, view processing status, and perform RAG queries.
4. **Search Panel** – Show web results with source attribution and allow “use in answer”.
5. **Settings** – Theme, model selection, retention policy, API endpoint overrides.
6. **Authentication UI** – Simple login/register flow (mock for local mode).

## 4. Non‑Functional Requirements
### 4.1 Performance
- **LLM Latency** – ≤ 2 seconds for typical 256‑token responses on recommended hardware (RTX 3060, 8 GB VRAM). Enable optional quantisation (`q4_K_M`) to meet the target.
- **Embedding Throughput** – ≤ 10 ms per 256‑token embedding call.
- **Search Response** – ≤ 1 second for top‑5 DuckDuckGo results.
- **API Throughput** – Minimum 50 concurrent requests without degradation (FastAPI + Uvicorn workers).

### 4.2 Security & Privacy
- **Data‑at‑Rest Encryption** – AES‑256‑GCM for SQLite file and Chroma vector store.
- **Key Management** – Store encryption key in OS keychain (Linux secret‑service) or environment variable.
- **Input Sanitisation** – Regex‑based filtering of user‑provided prompts to mitigate prompt injection.
- **Rate Limiting** – Per‑user request quota (configurable) to protect LLM and search APIs.
- **Audit Logging** – Log all API calls with user ID, endpoint, timestamp, and outcome.

### 4.3 Scalability
- **Horizontal Scaling** – Stateless FastAPI service; multiple instances behind a reverse proxy (NGINX) can be added.
- **Vector Store** – Chroma can be swapped for Milvus or Pinecone for > 1 M vectors without code changes.
- **Model Serving** – Ollama can run as a separate container; multiple models can be hot‑swapped.

### 4.4 Maintainability & Extensibility
- **Modular Codebase** – Services (`memory_service`, `knowledge_service`, `search_service`, `chat_service`) are independent and injected via FastAPI routers.
- **Configuration‑Driven** – All tunables live in `.env` and `app.config.Settings` (pydantic).
- **Testing** – Unit tests for each service (pytest) and integration tests for API endpoints.
- **Documentation** – OpenAPI spec auto‑generated; developer docs in `docs/`.

### 4.5 Reliability & Availability
- **Health Checks** – `/health` endpoint validates LLM and search availability.
- **Graceful Degradation** – If search is unavailable, fall back to memory‑only mode; if LLM fails, return error with guidance.
- **Backup & Restore** – Daily tarball of `data/` directory (SQLite + Chroma) with optional remote copy.

### 4.6 Usability
- **Responsive UI** – Web UI works on desktop and mobile browsers.
- **Accessibility** – ARIA labels, keyboard navigation, high‑contrast themes.
- **Internationalisation** – Core UI strings externalised; LLM prompts support Chinese and English.

## 5. Assumptions & Constraints
- The system will run primarily on a single user’s machine (local‑first). Cloud deployment is optional and uses the same code base.
- Ollama provides the LLM and embedding endpoints; no external API keys are required.
- Free DuckDuckGo search is sufficient for the MVP; paid APIs can be added later.
- Users have at least 16 GB RAM and a modest GPU (or CPU‑only fallback).
- All data is stored locally; no GDPR‑level data export is required beyond the provided `/data/export` endpoint.

## 6. Glossary
- **LLM** – Large Language Model.
- **RAG** – Retrieval‑Augmented Generation.
- **Chroma** – Open‑source vector database used for memory and knowledge embeddings.
- **Ollama** – Local model serving platform.
- **Tauri** – Framework for building native desktop apps with web UI.
- **Flutter** – Cross‑platform mobile UI toolkit.
- **AES‑256‑GCM** – Authenticated encryption algorithm for data at rest.
