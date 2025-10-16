"""
Flashcard Chat API - Conversational flashcard generation with loop prevention
Integrates with conversation manager and multi-model system
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime
from app.core.auth import get_current_user, get_supabase_client
from app.services.ai_chat_improved import (
    validate_request,
    retrieve_relevant_notes,
    process_chat_message
)
from app.services.conversation_manager import (
    get_conversation_state,
    save_conversation_state,
    clear_conversation_state
)
from app.services.flashcard_verification import generate_verified_flashcards
from app.services.model_manager import get_appropriate_model
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class FlashcardChatRequest(BaseModel):
    message: str
    session_id: str  # Frontend generates and maintains this
    chatbot_type: str = "flashcard_assistant"


class FlashcardChatResponse(BaseModel):
    type: str  # "message", "flashcards_generated", "error"
    message: str
    recommended_prompts: List[str] = []
    flashcards: Optional[List[Dict[str, Any]]] = None
    set_id: Optional[str] = None
    session_id: str


# ============================================================================
# MAIN CHAT ENDPOINT
# ============================================================================

@router.post("/flashcards/chat", response_model=FlashcardChatResponse)
async def flashcard_chat(
    request: FlashcardChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Conversational flashcard generation with loop prevention.
    
    Process:
    1. Validate request
    2. Get/create conversation state
    3. Process message with context tracking
    4. Either clarify or generate flashcards
    5. Return response with contextual prompts
    """
    
    try:
        logger.info(f"Flashcard chat request from user {user_id}, session {request.session_id}")
        
        # ========================================================================
        # STEP 1: Validate Request
        # ========================================================================
        validation = await validate_request(request.message, request.chatbot_type)
        
        if not validation["valid"]:
            logger.warning(f"Invalid request: {validation['reason']}")
            return FlashcardChatResponse(
                type="message",
                message=validation["suggested_response"],
                recommended_prompts=[
                    "Create flashcards from my notes",
                    "Generate study materials",
                    "Help me prepare for exams"
                ],
                session_id=request.session_id
            )
        
        # ========================================================================
        # STEP 2: Get Conversation State
        # ========================================================================
        conversation_state = get_conversation_state(
            user_id=user_id,
            session_id=request.session_id
        )
        
        logger.info(f"Conversation state: turn {conversation_state.turns_count}, subject={conversation_state.subject}")
        
        # ========================================================================
        # STEP 3: Retrieve Relevant Notes
        # ========================================================================
        relevant_notes = await retrieve_relevant_notes(
            user_id=user_id,
            query=request.message,
            supabase=supabase,
            subject_filter=conversation_state.subject,
            top_k=10
        )
        
        logger.info(f"Retrieved {len(relevant_notes)} relevant notes")
        
        # ========================================================================
        # STEP 4: Process Message
        # ========================================================================
        result = await process_chat_message(
            user_message=request.message,
            conversation_state=conversation_state,
            user_notes=relevant_notes
        )
        
        # ========================================================================
        # STEP 5: Handle Action
        # ========================================================================
        
        if result["action"] == "generate_flashcards":
            # Generate flashcards with verification
            logger.info(f"Generating flashcards: subject={conversation_state.subject}, quantity={conversation_state.quantity}")
            
            # Return immediate response
            yield_response = FlashcardChatResponse(
                type="message",
                message=result["message"],
                recommended_prompts=[],
                session_id=request.session_id
            )
            
            # Generate flashcards (this takes time)
            try:
                flashcards = await generate_verified_flashcards(
                    subject=conversation_state.subject or "general study",
                    user_notes=relevant_notes,
                    quantity=conversation_state.quantity or 10,
                    user_id=user_id
                )
                
                logger.info(f"Generated {len(flashcards)} flashcards")
                
                # Save to database
                flashcard_set_id = await save_flashcard_set_to_db(
                    user_id=user_id,
                    subject=conversation_state.subject,
                    flashcards=flashcards,
                    supabase=supabase
                )
                
                # Track in conversation state
                conversation_state.generated_sets.append({
                    "subject": conversation_state.subject,
                    "set_id": flashcard_set_id,
                    "count": len(flashcards),
                    "timestamp": datetime.now().isoformat()
                })
                
                # Reset state for potential next set
                conversation_state.reset_for_new_set()
                save_conversation_state(conversation_state)
                
                # Return completed flashcards
                return FlashcardChatResponse(
                    type="flashcards_generated",
                    message=f"Your {len(flashcards)} flashcards are ready! I've verified each one for accuracy.",
                    flashcards=flashcards,
                    set_id=flashcard_set_id,
                    recommended_prompts=[
                        "Create another set for a different subject",
                        "Generate more flashcards",
                        "Make a quiz from these"
                    ],
                    session_id=request.session_id
                )
                
            except Exception as e:
                logger.error(f"Error generating flashcards: {str(e)}", exc_info=True)
                return FlashcardChatResponse(
                    type="error",
                    message="I encountered an issue generating your flashcards. Please try again or contact support if this persists.",
                    recommended_prompts=[
                        "Try again",
                        "Create different flashcards",
                        "Contact support"
                    ],
                    session_id=request.session_id
                )
        
        else:
            # Clarification needed
            return FlashcardChatResponse(
                type="message",
                message=result["message"],
                recommended_prompts=result["recommended_prompts"],
                session_id=request.session_id
            )
    
    except Exception as e:
        logger.error(f"Flashcard chat error: {str(e)}", exc_info=True)
        return FlashcardChatResponse(
            type="error",
            message="I encountered an unexpected error. Please try again.",
            recommended_prompts=["Try again", "Start over"],
            session_id=request.session_id
        )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def save_flashcard_set_to_db(
    user_id: str,
    subject: Optional[str],
    flashcards: List[Dict[str, Any]],
    supabase
) -> str:
    """
    Save generated flashcard set to database.
    
    Returns:
        Flashcard set ID
    """
    
    try:
        # Create flashcard set
        set_id = str(uuid.uuid4())
        set_title = f"{subject or 'Study'} Flashcards - {datetime.now().strftime('%b %d, %Y')}"
        
        set_data = {
            "id": set_id,
            "user_id": user_id,
            "title": set_title,
            "description": f"AI-generated flashcards for {subject or 'general study'}",
            "total_cards": len(flashcards),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        
        # Insert flashcard set
        supabase.table("flashcard_sets").insert(set_data).execute()
        
        logger.info(f"Created flashcard set: {set_id}")
        
        # Insert individual flashcards
        flashcard_records = []
        for i, card in enumerate(flashcards):
            flashcard_records.append({
                "id": str(uuid.uuid4()),
                "set_id": set_id,
                "user_id": user_id,
                "front": card["front"],
                "back": card["back"],
                "position": i + 1,
                "mastery_level": 0,
                "times_reviewed": 0,
                "times_correct": 0,
                "times_incorrect": 0,
                "verified": card.get("verified", False),
                "confidence_score": card.get("confidence_score", 0.8),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            })
        
        # Batch insert flashcards
        if flashcard_records:
            supabase.table("flashcards").insert(flashcard_records).execute()
            logger.info(f"Inserted {len(flashcard_records)} flashcards")
        
        return set_id
        
    except Exception as e:
        logger.error(f"Error saving flashcard set: {str(e)}", exc_info=True)
        raise


# ============================================================================
# SESSION MANAGEMENT ENDPOINTS
# ============================================================================

@router.delete("/flashcards/chat/session/{session_id}")
async def clear_chat_session(
    session_id: str,
    user_id: str = Depends(get_current_user)
):
    """Clear conversation state for a session (start over)."""
    try:
        clear_conversation_state(user_id, session_id)
        logger.info(f"Cleared session {session_id} for user {user_id}")
        return {"success": True, "message": "Session cleared"}
    except Exception as e:
        logger.error(f"Error clearing session: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to clear session")


@router.get("/flashcards/chat/health")
async def health_check():
    """Check if flashcard chat service is operational."""
    return {
        "status": "healthy",
        "service": "flashcard_chat",
        "version": "2.0.0",
        "features": [
            "loop_prevention",
            "multi_model_optimization",
            "per_card_verification",
            "context_aware_prompts"
        ]
    }
