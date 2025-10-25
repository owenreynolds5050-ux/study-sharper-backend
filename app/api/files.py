# app/api/files.py
# Consolidated API for file and note management
# Replaces the old notes.py API - all functionality unified here
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from typing import Optional, List
import uuid
from app.core.auth import get_current_user
from app.core.database import supabase
from pydantic import BaseModel

router = APIRouter()

class FileUpdate(BaseModel):
    model_config = {"extra": "ignore"}
    
    title: Optional[str] = None
    content: Optional[str] = None
    folder_id: Optional[str] = None  # Can be null to remove from folder
    tags: Optional[List[str]] = None
    summary: Optional[str] = None

class PatchFileText(BaseModel):
    """Model for updating file content (extracted_text) via PATCH."""
    content: str  # Will be stored in both content and extracted_text

class FolderCreate(BaseModel):
    name: str
    color: str = "#3B82F6"
    parent_folder_id: Optional[str] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    parent_folder_id: Optional[str] = None


class FileCreate(BaseModel):
    title: str
    content: Optional[str] = None
    folder_id: Optional[str] = None
    file_type: Optional[str] = "md"

@router.get("/files")
async def list_files(
    folder_id: Optional[str] = Query(None),
    limit: int = Query(100, le=200),
    offset: int = Query(0),
    user_id: str = Depends(get_current_user)
):
    """
    List user's files (lightweight - no content).
    Optionally filter by folder.
    """
    # Build query - select only needed fields for performance
    query = supabase.table("files").select(
        "id, title, file_type, file_size_bytes, processing_status, "
        "extraction_method, has_images, folder_id, created_at, updated_at"
    ).eq("user_id", user_id).order("updated_at", desc=True)
    
    # Filter by folder if specified
    if folder_id:
        query = query.eq("folder_id", folder_id)
    
    # Add pagination
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    
    # Add cache headers (30 second cache)
    response = Response()
    response.headers["Cache-Control"] = "private, max-age=30"
    
    # Get total count
    count_result = supabase.table("files").select("id", count="exact").eq("user_id", user_id)
    if folder_id:
        count_result = count_result.eq("folder_id", folder_id)
    count_result = count_result.execute()
    
    total_count = count_result.count if hasattr(count_result, 'count') else len(result.data)
    
    # Add pagination headers
    response.headers["X-Total-Count"] = str(total_count)
    response.headers["X-Limit"] = str(limit)
    response.headers["X-Offset"] = str(offset)
    
    return {
        "files": result.data,
        "total": total_count,
        "limit": limit,
        "offset": offset
    }

@router.get("/files/{file_id}")
async def get_file(
    file_id: str,
    user_id: str = Depends(get_current_user)
):
    """Get full file details including content, extracted_text, and all other fields."""
    result = supabase.table("files").select("*").eq("id", file_id).eq("user_id", user_id).execute()
    
    if not result.data:
        raise HTTPException(404, "File not found")
    
    return result.data[0]


@router.post("/files")
async def create_file(
    file_data: FileCreate,
    user_id: str = Depends(get_current_user)
):
    """Create a new manual text note (no file upload)."""
    file_type = (file_data.file_type or "md").lower()

    if file_type not in {"md", "txt"}:
        raise HTTPException(400, "Unsupported file type for manual creation")

    content = file_data.content or ""
    file_id = str(uuid.uuid4())

    record = {
        "id": file_id,
        "user_id": user_id,
        "folder_id": file_data.folder_id,
        "title": file_data.title.strip() or "Untitled",
        "file_type": file_type,
        "content": content,
    }

    try:
        result = supabase.table("files").insert(record).execute()
    except Exception as exc:
        raise HTTPException(500, f"Failed to create note: {str(exc)}")

    if not result.data:
        raise HTTPException(500, "Failed to create note")

    # Trigger embedding generation for contentful notes (non-blocking)
    if content:
        try:
            from app.services.job_queue import job_queue, JobType, JobPriority
            await job_queue.add_job(
                job_type=JobType.EMBEDDING_GENERATION,
                job_data={"file_id": file_id, "user_id": user_id},
                priority=JobPriority.NORMAL,
            )
        except Exception as e:
            # Log but don't fail the request - embedding can be generated later
            print(f"Warning: Failed to queue embedding generation: {str(e)}")

    return result.data[0]

