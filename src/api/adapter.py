"""Adapter layer between OpenAI API format and Kai orchestrator.

This module provides conversion functions to translate between:
- OpenAI chat completion requests → Orchestrator format
- Orchestrator responses → OpenAI chat completion responses
"""

from typing import Any, Dict, List, Optional, AsyncIterator
from datetime import datetime
import logging
import asyncio

logger = logging.getLogger(__name__)


class OrchestratorAdapter:
    """Adapter for converting between OpenAI and orchestrator formats."""

    def __init__(self, orchestrator_client, reflection_agent=None, memory_vault=None):
        """Initialize adapter with orchestrator client.
        
        Args:
            orchestrator_client: Instance of Kai orchestrator
            reflection_agent: Optional reflection agent for continuous learning
            memory_vault: Optional memory vault for storing episodes
        """
        self.orchestrator = orchestrator_client
        self.reflection_agent = reflection_agent
        self.memory_vault = memory_vault

    def convert_request(
        self,
        openai_request: Dict[str, Any],
        provider: str,
        backend_model: str,
    ) -> Dict[str, Any]:
        """Convert OpenAI chat completion request to orchestrator format.
        
        Args:
            openai_request: OpenAI-formatted request dict
            provider: Backend provider (ollama/openrouter)
            backend_model: Backend-specific model name
            
        Returns:
            Orchestrator-formatted request dict
        """
        # Extract messages from OpenAI format
        messages = openai_request.get("messages", [])
        
        # Map OpenAI parameters to orchestrator parameters
        orchestrator_request = {
            "messages": messages,
            "provider": provider,
            "model": backend_model,
            "temperature": openai_request.get("temperature"),
            "max_tokens": openai_request.get("max_tokens"),
            "top_p": openai_request.get("top_p"),
            "frequency_penalty": openai_request.get("frequency_penalty"),
            "presence_penalty": openai_request.get("presence_penalty"),
            "stop": openai_request.get("stop"),
            "stream": openai_request.get("stream", False),
        }
        
        # Handle tools/functions if present
        if "tools" in openai_request:
            orchestrator_request["tools"] = openai_request["tools"]
        
        if "tool_choice" in openai_request:
            orchestrator_request["tool_choice"] = openai_request["tool_choice"]
        
        # Filter out None values
        orchestrator_request = {
            k: v for k, v in orchestrator_request.items() if v is not None
        }
        
        return orchestrator_request

    def convert_response(
        self,
        orchestrator_response: Dict[str, Any],
        model_name: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Convert orchestrator response to OpenAI chat completion format.
        
        Args:
            orchestrator_response: Response from orchestrator
            model_name: Original model name from request
            request_id: Unique request ID
            
        Returns:
            OpenAI-formatted response dict
        """
        # Extract content from orchestrator response
        content = orchestrator_response.get("content", "")
        
        # Build OpenAI response structure
        openai_response = {
            "id": request_id,
            "object": "chat.completion",
            "created": int(datetime.now().timestamp()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": orchestrator_response.get("finish_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": orchestrator_response.get("prompt_tokens", 0),
                "completion_tokens": orchestrator_response.get("completion_tokens", 0),
                "total_tokens": orchestrator_response.get("total_tokens", 0),
            },
            # Custom metadata for logging
            "_metadata": {
                "cost": orchestrator_response.get("cost", 0.0),
                "model_used": orchestrator_response.get("model_used", model_name),
            }
        }
        
        # Add tool calls if present
        if "tool_calls" in orchestrator_response:
            openai_response["choices"][0]["message"]["tool_calls"] = (
                orchestrator_response["tool_calls"]
            )
        
        return openai_response

    async def convert_stream_chunk(
        self,
        orchestrator_chunk: Dict[str, Any],
        model_name: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Convert orchestrator stream chunk to OpenAI format.
        
        Args:
            orchestrator_chunk: Chunk from orchestrator stream
            model_name: Original model name from request
            request_id: Unique request ID
            
        Returns:
            OpenAI-formatted stream chunk dict
        """
        # Extract delta content
        delta_content = orchestrator_chunk.get("delta", "")
        finish_reason = orchestrator_chunk.get("finish_reason")
        
        # Build OpenAI stream chunk structure
        chunk = {
            "id": request_id,
            "object": "chat.completion.chunk",
            "created": int(datetime.now().timestamp()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": finish_reason,
                }
            ],
        }
        
        # Add content to delta if present
        if delta_content:
            chunk["choices"][0]["delta"]["content"] = delta_content
        
        # Add role for first chunk
        if orchestrator_chunk.get("is_first_chunk"):
            chunk["choices"][0]["delta"]["role"] = "assistant"
        
        # Add tool calls delta if present
        if "tool_calls" in orchestrator_chunk:
            chunk["choices"][0]["delta"]["tool_calls"] = orchestrator_chunk["tool_calls"]
        
        return chunk

    async def invoke_orchestrator(
        self, request: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke orchestrator with request (non-streaming).
        
        Args:
            request: Orchestrator-formatted request
            
        Returns:
            Orchestrator response dict
        """
        logger.info(f"Invoking orchestrator: provider={request.get('provider')}, model={request.get('model')}")
        
        # Extract messages - get last user message as query
        messages = request.get("messages", [])
        if not messages:
            raise ValueError("No messages in request")
        
        # Get the last user message as the current query
        query_text = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query_text = msg.get("content", "")
                break
        
        if not query_text:
            raise ValueError("No user message found in request")
        
        # Get or create conversation session
        # For API, we use a session per request for stateless operation
        # Session ID could be passed in metadata or generated
        conversation = request.get("_conversation")
        if not conversation:
            # Create a minimal conversation session
            from src.models.conversation import ConversationSession
            conversation = ConversationSession(
                user_id=request.get("user", "api-user"),
                cost_limit=100.0,  # High limit for API usage
                request_source="api"
            )
            # Populate with message history (excluding last user message)
            for msg in messages[:-1]:  # All messages except the current query
                conversation.add_to_context({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        
        # Process query through orchestrator
        response = await self.orchestrator.process_query(
            query_text=query_text,
            conversation=conversation,
        )
        
        # Generate reflection in background (don't block response)
        if self.reflection_agent and self.memory_vault:
            # Fire and forget - reflection runs asynchronously
            asyncio.create_task(self._reflect_on_api_interaction(
                query_text=query_text,
                response_text=response.content,
                mode=response.mode if hasattr(response, 'mode') else 'unknown',
                tool_results=response.tool_results if hasattr(response, 'tool_results') else [],
            ))
        
        # Convert Response object to dict format
        # Calculate token usage (approximate if not available)
        # Messages in the request are dicts with 'role' and 'content'
        prompt_tokens = sum(
            msg.get("token_count", len(str(msg.get("content", ""))) // 4) 
            for msg in messages 
            if isinstance(msg, dict)
        )
        completion_tokens = response.token_count or len(response.content) // 4
        
        return {
            "content": response.content,
            "finish_reason": "stop",
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": response.cost if hasattr(response, 'cost') else 0.0,
            "model_used": response.model_used if hasattr(response, 'model_used') else request.get("model", "unknown"),
        }

    async def invoke_orchestrator_stream(
        self, request: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Invoke orchestrator with streaming request.
        
        Args:
            request: Orchestrator-formatted request
            
        Yields:
            Orchestrator response chunks
        """
        logger.info(f"Invoking orchestrator stream: provider={request.get('provider')}, model={request.get('model')}")
        
        # Extract messages
        messages = request.get("messages", [])
        if not messages:
            raise ValueError("No messages in request")
        
        # Get last user message
        query_text = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                query_text = msg.get("content", "")
                break
        
        if not query_text:
            raise ValueError("No user message found in request")
        
        # Convert to Message objects
        from src.core.llm_connector import Message
        message_objs = [
            Message(role=msg.get("role", "user"), content=msg.get("content", ""))
            for msg in messages
        ]
        
        # Get the appropriate connector
        provider = request.get("provider", "ollama")
        if provider == "ollama" and self.orchestrator.local_connector:
            connector = self.orchestrator.local_connector
        elif provider in self.orchestrator.external_connectors:
            connector = self.orchestrator.external_connectors[provider]
        else:
            raise ValueError(f"Provider {provider} not available")
        
        # Stream from connector
        temperature = request.get("temperature", 0.7)
        max_tokens = request.get("max_tokens")
        
        try:
            async for chunk in connector.generate_stream(
                messages=message_objs,
                temperature=temperature,
                max_tokens=max_tokens,
            ):
                yield {
                    "delta": chunk,
                    "is_first_chunk": False,
                }
            
            # Final chunk with finish_reason
            yield {
                "delta": "",
                "finish_reason": "stop",
            }
        
        except Exception as e:
            logger.error(f"Streaming error: {e}")
            raise RuntimeError(f"Failed to stream response: {str(e)}")
    
    async def _reflect_on_api_interaction(
        self,
        query_text: str,
        response_text: str,
        mode: str,
        tool_results: list,
    ):
        """Run reflection on API interaction in background.
        
        This runs asynchronously without blocking the response.
        Stores episodic memory and generates reflection.
        
        Args:
            query_text: User's query
            response_text: Assistant's response
            mode: Response mode (concise/expert/advisor)
            tool_results: List of tool results used
        """
        try:
            # Store episodic memory
            episode_record = await self.memory_vault.write_episodic(
                session_id="api_session",  # Generic session for API requests
                user_text=query_text,
                assistant_text=response_text,
                success=True,
                summary=response_text[:200],
                confidence=0.8,  # Default confidence for API interactions
                tags=[mode, "api"],
            )
            
            if episode_record:
                # Generate reflection
                tools_used = [t.tool_name for t in tool_results] if tool_results else []
                await self.reflection_agent.reflect_on_episode(
                    episode_id=episode_record.id,
                    user_text=query_text,
                    assistant_text=response_text,
                    success=True,
                    mode=mode,
                    tools_used=tools_used,
                )
                logger.debug(f"Background reflection completed for API interaction")
        except Exception as e:
            logger.warning(f"Background reflection failed: {e}")
