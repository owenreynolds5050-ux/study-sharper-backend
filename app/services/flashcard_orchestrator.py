"""
Flashcard Chat Orchestrator
Main logic coordinating intent classification, parameter extraction, and generation
"""

from typing import Dict, Any, List, Optional, Tuple
from app.services.intent_classifier import classify_intent, extract_flashcard_parameters
from app.services.session_manager import ConversationState, SessionManager
from app.services.rag_service import RAGService
from app.services.flashcard_generator import generate_verified_flashcards
import logging

logger = logging.getLogger(__name__)

# Exact message templates from spec
NON_STUDY_MESSAGE = "Unable to fulfill request: this assistant only handles study-related tasks (flashcards, notes, account-related study settings)."
GENERATION_START_TEMPLATE = "Generating {length} {difficulty} flashcards on {subtopic} ({subject}) — saving to your study deck. I'll verify accuracy now."
GENERATION_SUCCESS_TEMPLATE = "Done — {n} cards saved to '{title}'. Open deck?"
GENERATION_PARTIAL_TEMPLATE = "Done — {n} cards saved to '{title}'. {m} cards failed verification and were not saved. Open deck?"
LIMIT_EXCEEDED_FREE_TEMPLATE = "Your plan allows up to 20 cards. Want me to generate 20 cards instead, or upgrade to Premium to generate 50?"
VERIFICATION_ABORT_TEMPLATE = "Unable to generate verified flashcards for this request. Error: verification failed for {X} of {Y} cards."


