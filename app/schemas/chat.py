from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="user|assistant|system")
    content: str


class ChatRequest(BaseModel):
    user_id: str
    messages: List[ChatMessage]
    model: Optional[str] = None
    temperature: float = 0.7
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    answer: str
    model: str
    latency_ms: float
    cached: bool = False
    hallucination_flag: bool = False
    trace_id: Optional[str] = None
    feedback: Optional[str] = None


class FeedbackRequest(BaseModel):
    trace_id: str
    score: int  # -1 for thumbs down, +1 for thumbs up
    comment: Optional[str] = None
