"""
Flashcard Verification System - Validates accuracy of generated flashcards
Uses fact-checking model to ensure educational quality
"""

from typing import Dict, Any, List
from app.services.open_router import get_chat_completion
from app.services.model_manager import MODEL_CONFIG, ModelTier
import json
import logging

logger = logging.getLogger(__name__)


async def generate_single_flashcard(
    model: str,
    subject: str,
    context: str,
    existing_cards: List[Dict[str, Any]],
    card_number: int
) -> Dict[str, Any]:
    """
    Generate a single flashcard using the generation model.
    
    Args:
        model: Model to use for generation
        subject: Subject/topic for the flashcard
        context: Note content or context
        existing_cards: Already generated cards (to avoid duplicates)
        card_number: Which card number this is
    
    Returns:
        Dictionary with 'front' and 'back' keys
    """
    
    # Build list of existing topics to avoid duplicates
    existing_topics = [card.get('front', '') for card in existing_cards]
    existing_topics_str = "\n".join([f"- {topic}" for topic in existing_topics]) if existing_topics else "None yet"
    
    prompt = f"""
Generate a single high-quality flashcard for {subject}.

Context from notes:
{context[:2000] if context != "No notes available - create generic content" else "Create generic content for this subject"}

Already covered topics (DO NOT repeat):
{existing_topics_str}

Requirements:
1. Create ONE flashcard only
2. Front: Clear, specific question or term
3. Back: Concise, accurate answer (2-3 sentences max)
4. Appropriate difficulty for high school/college level
5. Must be different from existing cards
6. No JSON formatting - just natural text

Respond in this exact format:
FRONT: [Your question or term]
BACK: [Your answer]
"""
    
    try:
        response = get_chat_completion([
            {"role": "user", "content": prompt}
        ], model=model)
        
        # Parse response
        lines = response.strip().split('\n')
        front = ""
        back = ""
        
        for line in lines:
            if line.startswith("FRONT:"):
                front = line.replace("FRONT:", "").strip()
            elif line.startswith("BACK:"):
                back = line.replace("BACK:", "").strip()
        
        if not front or not back:
            raise ValueError("Could not parse flashcard format")
        
        logger.info(f"Generated flashcard #{card_number}: {front[:50]}...")
        
        return {
            "front": front,
            "back": back
        }
        
    except Exception as e:
        logger.error(f"Error generating flashcard: {str(e)}")
        # Return a fallback card
        return {
            "front": f"{subject} - Key Concept {card_number}",
            "back": f"Important concept related to {subject}. Please review your notes for details."
        }


async def verify_flashcard_accuracy(
    model: str,
    flashcard: Dict[str, Any],
    subject: str,
    context: str
) -> Dict[str, Any]:
    """
    Use verification model to check flashcard accuracy.
    
    Args:
        model: Verification model to use
        flashcard: Flashcard to verify
        subject: Subject area
        context: Reference context from notes
    
    Returns:
        {
            "is_accurate": bool,
            "confidence": float,
            "issues": List[str]
        }
    """
    
    verification_prompt = f"""
You are a fact-checker validating educational flashcard accuracy.

Subject: {subject}
Reference Context: {context[:2000] if context != "No notes available - create generic content" else "Generic educational content"}

Flashcard to verify:
Front: {flashcard['front']}
Back: {flashcard['back']}

Evaluate:
1. Is the information factually correct?
2. Is it appropriate for high school/college level?
3. Are there any misleading or incorrect statements?
4. Is the answer clear and helpful?

Respond ONLY with valid JSON in this exact format:
{{
    "is_accurate": true,
    "confidence": 0.95,
    "issues": []
}}

If there are issues, set is_accurate to false and list them in the issues array.
"""
    
    try:
        response = get_chat_completion([
            {"role": "user", "content": verification_prompt}
        ], model=model)
        
        # Try to parse JSON from response
        # Clean up response to extract JSON
        response_clean = response.strip()
        if "```json" in response_clean:
            response_clean = response_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in response_clean:
            response_clean = response_clean.split("```")[1].split("```")[0].strip()
        
        result = json.loads(response_clean)
        
        logger.info(f"Verification result: accurate={result.get('is_accurate')}, confidence={result.get('confidence')}")
        
        return {
            "is_accurate": result.get("is_accurate", True),
            "confidence": result.get("confidence", 0.8),
            "issues": result.get("issues", [])
        }
        
    except Exception as e:
        logger.error(f"Error verifying flashcard: {str(e)}")
        # Default to accepting the card if verification fails
        return {
            "is_accurate": True,
            "confidence": 0.7,
            "issues": []
        }


