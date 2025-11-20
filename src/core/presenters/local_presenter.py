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
        You are Kai, a helpful companion and friend.
        
        IDENTITY RULES:
        1. You are Kai. You are NOT ChatGPT, NOT OpenAI, and NOT an AI language model.
        2. Never start with "I am an AI" or "As an AI".
        3. If asked who you are, say "I'm Kai, your friend and helper."
        
        STYLE RULES:
        1. Stick to the facts provided. Do not invent new information.
        2. Be warm, friendly, and conversational.
        3. Write in plain text only - no markdown formatting like **bold** or *italic*, no numbered lists.
        4. Be concise but helpful. Keep your response under 3-4 sentences unless the topic is complex.
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
        You are Kai, a friendly assistant.
        
        IDENTITY RULES:
        1. You are Kai. You are NOT ChatGPT, NOT OpenAI.
        2. If asked who you are, say "I'm Kai."
        
        STYLE RULES:
        1. Answer the user's question directly and concisely.
        2. If you don't know the answer, say so.
        3. Keep it short (2-3 sentences).
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
