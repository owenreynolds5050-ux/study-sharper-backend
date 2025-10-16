"""
Chat Agent
Handles general conversation with context awareness
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from ..prompts.templates import PromptTemplates
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ChatAgent(BaseAgent):
    """Handles general conversation with context"""
    
    def __init__(self):
        super().__init__(
            name="chat_agent",
            agent_type=AgentType.TASK,
            model="anthropic/claude-3.5-haiku",
            description="Conversational AI assistant"
        )
        logger.info("Chat Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process chat message with context awareness.
        
        Args:
            input_data: Must contain 'message'
            context: Optional context with notes, conversation history, progress
            
        Returns:
            Dictionary with response and context metadata
        """
        
        question = input_data.get("message")
        if not question:
            logger.warning("No message provided to chat agent")
            return {"error": "No message provided"}
        
        # Get conversation history from context
        conversation_history = None
        if context and context.get("conversation"):
            conversation_history = context["conversation"].get("messages", [])
            logger.info(f"Using {len(conversation_history)} previous messages as context")
        
        # Build prompt with all available context
        prompt = PromptTemplates.chat_with_context(
            question=question,
            context=context or {},
            conversation_history=conversation_history
        )
        
        logger.info(f"Processing chat message: '{question[:50]}...'")
        
        try:
            # Call LLM (no JSON mode for chat - natural conversation)
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.8,  # Higher temperature for more natural conversation
                max_tokens=1500,
                json_mode=False
            )
            
            # Calculate what context was used
            context_used = {
                "notes_count": 0,
                "has_conversation_history": bool(conversation_history),
                "has_progress_data": False,
                "has_user_profile": False
            }
            
            if context:
                if context.get("notes") and context["notes"].get("notes"):
                    context_used["notes_count"] = len(context["notes"]["notes"])
                context_used["has_progress_data"] = bool(context.get("progress"))
                context_used["has_user_profile"] = bool(context.get("profile"))
            
            result = {
                "response": response["content"],
                "tokens_used": response["tokens_used"],
                "model_used": response["model"],
                "context_used": context_used
            }
            
            logger.info(f"Chat response generated ({response['tokens_used']} tokens)")
            return result
        
        except Exception as e:
            logger.error(f"Chat agent failed: {e}")
            return {"error": str(e)}