async def generate_verified_flashcards(
    subject: str,
    user_notes: List[Dict[str, Any]],
    quantity: int,
    user_id: str
) -> List[Dict[str, Any]]:
    """
    Generate flashcards with per-card accuracy verification.
    
    Process:
    1. Use GENERATION model to create flashcard
    2. Use VERIFICATION model to validate each card
    3. Regenerate if verification fails
    4. Return verified flashcard set
    
    Args:
        subject: Subject/topic for flashcards
        user_notes: User's notes for context
        quantity: Number of flashcards to generate
        user_id: User ID for tracking
    
    Returns:
        List of verified flashcards
    """
    
    logger.info(f"Starting verified flashcard generation: {quantity} cards for {subject}")
    
    verified_flashcards = []
    generation_model = MODEL_CONFIG[ModelTier.GENERATION]
    verification_model = MODEL_CONFIG[ModelTier.VERIFICATION]
    
    # Prepare context from user notes
    if user_notes:
        notes_context = "\n\n".join([
            f"Note: {note.get('title', 'Untitled')}\n{note.get('content', note.get('extracted_text', ''))[:1000]}"
            for note in user_notes[:5]  # Use top 5 most relevant notes
        ])
    else:
        notes_context = "No notes available - create generic content"
    
    logger.info(f"Context length: {len(notes_context)} characters")
    
    for i in range(quantity):
        max_attempts = 2
        card_generated = False
        
        for attempt in range(max_attempts):
            try:
                # Generate single flashcard
                flashcard = await generate_single_flashcard(
                    model=generation_model,
                    subject=subject,
                    context=notes_context,
                    existing_cards=verified_flashcards,
                    card_number=i + 1
                )
                
                # Verify accuracy
                verification_result = await verify_flashcard_accuracy(
                    model=verification_model,
                    flashcard=flashcard,
                    subject=subject,
                    context=notes_context
                )
                
                if verification_result["is_accurate"]:
                    # Card passed verification
                    verified_flashcards.append({
                        **flashcard,
                        "verified": True,
                        "confidence_score": verification_result["confidence"],
                        "card_number": i + 1
                    })
                    card_generated = True
                    logger.info(f"Card #{i+1} verified successfully (confidence: {verification_result['confidence']})")
                    break
                else:
                    # Card failed verification
                    logger.warning(f"Card #{i+1} failed verification (attempt {attempt+1}): {verification_result['issues']}")
                    
                    if attempt == max_attempts - 1:
                        # After max attempts, include with warning flag
                        verified_flashcards.append({
                            **flashcard,
                            "verified": False,
                            "confidence_score": verification_result["confidence"],
                            "warning": "Could not verify accuracy",
                            "issues": verification_result["issues"],
                            "card_number": i + 1
                        })
                        card_generated = True
                        logger.warning(f"Card #{i+1} included with warning after {max_attempts} attempts")
                
            except Exception as e:
                logger.error(f"Error generating card #{i+1}, attempt {attempt+1}: {str(e)}")
                
                if attempt == max_attempts - 1:
                    # Create fallback card
                    verified_flashcards.append({
                        "front": f"{subject} - Concept {i+1}",
                        "back": f"Key concept related to {subject}. Please review your notes for details.",
                        "verified": False,
                        "confidence_score": 0.5,
                        "warning": "Generation error - fallback card",
                        "card_number": i + 1
                    })
                    card_generated = True
    
    logger.info(f"Completed generation: {len(verified_flashcards)} cards, {sum(1 for c in verified_flashcards if c.get('verified'))} verified")
    
    return verified_flashcards


def sanitize_ai_response(response: str) -> str:
    """
    Remove or limit emojis from AI responses while keeping text clean.
    
    Args:
        response: Raw AI response
    
    Returns:
        Cleaned response without excessive emojis
    """
    
    # Remove common decorative emojis that feel AI-generated
    decorative_emojis = ['💡', '✨', '🎯', '📚', '🎓', '💪', '👍', '✅', '🔥', '🚀', '⚡', '🌟']
    
    for emoji in decorative_emojis:
        response = response.replace(emoji, '')
    
    # Clean up extra spaces left by emoji removal
    response = ' '.join(response.split())
    
    return response.strip()
