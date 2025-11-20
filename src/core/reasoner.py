# src/core/reasoner.py
import logging
import json
from typing import Any, Optional, Dict
from src.core.llm_connector import LLMConnector, Message
from src.models.knowledge import KnowledgeObject

logger = logging.getLogger(__name__)

class ReasoningEngine:
    def __init__(self, connector: LLMConnector):
        self.connector = connector

    async def analyze(
        self, 
        query: str, 
        context: Optional[Dict[str, Any]] = None,
        tools_output: Optional[Dict[str, Any]] = None
    ) -> KnowledgeObject:
        """
        Analyze a complex query and produce a Knowledge Object.
        """
        
        # 1. Construct System Prompt
        schema_json = KnowledgeObject.model_json_schema()
        system_prompt = f"""
        You are a Senior Analyst AI. Your job is to produce a structured Knowledge Object (JSON) 
        that answers the user's query comprehensively.
        
        RULES:
        1. Output ONLY valid JSON matching the schema below.
        2. Do not chat or provide preamble.
        3. Be objective and factual.
        4. If tools were used, incorporate their results.
        5. Explicitly state assumptions and limitations.
        
        SCHEMA:
        {json.dumps(schema_json, indent=2)}
        """
        
        # 2. Construct User Prompt
        user_content = f"Query: {query}\n"
        
        if context:
            user_content += f"\nContext: {json.dumps(context, default=str)}\n"
            
        if tools_output:
            user_content += f"\nTool Results: {json.dumps(tools_output, default=str)}\n"
            
        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=user_content)
        ]
        
        # 3. Call LLM with JSON Mode
        response = await self.connector.generate(
            messages=messages,
            temperature=0.2, # Low temp for factual consistency
            json_mode=True,
            max_tokens=4000
        )
        
        # 4. Parse and Validate
        try:
            data = json.loads(response.content)
            # Ensure required fields are present or set defaults if missing
            # The LLM might miss some optional fields, Pydantic will handle validation
            ko = KnowledgeObject(**data)
            return ko
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON from Reasoner: {response.content}")
            raise ValueError("Reasoner failed to produce valid JSON")
        except Exception as e:
            logger.error(f"Validation failed for Reasoner output: {e}")
            raise ValueError(f"Reasoner output did not match schema: {e}")
