"""
Agent Communication Models
Pydantic models for structured data exchange between agents and API
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from enum import Enum


class RequestType(str, Enum):
    """Types of user requests the system can handle"""
    CHAT = "chat"
    FLASHCARD_GENERATION = "flashcard_generation"
    QUIZ_GENERATION = "quiz_generation"
    EXAM_GENERATION = "exam_generation"
    SUMMARY_GENERATION = "summary_generation"
    NOTE_ANALYSIS = "note_analysis"
    STUDY_PLAN = "study_plan"


class AgentRequest(BaseModel):
    """
    Incoming request to the agent system.
    Represents a user's request with all necessary context.
    """
    type: RequestType
    user_id: str
    session_id: Optional[str] = None
    message: str
    options: Dict[str, Any] = Field(default_factory=dict)
    explicit_note_ids: Optional[List[str]] = None
    
    class Config:
        use_enum_values = True


class ExecutionPlan(BaseModel):
    """
    Plan created by orchestrator for executing a request.
    Defines the sequence of agent actions needed.
    """
    steps: List[Dict[str, Any]]
    estimated_time_ms: int
    requires_user_input: bool = False
    total_steps: int = 0
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.total_steps == 0:
            self.total_steps = len(self.steps)


class AgentProgress(BaseModel):
    """
    Progress update for frontend streaming.
    Allows real-time feedback to users during long operations.
    """
    step: int
    total_steps: int
    current_agent: str
    message: str
    timestamp: float
    percentage: Optional[int] = None
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.percentage is None and self.total_steps > 0:
            self.percentage = int((self.step / self.total_steps) * 100)


class AgentContext(BaseModel):
    """
    Shared context passed between agents during execution.
    Contains accumulated state and intermediate results.
    """
    user_id: str
    session_id: Optional[str] = None
    request_type: RequestType
    original_message: str
    
    # Retrieved context
    relevant_notes: List[Dict[str, Any]] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    
    # Intermediate results
    intermediate_results: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    total_tokens_used: int = 0
    agents_executed: List[str] = Field(default_factory=list)
    
    class Config:
        use_enum_values = True


class AgentMetadata(BaseModel):
    """
    Metadata about agent execution for monitoring and debugging.
    """
    agent_name: str
    agent_type: str
    model_used: str
    execution_time_ms: int
    tokens_used: int
    success: bool
    error: Optional[str] = None
    timestamp: float
