import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from src.core.reasoner import ReasoningEngine
from src.core.llm_connector import LLMConnector, LLMResponse, Message
from src.models.knowledge import KnowledgeObject

@pytest.mark.asyncio
async def test_reasoner_json_repair():
    # Mock Connector
    mock_connector = MagicMock(spec=LLMConnector)
    
    # First response: Invalid JSON
    invalid_json = "{ 'query': 'test', 'summary': 'invalid json because single quotes' }"
    
    # Second response: Valid JSON (Repair)
    valid_json = json.dumps({
        "query": "test",
        "summary": "This is a summary.",
        "detailed_points": [],
        "confidence": 1.0,
        "limitations": [],
        "kind": "qa"
    })
    
    # Setup generate side effects
    async def generate_side_effect(messages, **kwargs):
        # Check if it's the repair call (has "JSON repair tool" in system prompt)
        if messages[0].content == "You are a JSON repair tool. Output ONLY valid JSON.":
            return LLMResponse(
                content=valid_json,
                token_count=10,
                cost=0.0,
                model_used="test",
                finish_reason="stop"
            )
        else:
            return LLMResponse(
                content=invalid_json,
                token_count=10,
                cost=0.0,
                model_used="test",
                finish_reason="stop"
            )
            
    mock_connector.generate = AsyncMock(side_effect=generate_side_effect)
    
    reasoner = ReasoningEngine(mock_connector)
    
    # Run analyze
    ko = await reasoner.analyze("test query")
    
    # Verify
    assert isinstance(ko, KnowledgeObject)
    assert ko.query == "test"
    assert ko.summary == "This is a summary."
    
    # Verify that generate was called twice
    assert mock_connector.generate.call_count == 2
