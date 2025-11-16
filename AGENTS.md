# Kai Architectural Reference for AI Agents

CRITICAL: Read this entire document before making ANY changes to the Kai codebase. This is the source of truth for system architecture, design intent, and operational principles. Deviation from these patterns will break the system.

## Project Mission

Kai is a production-grade AI orchestrator designed to maximize local compute efficiency while maintaining access to powerful cloud models when necessary. The system prioritizes local-first inference using Granite running on Ollama, escalating to external models only when complexity demands it. All inter-model communication happens through structured JSON, eliminating token waste from natural language handoffs. The core design principle is deterministic planning where every math operation routes through code execution, every external fact goes through web search, and every user-facing response comes from the local Granite model. The system maintains strict cost controls with soft and hard caps, automatically degrading to cheaper models as budgets approach limits. Kai learns from every interaction through a reflection loop that distills patterns into improved prompts and routing rules without changing model weights.

## High-Level Architecture

The system operates on a four-tier model hierarchy designed for progressive capability escalation. Granite-local serves as the primary interface layer, handling all user interactions, plan generation, and response presentation. This model runs continuously on local hardware via Ollama, processing simple queries directly and formatting all final responses. When Granite detects complexity beyond its capabilities, it generates a JSON plan that may invoke external models.

Grok-4-fast operates as the mid-tier reasoner, handling queries that require multi-step logic, moderate analysis, or coordination of multiple tools. This model receives structured JSON requests from the plan executor and returns JSON responses containing reasoning chains, intermediate conclusions, or verification checks. Grok never directly addresses users and exists purely as a reasoning engine within the orchestration pipeline.

Claude Sonnet 4.5 functions as the high-tier specialist for critical verification tasks, complex reasoning that Grok cannot handle, safety validation of generated code or plans, and correction of errors detected in earlier processing stages. Sonnet receives highly structured verification requests and returns detailed analysis in JSON format. Like Grok, Sonnet never generates user-facing text.

Claude Opus 4.1 represents the top-tier planner reserved for system-level tasks like generating comprehensive documentation, designing new architectural components, or handling queries explicitly requesting maximum intelligence. Opus usage requires explicit user request or system-level trigger and incurs significant cost, making it inappropriate for routine queries.

## Tool Stack

The web_search tool provides grounded external information retrieval using DuckDuckGo as the primary provider with caching for efficiency. This tool is mandatory for any query requiring external facts, current information, or verification of claims. It returns structured search results with citations that must be preserved through the response pipeline.

The code_exec tool executes Python code in isolated Docker containers for all mathematical calculations, data processing, unit conversions, and algorithmic operations. This tool runs in sandboxed environments with memory and CPU limits, network isolation, and optional gVisor runtime for enhanced security. Every calculation must route through this tool rather than being performed mentally by any model.

The sanity_check tool validates numerical outputs against physical constraints and reasonable ranges. It catches errors like batteries with impossible energy densities, calculations yielding negative distances, or results off by orders of magnitude. This tool runs after code execution but before specialist verification.

The reflection agent analyzes completed episodes to extract patterns, identify successful strategies, and generate improved prompts or routing rules. It runs asynchronously after each interaction, storing insights in the memory vault for future reference. Reflection never modifies model weights but influences system behavior through prompt evolution.

The model_router determines which model handles each step of the execution plan based on complexity scoring, capability requirements, cost constraints, and current budget status. It implements fallback strategies when preferred models are unavailable and ensures cost caps are respected.

## File-by-File Responsibilities

src/core/orchestrator.py serves as the central coordination point that receives queries from CLI or API, manages conversation state, invokes the plan analyzer, executes plans through the plan executor, and returns formatted responses. It maintains references to all connectors, tools, and the cost tracker while implementing the fast path for simple queries that bypass planning.

src/core/plan_analyzer.py generates structured JSON execution plans by analyzing query complexity and required capabilities. It receives query text and context, determines which tools and models are needed, and produces a detailed step-by-step plan with dependencies. When JSON generation fails, it creates fallback plans using query analysis results.

src/core/plan_executor.py executes plans by running tools in topological order based on dependencies, passing results between steps, invoking specialists when specified, and aggregating all results for the presenter. It handles tool failures gracefully and maintains execution state throughout the pipeline.

src/core/presenters/granite_presenter.py transforms structured results into natural language responses. It receives tool outputs, specialist analyses, and citations, then generates user-friendly answers with proper attribution. This is the only component that produces user-facing text, ensuring consistent voice and style.

