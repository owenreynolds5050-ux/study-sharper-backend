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
        Handles timing, error catching, result formatting, and monitoring.
        
        Args:
            input_data: Input data for the agent
            context: Optional context from previous agents or system state
            
        Returns:
            AgentResult with success status, data, and metadata
        """
        start_time = time.time()
        request_id = input_data.get("request_id", "unknown")
        user_id = input_data.get("user_id")
        session_id = input_data.get("session_id")
        
        try:
            result_data = await self._execute_internal(input_data, context)
            execution_time = int((time.time() - start_time) * 1000)
            
            result = AgentResult(
                success=True,
                data=result_data,
                execution_time_ms=execution_time,
                model_used=self.model,
                tokens_used=result_data.get("tokens_used", 0) if isinstance(result_data, dict) else 0
            )
            
            # Log execution if monitor available
            if hasattr(self, 'monitor') and self.monitor and user_id:
                try:
                    await self.monitor.log_execution(
                        user_id=user_id,
                        session_id=session_id,
                        request_id=request_id,
                        agent_name=self.name,
                        input_data=input_data,
                        output_data=result_data if isinstance(result_data, dict) else {},
                        execution_time_ms=execution_time,
                        tokens_used=result.tokens_used,
                        model_used=self.model,
                        status="success"
                    )
                except Exception as log_error:
                    # Don't fail execution if logging fails
                    pass
            
            return result
        
        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            
            result = AgentResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                model_used=self.model
            )
            
            # Log failure if monitor available
            if hasattr(self, 'monitor') and self.monitor and user_id:
                try:
                    await self.monitor.log_execution(
                        user_id=user_id,
                        session_id=session_id,
                        request_id=request_id,
                        agent_name=self.name,
                        input_data=input_data,
                        output_data={},
                        execution_time_ms=execution_time,
                        tokens_used=0,
                        model_used=self.model,
                        status="failure",
                        error_message=str(e)
                    )
                except Exception as log_error:
                    # Don't fail execution if logging fails
                    pass
            
            return result
    
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
