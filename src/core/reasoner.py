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
        # schema_json = KnowledgeObject.model_json_schema() # Too verbose for some models
        system_prompt = f"""
        You are a Senior Analyst AI. Your job is to produce a structured Knowledge Object (JSON) 
        that answers the user's query comprehensively.
        
        RULES:
        1. Output ONLY valid JSON.
        2. Do not chat or provide preamble.
        3. Be objective and factual.
        4. If tools were used, incorporate their results.
        
        REQUIRED JSON STRUCTURE:
        {{
          "query": "The original query string",
          "summary": "A concise summary of the answer (2-3 sentences)",
          "detailed_points": [
            {{
              "title": "Point Title",
              "body": "Detailed explanation of this point",
              "importance": "high|medium|low",
              "citations": [
                {{
                  "source_id": "url",
                  "snippet": "relevant text",
                  "confidence": 0.9
                }}
              ]
            }}
          ],
          "confidence": 0.0 to 1.0,
          "limitations": ["List of any missing info or uncertainties"],
          "kind": "explanation|qa|refusal"
        }}
        
        EXAMPLE OUTPUT:
        {{
          "query": "Why is the sky blue?",
          "summary": "The sky appears blue due to Rayleigh scattering...",
          "detailed_points": [
            {{
              "title": "Rayleigh Scattering",
              "body": "Sunlight reaches Earth's atmosphere and is scattered...",
              "importance": "high",
              "citations": []
            }}
          ],
          "confidence": 0.95,
          "limitations": [],
          "kind": "explanation"
        }}
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
        content = response.content.strip()
        
        # Clean up markdown code blocks if present
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
            
        data = None
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Attempt to fix common JSON errors
            try:
                # Sometimes models double-escape quotes or wrap in extra braces
                if content.startswith("{{") and content.endswith("}}"):
                    content = content[1:-1]
                
                # Try to find the first { and last }
                start = content.find("{")
                end = content.rfind("}")
                if start != -1 and end != -1:
                    content = content[start:end+1]
                    data = json.loads(content)
            except Exception:
                pass
        
        if data is None:
            logger.error(f"Failed to parse JSON from Reasoner: {response.content}")
            raise ValueError("Reasoner failed to produce valid JSON")

        if isinstance(data, list):
            if len(data) > 0 and isinstance(data[0], dict):
                data = data[0]
            else:
                raise ValueError("Reasoner returned a list, expected a dictionary")

        try:
            # Ensure required fields are present or set defaults if missing
            # The LLM might miss some optional fields, Pydantic will handle validation
            ko = KnowledgeObject(**data)
            return ko
        except Exception as e:
            logger.error(f"Validation failed for Reasoner output: {e}")
            raise ValueError(f"Reasoner output did not match schema: {e}")
