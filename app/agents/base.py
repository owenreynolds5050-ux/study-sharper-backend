"""
Base Agent Classes
Defines the abstract base class and result models for all agents
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
import time
from enum import Enum


class AgentType(Enum):
    """Types of agents in the system"""
    ORCHESTRATOR = "orchestrator"
    CONTEXT = "context"
    TASK = "task"
    VALIDATION = "validation"
    UTILITY = "utility"


class AgentResult(BaseModel):
    """Standardized result from any agent execution"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: int
    tokens_used: int = 0
    model_used: Optional[str] = None
    confidence_score: Optional[float] = None  # 0.0 to 1.0
    
    class Config:
        use_enum_values = True


class BaseAgent(ABC):
    """
    Abstract base class that all agents inherit from.
    Provides standardized execution interface and error handling.
    """
    
    def __init__(
        self,
        name: str,
        agent_type: AgentType,
        model: str = "anthropic/claude-3.5-haiku",  # Default to Haiku for cost efficiency
        description: str = ""
    ):
        self.name = name
        self.agent_type = agent_type
        self.model = model
        self.description = description
    
    async def execute(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> AgentResult:
        """
        Execute agent and return standardized result.
        Handles timing, error catching, and result formatting.
        
        Args:
            input_data: Input data for the agent
            context: Optional context from previous agents or system state
            
        Returns:
            AgentResult with success status, data, and metadata
        """
        start_time = time.time()
        
        try:
            result_data = await self._execute_internal(input_data, context)
            execution_time = int((time.time() - start_time) * 1000)
            
            return AgentResult(
                success=True,
                data=result_data,
                execution_time_ms=execution_time,
                model_used=self.model
            )
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                model_used=self.model
            )
    
    @abstractmethod
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Internal execution logic - override this in subclasses.
        
        Args:
            input_data: Input data for the agent
            context: Optional context from previous agents or system state
            
        Returns:
            Dictionary with agent-specific result data
            
        Raises:
            Exception: Any errors during execution (caught by execute())
        """
        pass
