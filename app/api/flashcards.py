"""
Flashcard API Endpoints
Handles flashcard generation, CRUD operations, and spaced repetition reviews
"""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.auth import get_current_user, get_supabase_client
from app.core.database import supabase
from app.services.flashcards import (
    generate_flashcards_from_text,
    generate_flashcards_from_file,
    calculate_next_review_interval,
    update_mastery_level
)
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/flashcards/health")
async def flashcards_health_check():
    """Health check endpoint for flashcards API"""
    return {
        "status": "healthy",
        "service": "flashcards",
        "version": "1.0.0"
    }


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class GenerateFlashcardsRequest(BaseModel):
    note_ids: List[str]
    num_cards: int = 10
    difficulty: str = "medium"  # easy, medium, hard
    set_title: Optional[str] = None
    set_description: Optional[str] = None


class GenerateFromFileRequest(BaseModel):
    file_id: str
    num_cards: int = 10
    difficulty: str = "medium"  # easy, medium, hard


class FlashcardResponse(BaseModel):
    id: str
    set_id: str
    front: str
    back: str
    explanation: Optional[str] = None
    position: int
    mastery_level: int
    times_reviewed: int
    times_correct: int
    times_incorrect: int
    last_reviewed_at: Optional[str] = None
    next_review_at: Optional[str] = None
    source_note_id: Optional[str] = None
    created_at: str
    updated_at: str


class FlashcardSetResponse(BaseModel):
    id: str
    user_id: str
    title: str
    description: Optional[str] = None
    source_note_ids: List[str]
    total_cards: int
    mastered_cards: int
    created_at: str
    updated_at: str


class ReviewFlashcardRequest(BaseModel):
    was_correct: bool
    confidence_rating: Optional[int] = None  # 1-5
    time_spent_seconds: Optional[int] = None


class CreateFlashcardRequest(BaseModel):
    set_id: str
    front: str
    back: str
    explanation: Optional[str] = None


class UpdateFlashcardRequest(BaseModel):
    front: Optional[str] = None
    back: Optional[str] = None
    explanation: Optional[str] = None


class CreateFlashcardSetRequest(BaseModel):
    title: str
    description: Optional[str] = None


class AIChatRequest(BaseModel):
    message: str
    context: Optional[dict] = None


class AcceptSuggestionRequest(BaseModel):
    set_id: str
    accept: bool


# ============================================================================
# FLASHCARD GENERATION
# ============================================================================

