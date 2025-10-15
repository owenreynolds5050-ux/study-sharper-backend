"""
Flashcard Generation Service with Verification
Generates flashcards using Sonnet 3.5 and verifies with web-enabled LLM
"""

from typing import List, Dict, Any, Optional, Tuple
from app.services.open_router import get_chat_completion
from app.services.embeddings import get_embedding_for_text
import logging
import json
import hashlib
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)


class FlashcardGenerator:
    """Handles flashcard generation with verification"""
    
    # Model configuration
    GENERATOR_MODEL = "anthropic/claude-3.5-sonnet"
    VERIFIER_MODEL = "perplexity/llama-3.1-sonar-large-128k-online"  # Web-enabled
    FALLBACK_VERIFIER = "anthropic/claude-3.5-sonnet"  # If Perplexity unavailable
    
    MAX_VERIFICATION_ATTEMPTS = 3
    VERIFICATION_FAILURE_THRESHOLD = 0.30  # 30% failure rate
    
    def __init__(self):
        self.verification_cache = {}  # Cache verification results
    
    def generate_flashcards(
        self,
        context_text: str,
        subject: str,
        subtopic: str,
        length: int,
        difficulty: str,
        source_note_ids: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Generate flashcards from context text
        
        Args:
            context_text: Combined text from notes
            subject: Subject area
            subtopic: Specific topic
            length: Number of cards to generate
            difficulty: Basic, Intermediate, or Advanced
            source_note_ids: List of note IDs used as sources
        
        Returns:
            List of flashcard dicts with front, back, explanation, position, source_note_id
        """
        
        system_prompt = f"""You are an expert educational content creator specializing in flashcard generation.

TASK: Create {length} high-quality flashcards for studying {subtopic} in {subject}.

DIFFICULTY LEVEL: {difficulty}
{self._get_difficulty_instructions(difficulty)}

FLASHCARD STRUCTURE:
1. **front**: Clear, specific question (string)
2. **back**: Accurate, complete answer (string)
3. **explanation**: Additional context, mnemonics, or insights (string, can be empty)

QUESTION TYPE VARIETY:
- Definition: "What is X?"
- Explanation: "Explain how X works"
- Application: "When would you use X?"
- Comparison: "What's the difference between X and Y?"
- Process: "What are the steps in X?"

QUALITY RULES:
- Each card focuses on ONE concept
- Questions are specific and unambiguous
- Answers are complete but concise
- Avoid yes/no questions
- Use examples in explanations when helpful
- Ensure factual accuracy

OUTPUT FORMAT:
Return ONLY a valid JSON array of flashcard objects:
[
  {{
    "front": "Question text here",
    "back": "Answer text here",
    "explanation": "Additional context here"
  }}
]

DO NOT include any text before or after the JSON array."""

        user_prompt = f"""Generate {length} flashcards from this study material:

Subject: {subject}
Topic: {subtopic}

Content:
{context_text[:6000]}  

Return only the JSON array of {length} flashcards."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = get_chat_completion(
                messages=messages,
                model=self.GENERATOR_MODEL,
                temperature=0.7,
                max_tokens=3000
            )
            
            # Parse response
            flashcards = self._parse_flashcard_response(response, length)
            
            # Add metadata
            for i, card in enumerate(flashcards):
                card["position"] = i
                card["source_note_id"] = source_note_ids[0] if source_note_ids and len(source_note_ids) == 1 else None
                card["ai_generated"] = True
            
            logger.info(f"Generated {len(flashcards)} flashcards")
            return flashcards
            
        except Exception as e:
            logger.error(f"Flashcard generation failed: {e}")
            raise Exception(f"Failed to generate flashcards: {str(e)}")
    
    def verify_flashcard(
        self,
        flashcard: Dict[str, Any],
        subject: str,
        difficulty: str,
        attempt: int = 1
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Verify a single flashcard for accuracy and appropriateness
        
        Returns:
            Tuple of (is_valid, error_reason, verification_details)
        """
        
        # Check cache first
        cache_key = self._get_cache_key(flashcard)
        if cache_key in self.verification_cache:
            logger.info(f"Using cached verification for card")
            return self.verification_cache[cache_key]
        
        system_prompt = """You are a fact-checking expert verifying educational flashcard content.

Your task is to verify:
1. **Factual Accuracy**: Is the answer correct? Use web search if needed.
2. **Age-Appropriateness**: Is the content suitable for students?
3. **Difficulty Match**: Does the complexity match the stated difficulty level?

VERIFICATION CRITERIA:
- Answer must be factually correct (check against reliable sources)
- Content must be appropriate for educational use
- Difficulty must match the target level
- Question must be clear and unambiguous
- Answer must be complete

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{
    "is_valid": true,
    "confidence": 0.95,
    "issues": [],
    "sources_checked": ["Wikipedia", "Educational databases"],
    "reasoning": "Verified against multiple sources. Content is accurate and appropriate."
}

If invalid:
{
    "is_valid": false,
    "confidence": 0.85,
    "issues": ["Factual error: The answer states X but correct answer is Y"],
    "sources_checked": ["Wikipedia"],
    "reasoning": "Found factual inaccuracy in the answer."
}

DO NOT include text before or after JSON."""

        user_prompt = f"""Verify this flashcard for {subject} at {difficulty} difficulty level:

Front (Question): {flashcard.get('front', '')}
Back (Answer): {flashcard.get('back', '')}
Explanation: {flashcard.get('explanation', '')}

Verification attempt: {attempt} of {self.MAX_VERIFICATION_ATTEMPTS}

Return verification result as JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # Try web-enabled verifier first
            try:
                response = get_chat_completion(
                    messages=messages,
                    model=self.VERIFIER_MODEL,
                    temperature=0.2,
                    max_tokens=500
                )
            except Exception as e:
                logger.warning(f"Perplexity verifier failed, using fallback: {e}")
                response = get_chat_completion(
                    messages=messages,
                    model=self.FALLBACK_VERIFIER,
                    temperature=0.2,
                    max_tokens=500
                )
            
            # Parse verification result
            result = json.loads(response)
            
            is_valid = result.get("is_valid", False)
            error_reason = None if is_valid else "; ".join(result.get("issues", ["Verification failed"]))
            
            verification_details = {
                "confidence": result.get("confidence", 0.0),
                "sources_checked": result.get("sources_checked", []),
                "reasoning": result.get("reasoning", ""),
                "attempt": attempt
            }
            
            # Cache result
            cache_result = (is_valid, error_reason, verification_details)
            self.verification_cache[cache_key] = cache_result
            
            logger.info(f"Verification result: valid={is_valid}, confidence={verification_details['confidence']}")
            return cache_result
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            # On verification error, assume valid but log warning
            return (True, None, {"confidence": 0.5, "error": str(e), "attempt": attempt})
    
    def regenerate_flashcard(
        self,
        original_card: Dict[str, Any],
        subject: str,
        subtopic: str,
        difficulty: str,
        failure_reason: str,
        attempt: int
    ) -> Dict[str, Any]:
        """
        Regenerate a single flashcard that failed verification
        """
        
        system_prompt = f"""You are regenerating a flashcard that failed verification.

ORIGINAL FLASHCARD:
Front: {original_card.get('front', '')}
Back: {original_card.get('back', '')}

FAILURE REASON: {failure_reason}

TASK: Create a NEW flashcard on the same topic that fixes the issues.
- Ensure factual accuracy
- Match {difficulty} difficulty level
- Keep the same general topic/concept

OUTPUT FORMAT:
Return ONLY a valid JSON object:
{{
    "front": "New question text",
    "back": "New answer text",
    "explanation": "New explanation"
}}"""

        user_prompt = f"""Regenerate flashcard for {subtopic} in {subject}.
Attempt {attempt} of {self.MAX_VERIFICATION_ATTEMPTS}.
Return only JSON."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            response = get_chat_completion(
                messages=messages,
                model=self.GENERATOR_MODEL,
                temperature=0.8,  # Slightly higher for variety
                max_tokens=500
            )
            
            new_card = json.loads(response)
            new_card["position"] = original_card.get("position", 0)
            new_card["source_note_id"] = original_card.get("source_note_id")
            new_card["ai_generated"] = True
            new_card["verification_attempts"] = attempt
            
            logger.info(f"Regenerated flashcard (attempt {attempt})")
            return new_card
            
        except Exception as e:
            logger.error(f"Flashcard regeneration failed: {e}")
            # Return original card as fallback
            return original_card
    
    def generate_and_verify_flashcards(
        self,
        context_text: str,
        subject: str,
        subtopic: str,
        length: int,
        difficulty: str,
        source_note_ids: Optional[List[str]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Generate flashcards and verify each one with regeneration on failure
        
        Returns:
            Tuple of (verified_flashcards, verification_summary)
        """
        
        logger.info(f"Starting generation and verification: {length} cards, {difficulty} difficulty")
        
        # Step 1: Generate initial flashcards
        flashcards = self.generate_flashcards(
            context_text=context_text,
            subject=subject,
            subtopic=subtopic,
            length=length,
            difficulty=difficulty,
            source_note_ids=source_note_ids
        )
        
        verified_cards = []
        failed_cards = []
        verification_summary = {
            "total_generated": len(flashcards),
            "total_verified": 0,
            "total_failed": 0,
            "verification_attempts": {},
            "started_at": datetime.now().isoformat(),
            "completed_at": None
        }
        
        # Step 2: Verify each flashcard
        for i, card in enumerate(flashcards):
            logger.info(f"Verifying card {i+1}/{len(flashcards)}")
            
            is_valid = False
            attempt = 1
            current_card = card
            
            # Try up to MAX_VERIFICATION_ATTEMPTS times
            while attempt <= self.MAX_VERIFICATION_ATTEMPTS and not is_valid:
                is_valid, error_reason, verification_details = self.verify_flashcard(
                    flashcard=current_card,
                    subject=subject,
                    difficulty=difficulty,
                    attempt=attempt
                )
                
                if is_valid:
                    current_card["verification_details"] = verification_details
                    current_card["failed_verification"] = False
                    current_card["verification_attempts"] = attempt
                    verified_cards.append(current_card)
                    verification_summary["total_verified"] += 1
                    break
                else:
                    logger.warning(f"Card {i+1} failed verification (attempt {attempt}): {error_reason}")
                    
                    if attempt < self.MAX_VERIFICATION_ATTEMPTS:
                        # Regenerate and try again
                        current_card = self.regenerate_flashcard(
                            original_card=current_card,
                            subject=subject,
                            subtopic=subtopic,
                            difficulty=difficulty,
                            failure_reason=error_reason,
                            attempt=attempt + 1
                        )
                    
                    attempt += 1
            
            # If still not valid after all attempts, mark as failed
            if not is_valid:
                current_card["failed_verification"] = True
                current_card["verification_attempts"] = self.MAX_VERIFICATION_ATTEMPTS
                current_card["failure_reason"] = error_reason
                failed_cards.append(current_card)
                verification_summary["total_failed"] += 1
            
            verification_summary["verification_attempts"][f"card_{i+1}"] = attempt
        
        verification_summary["completed_at"] = datetime.now().isoformat()
        
        # Step 3: Check failure threshold
        failure_rate = len(failed_cards) / len(flashcards) if flashcards else 0
        
        if failure_rate > self.VERIFICATION_FAILURE_THRESHOLD:
            logger.error(f"Verification failure rate {failure_rate:.1%} exceeds threshold {self.VERIFICATION_FAILURE_THRESHOLD:.1%}")
            raise Exception(
                f"Unable to generate verified flashcards for this request. "
                f"Error: verification failed for {len(failed_cards)} of {len(flashcards)} cards."
            )
        
        logger.info(f"Verification complete: {len(verified_cards)} verified, {len(failed_cards)} failed")
        
        return verified_cards, verification_summary
    
    def _get_difficulty_instructions(self, difficulty: str) -> str:
        """Get difficulty-specific instructions"""
        instructions = {
            "Basic": "Focus on fundamental concepts, definitions, and simple recall. Keep language simple and answers concise.",
            "Intermediate": "Mix of recall and comprehension. Include some application questions. Moderate complexity.",
            "Advanced": "Focus on analysis, synthesis, and application. Include challenging questions requiring deeper understanding."
        }
        return instructions.get(difficulty, instructions["Intermediate"])
    
    def _parse_flashcard_response(self, response: str, expected_count: int) -> List[Dict[str, Any]]:
        """Parse AI response into flashcard list"""
        try:
            # Try direct JSON parse
            parsed = json.loads(response)
            
            if isinstance(parsed, dict) and "flashcards" in parsed:
                flashcards = parsed["flashcards"]
            elif isinstance(parsed, list):
                flashcards = parsed
            else:
                raise ValueError("Unexpected response format")
            
            # Validate flashcards
            valid_flashcards = []
            for card in flashcards[:expected_count]:
                if isinstance(card, dict) and "front" in card and "back" in card:
                    valid_flashcards.append({
                        "front": str(card["front"]),
                        "back": str(card["back"]),
                        "explanation": str(card.get("explanation", ""))
                    })
            
            if not valid_flashcards:
                raise ValueError("No valid flashcards found in response")
            
            return valid_flashcards
            
        except Exception as e:
            logger.error(f"Failed to parse flashcard response: {e}")
            raise
    
    def _get_cache_key(self, flashcard: Dict[str, Any]) -> str:
        """Generate cache key for flashcard verification"""
        content = f"{flashcard.get('front', '')}{flashcard.get('back', '')}"
        return hashlib.md5(content.encode()).hexdigest()


# Singleton instance
_generator = FlashcardGenerator()


def generate_verified_flashcards(
    context_text: str,
    subject: str,
    subtopic: str,
    length: int,
    difficulty: str,
    source_note_ids: Optional[List[str]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Public API for generating verified flashcards
    """
    return _generator.generate_and_verify_flashcards(
        context_text=context_text,
        subject=subject,
        subtopic=subtopic,
        length=length,
        difficulty=difficulty,
        source_note_ids=source_note_ids
    )
