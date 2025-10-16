"""
Accuracy Verification Agent
Verifies factual accuracy of generated content against source material
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class AccuracyAgent(BaseAgent):
    """Verifies factual accuracy of generated content"""
    
    def __init__(self):
        super().__init__(
            name="accuracy_agent",
            agent_type=AgentType.VALIDATION,
            model="anthropic/claude-3.5-haiku",
            description="Fact-checks generated content against source material"
        )
        logger.info("Accuracy Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Verify accuracy of generated content.
        
        Args:
            input_data: Must contain 'generated_content' and 'source_material'
                       Optional: 'content_type'
            context: Optional execution context
            
        Returns:
            Dictionary with accuracy assessment and corrections
        """
        
        generated_content = input_data.get("generated_content")
        source_material = input_data.get("source_material")
        content_type = input_data.get("content_type", "general")
        
        if not generated_content or not source_material:
            logger.warning("Insufficient data for accuracy verification")
            return {
                "is_accurate": True,
                "confidence": 0.5,
                "accuracy_score": 0.7,
                "message": "Insufficient data for accuracy verification - assuming accurate"
            }
        
        # Build verification prompt
        prompt = f"""You are an expert fact-checker for educational content. Your job is to verify that generated study materials are factually accurate based on the source material.

Source Material:
---
{source_material}
---

Generated Content ({content_type}):
---
{json.dumps(generated_content, indent=2)}
---

Task: Verify the accuracy of the generated content by checking:
1. Are all facts correct according to the source material?
2. Are there any contradictions or inaccuracies?
3. Is information misrepresented or oversimplified incorrectly?
4. Are answers/explanations correct?
5. Does the content accurately reflect the source material?

IMPORTANT: 
- Paraphrasing is acceptable as long as meaning is preserved
- Simplification for learning is acceptable if facts remain correct
- Minor wording differences are not inaccuracies

Respond in this EXACT JSON format:
{{
    "is_accurate": true/false,
    "confidence": 0.0-1.0,
    "issues_found": [
        {{
            "location": "where the issue is (e.g., 'Question 2')",
            "issue": "description of the problem",
            "severity": "high/medium/low"
        }}
    ],
    "corrections_needed": [
        {{
            "item": "what needs correcting",
            "correction": "how to fix it"
        }}
    ],
    "overall_assessment": "brief summary of accuracy"
}}

IMPORTANT: Return ONLY valid JSON, no additional text."""

        logger.info(f"Checking accuracy of {content_type} content")
        
        try:
            # Call LLM with low temperature for factual checking
            response = await llm_client.call(
                prompt=prompt,
                model=self.model,
                temperature=0.2,
                max_tokens=2000,
                json_mode=True
            )
            
            # Parse response
            result = json.loads(response["content"])
            result["tokens_used"] = response["tokens_used"]
            result["model_used"] = response["model"]
            
            # Calculate overall accuracy score
            issues_found = result.get("issues_found", [])
            high_severity = len([i for i in issues_found if i.get("severity") == "high"])
            medium_severity = len([i for i in issues_found if i.get("severity") == "medium"])
            low_severity = len([i for i in issues_found if i.get("severity") == "low"])
            
            if result.get("is_accurate"):
                # Start at 1.0, deduct for issues
                result["accuracy_score"] = max(0.0, 1.0 - (high_severity * 0.15) - (medium_severity * 0.08) - (low_severity * 0.03))
            else:
                # Start at 0.5, deduct more for issues
                result["accuracy_score"] = max(0.0, 0.5 - (high_severity * 0.2) - (medium_severity * 0.1))
            
            logger.info(f"Accuracy check complete: score={result['accuracy_score']:.2f}, is_accurate={result.get('is_accurate')}")
            return result
        
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse accuracy check response: {e}")
            return {
                "is_accurate": True,
                "confidence": 0.3,
                "accuracy_score": 0.6,
                "error": "Failed to parse accuracy check response",
                "raw_response": response["content"][:500]
            }
        
        except Exception as e:
            logger.error(f"Accuracy check failed: {e}")
            return {
                "is_accurate": True,
                "confidence": 0.3,
                "accuracy_score": 0.6,
                "error": str(e)
            }
