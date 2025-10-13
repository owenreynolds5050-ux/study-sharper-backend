"""
Flashcard Generation Service
Generates AI-powered flashcards from note content using OpenRouter
"""

from typing import List, Dict, Any
from app.services.open_router import get_chat_completion
import json
import re


def generate_flashcards_from_text(
    text: str,
    note_title: str = "",
    num_cards: int = 10,
    difficulty: str = "medium"
) -> List[Dict[str, str]]:
    """
    Generate flashcards from text content using AI.
    
    Args:
        text: The content to generate flashcards from
        note_title: Optional title of the note for context
        num_cards: Number of flashcards to generate (default: 10)
        difficulty: Difficulty level - 'easy', 'medium', or 'hard' (default: 'medium')
    
    Returns:
        List of flashcard dictionaries with 'front', 'back', and optionally 'explanation'
    """
    
    # Build the AI prompt based on difficulty
    difficulty_instructions = {
        "easy": "Focus on basic definitions and simple recall questions. Keep answers concise.",
        "medium": "Mix of recall and comprehension questions. Include some application questions.",
        "hard": "Focus on analysis, synthesis, and application. Include challenging questions that require deeper understanding."
    }
    
    difficulty_instruction = difficulty_instructions.get(difficulty, difficulty_instructions["medium"])
    
    system_prompt = f"""You are an expert educational content creator specializing in flashcard generation for students.

Your task is to create {num_cards} high-quality flashcards from the provided study material.

DIFFICULTY LEVEL: {difficulty.upper()}
{difficulty_instruction}

FLASHCARD GUIDELINES:
1. FRONT (Question): Should be clear, specific, and testable
2. BACK (Answer): Should be accurate, complete, and student-friendly
3. EXPLANATION (Optional): Add context, mnemonics, or additional insights when helpful

QUESTION TYPES TO INCLUDE:
- Definition questions: "What is X?"
- Concept questions: "Explain how X works"
- Application questions: "When would you use X?"
- Comparison questions: "What's the difference between X and Y?"
- Process questions: "What are the steps in X?"

IMPORTANT RULES:
- Each card should focus on ONE concept or fact
- Avoid yes/no questions - make questions specific
- Use examples in explanations when helpful
- Keep questions clear and unambiguous
- Make sure answers are complete but concise

OUTPUT FORMAT:
Return ONLY a valid JSON array of flashcard objects. Each object must have these fields:
- "front": the question (string)
- "back": the answer (string)
- "explanation": additional context (string, can be empty)

Example format:
[
  {{
    "front": "What is photosynthesis?",
    "back": "The process by which plants convert light energy into chemical energy (glucose) using carbon dioxide and water.",
    "explanation": "Remember the equation: 6CO₂ + 6H₂O + light → C₆H₁₂O₆ + 6O₂"
  }}
]

DO NOT include any text before or after the JSON array.
"""
    
    user_prompt = f"""Generate {num_cards} flashcards from this study material:

{"Title: " + note_title if note_title else ""}

Content:
{text}

Return only the JSON array of flashcards."""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        # Get AI response
        response = get_chat_completion(messages, model="anthropic/claude-3.5-sonnet")
        
        # Parse the JSON response
        flashcards = parse_flashcard_response(response)
        
        # Validate and clean flashcards
        valid_flashcards = []
        for card in flashcards[:num_cards]:  # Limit to requested number
            if validate_flashcard(card):
                valid_flashcards.append({
                    "front": card.get("front", "").strip(),
                    "back": card.get("back", "").strip(),
                    "explanation": card.get("explanation", "").strip()
                })
        
        if not valid_flashcards:
            raise ValueError("No valid flashcards generated from AI response")
        
        return valid_flashcards
        
    except Exception as e:
        raise Exception(f"Failed to generate flashcards: {str(e)}")


def parse_flashcard_response(response: str) -> List[Dict[str, str]]:
    """
    Parse AI response to extract JSON array of flashcards.
    Handles various response formats and cleans the output.
    """
    try:
        # Remove markdown code blocks if present
        response = response.strip()
        if response.startswith("```"):
            # Extract content between code blocks
            match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
            if match:
                response = match.group(1)
        
        # Parse JSON
        flashcards = json.loads(response)
        
        # Ensure it's a list
        if not isinstance(flashcards, list):
            raise ValueError("Response is not a JSON array")
        
        return flashcards
        
    except json.JSONDecodeError as e:
        # Try to find JSON array in the response
        json_match = re.search(r'\[[\s\S]*\]', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
        raise ValueError(f"Failed to parse flashcard JSON: {str(e)}")


def validate_flashcard(card: Dict[str, Any]) -> bool:
    """
    Validate that a flashcard has required fields and reasonable content.
    """
    if not isinstance(card, dict):
        return False
    
    # Must have front and back
    if "front" not in card or "back" not in card:
        return False
    
    front = str(card.get("front", "")).strip()
    back = str(card.get("back", "")).strip()
    
    # Must not be empty
    if not front or not back:
        return False
    
    # Reasonable length constraints
    if len(front) < 5 or len(back) < 5:
        return False
    
    if len(front) > 500 or len(back) > 1000:
        return False
    
    return True


def calculate_next_review_interval(mastery_level: int, was_correct: bool) -> int:
    """
    Calculate the next review interval in days based on spaced repetition algorithm.
    
    Args:
        mastery_level: Current mastery level (0-5)
        was_correct: Whether the user answered correctly
    
    Returns:
        Number of days until next review
    """
    if not was_correct:
        # Reset to level 1 if incorrect
        return 1
    
    # Spaced repetition intervals by mastery level
    intervals = {
        0: 0,   # Review immediately
        1: 1,   # Review in 1 day
        2: 3,   # Review in 3 days
        3: 7,   # Review in 1 week
        4: 14,  # Review in 2 weeks
        5: 30   # Review in 1 month
    }
    
    return intervals.get(mastery_level, 1)


def update_mastery_level(current_level: int, was_correct: bool) -> int:
    """
    Update mastery level based on review performance.
    
    Args:
        current_level: Current mastery level (0-5)
        was_correct: Whether the user answered correctly
    
    Returns:
        New mastery level (0-5)
    """
    if was_correct:
        # Increase mastery level, max at 5
        return min(current_level + 1, 5)
    else:
        # Reset to level 1 if incorrect
        return 1
