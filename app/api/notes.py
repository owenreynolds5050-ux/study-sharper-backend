from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
from app.core.auth import get_current_user, get_supabase_client

# Security model:
# - get_current_user() validates the JWT token and extracts user_id
# - get_supabase_client() uses service role key for database operations
# - All queries are filtered by user_id to ensure data isolation

router = APIRouter()

class NoteFolder(BaseModel):
    id: str
    user_id: str
    name: str
    color: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CreateNoteFolder(BaseModel):
    name: str
    color: str

@router.get("/folders", response_model=List[NoteFolder])
def get_folders(
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("note_folders").select("*").eq("user_id", user_id).order("created_at").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folders", response_model=NoteFolder)
async def create_folder(
    folder: CreateNoteFolder,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("note_folders").insert({"user_id": user_id, "name": folder.name, "color": folder.color}).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/folders/{folder_id}", response_model=NoteFolder)
async def update_folder(
    folder_id: str,
    folder: CreateNoteFolder,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("note_folders").update({"name": folder.name, "color": folder.color}).eq("id", folder_id).eq("user_id", user_id).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("note_folders").delete().eq("id", folder_id).eq("user_id", user_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class NoteLightweight(BaseModel):
    """Lightweight note model for list views - excludes heavy content fields."""
    id: str
    user_id: str
    title: str
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None
    file_path: Optional[str] = None
    processing_status: Optional[str] = None
    extraction_method: Optional[str] = None
    error_message: Optional[str] = None
    original_filename: Optional[str] = None
    ocr_processed: Optional[bool] = None
    edited_manually: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class Note(BaseModel):
    """Full note model with all fields including content."""
    id: str
    user_id: str
    title: str
    content: Optional[str] = None
    extracted_text: Optional[str] = None
    summary: Optional[str] = None
    transcription: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    processing_status: Optional[str] = None
    extraction_method: Optional[str] = None
    error_message: Optional[str] = None
    original_filename: Optional[str] = None
    ocr_processed: Optional[bool] = None
    edited_manually: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class CreateNote(BaseModel):
    title: str
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None

class UpdateNote(BaseModel):
    folder_id: Optional[str] = None

class PatchNoteText(BaseModel):
    """Model for updating extracted_text via PATCH."""
    extracted_text: str

@router.get("/notes", response_model=List[NoteLightweight])
def get_notes(
    response: Response,
    limit: int = 100,
    offset: int = 0,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get lightweight note list for a user with pagination.
    Returns only essential fields (id, title, folder_id, tags, timestamps).
    Optimized for fast loading with 1000+ notes.
    Cached for 30 seconds to reduce database load.
    
    Args:
        limit: Maximum number of notes to return (default: 100, max: 200)
        offset: Number of notes to skip (for pagination)
    """
    try:
        # Enforce max limit
        limit = min(limit, 200)
        
        # Add cache headers (30 second cache)
        response.headers["Cache-Control"] = "private, max-age=30"
        
        # Get total count for pagination
        count_response = supabase.table("notes").select(
            "id", count="exact"
        ).eq("user_id", user_id).execute()
        total_count = count_response.count if hasattr(count_response, 'count') else 0
        
        # Select only lightweight fields - excludes content, extracted_text, summary, transcription
        db_response = supabase.table("notes").select(
            "id, user_id, title, tags, folder_id, file_path, processing_status, extraction_method, error_message, original_filename, ocr_processed, edited_manually, created_at, updated_at"
        ).eq("user_id", user_id).order("updated_at", desc=True).range(offset, offset + limit - 1).execute()
        
        # Add pagination headers
        response.headers["X-Total-Count"] = str(total_count)
        response.headers["X-Limit"] = str(limit)
        response.headers["X-Offset"] = str(offset)
        
        return db_response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notes", response_model=Note)
async def create_note(
    note: CreateNote,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("notes").insert({
            "user_id": user_id,
            "title": note.title,
            "content": note.content,
            "tags": note.tags,
            "folder_id": note.folder_id
        }).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/notes/{note_id}", response_model=Note)
async def update_note(
    note_id: str,
    update: UpdateNote,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        response = supabase.table("notes").update({"folder_id": update.folder_id}).eq("id", note_id).eq("user_id", user_id).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notes/{note_id}", response_model=Note)
def get_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get full note data including content, extracted_text, and all other fields.
    Used for viewing/editing individual notes.
    """
    try:
        response = supabase.table("notes").select("*").eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/notes/{note_id}", response_model=Note)
async def patch_note_text(
    note_id: str,
    patch_data: PatchNoteText,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Update the extracted_text of a note (user editing).
    Sets edited_manually=true and updates updated_at timestamp.
    Does NOT trigger re-processing.
    """
    try:
        # Validate text is not empty
        if not patch_data.extracted_text or not patch_data.extracted_text.strip():
            raise HTTPException(status_code=400, detail="Extracted text cannot be empty")
        
        # Validate text size (1MB = 1,048,576 bytes)
        text_size = len(patch_data.extracted_text.encode('utf-8'))
        if text_size > 1_048_576:
            raise HTTPException(
                status_code=400, 
                detail=f"Text too large ({text_size:,} bytes). Maximum size is 1MB (1,048,576 bytes)"
            )
        
        # Verify user owns this note
        check_response = supabase.table("notes").select("id").eq("id", note_id).eq("user_id", user_id).execute()
        if not check_response.data or len(check_response.data) == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Update extracted_text and set edited_manually=true
        # updated_at is automatically updated by the database trigger
        response = supabase.table("notes").update({
            "extracted_text": patch_data.extracted_text,
            "edited_manually": True
        }).eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=500, detail="Failed to update note")
        
        return response.data[0]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/notes/{note_id}")
async def delete_note(
    note_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    try:
        # First, get the note to find the file path
        response = supabase.table("notes").select("file_path").eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note = response.data[0]

        # If there's a file, delete it from storage
        if note and note.get("file_path"):
            supabase.storage.from_("notes-pdfs").remove([note["file_path"]])

        # Then, delete the note from the database
        response = supabase.table("notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
        return {"success": True}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
