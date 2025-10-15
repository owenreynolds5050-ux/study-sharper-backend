"""
Unified AI Chat API - Handles all chatbot interactions
Supports: Flashcard Assistant, Quiz Generator, Summary Creator, etc.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core.auth import get_current_user, get_supabase_client
from app.services.ai_chat import (
    validate_request,
    retrieve_relevant_notes,
    analyze_user_intent,
    generate_recommended_prompts,
    generate_ai_response
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ConversationMessage(BaseModel):
    role: str  # "user" or "assistant"
    message: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    prompt: str
    chatbot_type: str  # "flashcard_assistant", "quiz_generator", "summary_creator", etc.
    conversation_history: Optional[List[ConversationMessage]] = []
    subject_filter: Optional[str] = None  # Optional subject to focus on


class ChatResponse(BaseModel):
    message: str  # Natural language response ONLY
    recommended_prompts: List[str]
    action_taken: str  # "response_provided", "needs_clarification", "content_generated", etc.
    generated_content: Optional[Dict[str, Any]] = None  # Actual flashcards/quiz if generated
    sources: Optional[List[Dict[str, str]]] = None  # Note sources used


# ============================================================================
# MAIN AI CHAT ENDPOINT
# ============================================================================

@router.post("/ai/chat", response_model=ChatResponse)
async def ai_chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Main AI chat endpoint - handles all chatbot interactions.
    
    Process:
    1. Validate request (content moderation, capability check)
    2. Retrieve relevant notes via RAG
    3. Analyze user intent and detect subject
    4. Handle content mismatch scenarios
    5. Generate AI response with context
    6. Return natural language response with recommendations
    """
    
    try:
        # ========================================================================
        # STEP 1: Validate Request
        # ========================================================================
        validation = await validate_request(request.prompt, request.chatbot_type)
        
        if not validation["valid"]:
            logger.warning(f"Invalid request: {validation['reason']} - User: {user_id}")
            
            # Get user's notes for recommendations
            user_notes_response = supabase.table("notes").select(
                "id, title, subject"
            ).eq("user_id", user_id).limit(10).execute()
            
            return ChatResponse(
                message=validation["suggested_response"],
                recommended_prompts=await generate_recommended_prompts(
                    user_notes=user_notes_response.data or [],
                    current_context="validation_failed",
                    chatbot_type=request.chatbot_type
                ),
                action_taken="validation_failed",
                generated_content=None,
                sources=None
            )
        
        # ========================================================================
        # STEP 2: Retrieve Relevant Notes via RAG
        # ========================================================================
        relevant_notes = await retrieve_relevant_notes(
            user_id=user_id,
            query=request.prompt,
            supabase=supabase,
            subject_filter=request.subject_filter,
            top_k=10
        )
        
        logger.info(f"Retrieved {len(relevant_notes)} relevant notes for user {user_id}")
        
        # ========================================================================
        # STEP 3: Analyze User Intent
        # ========================================================================
        intent_analysis = await analyze_user_intent(
            prompt=request.prompt,
            available_notes=relevant_notes,
            chatbot_type=request.chatbot_type
        )
        
        logger.info(f"Intent analysis: {intent_analysis['intent']}, Subject: {intent_analysis.get('requested_subject')}, Confidence: {intent_analysis.get('confidence')}")
        
        # ========================================================================
        # STEP 4: Handle Content Mismatch Scenarios
        # ========================================================================
        
        # Case 1: User requested specific subject but we don't have matching notes
        if (intent_analysis.get("requested_subject") and 
            not intent_analysis.get("has_matching_content") and
            intent_analysis.get("confidence", 0) > 0.6):
            
            requested_subject = intent_analysis["requested_subject"]
            available_subjects = intent_analysis.get("available_subjects", [])
            
            if not relevant_notes:
                # No notes at all
                message = f"I don't see any notes uploaded yet. I can create generic {requested_subject} study materials, but they'll be much more personalized and helpful once you upload your class notes. Would you like to proceed with generic content?"
            else:
                # Have notes but different subject
                available_str = ", ".join(available_subjects[:3])
                if len(available_subjects) > 3:
                    available_str += f", and {len(available_subjects) - 3} more"
                
                message = f"I couldn't find {requested_subject} notes in your collection. Would you like me to create generic {requested_subject} materials, or use your available notes on {available_str}?"
            
            return ChatResponse(
                message=message,
                recommended_prompts=await generate_recommended_prompts(
                    user_notes=relevant_notes,
                    current_context="subject_mismatch",
                    chatbot_type=request.chatbot_type
                ),
                action_taken="awaiting_clarification",
                generated_content=None,
                sources=[{"id": n["id"], "title": n.get("title", "Untitled")} for n in relevant_notes[:5]]
            )
        
        # Case 2: Ambiguous request - needs clarification
        if intent_analysis.get("needs_clarification") and intent_analysis.get("confidence", 0) < 0.5:
            available_subjects = intent_analysis.get("available_subjects", [])
            
            if available_subjects:
                subjects_str = ", ".join(available_subjects[:4])
                message = f"I'd be happy to help! Which subject would you like to focus on? You have notes on: {subjects_str}."
            else:
                message = "I'd love to help you create study materials! Could you tell me which subject or topic you'd like to focus on?"
            
            return ChatResponse(
                message=message,
                recommended_prompts=await generate_recommended_prompts(
                    user_notes=relevant_notes,
                    current_context="needs_clarification",
                    chatbot_type=request.chatbot_type
                ),
                action_taken="awaiting_clarification",
                generated_content=None,
                sources=None
            )
        
        # ========================================================================
        # STEP 5: Generate AI Response with Context
        # ========================================================================
        ai_context = {
            "relevant_notes": relevant_notes,
            "user_intent": intent_analysis,
            "conversation_history": [msg.dict() for msg in request.conversation_history],
            "chatbot_type": request.chatbot_type
        }
        
        ai_response = await generate_ai_response(
            prompt=request.prompt,
            context=ai_context,
            chatbot_type=request.chatbot_type
        )
        
        # ========================================================================
        # STEP 6: Generate Recommended Prompts
        # ========================================================================
        recommended_prompts = await generate_recommended_prompts(
            user_notes=relevant_notes,
            current_context=request.prompt,
            chatbot_type=request.chatbot_type
        )
        
        # ========================================================================
        # STEP 7: Format and Return Response
        # ========================================================================
        return ChatResponse(
            message=ai_response["natural_text"],
            recommended_prompts=recommended_prompts,
            action_taken=ai_response["action"],
            generated_content=ai_response.get("generated_content"),
            sources=[{"id": n["id"], "title": n.get("title", "Untitled")} for n in relevant_notes[:5]] if relevant_notes else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in AI chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while processing your request. Please try again."
        )


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/ai/chat/health")
async def health_check():
    """Check if AI chat service is operational."""
    return {
        "status": "healthy",
        "service": "ai_chat",
        "version": "1.0.0"
    }
