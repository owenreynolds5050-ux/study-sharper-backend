"""
Quality Assurance Agent
Ensures content meets quality standards for educational value
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class QualityAgent(BaseAgent):
    """Ensures content meets quality standards"""
    
    def __init__(self):
        super().__init__(
            name="quality_agent",
            agent_type=AgentType.VALIDATION,
            model="anthropic/claude-3.5-haiku",
            description="Validates content quality and educational value"
        )
        logger.info("Quality Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Check content quality.
        
        Args:
            input_data: Must contain 'content'
                       Optional: 'content_type', 'criteria'
            context: Optional execution context
            
        Returns:
            Dictionary with quality assessment and improvements
        """
        
        content = input_data.get("content")
        content_type = input_data.get("content_type", "general")
        quality_criteria = input_data.get("criteria", {})
        
        if not content:
            logger.info("No content to check - returning acceptable quality")
            return {
                "meets_standards": True,
                "confidence": 0.5,
                "quality_score": 0.7,
                "message": "No content to check"
            }
        
        # Type-specific criteria
        type_criteria = {
            "flashcards": "clear questions, concise answers, proper difficulty, good coverage",
            "quiz": "unambiguous questions, correct answers, good explanations, appropriate difficulty",
            "exam": "comprehensive coverage, appropriate difficulty progression, clear instructions, proper structure",
            "summary": "captures key points, proper organization, appropriate length, clear language",
            "chat": "helpful response, accurate information, conversational tone, addresses question"
        }
        
        specific_criteria = type_criteria.get(content_type, "general educational quality")
        
        # Build quality check prompt
        prompt = f"""You are a quality assurance expert for educational content. Evaluate the following {content_type}.

Content:
---
{json.dumps(content, indent=2)}
---

Quality Criteria for {content_type}:
- {specific_criteria}
- Clear and understandable language
- Appropriate for students
- Educationally valuable
- Well-organized and structured
- Free of errors (spelling, grammar, formatting)
- Engaging and effective for learning

Respond in this EXACT JSON format:
{{
    "meets_standards": true/false,
    "confidence": 0.0-1.0,
    "quality_score": 0.0-1.0,
    "strengths": ["list", "of", "strengths"],
    "weaknesses": [
        {{
            "issue": "description",
            "severity": "high/medium/low",
            "suggestion": "how to improve"
        }}
    ],
    "improvements_needed": [
        "specific improvements"
    ],
    "overall_assessment": "brief summary"
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

        logger.info(f"Checking quality of {content_type} content")
        
        try:
            # Call LLM
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.3,
                max_tokens=2000,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            # Calculate quality score if not provided
            if "quality_score" not in result or result["quality_score"] is None:
                weaknesses = result.get("weaknesses", [])
                high_severity = len([w for w in weaknesses if w.get("severity") == "high"])
                medium_severity = len([w for w in weaknesses if w.get("severity") == "medium"])
                low_severity = len([w for w in weaknesses if w.get("severity") == "low"])
                
                # Start at 1.0, deduct for weaknesses
                result["quality_score"] = max(0.3, 1.0 - (high_severity * 0.2) - (medium_severity * 0.1) - (low_severity * 0.05))
            
            # Ensure meets_standards aligns with quality_score
            if result["quality_score"] < 0.6:
                result["meets_standards"] = False
            
            logger.info(f"Quality check complete: score={result['quality_score']:.2f}, meets_standards={result.get('meets_standards')}")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse quality check response: {e}")
            return {
                "meets_standards": True,
                "confidence": 0.4,
                "quality_score": 0.7,
                "error": "Failed to parse quality check response - assuming acceptable quality",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Quality check failed: {e}")
            return {
                "meets_standards": True,
                "confidence": 0.4,
                "quality_score": 0.7,
                "error": str(e)
            }