class FlashcardOrchestrator:
    """Orchestrates the flashcard generation conversation flow"""
    
    MAX_CLARIFICATIONS = 4
    FREE_TIER_MAX = 20
    PREMIUM_MAX = 50
    DEFAULT_LENGTH = 10
    
    def __init__(self, session_manager: SessionManager, rag_service: RAGService):
        self.session_manager = session_manager
        self.rag_service = rag_service
    
    async def process_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing user messages
        
        Returns:
            Dict with:
            - type: "message" | "generating" | "success" | "error" | "upgrade_prompt"
            - message: str
            - buttons: List[Dict] (optional)
            - set_id: str (optional, for success)
            - flashcards: List[Dict] (optional, for success)
        """
        
        # Save user message
        self.session_manager.save_user_message(user_id, session_id, message)
        
        # Get or create session state
        state = self.session_manager.get_or_create_session(user_id, session_id)
        state.last_message = message
        
        # Step 1: Classify intent
        intent_result = classify_intent(message, context=state.to_dict())
        intent = intent_result["intent"]
        
        logger.info(f"Classified intent: {intent}")
        
        # Route based on intent
        if intent == "non_study":
            response = self._handle_non_study()
        elif intent == "flashcards":
            response = await self._handle_flashcards(user_id, session_id, message, state, user_profile)
        elif intent == "notes":
            response = self._handle_notes()
        elif intent == "account":
            response = self._handle_account()
        else:  # other_study
            response = self._handle_other_study()
        
        # Save assistant response
        self.session_manager.save_session(state, response["message"])
        
        return response
    
    def _handle_non_study(self) -> Dict[str, Any]:
        """Handle non-study related requests"""
        return {
            "type": "message",
            "message": NON_STUDY_MESSAGE,
            "buttons": []
        }
    
    async def _handle_flashcards(
        self,
        user_id: str,
        session_id: str,
        message: str,
        state: ConversationState,
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Handle flashcard generation requests"""
        
        # Extract parameters from message
        extracted = extract_flashcard_parameters(message, context=state.to_dict())
        
        # Update state with extracted parameters
        for param, value in extracted.items():
            if value is not None:
                state.update_param(param, value)
        
        # Check if we have all required parameters
        missing = state.get_missing_params()
        
        if missing:
            # Need clarification
            return await self._handle_missing_params(user_id, state, missing)
        
        # All parameters present - check limits and generate
        return await self._generate_flashcards(user_id, session_id, state, user_profile)
    
    async def _handle_missing_params(
        self,
        user_id: str,
        state: ConversationState,
        missing: List[str]
    ) -> Dict[str, Any]:
        """Handle missing parameters with clarifying questions"""
        
        # Check clarification limit
        if state.clarification_count >= self.MAX_CLARIFICATIONS:
            return {
                "type": "error",
                "message": "I can't proceed without subject and subtopic.",
                "buttons": []
            }
        
        state.clarification_count += 1
        
        # Handle missing parameters in order of priority
        if "length" in missing:
            # Auto-fill with default
            state.length = self.DEFAULT_LENGTH
            missing.remove("length")
        
        if "difficulty" in missing:
            # Infer from grade or default to Intermediate
            state.difficulty = self._infer_difficulty(user_id)
            missing.remove("difficulty")
        
        if "subtopic" in missing and state.subject:
            # Ask for subtopic with suggestions
            suggestions = self._get_subtopic_suggestions(state.subject)
            return {
                "type": "message",
                "message": f"Is there any specific {state.subject} topic you want flashcards for?",
                "buttons": [
                    {"text": suggestion, "value": suggestion}
                    for suggestion in suggestions
                ] + [
                    {"text": "Other", "value": "other"},
                    {"text": "No preference / general", "value": "general"}
                ]
            }
        
        if "subject" in missing or "subtopic" in missing:
            # Try to infer from notes
            notes = await self.rag_service.retrieve_relevant_notes(
                user_id=user_id,
                query=state.last_message or "",
                top_k=5
            )
            
            if notes:
                inferred_subject = self.rag_service.infer_subject_from_notes(notes)
                if inferred_subject:
                    state.subject = inferred_subject
                    missing = [m for m in missing if m != "subject"]
            
            if "subject" in missing:
                # Ask for subject
                return {
                    "type": "message",
                    "message": "What subject and topic do you want flashcards for?",
                    "buttons": [
                        {"text": "Biology", "value": "Biology"},
                        {"text": "Chemistry", "value": "Chemistry"},
                        {"text": "History", "value": "History"},
                        {"text": "Math", "value": "Math"},
                        {"text": "Physics", "value": "Physics"},
                        {"text": "Other", "value": "other"}
                    ]
                }
        
        # If we've filled in missing params, try again
        if not state.get_missing_params():
            return await self._generate_flashcards(user_id, "", state, None)
        
        return {
            "type": "message",
            "message": "I need more information to generate flashcards. What subject and topic?",
            "buttons": []
        }
    
    async def _generate_flashcards(
        self,
        user_id: str,
        session_id: str,
        state: ConversationState,
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate flashcards with all parameters present"""
        
        # Check rate limit
        is_premium = user_profile.get("is_premium", False) if user_profile else False
        rate_limit = self.session_manager.check_rate_limit(user_id, is_premium)
        
        if not rate_limit["allowed"]:
            return {
                "type": "error",
                "message": f"You've reached your daily limit of {rate_limit['limit']} flashcard sets. Please try again tomorrow.",
                "buttons": []
            }
        
        # Check length limits
        requested_length = state.length or self.DEFAULT_LENGTH
        max_allowed = self.PREMIUM_MAX if is_premium else self.FREE_TIER_MAX
        
        if requested_length > max_allowed:
            if not is_premium:
                # Free user requesting > 20
                return {
                    "type": "upgrade_prompt",
                    "message": LIMIT_EXCEEDED_FREE_TEMPLATE,
                    "buttons": [
                        {"text": "Generate 20 cards", "value": "generate_20"},
                        {"text": "Upgrade to Premium", "value": "upgrade"}
                    ]
                }
            else:
                # Premium user requesting > 50
                return {
                    "type": "message",
                    "message": f"Premium allows up to 50 cards. Want me to generate 50 instead?",
                    "buttons": [
                        {"text": "Generate 50 cards", "value": "generate_50"}
                    ]
                }
        
        # Retrieve notes if requested
        notes = []
        if state.from_notes:
            notes = await self.rag_service.retrieve_relevant_notes(
                user_id=user_id,
                query=f"{state.subject} {state.subtopic}",
                subject_filter=state.subject,
                top_k=10
            )
        
        if not notes:
            # No notes found or not requested - use general knowledge
            context_text = f"Generate flashcards about {state.subtopic} in {state.subject}."
        else:
            # Combine notes content
            context_text = self.rag_service.combine_notes_content(notes, max_length=6000)
        
        # Return immediate "generating" response
        generation_message = GENERATION_START_TEMPLATE.format(
            length=requested_length,
            difficulty=state.difficulty,
            subtopic=state.subtopic,
            subject=state.subject
        )
        
        # Note: In a real async system, this would start a background job
        # For now, we'll generate synchronously but the API will handle async
        
        return {
            "type": "generating",
            "message": generation_message,
            "buttons": [],
            "generation_params": {
                "context_text": context_text,
                "subject": state.subject,
                "subtopic": state.subtopic,
                "length": requested_length,
                "difficulty": state.difficulty,
                "source_note_ids": [note["id"] for note in notes] if notes else []
            }
        }
    
    def _handle_notes(self) -> Dict[str, Any]:
        """Handle notes/summary requests (placeholder)"""
        return {
            "type": "message",
            "message": "Notes generation feature is coming soon! For now, I can help you create flashcards from your notes.",
            "buttons": [
                {"text": "Create flashcards", "value": "create_flashcards"}
            ]
        }
    
    def _handle_account(self) -> Dict[str, Any]:
        """Handle account settings requests (placeholder)"""
        return {
            "type": "message",
            "message": "For account settings, please visit your account page.",
            "buttons": [
                {"text": "Go to Account", "value": "account_page"}
            ]
        }
    
    def _handle_other_study(self) -> Dict[str, Any]:
        """Handle other study-related requests"""
        return {
            "type": "message",
            "message": "I can't do this yet — this feature is not implemented. I can help you create flashcards!",
            "buttons": [
                {"text": "Create flashcards", "value": "create_flashcards"}
            ]
        }
    
    def _infer_difficulty(self, user_id: str) -> str:
        """Infer difficulty from user grade or default to Intermediate"""
        try:
            response = self.session_manager.supabase.table("profiles").select(
                "grade"
            ).eq("id", user_id).single().execute()
            
            if response.data and response.data.get("grade"):
                grade = response.data["grade"]
                
                # Map grade to difficulty
                if grade in ["6", "7", "8", "9"]:
                    return "Basic"
                elif grade in ["10", "11"]:
                    return "Intermediate"
                elif grade in ["12", "College", "University"]:
                    return "Advanced"
            
        except Exception as e:
            logger.error(f"Error inferring difficulty: {e}")
        
        return "Intermediate"
    
    def _get_subtopic_suggestions(self, subject: str) -> List[str]:
        """Get popular subtopic suggestions for a subject"""
        suggestions_map = {
            "Biology": ["Cell Structure", "Genetics", "Evolution", "Ecology"],
            "Chemistry": ["Atomic Structure", "Chemical Bonds", "Reactions", "Organic Chemistry"],
            "Physics": ["Motion", "Forces", "Energy", "Electricity"],
            "History": ["American Revolution", "World War II", "Ancient Rome", "Renaissance"],
            "Math": ["Algebra", "Geometry", "Calculus", "Statistics"],
            "English": ["Shakespeare", "Poetry", "Grammar", "Literary Analysis"]
        }
        
        return suggestions_map.get(subject, ["General Topics"])


def get_flashcard_orchestrator(session_manager: SessionManager, rag_service: RAGService) -> FlashcardOrchestrator:
    """Factory function to create FlashcardOrchestrator"""
    return FlashcardOrchestrator(session_manager, rag_service)
