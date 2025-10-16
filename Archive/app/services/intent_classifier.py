"""
Intent Classification Service
Classifies user messages into study-related categories for routing
"""

from typing import Dict, Any, Optional
from app.services.open_router import get_chat_completion
import logging
import json

logger = logging.getLogger(__name__)


def classify_intent(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Classify user intent into one of the following categories:
    - non_study: Not study-related
    - flashcards: Flashcard generation request
    - notes: Notes/summary generation request
    - account: Account settings request
    - other_study: Other study-related but not implemented
    
    Returns:
        Dict with keys:
        - intent: str (one of the above)
        - confidence: float (0-1)
        - extracted_params: dict (any parameters extracted from message)
    """
    
    system_prompt = """You are an intent classifier for a study assistant chatbot.

Your task is to classify user messages into ONE of these categories:

1. **non_study**: The message is NOT related to studying, education, flashcards, notes, or account settings.
   Examples: "What's the weather?", "Tell me a joke", "How are you?"

2. **flashcards**: The user wants to create, generate, or work with flashcards.
   Examples: "Create flashcards from my notes", "Generate 20 biology flashcards", "Make cards about the American Revolution"

3. **notes**: The user wants to create summaries, generate notes, or work with note content (but NOT flashcards).
   Examples: "Summarize my chemistry notes", "Create a study guide", "Generate notes from this topic"

4. **account**: The user wants to manage account settings, check their plan, or modify preferences.
   Examples: "What's my plan?", "Upgrade to premium", "Change my settings"

5. **other_study**: Study-related but doesn't fit the above categories.
   Examples: "Help me study for my exam", "What should I focus on?", "Create a study schedule"

IMPORTANT RULES:
- If the message mentions "flashcard" or "cards", it's almost always **flashcards**
- If the message mentions "summary" or "notes" (without flashcards), it's **notes**
- If the message is about weather, jokes, general chat, it's **non_study**
- When in doubt between study categories, prefer **flashcards** if generation is implied

OUTPUT FORMAT:
Return ONLY a valid JSON object with these fields:
{
    "intent": "flashcards",  // One of: non_study, flashcards, notes, account, other_study
    "confidence": 0.95,      // Float between 0 and 1
    "reasoning": "User explicitly asked to create flashcards",
    "extracted_params": {    // Optional: any parameters you can extract
        "subject": "biology",
        "subtopic": "cell structure",
        "length": 20,
        "difficulty": "intermediate"
    }
}

DO NOT include any text before or after the JSON object."""

    user_prompt = f"""Classify this user message:

Message: "{message}"

{f'Previous context: {json.dumps(context)}' if context else ''}

Return the classification as JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = get_chat_completion(
            messages=messages,
            model="anthropic/claude-3.5-sonnet",
            temperature=0.3,  # Lower temperature for more consistent classification
            max_tokens=500
        )
        
        # Parse JSON response
        try:
            result = json.loads(response)
            
            # Validate required fields
            if "intent" not in result:
                logger.error("Intent classification missing 'intent' field")
                return _fallback_classification(message)
            
            # Ensure confidence is present and valid
            if "confidence" not in result or not isinstance(result["confidence"], (int, float)):
                result["confidence"] = 0.8
            
            # Ensure extracted_params exists
            if "extracted_params" not in result:
                result["extracted_params"] = {}
            
            logger.info(f"Classified intent: {result['intent']} (confidence: {result['confidence']})")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse intent classification JSON: {e}")
            logger.error(f"Raw response: {response}")
            return _fallback_classification(message)
    
    except Exception as e:
        logger.error(f"Intent classification failed: {e}")
        return _fallback_classification(message)


def _fallback_classification(message: str) -> Dict[str, Any]:
    """
    Fallback classification using simple keyword matching
    when AI classification fails
    """
    message_lower = message.lower()
    
    # Check for flashcard keywords
    flashcard_keywords = ["flashcard", "flash card", "cards", "deck", "quiz card"]
    if any(keyword in message_lower for keyword in flashcard_keywords):
        return {
            "intent": "flashcards",
            "confidence": 0.7,
            "reasoning": "Fallback: detected flashcard keywords",
            "extracted_params": {}
        }
    
    # Check for notes keywords
    notes_keywords = ["summary", "summarize", "notes", "study guide"]
    if any(keyword in message_lower for keyword in notes_keywords):
        return {
            "intent": "notes",
            "confidence": 0.7,
            "reasoning": "Fallback: detected notes keywords",
            "extracted_params": {}
        }
    
    # Check for account keywords
    account_keywords = ["account", "plan", "premium", "upgrade", "settings", "subscription"]
    if any(keyword in message_lower for keyword in account_keywords):
        return {
            "intent": "account",
            "confidence": 0.7,
            "reasoning": "Fallback: detected account keywords",
            "extracted_params": {}
        }
    
    # Check for study keywords
    study_keywords = ["study", "learn", "exam", "test", "homework", "assignment"]
    if any(keyword in message_lower for keyword in study_keywords):
        return {
            "intent": "other_study",
            "confidence": 0.6,
            "reasoning": "Fallback: detected general study keywords",
            "extracted_params": {}
        }
    
    # Default to non-study
    return {
        "intent": "non_study",
        "confidence": 0.5,
        "reasoning": "Fallback: no study-related keywords detected",
        "extracted_params": {}
    }


def extract_flashcard_parameters(message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Extract flashcard generation parameters from user message
    
    Returns dict with:
    - subject: Optional[str]
    - subtopic: Optional[str]
    - length: Optional[int]
    - difficulty: Optional[str]
    - from_notes: bool
    """
    
    system_prompt = """You are a parameter extractor for flashcard generation.

Extract these parameters from the user's message:
1. **subject**: The main subject (e.g., "Biology", "History", "Math")
2. **subtopic**: Specific topic within the subject (e.g., "Cell Structure", "American Revolution")
3. **length**: Number of flashcards requested (integer)
4. **difficulty**: Difficulty level - must be one of: "Basic", "Intermediate", "Advanced"
5. **from_notes**: Boolean - true if user wants to use their existing notes

RULES:
- If no length specified, return null (not a default value)
- If no difficulty specified, return null (not a default value)
- Subject and subtopic can be inferred from context
- from_notes is true if message mentions "from my notes", "use my notes", etc.

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
    "subject": "Biology",
    "subtopic": "Cell Structure",
    "length": 15,
    "difficulty": "Intermediate",
    "from_notes": true
}

Use null for any parameter not found. DO NOT include text before or after JSON."""

    user_prompt = f"""Extract flashcard parameters from this message:

Message: "{message}"

{f'Previous context: {json.dumps(context)}' if context else ''}

Return the parameters as JSON."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        response = get_chat_completion(
            messages=messages,
            model="anthropic/claude-3.5-sonnet",
            temperature=0.3,
            max_tokens=300
        )
        
        result = json.loads(response)
        
        # Ensure all expected keys exist
        params = {
            "subject": result.get("subject"),
            "subtopic": result.get("subtopic"),
            "length": result.get("length"),
            "difficulty": result.get("difficulty"),
            "from_notes": result.get("from_notes", False)
        }
        
        logger.info(f"Extracted parameters: {params}")
        return params
        
    except Exception as e:
        logger.error(f"Parameter extraction failed: {e}")
        return {
            "subject": None,
            "subtopic": None,
            "length": None,
            "difficulty": None,
            "from_notes": "notes" in message.lower()
        }
