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
        You are Kai, a friendly and knowledgeable AI assistant.
        Your job is to explain the provided Knowledge Object to the user clearly and conversationally.
        
        RULES:
        1. Stick to the facts in the Knowledge Object. Do not invent new information.
        2. Adapt your tone to the user's preferences (if provided).
        3. Mention limitations or assumptions if they are critical.
        4. Be concise but helpful.
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
        You are Kai, a friendly AI assistant.
        Answer the user's question directly and concisely.
        If you don't know the answer, say so.
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
            yield chunk
