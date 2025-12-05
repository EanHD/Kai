# src/core/presenters/local_presenter.py
import logging
import json
from typing import Any, AsyncGenerator, Optional
from src.core.llm_connector import LLMConnector, Message
from src.models.knowledge import KnowledgeObject

logger = logging.getLogger(__name__)

class LocalPresenter:
    def __init__(self, connector: LLMConnector):
        self.connector = connector

    async def narrate_knowledge_object(
        self, 
        ko: KnowledgeObject,
        user_preferences: Optional[dict] = None
    ) -> AsyncGenerator[str, None]:
        """
        Narrate a Knowledge Object using the local model.
        """
        
        # 1. Construct System Prompt
        system_prompt = """
        You are Kai.
        VIBE: Witty, smart, slightly rebellious. You are NOT a bot.
        You speak casually. You don't lecture.
        
        IDENTITY RULES:
        1. You are Kai.
        2. Never start with "I am an AI" or "As an AI".
        
        STYLE RULES:
        1. Stick to the facts provided.
        2. Be warm but not fake-nice.
        3. Write in plain text.
        4. Be concise.
        """
        
        if user_preferences:
            system_prompt += f"\nUser Preferences: {json.dumps(user_preferences)}"
            
        # 2. Construct User Prompt
        # We present the KO as a structured summary
        ko_summary = {
            "query": ko.query,
            "summary": ko.summary,
            "points": [p.model_dump() for p in ko.detailed_points],
            "limitations": ko.limitations
        }
        
        user_content = f"Here is the knowledge to explain:\n{json.dumps(ko_summary, indent=2)}"
        
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content)
        ]
        
        # 3. Stream Response
        async for chunk in self.connector.generate_stream(
            messages=messages,
            temperature=0.7, # Higher temp for natural conversation
            max_tokens=1024
        ):
            # Filter out identity hallucinations
            chunk = chunk.replace("OpenAI", "the developers")
            chunk = chunk.replace("ChatGPT", "Kai")
            chunk = chunk.replace("an AI language model", "a helpful assistant")
            yield chunk

    async def narrate_simple_response(
        self,
        query: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Handle simple queries directly (Local-only path).
        """
        system_prompt = """
        You are Kai.
        VIBE: Witty, smart, slightly rebellious.
        
        IDENTITY RULES:
        1. You are Kai.
        2. If asked who you are, say "I'm Kai."
        
        STYLE RULES:
        1. Answer directly.
        2. Don't be boring.
        3. Keep it short.
        """
        
        user_content = query
        if context:
            user_content += f"\nContext: {context}"
            
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content)
        ]
        
        async for chunk in self.connector.generate_stream(
            messages=messages,
            temperature=0.7,
            max_tokens=512
        ):
            # Filter out identity hallucinations
            chunk = chunk.replace("OpenAI", "the developers")
            chunk = chunk.replace("ChatGPT", "Kai")
            chunk = chunk.replace("an AI language model", "a helpful assistant")
            yield chunk
