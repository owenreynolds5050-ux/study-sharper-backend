"""
Main Orchestrator Agent
Routes requests and coordinates subagents (Phase 1: Simple routing only)
"""

from typing import Dict, Any, List, Callable
from .base import BaseAgent, AgentType, AgentResult
from .models import AgentRequest, RequestType, AgentProgress, ExecutionPlan
import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class MainOrchestrator(BaseAgent):
    """
    Main orchestrator that routes requests to subagents.
    Phase 1: Simple pattern-based intent classification without LLM.
    Phase 2+: Will coordinate actual subagent execution.
    """
    
    def __init__(self):
        super().__init__(
            name="main_orchestrator",
            agent_type=AgentType.ORCHESTRATOR,
            model="anthropic/claude-sonnet-4-20250514",  # Use Sonnet for orchestrator
            description="Routes requests and coordinates subagents"
        )
        self.progress_callbacks: List[Callable] = []
        logger.info(f"MainOrchestrator initialized with model: {self.model}")
    
    def add_progress_callback(self, callback: Callable):
        """
        Add callback for progress updates.
        Useful for streaming progress to frontend.
        
        Args:
            callback: Async function that receives AgentProgress objects
        """
        self.progress_callbacks.append(callback)
        logger.debug(f"Progress callback added. Total callbacks: {len(self.progress_callbacks)}")
    
    def remove_progress_callback(self, callback: Callable):
        """
        Remove a progress callback.
        
        Args:
            callback: The callback function to remove
        """
        if callback in self.progress_callbacks:
            self.progress_callbacks.remove(callback)
            logger.debug(f"Progress callback removed. Total callbacks: {len(self.progress_callbacks)}")
    
    async def _send_progress(
        self,
        step: int,
        total: int,
        agent_name: str,
        message: str
    ):
        """
        Send progress update to all registered callbacks.
        
        Args:
            step: Current step number
            total: Total number of steps
            agent_name: Name of currently executing agent
            message: Progress message
        """
        progress = AgentProgress(
            step=step,
            total_steps=total,
            current_agent=agent_name,
            message=message,
            timestamp=time.time()
        )
        
        logger.debug(f"Progress: {step}/{total} - {agent_name}: {message}")
        
        for callback in self.progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress)
                else:
                    callback(progress)
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Main orchestration logic.
        Phase 1: Simple intent classification and routing plan.
        
        Args:
            input_data: Request data (should match AgentRequest schema)
            context: Optional execution context
            
        Returns:
            Dictionary with orchestration result
        """
        # Parse request
        try:
            request = AgentRequest(**input_data)
            logger.info(f"Orchestrator processing request: type={request.type}, user={request.user_id}")
        except Exception as e:
            logger.error(f"Failed to parse AgentRequest: {e}")
            raise ValueError(f"Invalid request format: {e}")
        
        # Send initial progress
        await self._send_progress(1, 3, self.name, "Analyzing request...")
        
        # Classify intent using pattern matching (no LLM in Phase 1)
        intent = self._quick_classify(request)
        logger.info(f"Intent classified as: {intent}")
        
        await self._send_progress(2, 3, self.name, f"Intent identified: {intent}")
        
        # Create execution plan (Phase 1: just a placeholder)
        plan = self._create_execution_plan(intent, request)
        
        await self._send_progress(3, 3, self.name, "Request analysis complete")
        
        # Return Phase 1 response
        return {
            "intent": intent,
            "message": f"Orchestrator received request of type: {request.type}",
            "original_message": request.message,
            "execution_plan": plan.dict(),
            "next_phase": "In Phase 2, we'll add actual subagent execution",
            "user_id": request.user_id,
            "session_id": request.session_id,
            "phase": 1
        }
    
    def _quick_classify(self, request: AgentRequest) -> str:
        """
        Fast pattern matching classification without LLM.
        Uses keyword matching to determine intent.
        
        Args:
            request: The agent request to classify
            
        Returns:
            Classified intent as string
        """
        message_lower = request.message.lower()
        
        # If request type is explicit and not generic chat, use it
        if request.type != RequestType.CHAT.value:
            logger.debug(f"Using explicit request type: {request.type}")
            return request.type
        
        # Pattern matching for common keywords
        patterns = {
            RequestType.FLASHCARD_GENERATION.value: [
                "flashcard", "flash card", "cards", "memorize", "drill"
            ],
            RequestType.QUIZ_GENERATION.value: [
                "quiz", "test", "practice", "questions", "assessment"
            ],
            RequestType.EXAM_GENERATION.value: [
                "exam", "final", "midterm", "comprehensive test"
            ],
            RequestType.SUMMARY_GENERATION.value: [
                "summary", "summarize", "tldr", "overview", "brief"
            ],
            RequestType.NOTE_ANALYSIS.value: [
                "analyze", "analysis", "review", "evaluate", "assess"
            ],
            RequestType.STUDY_PLAN.value: [
                "study plan", "schedule", "organize", "plan my study"
            ]
        }
        
        # Check each pattern
        for intent, keywords in patterns.items():
            if any(keyword in message_lower for keyword in keywords):
                logger.debug(f"Pattern matched: {intent}")
                return intent
        
        # Default to chat if no patterns match
        logger.debug("No pattern matched, defaulting to chat")
        return RequestType.CHAT.value
    
    def _create_execution_plan(
        self,
        intent: str,
        request: AgentRequest
    ) -> ExecutionPlan:
        """
        Create execution plan based on intent.
        Phase 1: Simple placeholder plans.
        
        Args:
            intent: Classified intent
            request: Original request
            
        Returns:
            ExecutionPlan with steps
        """
        # Phase 1: Create simple placeholder plans
        base_steps = [
            {
                "agent": "context_agent",
                "action": "retrieve_relevant_notes",
                "description": "Find relevant notes from user's collection"
            },
            {
                "agent": "task_agent",
                "action": f"execute_{intent}",
                "description": f"Execute {intent} task"
            },
            {
                "agent": "validation_agent",
                "action": "validate_output",
                "description": "Validate and format final output"
            }
        ]
        
        plan = ExecutionPlan(
            steps=base_steps,
            estimated_time_ms=5000,  # Placeholder estimate
            requires_user_input=False
        )
        
        logger.debug(f"Execution plan created with {len(plan.steps)} steps")
        return plan
