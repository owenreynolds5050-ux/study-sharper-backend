"""
Exam Generation Agent
Creates comprehensive exams with multiple sections
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from ..prompts.templates import PromptTemplates
from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class ExamAgent(BaseAgent):
    """Generates comprehensive exams"""
    
    def __init__(self):
        super().__init__(
            name="exam_agent",
            agent_type=AgentType.TASK,
            model="anthropic/claude-3.5-haiku",
            description="Creates practice exams"
        )
        logger.info("Exam Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate exam from content.
        
        Args:
            input_data: Must contain 'content' or context must have notes
                       Optional: 'duration_minutes', 'difficulty', 'sections'
            context: Optional context with notes, user preferences
            
        Returns:
            Dictionary with exam object and metadata
        """
        
        content = input_data.get("content")
        duration = input_data.get("duration_minutes", 60)
        difficulty = input_data.get("difficulty")
        sections = input_data.get("sections")
        
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
                logger.warning("No content provided for exam generation")
                return {"error": "No content provided for exam generation"}
        
        # Get user preferences
        if context and context.get("profile"):
            prefs = context["profile"].get("preferences", {})
            if not difficulty:
                difficulty = prefs.get("preferred_difficulty", "medium")
        
        if not difficulty:
            difficulty = "medium"
        
        # Build prompt
        prompt = PromptTemplates.exam_generation(
            content=content,
            duration_minutes=duration,
            difficulty=difficulty,
            sections=sections
        )
        
        logger.info(f"Generating {duration}-minute exam at {difficulty} difficulty")
        
        try:
            # Call LLM (exams need more tokens)
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.7,
                max_tokens=4000,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            logger.info(f"Successfully generated exam with {len(result.get('exam', {}).get('sections', []))} sections")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse exam JSON response: {e}")
            return {
                "error": "Failed to parse exam generation response",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Exam generation failed: {e}")
            return {"error": str(e)}