src/core/query_analyzer.py performs rapid pattern matching and complexity detection on incoming queries to determine required capabilities like code execution or web search. It uses regex patterns and keyword matching to detect mathematical expressions, battery pack notation, external fact requests, and other query types requiring specific tools.

src/core/response_processor.py handles post-processing of final answers including citation formatting, markdown cleanup, length validation, and quality checks before responses reach users.

src/core/sanity_checker.py validates numerical results against physical constraints and reasonable ranges. It contains domain-specific validators for battery energy density, distance calculations, percentage values, and other measurable quantities.

src/core/cost_tracker.py maintains running totals of token usage and costs across all model calls. It enforces soft caps at eighty percent and hard caps at one hundred percent of configured budgets, triggering automatic degradation to cheaper models or local-only mode.

src/core/code_generator.py produces executable Python code from task specifications for common calculation patterns like battery pack energy, unit conversions, physics calculations, and generic math operations. It works with code_exec_wrapper to provide task-based execution.

src/core/conversation_service.py manages conversation history, context windows, and message formatting for both CLI and API interfaces. It handles truncation of long conversations and maintains conversation state across multiple turns.

src/tools/web_search.py implements the web search interface with DuckDuckGo integration, result caching, citation extraction, and fallback strategies for rate limits or failures. It returns structured data that preserves source attribution through the pipeline.

src/tools/code_exec_wrapper.py provides safe code execution with task-based routing for common calculations, validation of input schemas, Docker container management, and timeout enforcement. It handles battery calculations with XsYp notation parsing, unit conversions, physics problems, and generic math through specialized task handlers.

src/tools/code_executor.py manages the Docker container lifecycle for code execution including container creation with resource limits, code injection, output capture, timeout handling, and cleanup. It provides the low-level execution engine that code_exec_wrapper orchestrates.

src/tools/memory_store.py interfaces with the memory vault for storing and retrieving personal information, preferences, and learned patterns. It handles encryption, retrieval, and vector search across stored memories.

src/tools/sentiment_analyzer.py analyzes emotional tone in user queries to inform response mode selection and model routing decisions. It detects frustration, excitement, confusion, and other emotional states.

src/agents/reflection_agent.py performs post-interaction analysis to identify what worked and what failed, extracts reusable patterns and strategies, generates improved prompts and routing rules, and maintains learning history in the memory vault.

src/api/adapter.py provides the OpenAI-compatible REST interface that translates between OpenAI format and internal structures, manages streaming responses, tracks costs per request, and maintains session state across requests.

src/api/streaming.py implements server-sent events for streaming responses in OpenAI format, handling chunk generation, error propagation, and connection management.

src/api/handlers/chat.py processes chat completion requests including input validation, conversation context management, orchestrator invocation, and response formatting in OpenAI schema.

src/api/handlers/health.py provides health check endpoints that verify Ollama connectivity, external model availability, tool readiness, and overall system status.

src/api/handlers/models.py returns the list of available models in OpenAI format, translating internal model configurations to the expected API schema.

src/core/providers/ollama_provider.py manages communication with the local Ollama service for Granite model inference. It handles connection pooling, request formatting, response parsing, and error handling for local model calls.

src/core/providers/openrouter_provider.py manages communication with OpenRouter for external model access including Grok and Claude variants. It handles API authentication, request formatting, streaming responses, and cost calculation based on token usage.

src/storage/memory_vault.py provides encrypted storage for personal information, conversation history, and learned patterns. It implements vector search for semantic retrieval and maintains privacy through encryption at rest.

src/storage/sqlite_store.py manages structured data storage in SQLite for conversation logs, episode summaries, reflection outputs, and system metrics.

src/storage/vector_store.py provides vector embedding and similarity search capabilities for RAG-based retrieval and semantic memory lookup.

config/models.yaml defines available models with their capabilities, context windows, costs, and routing preferences. This configuration determines which models are available for each tier of reasoning.

config/tools.yaml specifies enabled tools with their configuration parameters, fallback strategies, and resource limits. This controls which capabilities are available to the system.

config/api.yaml contains API server configuration including ports, CORS settings, rate limits, and authentication requirements.

tests/production/ contains critical validation tests that verify calculation accuracy, multi-tool coordination, cost enforcement, and response quality using real API calls to ensure the system works correctly in production.

tests/integration/ validates end-to-end workflows including orchestration patterns, model routing, cost tracking, and API compatibility with multiple test configurations.

