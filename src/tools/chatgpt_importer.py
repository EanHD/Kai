"""Tool for importing ChatGPT history into Kai's memory vault."""

import json
import logging
import uuid
from datetime import datetime
from typing import Any, List, Dict

from src.core.llm_connector import LLMConnector, Message
from src.storage.memory_vault import MemoryVault

logger = logging.getLogger(__name__)

EXTRACTION_PROMPT = """Analyze this conversation from the user's ChatGPT history.

Conversation:
{conversation_text}

Extract the following:
1. A brief title and 2-sentence summary (Semantic Memory).
2. User preferences (e.g., "prefers concise answers", "hates markdown tables").
3. Explicit rules or corrections (e.g., "never do X", "always do Y").

Format as JSON:
{{
    "summary": {{ "title": "...", "text": "..." }},
    "preferences": ["pref1", "pref2"],
    "rules": ["rule1", "rule2"]
}}
"""

class ChatGPTImporter:
    """Importer for ChatGPT conversations.json."""

    def __init__(self, memory_vault: MemoryVault, llm_connector: LLMConnector):
        self.vault = memory_vault
        self.llm = llm_connector

    async def import_file(self, file_path: str) -> Dict[str, int]:
        """Import conversations from a JSON file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return {"error": str(e)}

        return await self.process_conversations(data)

    async def process_conversations(self, conversations: List[Dict[str, Any]]) -> Dict[str, int]:
        """Process a list of conversations."""
        stats = {
            "conversations": 0,
            "episodes": 0,
            "semantic": 0,
            "preferences": 0,
            "rules": 0
        }

        total = len(conversations)
        print(f"Found {total} conversations. Starting import...")

        for i, conv in enumerate(conversations):
            # Progress update every 10 items
            if i % 10 == 0:
                print(f"Processing {i}/{total}...")

            # Extract messages
            mapping = conv.get("mapping", {})
            messages = []
            
            # Sort by create_time to get chronological order if possible, 
            # but mapping is a tree. We need to traverse the current_node path.
            current_node = conv.get("current_node")
            while current_node:
                node = mapping.get(current_node)
                if not node:
                    break
                
                message = node.get("message")
                if message and message.get("content") and message.get("content", {}).get("content_type") == "text":
                    role = message.get("author", {}).get("role")
                    parts = message.get("content", {}).get("parts", [])
                    text = "".join([str(p) for p in parts if p])
                    
                    if text and role in ["user", "assistant"]:
                        messages.append({"role": role, "content": text, "create_time": message.get("create_time")})
                
                current_node = node.get("parent")

            # Reverse to get chronological order (since we traversed backwards)
            messages.reverse()

            if not messages:
                continue

            stats["conversations"] += 1
            
            # Store Episodic Memories (Turns)
            conversation_text = ""
            for j in range(0, len(messages) - 1):
                msg = messages[j]
                next_msg = messages[j+1]
                
                if msg["role"] == "user" and next_msg["role"] == "assistant":
                    self.vault.add_episode(
                        session_id=f"chatgpt-{conv.get('id')}",
                        user_text=msg["content"],
                        assistant_text=next_msg["content"],
                        success=True,
                        summary=f"Imported from ChatGPT: {conv.get('title', 'Untitled')}",
                        confidence=1.0,
                        tags=["chatgpt_import", "historical"]
                    )
                    stats["episodes"] += 1
                    
                    conversation_text += f"User: {msg['content']}\nAssistant: {next_msg['content']}\n\n"

            # Analyze for Semantic/Preference/Rules (only for substantial convos)
            if len(conversation_text) > 500:
                try:
                    analysis = await self._analyze_conversation(conversation_text[:4000]) # Limit context
                    
                    if analysis.get("summary"):
                        self.vault.add(
                            "semantic",
                            payload={
                                "title": analysis["summary"].get("title"),
                                "text": analysis["summary"].get("text"),
                                "source": "chatgpt_import"
                            },
                            summary=analysis["summary"].get("title"),
                            confidence=1.0,
                            tags=["chatgpt_import", "summary"]
                        )
                        stats["semantic"] += 1

                    for pref in analysis.get("preferences", []):
                        self.vault.add(
                            "preference",
                            payload={"preference": pref, "source": "chatgpt_import"},
                            summary=f"Preference: {pref[:50]}...",
                            confidence=1.0,
                            tags=["chatgpt_import", "preference"]
                        )
                        stats["preferences"] += 1

                    for rule in analysis.get("rules", []):
                        self.vault.add(
                            "checklist", # Storing rules as checklists/rules
                            payload={"rule": rule, "source": "chatgpt_import"},
                            summary=f"Rule: {rule[:50]}...",
                            confidence=1.0,
                            tags=["chatgpt_import", "rule"]
                        )
                        stats["rules"] += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to analyze conversation {conv.get('id')}: {e}")

        return stats

    async def _analyze_conversation(self, text: str) -> Dict[str, Any]:
        """Run LLM analysis on conversation text."""
        prompt = EXTRACTION_PROMPT.format(conversation_text=text)
        messages = [Message(role="user", content=prompt)]
        
        try:
            response = await self.llm.generate(messages, temperature=0.1, max_tokens=500)
            content = response.content
            
            # Parse JSON
            import re
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return {}
        except Exception:
            return {}
