"""
Flashcard Chatbot API
Main API endpoint implementing the complete flashcard chatbot specification
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from app.core.auth import get_current_user, get_supabase_client
from app.services.session_manager import get_session_manager
from app.services.rag_service import get_rag_service
from app.services.flashcard_orchestrator import get_flashcard_orchestrator
from app.services.job_manager import get_job_manager
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str


class ButtonModel(BaseModel):
    text: str
    value: str


class ChatResponse(BaseModel):
    type: str  # "message", "generating", "success", "error", "upgrade_prompt"
    message: str
    buttons: List[ButtonModel] = []
    job_id: Optional[str] = None
    set_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    total_cards: int
    verified_cards: int
    failed_cards: int
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


# ============================================================================
# MAIN CHAT ENDPOINT
# ============================================================================

@router.post("/flashcards/chatbot", response_model=ChatResponse)
async def flashcard_chatbot(
    request: ChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Main flashcard chatbot endpoint
    
    Implements the complete specification:
    1. Intent classification and routing
    2. Parameter extraction and clarification
    3. Rate limiting and premium enforcement
    4. Async generation with verification
    5. Session state persistence
    """
    
    try:
        logger.info(f"Chatbot request from user {user_id}, session {request.session_id}")
        
        # Initialize services
        session_manager = get_session_manager(supabase)
        rag_service = get_rag_service(supabase)
        orchestrator = get_flashcard_orchestrator(session_manager, rag_service)
        job_manager = get_job_manager(supabase)
        
        # Get user profile
        try:
            profile_response = supabase.table("profiles").select(
                "is_premium, grade"
            ).eq("id", user_id).single().execute()
            user_profile = profile_response.data if profile_response.data else {}
        except:
            user_profile = {}
        
        # Process message through orchestrator
        result = await orchestrator.process_message(
            user_id=user_id,
            session_id=request.session_id,
            message=request.message,
            user_profile=user_profile
        )
        
        # If result is "generating", create and start job
        if result["type"] == "generating":
            params = result.get("generation_params", {})
            
            # Create job
            job_id = job_manager.create_job(user_id, params)
            
            # Start job in background
            job_manager.start_job(job_id)
            
            # Increment generation count
            session_manager.increment_generation_count(user_id)
            
            # Return response with job_id
            return ChatResponse(
                type="generating",
                message=result["message"],
                buttons=[],
                job_id=job_id
            )
        
        # Convert buttons to ButtonModel
        buttons = [
            ButtonModel(text=btn["text"], value=btn["value"])
            for btn in result.get("buttons", [])
        ]
        
        return ChatResponse(
            type=result["type"],
            message=result["message"],
            buttons=buttons,
            set_id=result.get("set_id")
        )
        
    except Exception as e:
        logger.error(f"Chatbot error: {e}", exc_info=True)
        return ChatResponse(
            type="error",
            message="Encountered error: INTERNAL_ERROR — An unexpected error occurred. Please try again.",
            buttons=[]
        )


# ============================================================================
# JOB STATUS ENDPOINT
# ============================================================================

@router.get("/flashcards/generate/status", response_model=JobStatusResponse)
async def get_generation_status(
    job_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get status of a flashcard generation job
    
    Frontend should poll this endpoint while job is running
    """
    
    try:
        job_manager = get_job_manager(supabase)
        job_status = job_manager.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Verify ownership
        if job_status["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        
        return JobStatusResponse(
            job_id=job_status["job_id"],
            status=job_status["status"],
            progress=job_status.get("progress", 0),
            total_cards=job_status.get("total_cards", 0),
            verified_cards=job_status.get("verified_cards", 0),
            failed_cards=job_status.get("failed_cards", 0),
            result=job_status.get("result"),
            error_message=job_status.get("error_message")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting job status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")


# ============================================================================
# REGENERATE FAILED CARDS ENDPOINT
# ============================================================================

@router.post("/flashcards/regenerate_failed")
async def regenerate_failed_cards(
    set_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Regenerate cards that failed verification
    """
    
    try:
        # Verify set ownership
        set_response = supabase.table("flashcard_sets").select(
            "id"
        ).eq("id", set_id).eq("user_id", user_id).execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        # Create regeneration job
        job_manager = get_job_manager(supabase)
        job_id = job_manager.regenerate_failed_cards(user_id, set_id)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": "Regenerating failed cards..."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error regenerating cards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CLEAR SESSION ENDPOINT
# ============================================================================

@router.delete("/flashcards/chatbot/session/{session_id}")
async def clear_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Clear conversation state for a session (start over)
    """
    
    try:
        session_manager = get_session_manager(supabase)
        session_manager.clear_session(user_id, session_id)
        
        return {
            "success": True,
            "message": "Session cleared"
        }
        
    except Exception as e:
        logger.error(f"Error clearing session: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear session")


# ============================================================================
# GET FLASHCARD SET ENDPOINT
# ============================================================================

@router.get("/flashcards/sets/{set_id}")
async def get_flashcard_set_with_cards(
    set_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get a flashcard set with its cards (for "Open deck" button)
    """
    
    try:
        # Get set
        set_response = supabase.table("flashcard_sets").select(
            "*"
        ).eq("id", set_id).eq("user_id", user_id).single().execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        # Get cards
        cards_response = supabase.table("flashcards").select(
            "*"
        ).eq("set_id", set_id).eq("user_id", user_id).order("position").execute()
        
        return {
            "set": set_response.data,
            "flashcards": cards_response.data or [],
            "count": len(cards_response.data) if cards_response.data else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting flashcard set: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# UPDATE SET TITLE ENDPOINT
# ============================================================================

@router.put("/flashcards/sets/{set_id}/title")
async def update_set_title(
    set_id: str,
    title: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Update flashcard set title (only field users can edit for AI-generated sets)
    """
    
    try:
        # Verify ownership
        set_response = supabase.table("flashcard_sets").select(
            "id"
        ).eq("id", set_id).eq("user_id", user_id).execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        # Update title
        update_response = supabase.table("flashcard_sets").update({
            "title": title
        }).eq("id", set_id).execute()
        
        return {
            "success": True,
            "set": update_response.data[0] if update_response.data else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating set title: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

@router.get("/flashcards/chatbot/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "status": "healthy",
        "service": "flashcard_chatbot",
        "version": "1.0.0",
        "features": [
            "intent_classification",
            "parameter_extraction",
            "rag_context_retrieval",
            "multi_model_verification",
            "session_persistence",
            "rate_limiting",
            "premium_enforcement"
        ]
    }
