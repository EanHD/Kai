# src/models/knowledge.py
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime

class Citation(BaseModel):
    source_id: str          # URL, doc_id, etc.
    snippet: str
    span: Optional[str] = None  # line range, paragraph id
    confidence: float

class Point(BaseModel):
    title: str
    body: str
    importance: Literal["low", "medium", "high"] = "medium"
    citations: List[Citation] = []

class SuggestedFollowUp(BaseModel):
    user_prompt: str
    rationale: str

class KnowledgeObject(BaseModel):
    version: str = "1.0"
    kind: Literal["qa", "explanation", "comparison", "plan", "debug", "refusal"] = "qa"
    query: str
    summary: str
    detailed_points: List[Point]
    citations: List[Citation] = []
    related_entities: List[str] = []
    confidence: float
    assumptions: List[str] = []
    limitations: List[str] = []
    used_tools: List[str] = []
    suggested_followups: List[SuggestedFollowUp] = []
    metadata: Dict[str, Any] = {}
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
