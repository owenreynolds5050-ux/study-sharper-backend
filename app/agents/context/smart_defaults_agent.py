"""
Smart Defaults Agent
Intelligently infers missing information to avoid nagging the user
Uses LLM to make educated guesses based on context
"""

from ..base import BaseAgent, AgentType
from ..utils.llm_client import llm_client
from typing import Dict, Any, Optional
import json
import logging

logger = logging.getLogger(__name__)


class SmartDefaultsAgent(BaseAgent):
    """Infers missing information to avoid nagging user"""
    
    def __init__(self):
        super().__init__(
            name="smart_defaults_agent",
            agent_type=AgentType.UTILITY,
            model="anthropic/claude-3.5-haiku",
            description="Intelligently infers missing context"
        )
        logger.info("Smart Defaults Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Infer missing parameters based on context.
        
        Args:
            input_data: Must contain 'missing_param' and 'context'
            context: Optional execution context
            
        Returns:
            Dictionary with inferred value, confidence, and reasoning
        """
        
        missing_param = input_data.get("missing_param")
        user_context = input_data.get("context", {})
        
        if not missing_param:
            logger.warning("Smart Defaults agent called without missing_param")
            return {"error": "No missing parameter specified"}
        
        try:
            # Build inference prompt
            prompt = self._build_inference_prompt(missing_param, user_context)
            
            # Call LLM for inference
            response = await llm_client.call(
                prompt=prompt,
                system_prompt="You are an intelligent assistant that infers missing information based on context. Always respond in valid JSON format.",
                temperature=0.3,
                max_tokens=500,
                json_mode=True
            )
            
            # Parse response
            try:
                result = json.loads(response["content"])
                
                return {
                    "inferred_value": result.get("value"),
                    "confidence": result.get("confidence", 0.5),
                    "reasoning": result.get("reasoning"),
                    "alternatives": result.get("alternatives", []),
                    "tokens_used": response["tokens_used"],
                    "should_ask_user": result.get("confidence", 0.5) < 0.5
                }
            
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM JSON response: {e}")
                return {
                    "error": "Failed to parse LLM response",
                    "raw_response": response["content"]
                }
        
        except Exception as e:
            logger.error(f"Smart Defaults agent error: {e}")
            return {"error": str(e)}
    
    def _build_inference_prompt(
        self,
        missing_param: str,
        user_context: Dict[str, Any]
    ) -> str:
        """Build prompt for inference"""
        
        context_summary = json.dumps(user_context, indent=2)
        
        return f"""Given the following user context, infer the most likely value for the missing parameter: "{missing_param}"

User Context:
{context_summary}

Respond in this exact JSON format:
{{
    "value": "your inferred value",
    "confidence": 0.85,
    "reasoning": "brief explanation of why you chose this value",
    "alternatives": ["alternative1", "alternative2"]
}}

Confidence scale:
- Below 0.5: Low confidence, user should be asked for clarification
- 0.5-0.8: Medium confidence, offer as suggestion with alternatives
- Above 0.8: High confidence, use the inference

Be conservative with confidence scores. Only use high confidence when the context strongly suggests a specific value."""
