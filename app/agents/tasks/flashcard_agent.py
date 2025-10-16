"""
Flashcard Generation Agent
Creates flashcards from content using LLM
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from ..prompts.templates import PromptTemplates
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class FlashcardAgent(BaseAgent):
    """Generates flashcards from content"""
    
    def __init__(self):
        super().__init__(
            name="flashcard_agent",
            agent_type=AgentType.TASK,
            model="anthropic/claude-3.5-haiku",
            description="Creates flashcards from notes or content"
        )
        logger.info("Flashcard Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate flashcards from content.
        
        Args:
            input_data: Must contain 'content' or context must have notes
                       Optional: 'count', 'difficulty', 'topic'
            context: Optional context with notes, user preferences
            
        Returns:
            Dictionary with flashcards array and metadata
        """
        
        # Extract parameters
        content = input_data.get("content")
        count = input_data.get("count", 10)
        difficulty = input_data.get("difficulty")
        topic = input_data.get("topic")
        
        # If no content provided, try to get from context (notes)
        if not content:
            if context and context.get("notes") and context["notes"].get("notes"):
                notes = context["notes"]["notes"]
                content = "\n\n".join([
                    f"**{note.get('title', 'Untitled')}**\n{note.get('content', '')}"
                    for note in notes
                ])
                logger.info(f"Using {len(notes)} notes as content source")
            else:
                logger.warning("No content provided for flashcard generation")
                return {"error": "No content provided for flashcard generation"}
        
        # Get user preferences from context
        user_prefs = None
        if context and context.get("profile"):
            user_prefs = context["profile"].get("preferences", {})
            # Use user's preferred difficulty if not explicitly set
            if not difficulty and user_prefs.get("preferred_difficulty"):
                difficulty = user_prefs["preferred_difficulty"]
                logger.info(f"Using user preferred difficulty: {difficulty}")
        
        # Default difficulty
        if not difficulty:
            difficulty = "medium"
        
        # Build prompt using template
        prompt = PromptTemplates.flashcard_generation(
            content=content,
            count=count,
            difficulty=difficulty,
            topic=topic,
            user_preferences=user_prefs
        )
        
        logger.info(f"Generating {count} flashcards at {difficulty} difficulty")
        
        try:
            # Call LLM
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_tokens=3000,
                json_mode=True
            )
            
            # Parse JSON response
            result = json.loads(response["content"])
            
            # Add metadata
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            result["generation_params"] = {
                "count": count,
                "difficulty": difficulty,
                "topic": topic
            }
            
            logger.info(f"Successfully generated {len(result.get('flashcards', []))} flashcards")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse flashcard JSON response: {e}")
            return {
                "error": "Failed to parse flashcard generation response",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Flashcard generation failed: {e}")
            return {"error": str(e)}
