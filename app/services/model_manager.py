"""
Multi-Model Manager - Intelligent model selection for cost optimization
Uses different models based on conversation stage and task complexity
"""

from enum import Enum
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ModelTier(Enum):
    """Model tiers for different conversation stages"""
    INITIAL_PARSE = "initial"      # Understand user's initial request
    CONVERSATION = "conversation"   # Clarification questions
    GENERATION = "generation"       # Create flashcards
    VERIFICATION = "verification"   # Validate accuracy

# Model configuration with cost optimization
MODEL_CONFIG: Dict[ModelTier, str] = {
    ModelTier.INITIAL_PARSE: "anthropic/claude-3.5-sonnet",  # Mid-tier, good quality
    ModelTier.CONVERSATION: "anthropic/claude-3-haiku",      # Cheap for clarifications
    ModelTier.GENERATION: "anthropic/claude-3.5-sonnet",     # Best for content creation
    ModelTier.VERIFICATION: "perplexity/llama-3.1-sonar-large-128k-online"  # Fact-checking
}

# Cost tracking (approximate costs per 1M tokens)
MODEL_COSTS = {
    "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
    "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
    "perplexity/llama-3.1-sonar-large-128k-online": {"input": 1.0, "output": 1.0}
}


def get_appropriate_model(conversation_stage: str, context: Dict[str, Any]) -> str:
    """
    Determine which model to use based on conversation stage.
    
    Logic:
    - First message from user: INITIAL_PARSE (understand intent)
    - Follow-up questions/clarifications: CONVERSATION (cheap)
    - Ready to generate flashcards: GENERATION (expensive)
    - Per-flashcard validation: VERIFICATION (fact-check)
    
    Args:
        conversation_stage: Stage of conversation
        context: Additional context for decision making
    
    Returns:
        Model identifier string
    """
    
    if context.get("is_first_message"):
        logger.info("Using INITIAL_PARSE model for first message")
        return MODEL_CONFIG[ModelTier.INITIAL_PARSE]
    
    if context.get("ready_to_generate"):
        logger.info("Using GENERATION model for flashcard creation")
        return MODEL_CONFIG[ModelTier.GENERATION]
    
    if context.get("validating_flashcard"):
        logger.info("Using VERIFICATION model for accuracy check")
        return MODEL_CONFIG[ModelTier.VERIFICATION]
    
    # Default to cheap model for conversation
    logger.info("Using CONVERSATION model for clarification")
    return MODEL_CONFIG[ModelTier.CONVERSATION]


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost for a model call.
    
    Args:
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
    
    Returns:
        Estimated cost in USD
    """
    
    if model not in MODEL_COSTS:
        logger.warning(f"Unknown model for cost estimation: {model}")
        return 0.0
    
    costs = MODEL_COSTS[model]
    input_cost = (input_tokens / 1_000_000) * costs["input"]
    output_cost = (output_tokens / 1_000_000) * costs["output"]
    
    total_cost = input_cost + output_cost
    logger.debug(f"Estimated cost for {model}: ${total_cost:.6f}")
    
    return total_cost
