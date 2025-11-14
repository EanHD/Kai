# Feature Specification: FastAPI OpenAI-Compatible Endpoint

**Feature Branch**: `002-fastapi-openai-endpoint`  
**Created**: November 13, 2025  
**Status**: Draft  
**Input**: User request: "let's turn main.py in the root into fastapi full openai compatible endpoint for port 9000"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - OpenAI Chat Completions Endpoint (Priority: P1)

A developer sends POST requests to `/v1/chat/completions` endpoint and receives responses in OpenAI-compatible format, enabling drop-in replacement of OpenAI API.

**Why this priority**: This is the core API compatibility - without this, the endpoint cannot replace OpenAI's API in existing applications.

**Independent Test**: Can be fully tested by sending various chat completion requests matching OpenAI's API format and verifying responses match OpenAI's response schema.

**Acceptance Scenarios**:

1. **Given** a client sends a standard chat completion request, **When** the endpoint processes it, **Then** it returns a response matching OpenAI's response format exactly
2. **Given** a request includes streaming enabled, **When** processed, **Then** the endpoint streams SSE responses matching OpenAI's streaming format
3. **Given** a request includes system/user/assistant messages, **When** processed, **Then** conversation context is maintained correctly
4. **Given** invalid request format is sent, **When** validated, **Then** error responses match OpenAI's error format

---

### User Story 2 - Model Selection and Routing (Priority: P1)

A developer specifies a model name in the request, and the system intelligently routes to the appropriate backend (local or external) based on model availability.

**Why this priority**: Enables transparent model switching and maintains compatibility with OpenAI's model selection pattern.

**Independent Test**: Can be fully tested by requesting different model names and verifying correct routing to local (Ollama) or external (OpenRouter) models.

**Acceptance Scenarios**:

1. **Given** a request specifies a local model name, **When** routed, **Then** it uses Ollama backend with correct model
2. **Given** a request specifies an external model name, **When** routed, **Then** it uses OpenRouter backend with API key
3. **Given** a requested model is unavailable, **When** validated, **Then** it returns appropriate error with available models list
4. **Given** no model specified, **When** processed, **Then** it uses default model from configuration

---

### User Story 3 - Tool Calling Support (Priority: P2)

A developer includes tool/function definitions in the request, and the system executes tools (web search, code execution, memory) and returns results in OpenAI's function calling format.

**Why this priority**: Extends API compatibility to include OpenAI's function calling capabilities, enabling advanced integrations.

**Independent Test**: Can be fully tested by sending requests with tool definitions and verifying the system calls tools and formats responses correctly.

**Acceptance Scenarios**:

1. **Given** a request includes web search tool definition, **When** model requests tool call, **Then** web search is executed and results returned in function call format
2. **Given** a request includes code execution tool, **When** model generates code, **Then** code is executed safely and results returned
3. **Given** multiple tool calls are required, **When** processed, **Then** all tools execute and results are aggregated correctly
4. **Given** a tool execution fails, **When** handled, **Then** appropriate error is returned in tool call response

---

### User Story 4 - API Key Authentication (Priority: P2)

A developer includes an API key in request headers, and the system validates it before processing requests, ensuring secure access control.

**Why this priority**: Prevents unauthorized access and enables usage tracking per API key.

**Independent Test**: Can be fully tested by sending requests with valid/invalid/missing API keys and verifying authentication behavior.

**Acceptance Scenarios**:

1. **Given** a request includes valid API key, **When** authenticated, **Then** request is processed normally
2. **Given** a request has invalid API key, **When** validated, **Then** 401 Unauthorized response is returned
3. **Given** a request has no API key, **When** checked, **Then** either denied or uses default key based on configuration
4. **Given** API key usage, **When** tracked, **Then** costs and requests are attributed correctly

---

### User Story 5 - Health and Status Endpoints (Priority: P3)

A developer queries health and model list endpoints to verify service availability and discover available models.