tests/unit/ provides isolated testing of individual components including code generators, sanitizers, response processors, and tool implementations.

tests/regression/ prevents reintroduction of previously fixed bugs with targeted tests for each resolved issue including calculation errors, serialization problems, and API mismatches.

tests/static/ enforces code quality standards through linting, formatting checks, and import validation.

tests/stress/ validates system behavior under load including concurrent requests, long conversations, and resource exhaustion scenarios.

## The Ideal Workflow

Every query begins with Granite performing rapid complexity analysis to determine if the query requires tools or external models. Simple queries like greetings or factual recalls take the fast path directly through Granite without planning. Complex queries trigger plan generation where Granite produces a JSON execution plan specifying required tools and potential model escalations.

The plan executor runs tools in dependency order, starting with information gathering via web search if external facts are needed. All calculations route mandatorily through code_exec with structured task definitions rather than raw code. The sanity checker validates all numerical results against physical constraints. If results require verification or complex reasoning, the executor invokes Grok for mid-tier analysis. Critical verifications or safety checks escalate to Sonnet for thorough validation.

After all tools and specialists complete, results flow to the Granite presenter which transforms structured data into natural language. Granite weaves tool outputs, specialist insights, and citations into coherent answers while maintaining consistent voice and appropriate detail level. The reflection agent asynchronously analyzes the complete episode for learning opportunities.

Cost optimization happens at every decision point. The fast path avoids all external costs for simple queries. The planner minimizes external model calls by batching work locally. The executor uses Grok instead of Sonnet when possible. The presenter always uses local Granite rather than external models. As sessions approach cost limits, the system automatically prefers cheaper models and eventually restricts to local-only operation.

## Failure Modes and Expectations

When a tool is unavailable, the system logs the failure and attempts fallback strategies such as using cached results for web search or providing clear error messages for code execution. The presenter acknowledges tool failures transparently rather than hallucinating results.

When a plan is missing required steps like math queries without code_exec, the plan validation logs warnings and either injects missing steps automatically or refuses to provide confident numerical answers. The system never allows models to perform mental math.

When JSON parsing fails from any model, the system attempts multiple extraction strategies including markdown extraction, bracket matching, and pattern recognition. If parsing completely fails, appropriate fallbacks activate such as using query analysis for planning or simplified responses for presentation.

When external APIs fail or timeout, the system provides degraded but honest responses acknowledging the limitation. Local models explain what cannot be done rather than fabricating information. Cost tracking remains accurate even during failures.

When sanity checks flag unrealistic values, the system escalates to specialist verification automatically. Grok or Sonnet analyze why the calculation produced unusual results. The presenter includes appropriate caveats about uncertain calculations.

## Guiding Principles

Granite never roleplays tool execution or pretends to search the web or run code. It generates plans that invoke actual tools and formats real results. This prevents hallucinated search results or incorrect calculations.

No model ever performs mental math regardless of query simplicity. Every calculation from basic arithmetic to complex physics must route through code_exec. This ensures accuracy and auditability.

Sonnet never writes prose intended for users. It produces JSON analysis that Granite transforms into natural language. This separation ensures consistent voice and prevents expensive tokens on formatting.

Granite always serves as the final presenter regardless of which models contributed to reasoning. This provides consistent user experience and keeps presentation costs minimal.

JSON handoffs between models are deterministic with defined schemas. This eliminates ambiguity and reduces token usage compared to natural language handoffs. Models communicate through structured data rather than prose.

Cost optimization is a core system value influencing every architectural decision. The system tracks costs precisely, enforces caps strictly, and degrades gracefully as budgets deplete. Local-first processing minimizes external API calls while maintaining quality.

## Critical Implementation Rules

NEVER allow any model to perform calculations mentally. If you see code that allows LLMs to do math directly, this is a bug that must be fixed by routing through code_exec.

NEVER create user-facing responses from external models. All final answers must flow through Granite presenter to maintain consistent voice and minimize cost.

NEVER bypass the plan-execute-present pattern for complex queries. Simple fast-path queries are acceptable but anything requiring tools or reasoning must follow the full pipeline.

NEVER modify the query analyzer patterns or code_exec task handlers without testing against the production test suite. These components have specific regex patterns and task schemas that are validated by tests.

NEVER change JSON schemas without updating all consumers. Plan structures, tool inputs, and specialist outputs have defined formats that multiple components depend on.

