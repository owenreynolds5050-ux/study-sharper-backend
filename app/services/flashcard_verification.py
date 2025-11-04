"""
Quality verification system for AI-generated flashcards.
Checks: Accuracy, Truth, Relevance, Appropriateness
"""

from typing import List, Dict
from app.services.open_router import get_chat_completion, VERIFICATION_MODEL

import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class FlashcardVerifier:
    """Verifies flashcard quality using LLM evaluation."""
    
    def __init__(self):
        self.model = VERIFICATION_MODEL

        self.thresholds = {
            "accuracy": 0.7,
            "truth": 0.8,
            "relevance": 0.7,
            "appropriateness": 0.75
        }
        self.overall_threshold = 0.73
    
    async def verify_flashcard(
        self,
        front: str,
        back: str,
        explanation: str,
        source_text: str = "",
        difficulty: str = "medium"
    ) -> Dict:
        """
        Verify a single flashcard.
        
        Returns:
        {
            "accuracy_score": 0.85,
            "truth_score": 0.90,
            "relevance_score": 0.80,
            "appropriateness_score": 0.88,
            "overall_score": 0.86,
            "passed": true/false,
            "issues": ["issue1", "issue2"],
            "suggestions": "Optional improvement suggestions"
        }
        """
        
        prompt = f"""You are an expert educator evaluating the quality of a flashcard.

FLASHCARD TO VERIFY:
Front (Question): {front}
Back (Answer): {back}
Explanation: {explanation}
{"Source Material: " + source_text[:500] if source_text else ""}

EVALUATION CRITERIA:

1. ACCURACY (0-1): Is the answer factually correct? Does it accurately answer the question?
2. TRUTH (0-1): Is the information truthful and not misleading?
3. RELEVANCE (0-1): Is the question/answer pair relevant to learning? Does it test meaningful knowledge?
4. APPROPRIATENESS (0-1): Is the content appropriate for a student at {difficulty} level?

Respond in this exact JSON format:
{{
    "accuracy_score": 0.0,
    "truth_score": 0.0,
    "relevance_score": 0.0,
    "appropriateness_score": 0.0,
    "issues": [],
    "suggestions": ""
}}

Be strict but fair. A score of 0.7+ is good. Only respond with valid JSON, no other text."""
        
        try:
            response = get_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                model=self.model,
                temperature=0.3,
                max_tokens=500  # Increased to allow more detailed Grok responses
            )
            
            # Parse JSON response
            result = json.loads(response)
            
            # Calculate overall score (weighted average)
            overall = (
                result["accuracy_score"] * 0.35 +
                result["truth_score"] * 0.35 +
                result["relevance_score"] * 0.20 +
                result["appropriateness_score"] * 0.10
            )
            result["overall_score"] = round(overall, 2)
            
            # Determine pass/fail
            result["passed"] = (
                result["accuracy_score"] >= self.thresholds["accuracy"] and
                result["truth_score"] >= self.thresholds["truth"] and
                result["relevance_score"] >= self.thresholds["relevance"] and
                result["appropriateness_score"] >= self.thresholds["appropriateness"] and
                overall >= self.overall_threshold
            )
            
            return result
            
        except json.JSONDecodeError:
            logger.error("Failed to parse verification response")
            return {
                "accuracy_score": 0,
                "truth_score": 0,
                "relevance_score": 0,
                "appropriateness_score": 0,
                "overall_score": 0,
                "passed": False,
                "issues": ["Verification system error"],
                "suggestions": ""
            }
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return {
                "accuracy_score": 0,
                "truth_score": 0,
                "relevance_score": 0,
                "appropriateness_score": 0,
                "overall_score": 0,
                "passed": False,
                "issues": [f"Verification failed: {str(e)}"],
                "suggestions": ""
            }
    
    async def verify_batch(
        self,
        flashcards: List[Dict],
        source_text: str = "",
        difficulty: str = "medium"
    ) -> List[Dict]:
        """Verify multiple flashcards."""
        results = []
        for card in flashcards:
            result = await self.verify_flashcard(
                front=card["front"],
                back=card["back"],
                explanation=card.get("explanation", ""),
                source_text=source_text,
                difficulty=difficulty
            )
            results.append(result)
        return results

# Singleton instance
verifier = FlashcardVerifier()