**Why this priority**: Standard API practice for service monitoring and discovery.

**Independent Test**: Can be fully tested by calling `/health` and `/v1/models` endpoints and verifying correct responses.

**Acceptance Scenarios**:

1. **Given** service is running, **When** `/health` is called, **Then** it returns 200 OK with status details
2. **Given** models are available, **When** `/v1/models` is called, **Then** it returns list in OpenAI format
3. **Given** Ollama is down, **When** health checked, **Then** status reflects degraded state
4. **Given** startup, **When** dependencies initialize, **Then** health endpoint reports ready status

## Success Criteria *(mandatory)*

**Measurable Outcomes**:

1. **API Compatibility**: 100% compatibility with OpenAI Chat Completions API v1 specification
2. **Response Time**: P95 latency under 200ms for local model routing (excluding LLM inference time)
3. **Concurrent Requests**: Handle 50+ concurrent requests without degradation
4. **Error Rate**: Less than 0.1% error rate under normal operation
5. **Uptime**: 99.9% uptime during testing period

**Must Have**:
- Full OpenAI `/v1/chat/completions` endpoint compatibility
- Streaming response support with SSE
- Model routing to local and external providers
- Request validation matching OpenAI API
- Error responses matching OpenAI format

**Should Have**:
- Tool/function calling support
- API key authentication
- Rate limiting per API key
- Usage tracking and metrics
- Health monitoring endpoints

**Could Have**:
- OpenAI embeddings endpoint compatibility
- CORS configuration for web clients
- Request/response logging
- OpenAPI/Swagger documentation

**Won't Have** *(this release)*:
- Full OpenAI API compatibility beyond chat completions
- Image generation endpoints
- Fine-tuning endpoints
- Assistants API

## Edge Cases & Constraints *(mandatory)*

**Edge Cases**:

1. **Long-running requests**: Streaming responses must handle client disconnections gracefully
2. **Large message histories**: Very long conversation contexts should truncate appropriately
3. **Concurrent tool executions**: Multiple tools called simultaneously must not cause race conditions
4. **Model unavailability**: If specified model is down, should fail gracefully with clear error
5. **Malformed requests**: Invalid JSON or missing fields should return descriptive errors

**Technical Constraints**:

1. **Port**: Must run on port 9000 as specified
2. **Protocol**: HTTP/1.1 with SSE for streaming
3. **Format**: Exact OpenAI API compatibility for drop-in replacement
4. **Performance**: Non-blocking async for all I/O operations
5. **Dependencies**: Reuse existing orchestrator, no duplicate logic

**Privacy/Security**:

1. **API Keys**: Stored securely, never logged in plain text
2. **Request Data**: Conversation data follows existing privacy policies
3. **Rate Limiting**: Prevent abuse through API key-based limits
4. **Input Validation**: Prevent injection attacks through strict validation

## Dependencies & Assumptions *(mandatory)*

**Depends On**:
- Existing orchestrator from 001-llm-orchestrator-wrapper (completed)
- Ollama running on localhost:11434
- OpenRouter API key (optional, for external models)

**Assumes**:
- Orchestrator API is stable and well-tested
- FastAPI is acceptable framework choice
- SSE is acceptable for streaming (vs WebSocket)
- OpenAI Chat Completions API v1 is the target compatibility spec

## Open Questions *(mandatory)*

1. **API Key Storage**: Should API keys be stored in database or configuration file?
   - **Decision needed by**: Implementation start
   - **Impact**: Authentication architecture

2. **Rate Limiting Strategy**: Per-key limits or global limits?
   - **Decision needed by**: Implementation start
   - **Impact**: Resource allocation

3. **Logging Level**: Should we log full requests/responses or just metadata?
   - **Decision needed by**: Implementation start
   - **Impact**: Privacy and debugging capabilities

4. **Error Handling**: How verbose should error messages be in production?
   - **Decision needed by**: Testing phase
   - **Impact**: Security vs debuggability trade-off
