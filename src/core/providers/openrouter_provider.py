"""OpenRouter provider implementation for external model routing."""

from typing import List, Optional, Dict, Any
from openai import AsyncOpenAI
from src.core.llm_connector import LLMConnector, Message, LLMResponse
import logging

logger = logging.getLogger(__name__)


class OpenRouterProvider(LLMConnector):
    """OpenRouter provider for external models (Claude Opus, etc.)."""

    def __init__(self, model_config: Dict[str, Any], api_key: str):
        """Initialize OpenRouter provider.
        
        Args:
            model_config: Model configuration dict
            api_key: OpenRouter API key
        """
        super().__init__(model_config)
        self.client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    async def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
        **kwargs
    ) -> LLMResponse:
        """Generate response using OpenRouter.
        
        Args:
            messages: Conversation messages
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            json_mode: Enable JSON response format
            **kwargs: Additional OpenAI-compatible parameters
            
        Returns:
            LLMResponse with generated content
        """
        try:
            # Convert messages to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content}
                for msg in messages
            ]
            
            # Build request parameters
            params = {
                "model": self.model_name,
                "messages": openai_messages,
                "temperature": temperature,
            }
            
            if max_tokens:
                params["max_tokens"] = max_tokens
            
            # Enable JSON mode if requested and supported
            if json_mode and self.supports_capability("json_mode"):
                params["response_format"] = {"type": "json_object"}
            
            # Add any extra parameters
            params.update(kwargs)
            
            # Call OpenRouter API
            response = await self.client.chat.completions.create(**params)
            
            # Extract response content
            content = response.choices[0].message.content
            finish_reason = response.choices[0].finish_reason
            
            # Extract token usage
            usage = response.usage
            prompt_tokens = usage.prompt_tokens
            completion_tokens = usage.completion_tokens
            total_tokens = usage.total_tokens
            
            # Calculate cost
            cost = self.calculate_cost(prompt_tokens, completion_tokens)
            
            return LLMResponse(
                content=content,
                token_count=total_tokens,
                cost=cost,
                model_used=self.model_name,
                finish_reason=finish_reason,
                metadata={
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "model_id": response.model,
                }
            )
        
        except Exception as e:
            logger.error(f"OpenRouter generation error: {e}")
            raise

    async def check_health(self) -> bool:
        """Check if OpenRouter API is accessible.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            # Make a minimal request to check API connectivity
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1,
            )
            return True
        
        except Exception as e:
            logger.error(f"OpenRouter health check failed: {e}")
            return False

    async def generate_structured(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
        output_schema: Optional[Dict[str, Any]] = None,
        temperature: float = 0.3,
        **kwargs
    ) -> LLMResponse:
        """Generate structured JSON response for complex tasks.
        
        This method minimizes token usage by:
        - Using concise system prompts
        - Enforcing JSON output format
        - Providing clear output schema
        
        Args:
            task_description: Clear description of the task
            context: Optional context dict (minimal)
            output_schema: Expected JSON structure
            temperature: Lower temperature for structured output
            **kwargs: Additional parameters
            
        Returns:
            LLMResponse with JSON content
        """
        # Build concise system message with schema
        system_msg = "Respond with valid JSON only. No explanation."
        
        if output_schema:
            system_msg += f" Schema: {output_schema}"
        
        # Build minimal user message
        user_msg = task_description
        
        if context:
            # Add context compactly
            context_str = " ".join([f"{k}:{v}" for k, v in context.items()])
            user_msg += f" Context: {context_str}"
        
        messages = [
            Message(role="system", content=system_msg),
            Message(role="user", content=user_msg),
        ]
        
        # Generate with JSON mode enabled
        return await self.generate(
            messages=messages,
            temperature=temperature,
            json_mode=True,
            **kwargs
        )