ALWAYS preserve citations through the response pipeline. Web search results include source attribution that must reach the final answer.

ALWAYS validate numerical outputs through sanity checking before presenting to users. Physical impossibilities should trigger warnings or re-verification.

ALWAYS track costs accurately. Every model call must update the cost tracker with actual token usage and calculated costs.

ALWAYS maintain the four-tier model hierarchy. Do not bypass tiers or create direct connections that violate the escalation pattern.

ALWAYS use structured logging with emojis and clear categorization. Logs should indicate query start, plan generation, tool execution, model routing, and completion with timing and cost data.

## Common Patterns and Anti-Patterns

CORRECT: Query contains math expression, query analyzer detects code_exec requirement, plan includes code_exec step with proper task schema, executor runs calculation, sanity checker validates result, presenter formats answer with calculation shown.

INCORRECT: Query contains math, Granite attempts calculation in prompt, returns potentially wrong answer without verification.

CORRECT: Query asks for current information, plan includes web_search step, search returns results with citations, presenter weaves facts into answer with source attribution.

INCORRECT: Query asks for current info, model hallucinates facts without search, no citations provided.

CORRECT: Complex reasoning needed, plan invokes Grok specialist with structured JSON request, Grok returns analysis, Granite presents insights in natural language.

INCORRECT: Complex query goes directly to Sonnet bypassing Grok tier, wastes expensive tokens on mid-tier work.

CORRECT: JSON parse fails, system extracts using fallback patterns, logs warning, creates simplified plan using query analysis.

INCORRECT: JSON parse fails, system crashes or returns error to user without attempting recovery.

CORRECT: Cost approaching soft cap, system switches to cheaper models, logs degradation, continues with reduced capabilities.

INCORRECT: Cost exceeds hard cap, system continues making expensive calls, budget violated.

## Testing Requirements

Before ANY change to core orchestration, plan generation, or tool execution, run the production test suite to verify calculations remain accurate. The battery pack tests validate the critical path of query analysis, plan generation, code execution, and result presentation.

Before changing model routing logic, run integration tests to verify tier selection, cost tracking, and fallback behavior work correctly across different query types.

Before modifying tool schemas or JSON formats, run regression tests to ensure previously fixed bugs do not reappear and existing functionality remains intact.

After any code changes, run static tests to verify formatting, linting, and import correctness. The codebase maintains strict quality standards.

When adding new features, add corresponding tests in the appropriate suite. Production tests for critical paths, integration tests for workflows, unit tests for components, regression tests for bug fixes.

## System State and Configuration

The system expects specific environment variables in the .env file including OPENROUTER_API_KEY for external model access, BRAVE_API_KEY for web search (optional), and OLLAMA_BASE_URL for local model endpoint.

The Ollama service must be running with the granite4:micro-h model available. Check with ollama list and pull if missing.

Docker must be available for code execution with appropriate permissions to create containers, mount volumes, and enforce resource limits.

Configuration files in config/ directory control available models, enabled tools, and API settings. Changes to these files affect system capabilities and should be tested carefully.

The data/ directory contains persistent storage for memory vault, conversation logs, and vector embeddings. This directory should not be deleted as it contains learning history.

## Additional Context for AI Agents

When asked to make changes, ALWAYS start by reading the relevant test files to understand expected behavior. Tests encode the requirements and edge cases that must be preserved.

When debugging issues, check logs for structured entries showing the query path through the system. Logs indicate which models were called, which tools executed, and where failures occurred.

When improving performance, focus on reducing external model calls rather than optimizing local processing. The bottleneck is API latency and cost, not local compute.

When adding features, consider impact on cost tracking, plan validation, and response formatting. New capabilities should integrate with existing patterns rather than creating parallel paths.

When fixing bugs, add regression tests to prevent reoccurrence. Document the fix in CHANGELOG.md with clear description of the problem and solution.

The codebase uses Python 3.11+ features including type hints, dataclasses, and pattern matching. Maintain consistency with existing code style and use ruff for formatting.

The project uses uv for dependency management. Changes to dependencies should update pyproject.toml and regenerate requirements.lock for reproducible builds.

The API interface is OpenAI-compatible for easy integration with existing tools and libraries. Maintain schema compatibility when modifying API responses.

The reflection loop runs asynchronously and may not complete before the next query. Design for eventual consistency rather than immediate availability of learned patterns.

The system is production-ready with 95% test coverage across 148 tests. Maintain this quality bar for all new code. Breaking changes require updating documentation and version numbers.