@router.post("/flashcards/generate")
async def generate_flashcards(
    request: GenerateFlashcardsRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Generate AI-powered flashcards from one or more notes.
    """
    try:
        # Validate difficulty
        if request.difficulty not in ["easy", "medium", "hard"]:
            raise HTTPException(status_code=400, detail="Invalid difficulty level")
        
        # Fetch files content
        notes_response = supabase.table("files").select(
            "id, title, content, extracted_text"
        ).in_("id", request.note_ids).eq("user_id", user_id).execute()
        
        if not notes_response.data:
            raise HTTPException(status_code=404, detail="No files found")
        
        # Combine note content
        combined_text = []
        note_titles = []
        
        for note in notes_response.data:
            note_titles.append(note.get("title", "Untitled"))
            content = note.get("content") or note.get("extracted_text") or ""
            if content:
                combined_text.append(f"## {note['title']}\n\n{content}")
        
        full_text = "\n\n".join(combined_text)
        
        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Notes have no content")
        
        # Truncate if too long (max 8000 chars for AI processing)
        if len(full_text) > 8000:
            full_text = full_text[:8000] + "\n\n[Content truncated...]"
        
        # Generate flashcards using AI
        flashcards = generate_flashcards_from_text(
            text=full_text,
            note_title=" & ".join(note_titles[:3]),  # First 3 titles
            num_cards=request.num_cards,
            difficulty=request.difficulty
        )
        
        # Create flashcard set
        set_title = request.set_title or f"Flashcards: {' & '.join(note_titles[:2])}"
        if len(note_titles) > 2:
            set_title += f" (+{len(note_titles) - 2} more)"
        
        set_data = {
            "user_id": user_id,
            "title": set_title[:200],  # Limit length
            "description": request.set_description,
            "source_note_ids": request.note_ids
        }
        
        set_response = supabase.table("flashcard_sets").insert(set_data).execute()
        
        if not set_response.data:
            raise HTTPException(status_code=500, detail="Failed to create flashcard set")
        
        flashcard_set = set_response.data[0]
        set_id = flashcard_set["id"]
        
        # Insert flashcards
        flashcard_records = []
        for i, card in enumerate(flashcards):
            flashcard_records.append({
                "user_id": user_id,
                "set_id": set_id,
                "front": card["front"],
                "back": card["back"],
                "explanation": card.get("explanation", ""),
                "position": i,
                "source_note_id": request.note_ids[0] if len(request.note_ids) == 1 else None
            })
        
        cards_response = supabase.table("flashcards").insert(flashcard_records).execute()
        
        if not cards_response.data:
            raise HTTPException(status_code=500, detail="Failed to create flashcards")
        
        return {
            "success": True,
            "set": flashcard_set,
            "flashcards": cards_response.data,
            "count": len(cards_response.data)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate flashcards: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate flashcards: {str(e)}")


@router.post("/flashcards/suggest")
async def generate_suggested_flashcards(
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Auto-generate suggested flashcard sets from recent notes.
    Called after note upload or on daily refresh.
    """
    try:
        from app.services.flashcards import generate_suggested_flashcards_for_user
        
        suggestions = await generate_suggested_flashcards_for_user(user_id, supabase)
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Failed to generate suggestions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {str(e)}")


@router.post("/flashcards/chat")
async def flashcard_ai_chat(
    request: AIChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    AI chatbot for flashcard generation with natural language prompts.
    Uses RAG to find relevant notes and generate flashcards.
    """
    try:
        from app.services.flashcards import process_flashcard_chat_request
        
        response = await process_flashcard_chat_request(
            user_id=user_id,
            message=request.message,
            context=request.context,
            supabase=supabase
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Chat request failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat request failed: {str(e)}")


# ============================================================================
# FLASHCARD SETS - CRUD
# ============================================================================

@router.post("/flashcards/sets/create")
async def create_blank_flashcard_set(
    request: CreateFlashcardSetRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Create a blank flashcard set for manual card creation."""
    try:
        set_data = {
            "user_id": user_id,
            "title": request.title,
            "description": request.description,
            "source_note_ids": [],
            "ai_generated": False,
            "is_suggested": False
        }
        
        response = supabase.table("flashcard_sets").insert(set_data).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create flashcard set")
        
        return {
            "success": True,
            "set": response.data[0]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create set: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to create set: {str(e)}")


@router.post("/flashcards/suggestions/{set_id}/accept")
async def accept_or_reject_suggestion(
    set_id: str,
    request: AcceptSuggestionRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Accept or reject a suggested flashcard set."""
    try:
        # Verify ownership
        set_response = supabase.table("flashcard_sets").select("*").eq(
            "id", set_id
        ).eq("user_id", user_id).eq("is_suggested", True).execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Suggested set not found")
        
        # Update acceptance status
        update_data = {"is_accepted": request.accept}
        
        if not request.accept:
            # If rejected, mark for deletion or hide
            update_data["is_accepted"] = False
        
        supabase.table("flashcard_sets").update(update_data).eq("id", set_id).execute()
        
        return {
            "success": True,
            "accepted": request.accept
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/sets", response_model=List[FlashcardSetResponse])
async def get_flashcard_sets(
    response: Response,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get all flashcard sets for the current user."""
    try:
        # Set cache control headers to prevent browser/server caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        data = supabase.table("flashcard_sets").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).execute()
        
        return data.data
    except Exception as e:
        logger.error(f"Failed to get flashcard sets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get flashcard sets: {str(e)}")


@router.get("/flashcards/suggestions")
async def get_suggested_flashcard_sets(
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get suggested flashcard sets for the current user."""
    try:
        response = supabase.rpc("get_suggested_flashcard_sets", {
            "p_user_id": user_id
        }).execute()
        
        return {
            "success": True,
            "suggestions": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        logger.error(f"Failed to get suggested flashcard sets: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get suggested flashcard sets: {str(e)}")


@router.get("/flashcards/sets/{set_id}")
async def get_flashcard_set(
    set_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get a specific flashcard set with its cards."""
    try:
        # Get set
        set_response = supabase.table("flashcard_sets").select("*").eq(
            "id", set_id
        ).eq("user_id", user_id).single().execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        # Get cards in the set
        cards_response = supabase.table("flashcards").select("*").eq(
            "set_id", set_id
        ).eq("user_id", user_id).order("position").execute()
        
        return {
            "set": set_response.data,
            "flashcards": cards_response.data or []
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/flashcards/sets/{set_id}")
async def delete_flashcard_set(
    set_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Delete a flashcard set and all its cards."""
    try:
        response = supabase.table("flashcard_sets").delete().eq(
            "id", set_id
        ).eq("user_id", user_id).execute()

        deleted_rows = response.data or []
        if not deleted_rows:
            logger.warning(f"Delete requested for set {set_id} but no rows removed")
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        return {"success": True, "deleted": len(deleted_rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FLASHCARDS - CRUD
# ============================================================================

@router.get("/flashcards/{set_id}/cards", response_model=List[FlashcardResponse])
async def get_flashcards(
    set_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get all flashcards in a set."""
    try:
        response = supabase.table("flashcards").select("*").eq(
            "set_id", set_id
        ).eq("user_id", user_id).order("position").execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flashcards")
async def create_flashcard(
    request: CreateFlashcardRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Create a new flashcard manually."""
    try:
        # Verify set exists and belongs to user
        set_response = supabase.table("flashcard_sets").select("id").eq(
            "id", request.set_id
        ).eq("user_id", user_id).execute()
        
        if not set_response.data:
            raise HTTPException(status_code=404, detail="Flashcard set not found")
        
        # Get max position
        max_pos_response = supabase.table("flashcards").select("position").eq(
            "set_id", request.set_id
        ).order("position", desc=True).limit(1).execute()
        
        next_position = 0
        if max_pos_response.data:
            next_position = max_pos_response.data[0]["position"] + 1
        
        # Create flashcard
        flashcard_data = {
            "user_id": user_id,
            "set_id": request.set_id,
            "front": request.front,
            "back": request.back,
            "explanation": request.explanation,
            "position": next_position,
            "ai_generated": False
        }
        
        response = supabase.table("flashcards").insert(flashcard_data).execute()
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/flashcards/{flashcard_id}")
async def update_flashcard(
    flashcard_id: str,
    request: UpdateFlashcardRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Update a flashcard."""
    try:
        update_data = {}
        if request.front is not None:
            update_data["front"] = request.front
        if request.back is not None:
            update_data["back"] = request.back
        if request.explanation is not None:
            update_data["explanation"] = request.explanation
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        response = supabase.table("flashcards").update(update_data).eq(
            "id", flashcard_id
        ).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/flashcards/{flashcard_id}")
async def delete_flashcard(
    flashcard_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Delete a flashcard."""
    try:
        response = supabase.table("flashcards").delete().eq(
            "id", flashcard_id
        ).eq("user_id", user_id).execute()
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SPACED REPETITION - REVIEW
# ============================================================================

@router.post("/flashcards/{flashcard_id}/review")
async def review_flashcard(
    flashcard_id: str,
    request: ReviewFlashcardRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Record a flashcard review and update spaced repetition data."""
    try:
        # Get current flashcard
        card_response = supabase.table("flashcards").select("*").eq(
            "id", flashcard_id
        ).eq("user_id", user_id).single().execute()
        
        if not card_response.data:
            raise HTTPException(status_code=404, detail="Flashcard not found")
        
        card = card_response.data
        
        # Update mastery level and calculate next review
        current_level = card.get("mastery_level", 0)
        new_level = update_mastery_level(current_level, request.was_correct)
        interval_days = calculate_next_review_interval(new_level, request.was_correct)
        next_review = datetime.now() + timedelta(days=interval_days)
        
        # Update flashcard statistics
        update_data = {
            "mastery_level": new_level,
            "times_reviewed": card.get("times_reviewed", 0) + 1,
            "times_correct": card.get("times_correct", 0) + (1 if request.was_correct else 0),
            "times_incorrect": card.get("times_incorrect", 0) + (0 if request.was_correct else 1),
            "last_reviewed_at": datetime.now().isoformat(),
            "next_review_at": next_review.isoformat()
        }
        
        supabase.table("flashcards").update(update_data).eq("id", flashcard_id).execute()
        
        # Record review in history
        review_data = {
            "user_id": user_id,
            "flashcard_id": flashcard_id,
            "set_id": card["set_id"],
            "was_correct": request.was_correct,
            "confidence_rating": request.confidence_rating,
            "time_spent_seconds": request.time_spent_seconds
        }
        
        supabase.table("flashcard_reviews").insert(review_data).execute()
        
        return {
            "success": True,
            "mastery_level": new_level,
            "next_review_at": next_review.isoformat(),
            "interval_days": interval_days
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/flashcards/due")
async def get_due_flashcards(
    set_id: Optional[str] = None,
    limit: int = 20,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Get flashcards that are due for review."""
    try:
        params = {
            "p_user_id": user_id,
            "p_limit": limit
        }
        
        if set_id:
            params["p_set_id"] = set_id
        
        response = supabase.rpc("get_flashcards_due_for_review", params).execute()
        
        return {
            "success": True,
            "flashcards": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flashcards/generate-from-file")
async def generate_from_file(
    request: GenerateFromFileRequest,
    current_user: str = Depends(get_current_user)
):
    """Generate flashcards from a specific uploaded file."""
    try:
        # Validate file exists and user owns it
        file = supabase.table("files").select("*").eq(
            "id", request.file_id
        ).eq("user_id", current_user).single().execute()
        
        if not file.data:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Generate flashcards
        result = await generate_flashcards_from_file(
            file_id=request.file_id,
            user_id=current_user,
            num_cards=request.num_cards,
            difficulty=request.difficulty,
            supabase=supabase
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
