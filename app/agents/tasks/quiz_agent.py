"""
Quiz Generation Agent
Creates quizzes with multiple question types
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from ..prompts.templates import PromptTemplates
from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class QuizAgent(BaseAgent):
    """Generates quizzes from content"""
    
    def __init__(self):
        super().__init__(
            name="quiz_agent",
            agent_type=AgentType.TASK,
            model="anthropic/claude-3.5-haiku",
            description="Creates practice quizzes"
        )
        logger.info("Quiz Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate quiz from content.
        
        Args:
            input_data: Must contain 'content' or context must have notes
                       Optional: 'question_count', 'difficulty', 'question_types'
            context: Optional context with notes, user preferences
            
        Returns:
            Dictionary with quiz object and metadata
        """
        
        content = input_data.get("content")
        question_count = input_data.get("question_count", 10)
        difficulty = input_data.get("difficulty")
        question_types = input_data.get("question_types")
        
        # Get content from context if not provided
        if not content:
            if context and context.get("notes") and context["notes"].get("notes"):
                notes = context["notes"]["notes"]
                content = "\n\n".join([
                    f"**{note.get('title', 'Untitled')}**\n{note.get('content', '')}"
                    for note in notes
                ])
                logger.info(f"Using {len(notes)} notes as content source")
            else:
                logger.warning("No content provided for quiz generation")
                return {"error": "No content provided for quiz generation"}
        
        # Get user preferences
        if context and context.get("profile"):
            prefs = context["profile"].get("preferences", {})
            if not difficulty:
                difficulty = prefs.get("preferred_difficulty", "medium")
        
        if not difficulty:
            difficulty = "medium"
        
        # Build prompt
        prompt = PromptTemplates.quiz_generation(
            content=content,
            question_count=question_count,
            difficulty=difficulty,
            question_types=question_types
        )
        
        logger.info(f"Generating quiz with {question_count} questions at {difficulty} difficulty")
        
        try:
            # Call LLM
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_tokens=3500,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            logger.info(f"Successfully generated quiz with {len(result.get('quiz', {}).get('questions', []))} questions")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quiz JSON response: {e}")
            return {
                "error": "Failed to parse quiz generation response",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Quiz generation failed: {e}")
            return {"error": str(e)}
