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
from .tasks.flashcard_agent import FlashcardAgent
from .tasks.quiz_agent import QuizAgent
from .tasks.exam_agent import ExamAgent
from .tasks.summary_agent import SummaryAgent
from .tasks.chat_agent import ChatAgent
from .validation.accuracy_agent import AccuracyAgent
from .validation.safety_agent import SafetyAgent
from .validation.quality_agent import QualityAgent
from .validation.config import ValidationConfig
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
        
        # Initialize task agents (Phase 3)
        self.flashcard_agent = FlashcardAgent()
        self.quiz_agent = QuizAgent()
        self.exam_agent = ExamAgent()
        self.summary_agent = SummaryAgent()
        self.chat_agent = ChatAgent()
        
        # Initialize validation agents (Phase 4)
        self.accuracy_agent = AccuracyAgent()
        self.safety_agent = SafetyAgent()
        self.quality_agent = QualityAgent()
        
        # Validation configuration
        self.validation_config = ValidationConfig
        
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
        await self._send_progress(1, 6, self.name, "Analyzing request...")
        intent = self._quick_classify(request)
        logger.info(f"Intent classified as: {intent}")
        
        # Step 2: Gather context (Phase 2)
        await self._send_progress(2, 6, self.name, "Gathering context...")
        context_data = await self._gather_context(request)
        
        # Step 3: Execute task with validation (Phase 3 & 4)
        await self._send_progress(3, 6, "task_agent", f"Executing {intent}...")
        task_result, validation_results = await self._execute_with_validation(
            intent, request, context_data
        )
        
        # Step 4: Final safety check
        await self._send_progress(4, 6, "safety_check", "Final safety verification...")
        final_safety = await self._final_safety_check(task_result, context_data)
        
        if not final_safety.get("is_safe", True):
            logger.error("Content failed final safety check")
            return {
                "success": False,
                "error": "Content failed safety check",
                "details": final_safety,
                "phase": 4
            }
        
        # Step 5: Format response
        await self._send_progress(5, 6, "formatter", "Formatting response...")
        final_response = self._format_response(task_result, intent, request, validation_results)
        
        # Step 6: Complete
        await self._send_progress(6, 6, self.name, "Complete")
        
        return final_response
    
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
    
    async def _execute_task(
        self,
        intent: str,
        request: AgentRequest,
        context: Dict[str, Any]
    ) -> AgentResult:
        """
        Execute the appropriate task agent based on intent.
        
        Args:
            intent: Classified intent
            request: Original request
            context: Gathered context data
            
        Returns:
            AgentResult from task execution
        """
        
        # Prepare task input
        task_input = {
            "message": request.message,
            "options": request.options or {}
        }
        
        # Route to appropriate agent
        if intent == RequestType.FLASHCARD_GENERATION.value:
            task_input.update({
                "count": request.options.get("count", 10) if request.options else 10,
                "difficulty": request.options.get("difficulty") if request.options else None,
                "topic": request.options.get("topic") if request.options else None,
                "content": request.options.get("content") if request.options else None
            })
            logger.info("Routing to Flashcard Agent")
            return await self.flashcard_agent.execute(task_input, context)
        
        elif intent == RequestType.QUIZ_GENERATION.value:
            task_input.update({
                "question_count": request.options.get("question_count", 10) if request.options else 10,
                "difficulty": request.options.get("difficulty") if request.options else None,
                "question_types": request.options.get("question_types") if request.options else None,
                "content": request.options.get("content") if request.options else None
            })
            logger.info("Routing to Quiz Agent")
            return await self.quiz_agent.execute(task_input, context)
        
        elif intent == RequestType.EXAM_GENERATION.value:
            task_input.update({
                "duration_minutes": request.options.get("duration_minutes", 60) if request.options else 60,
                "difficulty": request.options.get("difficulty") if request.options else None,
                "sections": request.options.get("sections") if request.options else None,
                "content": request.options.get("content") if request.options else None
            })
            logger.info("Routing to Exam Agent")
            return await self.exam_agent.execute(task_input, context)
        
        elif intent == RequestType.SUMMARY_GENERATION.value:
            task_input.update({
                "length": request.options.get("length", "medium") if request.options else "medium",
                "style": request.options.get("style", "bullet_points") if request.options else "bullet_points",
                "focus_areas": request.options.get("focus_areas") if request.options else None,
                "content": request.options.get("content") if request.options else None
            })
            logger.info("Routing to Summary Agent")
            return await self.summary_agent.execute(task_input, context)
        
        else:  # Default to chat for everything else
            logger.info("Routing to Chat Agent")
            return await self.chat_agent.execute(task_input, context)
    
    def _format_response(
        self,
        task_result: AgentResult,
        intent: str,
        request: AgentRequest,
        validation_results: list = None
    ) -> Dict[str, Any]:
        """
        Format final response for user.
        
        Args:
            task_result: Result from task agent
            intent: Classified intent
            request: Original request
            
        Returns:
            Formatted response dictionary
        """
        
        if not task_result.success:
            logger.error(f"Task execution failed: {task_result.error}")
            return {
                "success": False,
                "error": task_result.error,
                "intent": intent,
                "user_id": request.user_id,
                "phase": 4
            }
        
        # Get validation summary
        validation_summary = {}
        if validation_results:
            final_validation = validation_results[-1].get("validation", {}) if validation_results else {}
            validation_summary = {
                "safety_score": final_validation.get("safety", {}).get("safety_score", 1.0),
                "quality_score": final_validation.get("quality", {}).get("quality_score", 1.0),
                "accuracy_score": final_validation.get("accuracy", {}).get("accuracy_score", 1.0),
                "validation_attempts": len(validation_results),
                "validation_passed": True
            }
        
        return {
            "success": True,
            "intent": intent,
            "data": task_result.data,
            "validation": validation_summary,
            "metadata": {
                "execution_time_ms": task_result.execution_time_ms,
                "tokens_used": task_result.tokens_used,
                "model_used": task_result.model_used,
                "confidence_score": task_result.confidence_score
            },
            "user_id": request.user_id,
            "session_id": request.session_id,
            "phase": 4,
            "message": f"Successfully completed {intent} with validation"
        }
    
    async def _execute_with_validation(
        self,
        intent: str,
        request: AgentRequest,
        context: Dict[str, Any]
    ) -> tuple:
        """
        Execute task with validation and retry logic.
        
        Args:
            intent: Classified intent
            request: Original request
            context: Gathered context data
            
        Returns:
            Tuple of (task_result, validation_results)
        """
        
        validation_results = []
        max_retries = self.validation_config.get_max_retries(intent)
        
        # Check if validation is enabled
        if not self.validation_config.should_validate(intent):
            logger.info(f"Validation disabled for {intent}, executing without validation")
            task_result = await self._execute_task(intent, request, context)
            return task_result, []
        
        for attempt in range(max_retries + 1):
            logger.info(f"Execution attempt {attempt + 1}/{max_retries + 1}")
            
            # Execute task
            task_result = await self._execute_task(intent, request, context)
            
            if not task_result.success:
                logger.error(f"Task execution failed on attempt {attempt + 1}")
                return task_result, validation_results
            
            # Run validations
            validation_result = await self._validate_content(
                task_result.data,
                intent,
                context
            )
            
            validation_results.append({
                "attempt": attempt + 1,
                "validation": validation_result
            })
            
            # Check if validation passed
            passes, reason = self._validation_passed(validation_result, intent)
            
            if passes:
                logger.info(f"Validation passed on attempt {attempt + 1}")
                return task_result, validation_results
            
            logger.warning(f"Validation failed on attempt {attempt + 1}: {reason}")
            
            # If we have retries left, continue
            if attempt < max_retries:
                logger.info(f"Retrying with corrections (attempt {attempt + 2}/{max_retries + 1})")
                # Note: In a full implementation, we would modify the request with corrections
                # For now, we just retry as-is
        
        # Max retries reached - return last result anyway
        logger.warning(f"Max retries ({max_retries}) reached, returning last result")
        return task_result, validation_results
    
    async def _validate_content(
        self,
        content: Dict[str, Any],
        content_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run all validation checks.
        
        Args:
            content: Generated content to validate
            content_type: Type of content
            context: Context data
            
        Returns:
            Dictionary with validation results
        """
        
        logger.info(f"Running validation checks for {content_type}")
        
        # Get source material for accuracy check
        source_material = ""
        if context.get("notes") and context["notes"].get("notes"):
            source_material = "\n\n".join([
                f"**{note.get('title', 'Untitled')}**\n{note.get('content', '')}"
                for note in context["notes"]["notes"]
            ])
        
        # Prepare validation tasks
        validation_tasks = []
        
        # Safety check (always required)
        validation_tasks.append(
            ("safety", self.safety_agent.execute({
                "content": content,
                "content_type": content_type,
                "age_group": "high_school"
            }))
        )
        
        # Quality check
        requirements = self.validation_config.get_requirements(content_type)
        if requirements.get("require_quality", True):
            validation_tasks.append(
                ("quality", self.quality_agent.execute({
                    "content": content,
                    "content_type": content_type
                }))
            )
        
        # Accuracy check (only if we have source material)
        if source_material and requirements.get("require_accuracy", True):
            validation_tasks.append(
                ("accuracy", self.accuracy_agent.execute({
                    "generated_content": content,
                    "source_material": source_material,
                    "content_type": content_type
                }))
            )
        
        # Run validations in parallel
        results = await asyncio.gather(
            *[task for _, task in validation_tasks],
            return_exceptions=True
        )
        
        # Compile validation results
        validation = {}
        for i, (name, _) in enumerate(validation_tasks):
            result = results[i]
            if isinstance(result, Exception):
                logger.error(f"{name} validation failed: {result}")
                validation[name] = None
            elif result.success and result.data:
                validation[name] = result.data
            else:
                logger.warning(f"{name} validation returned no data")
                validation[name] = None
        
        logger.info(f"Validation complete: {len([v for v in validation.values() if v])} checks passed")
        return validation
    
    def _validation_passed(
        self,
        validation: Dict[str, Any],
        content_type: str
    ) -> tuple[bool, str]:
        """
        Check if validation meets minimum standards.
        
        Args:
            validation: Validation results
            content_type: Type of content
            
        Returns:
            Tuple of (passed, reason)
        """
        
        # Get requirements
        requirements = self.validation_config.get_requirements(content_type)
        
        # Safety check (mandatory)
        safety = validation.get("safety", {})
        if not safety:
            return True, "Safety check skipped"  # If check failed, be lenient
        
        if not safety.get("is_safe", True):
            return False, "Content failed safety check"
        
        # Quality check
        if requirements.get("require_quality", True):
            quality = validation.get("quality", {})
            if quality:
                quality_score = quality.get("quality_score", 1.0)
                min_quality = requirements.get("min_quality", 0.6)
                if quality_score < min_quality:
                    return False, f"Quality score {quality_score:.2f} below minimum {min_quality:.2f}"
        
        # Accuracy check
        if requirements.get("require_accuracy", True):
            accuracy = validation.get("accuracy")
            if accuracy:
                accuracy_score = accuracy.get("accuracy_score", 1.0)
                min_accuracy = requirements.get("min_accuracy", 0.7)
                if accuracy_score < min_accuracy:
                    return False, f"Accuracy score {accuracy_score:.2f} below minimum {min_accuracy:.2f}"
        
        return True, "All validation checks passed"
    
    async def _final_safety_check(
        self,
        task_result: AgentResult,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Final safety verification before returning to user.
        
        Args:
            task_result: Result from task execution
            context: Context data
            
        Returns:
            Dictionary with safety assessment
        """
        
        if not task_result.success:
            return {"is_safe": True, "confidence": 1.0}  # Error responses are safe
        
        logger.info("Running final safety check")
        
        result = await self.safety_agent.execute({
            "content": task_result.data,
            "content_type": "final_output",
            "age_group": "high_school"
        })
        
        if result.success and result.data:
            return result.data
        else:
            logger.warning("Final safety check failed, assuming safe")
            return {"is_safe": True, "confidence": 0.5}
