"""
Summary Generation Agent
Creates study summaries from content
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from ..prompts.templates import PromptTemplates
from typing import Dict, Any, Optional, List
import json
import logging

logger = logging.getLogger(__name__)


class SummaryAgent(BaseAgent):
    """Generates summaries from content"""
    
    def __init__(self):
        super().__init__(
            name="summary_agent",
            agent_type=AgentType.TASK,
            model="anthropic/claude-3.5-haiku",
            description="Creates study summaries"
        )
        logger.info("Summary Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate summary from content.
        
        Args:
            input_data: Must contain 'content' or context must have notes
                       Optional: 'length', 'style', 'focus_areas'
            context: Optional context with notes, user preferences
            
        Returns:
            Dictionary with summary object and metadata
        """
        
        content = input_data.get("content")
        length = input_data.get("length")
        style = input_data.get("style", "bullet_points")
        focus_areas = input_data.get("focus_areas")
        
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
                logger.warning("No content provided for summary generation")
                return {"error": "No content provided for summary generation"}
        
        # Get user preference for detail level
        if context and context.get("profile"):
            prefs = context["profile"].get("preferences", {})
            if not length and prefs.get("preferred_detail_level"):
                # Map detail level to length
                detail_to_length = {
                    "brief": "short",
                    "detailed": "medium",
                    "comprehensive": "long"
                }
                length = detail_to_length.get(prefs["preferred_detail_level"], "medium")
                logger.info(f"Using user preferred detail level: {length}")
        
        if not length:
            length = "medium"
        
        # Build prompt
        prompt = PromptTemplates.summary_generation(
            content=content,
            length=length,
            style=style,
            focus_areas=focus_areas
        )
        
        logger.info(f"Generating {length} summary in {style} style")
        
        try:
            # Call LLM (lower temperature for summaries)
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.5,
                max_tokens=2500,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            logger.info(f"Successfully generated summary with {len(result.get('summary', {}).get('main_points', []))} main points")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summary JSON response: {e}")
            return {
                "error": "Failed to parse summary generation response",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return {"error": str(e)}
