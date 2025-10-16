"""
Content Safety Agent
Ensures content is appropriate and safe for students
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class SafetyAgent(BaseAgent):
    """Ensures content is appropriate for students"""
    
    def __init__(self):
        super().__init__(
            name="safety_agent",
            agent_type=AgentType.VALIDATION,
            model="anthropic/claude-3.5-haiku",
            description="Checks content appropriateness and safety"
        )
        logger.info("Safety Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check content safety and appropriateness.
        
        Args:
            input_data: Must contain 'content'
                       Optional: 'content_type', 'age_group'
            context: Optional execution context
            
        Returns:
            Dictionary with safety assessment and concerns
        """
        
        content = input_data.get("content")
        content_type = input_data.get("content_type", "general")
        age_group = input_data.get("age_group", "high_school")
        
        if not content:
            logger.info("No content to check - returning safe")
            return {
                "is_safe": True,
                "confidence": 1.0,
                "safety_score": 1.0,
                "message": "No content to check"
            }
        
        # Build safety check prompt
        prompt = f"""You are a content safety checker for an educational platform serving {age_group} students.

Content Type: {content_type}
Content to Check:
---
{json.dumps(content, indent=2)}
---

Check for:
1. Inappropriate language or content
2. Harmful or dangerous information
3. Bias or discriminatory content
4. Age-inappropriate material
5. Misleading or manipulative content
6. Privacy concerns

IMPORTANT CONTEXT:
- This is an EDUCATIONAL platform
- Some mature topics (history, science, literature) are appropriate when presented educationally
- Academic discussion of difficult topics is acceptable
- Focus on harmful content, not educational content about difficult subjects

Respond in this EXACT JSON format:
{{
    "is_safe": true/false,
    "confidence": 0.0-1.0,
    "concerns": [
        {{
            "type": "inappropriate_language/harmful_content/bias/age_inappropriate/privacy/other",
            "description": "what the concern is",
            "severity": "high/medium/low",
            "location": "where in the content"
        }}
    ],
    "recommendations": [
        "suggested changes if any"
    ],
    "overall_assessment": "brief summary"
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

        logger.info(f"Checking safety of {content_type} content for {age_group}")
        
        try:
            # Call LLM with very low temperature for safety checking
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.1,
                max_tokens=1500,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            # Calculate safety score
            concerns = result.get("concerns", [])
            high_severity = len([c for c in concerns if c.get("severity") == "high"])
            medium_severity = len([c for c in concerns if c.get("severity") == "medium"])
            low_severity = len([c for c in concerns if c.get("severity") == "low"])
            
            if high_severity > 0:
                result["safety_score"] = 0.0
                result["is_safe"] = False
                logger.warning(f"Content failed safety check: {high_severity} high severity issues")
            elif medium_severity > 0:
                result["safety_score"] = max(0.5, 1.0 - (medium_severity * 0.2))
                # Medium severity issues are still considered safe but flagged
                result["is_safe"] = result.get("is_safe", True)
                logger.info(f"Content has {medium_severity} medium severity concerns")
            else:
                result["safety_score"] = max(0.9, 1.0 - (low_severity * 0.05))
                logger.info("Content passed safety check")
            
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse safety check response: {e}")
            # If parsing fails, err on the side of caution
            return {
                "is_safe": False,
                "confidence": 0.5,
                "safety_score": 0.5,
                "error": "Failed to parse safety check response - flagging for manual review",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Safety check failed: {e}")
            # On error, be cautious
            return {
                "is_safe": False,
                "confidence": 0.3,
                "safety_score": 0.5,
                "error": str(e)
            }