@router.patch("/files/{file_id}")
async def update_file(
    file_id: str,
    update_data: FileUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update file metadata, content, tags, or other fields"""
    # Check ownership
    existing = supabase.table("files").select("id").eq("id", file_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(404, "File not found")
    
    # Build update dict
    updates = {}
    if update_data.title is not None:
        updates["title"] = update_data.title
    # Handle folder_id specially - check if it was explicitly provided in request
    # This allows setting folder_id to null to remove from folder
    # In Pydantic v2, model_fields_set tracks which fields were explicitly set
    if hasattr(update_data, 'model_fields_set') and 'folder_id' in update_data.model_fields_set:
        updates["folder_id"] = update_data.folder_id
    elif update_data.folder_id is not None:
        updates["folder_id"] = update_data.folder_id
    if update_data.content is not None:
        updates["content"] = update_data.content
        updates["edited_manually"] = True
        
        # If content changed, re-generate embedding
        from app.services.job_queue import job_queue, JobType, JobPriority
        await job_queue.add_job(
            job_type=JobType.EMBEDDING_GENERATION,
            job_data={"file_id": file_id, "user_id": user_id},
            priority=JobPriority.NORMAL
        )
    if update_data.tags is not None:
        updates["tags"] = update_data.tags
    if update_data.summary is not None:
        updates["summary"] = update_data.summary
    
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    
    result = supabase.table("files").update(updates).eq("id", file_id).execute()
    
    if not result.data:
        raise HTTPException(500, "Failed to update file")
    
    return result.data[0]

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a file and its associated storage"""
    # Get file info
    file_result = supabase.table("files").select("file_size_bytes, file_path").eq("id", file_id).eq("user_id", user_id).execute()
    
    if not file_result.data:
        raise HTTPException(404, "File not found")
    
    file_data = file_result.data[0]
    
    # Delete from storage if file exists
    if file_data.get("file_path"):
        try:
            supabase.storage.from_("notes-pdfs").remove([file_data["file_path"]])
        except Exception as e:
            print(f"Warning: Could not delete file from storage: {e}")
    
    # Delete from database (cascades to embeddings)
    delete_result = supabase.table("files").delete().eq("id", file_id).eq("user_id", user_id).execute()
    
    if not delete_result.data:
        raise HTTPException(500, "Failed to delete file from database")
    
    return {"success": True}

@router.get("/folders")
async def list_folders(user_id: str = Depends(get_current_user)):
    """List all user's folders in tree structure"""
    import logging
    logging.info(f"[FILES API] Fetching folders for user_id: {user_id}")
    result = supabase.table("note_folders").select("*").eq("user_id", user_id).order("created_at").execute()
    logging.info(f"[FILES API] Found {len(result.data)} folders")
    
    return {"folders": result.data}

@router.post("/folders")
async def create_folder(
    folder_data: FolderCreate,
    user_id: str = Depends(get_current_user)
):
    """Create a new folder"""
    import logging
    logging.info(f"[FILES API] Creating folder '{folder_data.name}' for user_id: {user_id}")
    # Note: note_folders table doesn't have depth/parent_folder_id columns
    # Simplified folder creation
    parent_folder_id = folder_data.parent_folder_id
    if parent_folder_id:
        parent_query = supabase.table("note_folders").select("id, parent_folder_id").eq("id", parent_folder_id).eq("user_id", user_id).execute()
        if not parent_query.data:
            raise HTTPException(400, "Parent folder not found")
        if parent_query.data[0].get("parent_folder_id"):
            raise HTTPException(400, "Cannot create subfolder deeper than one level")

    record = {
        "user_id": user_id,
        "name": folder_data.name,
        "color": folder_data.color,
        "parent_folder_id": parent_folder_id if parent_folder_id else None
    }

    result = supabase.table("note_folders").insert(record).execute()
    logging.info(f"[FILES API] Folder created successfully: {result.data[0].get('id')}")
    
    return result.data[0]

@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    update_data: FolderUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update folder name or color"""
    # Check ownership
    existing = supabase.table("note_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(404, "Folder not found")
    
    updates = update_data.model_dump(exclude_unset=True)

    if "parent_folder_id" in updates:
        new_parent = updates["parent_folder_id"]

        if new_parent == "":
            new_parent = None

        if new_parent == folder_id:
            raise HTTPException(400, "Folder cannot be its own parent")

        if new_parent:
            parent_query = supabase.table("note_folders").select("id, parent_folder_id").eq("id", new_parent).eq("user_id", user_id).execute()
            if not parent_query.data:
                raise HTTPException(400, "Parent folder not found")
            if parent_query.data[0].get("parent_folder_id"):
                raise HTTPException(400, "Cannot move folder into a subfolder")

            child_check = supabase.table("note_folders").select("id").eq("parent_folder_id", folder_id).eq("user_id", user_id).execute()
            if child_check.data and parent_query.data[0]["id"]:
                raise HTTPException(400, "Cannot move parent folder into another folder while it has subfolders")

            updates["parent_folder_id"] = new_parent
        else:
            updates["parent_folder_id"] = None

    if not updates:
        raise HTTPException(400, "No valid fields to update")

    result = supabase.table("note_folders").update(updates).eq("id", folder_id).execute()
    
    return result.data[0]

@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a folder (files will have folder_id set to NULL)"""
    # Check ownership
    existing = supabase.table("note_folders").select("id").eq("id", folder_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(404, "Folder not found")
    
    # Delete (ON DELETE SET NULL for files)
    supabase.table("note_folders").delete().eq("id", folder_id).execute()
    
    return {"success": True}

@router.get("/quota")
async def get_quota(user_id: str = Depends(get_current_user)):
    """Get user's current quota status"""
    from app.services.quota_service import get_quota_info
    
    return await get_quota_info(user_id)


# ============================================================================
# LEGACY NOTES API COMPATIBILITY ENDPOINTS
# These endpoints maintain backward compatibility with the old /api/notes API
# They simply proxy to the files endpoints above
# ============================================================================

@router.get("/notes")
async def get_notes_legacy(
    response: Response,
    limit: int = 100,
    offset: int = 0,
    user_id: str = Depends(get_current_user)
):
    """Legacy notes endpoint - proxies to files API"""
    return await list_files(None, limit, offset, user_id)

@router.get("/notes/{note_id}")
async def get_note_legacy(
    note_id: str,
    user_id: str = Depends(get_current_user)
):
    """Legacy note detail endpoint - proxies to files API"""
    return await get_file(note_id, user_id)

@router.post("/notes")
async def create_note_legacy(
    file_data: FileCreate,
    user_id: str = Depends(get_current_user)
):
    """Legacy note creation endpoint - proxies to files API"""
    result = await create_file(file_data, user_id)
    return result["file"] if isinstance(result, dict) and "file" in result else result

@router.patch("/notes/{note_id}")
async def patch_note_legacy(
    note_id: str,
    patch_data: PatchFileText,
    user_id: str = Depends(get_current_user)
):
    """Legacy note text update endpoint - proxies to files API"""
    update_data = FileUpdate(content=patch_data.content)
    return await update_file(note_id, update_data, user_id)

@router.delete("/notes/{note_id}")
async def delete_note_legacy(
    note_id: str,
    user_id: str = Depends(get_current_user)
):
    """Legacy note deletion endpoint - proxies to files API"""
    return await delete_file(note_id, user_id)

@router.put("/notes/{note_id}")
async def update_note_folder_legacy(
    note_id: str,
    update_data: FileUpdate,
    user_id: str = Depends(get_current_user)
):
    """Legacy note update endpoint - proxies to files API"""
    return await update_file(note_id, update_data, user_id)
