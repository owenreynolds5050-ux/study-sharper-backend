"""
Main Orchestrator Agent
Routes requests and coordinates subagents (Phase 1: Simple routing only)
"""

from typing import Dict, Any, List, Callable
from .base import BaseAgent, AgentType, AgentResult
from .models import AgentRequest, RequestType, AgentProgress, ExecutionPlan
from .context.rag_agent import RAGAgent
from .context.user_profile_agent import UserProfileAgent
from .context.progress_agent import ProgressAgent
from .context.conversation_agent import ConversationAgent
from .context.smart_defaults_agent import SmartDefaultsAgent
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
        
        # Initialize context agents (Phase 2)
        self.rag_agent = RAGAgent()
        self.profile_agent = UserProfileAgent()
        self.progress_agent = ProgressAgent()
        self.conversation_agent = ConversationAgent()
        self.smart_defaults_agent = SmartDefaultsAgent()
        
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
        
        # Step 1: Classify intent
        await self._send_progress(1, 4, self.name, "Analyzing request...")
        intent = self._quick_classify(request)
        logger.info(f"Intent classified as: {intent}")
        
        # Step 2: Gather context (Phase 2)
        await self._send_progress(2, 4, self.name, "Gathering context...")
        context_data = await self._gather_context(request)
        
        # Step 3: Create execution plan
        await self._send_progress(3, 4, self.name, "Creating execution plan...")
        plan = self._create_execution_plan(intent, request)
        
        # Step 4: Complete
        await self._send_progress(4, 4, self.name, "Analysis complete")
        
        # Return Phase 2 response with context
        return {
            "intent": intent,
            "context": context_data,
            "execution_plan": plan.dict(),
            "message": f"Phase 2: Context gathering complete for {intent}",
            "original_message": request.message,
            "user_id": request.user_id,
            "session_id": request.session_id,
            "phase": 2,
            "next_phase": "Phase 3 will add task execution agents"
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
    
    async def _gather_context(self, request: AgentRequest) -> Dict[str, Any]:
        """
        Gather context from multiple sources in parallel.
        Intelligently determines which context to gather based on request.
        
        Args:
            request: The agent request
            
        Returns:
            Dictionary with gathered context from various agents
        """
        
        context_tasks = []
        message_lower = request.message.lower()
        
        # Always get user profile (lightweight and useful)
        context_tasks.append(
            ("profile", self.profile_agent.execute({
                "user_id": request.user_id
            }))
        )
        
        # Get conversation history if session exists
        if request.session_id:
            context_tasks.append(
                ("conversation", self.conversation_agent.execute({
                    "session_id": request.session_id,
                    "user_id": request.user_id,
                    "limit": 10
                }))
            )
        
        # Get RAG context if message suggests content retrieval
        if any(word in message_lower for word in ["notes", "from my", "about", "on", "flashcard", "quiz"]):
            context_tasks.append(
                ("notes", self.rag_agent.execute({
                    "query": request.message,
                    "user_id": request.user_id,
                    "note_ids": request.explicit_note_ids,
                    "top_k": 5
                }))
            )
        
        # Get progress if request involves study planning or performance
        if any(word in message_lower for word in ["study", "progress", "performance", "how am i", "stats"]):
            context_tasks.append(
                ("progress", self.progress_agent.execute({
                    "user_id": request.user_id,
                    "days_back": 30
                }))
            )
        
        # Execute all context gathering in parallel
        logger.info(f"Gathering {len(context_tasks)} context sources in parallel")
        results = await asyncio.gather(*[task for _, task in context_tasks], return_exceptions=True)
        
        # Compile context
        compiled_context = {
            "profile": None,
            "conversation": None,
            "notes": None,
            "progress": None,
            "errors": []
        }
        
        for i, result in enumerate(results):
            context_name = context_tasks[i][0]
            
            if isinstance(result, Exception):
                logger.error(f"Context gathering failed for {context_name}: {result}")
                compiled_context["errors"].append({
                    "source": context_name,
                    "error": str(result)
                })
                continue
            
            if result.success and result.data:
                compiled_context[context_name] = result.data
                logger.debug(f"Context gathered from {context_name}")
            else:
                logger.warning(f"Context agent {context_name} returned no data")
        
        # Remove errors key if empty
        if not compiled_context["errors"]:
            del compiled_context["errors"]
        
        return compiled_context
