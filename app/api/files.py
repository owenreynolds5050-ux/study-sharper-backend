# app/api/files.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
import uuid
from app.core.auth import get_current_user
from app.core.database import supabase
from pydantic import BaseModel

router = APIRouter()

class FileUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    folder_id: Optional[str] = None

class FolderCreate(BaseModel):
    name: str
    color: str = "#3B82F6"
    parent_folder_id: Optional[str] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


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
    query = supabase.table("notes").select(
        "id, title, file_type, file_size_bytes, processing_status, "
        "extraction_method, has_images, folder_id, created_at, updated_at"
    ).eq("user_id", user_id).order("updated_at", desc=True)
    
    # Filter by folder if specified
    if folder_id:
        query = query.eq("folder_id", folder_id)
    
    # Add pagination
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    
    # Get total count
    count_result = supabase.table("notes").select("id", count="exact").eq("user_id", user_id)
    if folder_id:
        count_result = count_result.eq("folder_id", folder_id)
    count_result = count_result.execute()
    
    total_count = count_result.count if hasattr(count_result, 'count') else len(result.data)
    
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
    """Get full file details including content"""
    result = supabase.table("notes").select("*").eq("id", file_id).eq("user_id", user_id).execute()
    
    if not result.data:
        raise HTTPException(404, "File not found")
    
    return result.data[0]


@router.post("/files")
async def create_file(
    file_data: FileCreate,
    user_id: str = Depends(get_current_user)
):
    """Create a new manual note/file."""
    file_type = (file_data.file_type or "md").lower()

    if file_type not in {"md", "txt"}:
        raise HTTPException(400, "Unsupported file type for manual creation")

    content = file_data.content or ""
    file_size_bytes = len(content.encode("utf-8"))
    file_id = str(uuid.uuid4())

    record = {
        "id": file_id,
        "user_id": user_id,
        "folder_id": file_data.folder_id,
        "title": file_data.title.strip() or "Untitled",
        "file_type": file_type,
        "content": content,
        "extracted_text": content,  # For consistency with notes table
        "file_size_bytes": file_size_bytes,
        "processing_status": "completed",
        "extraction_method": "manual",
        "original_filename": f"{(file_data.title.strip() or 'note')}.{file_type}",
        "edited_manually": True,
    }

    try:
        result = supabase.table("notes").insert(record).execute()
    except Exception as exc:
        # Log the full error for debugging
        import traceback
        error_details = traceback.format_exc()
        print(f"Error creating note: {error_details}")
        raise HTTPException(500, f"Failed to create note: {str(exc)}")

    if not result.data:
        raise HTTPException(500, "Failed to create note")

    # Update quota / counts
    from app.services.quota_service import increment_upload_count

    await increment_upload_count(user_id, file_size_bytes)

    # Trigger embedding generation for contentful notes
    if content:
        from app.services.job_queue import job_queue, JobType, JobPriority

        await job_queue.add_job(
            job_type=JobType.EMBEDDING_GENERATION,
            job_data={"file_id": file_id, "user_id": user_id},
            priority=JobPriority.NORMAL,
        )

    return {"file": result.data[0]}

@router.patch("/files/{file_id}")
async def update_file(
    file_id: str,
    update_data: FileUpdate,
    user_id: str = Depends(get_current_user)
):
    """Update file metadata or content"""
    # Check ownership
    existing = supabase.table("notes").select("id").eq("id", file_id).eq("user_id", user_id).execute()
    if not existing.data:
        raise HTTPException(404, "File not found")
    
    # Build update dict
    updates = {}
    if update_data.title is not None:
        updates["title"] = update_data.title
    if update_data.folder_id is not None:
        updates["folder_id"] = update_data.folder_id
    if update_data.content is not None:
        updates["content"] = update_data.content
        
        # If content changed, re-generate embedding
        from app.services.job_queue import job_queue, JobType, JobPriority
        await job_queue.add_job(
            job_type=JobType.EMBEDDING_GENERATION,
            job_data={"file_id": file_id, "user_id": user_id},
            priority=JobPriority.NORMAL
        )
    
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    
    result = supabase.table("notes").update(updates).eq("id", file_id).execute()
    
    return result.data[0]

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user)
):
    """Delete a file"""
    from app.services.quota_service import decrement_file_count
    
    # Get file info
    file_result = supabase.table("notes").select("file_size_bytes, file_path").eq("id", file_id).eq("user_id", user_id).execute()
    
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
    supabase.table("notes").delete().eq("id", file_id).execute()
    
    # Update quota
    await decrement_file_count(user_id, file_data.get("file_size_bytes", 0))
    
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
    result = supabase.table("note_folders").insert({
        "user_id": user_id,
        "name": folder_data.name,
        "color": folder_data.color
    }).execute()
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
    
    updates = {}
    if update_data.name is not None:
        updates["name"] = update_data.name
    if update_data.color is not None:
        updates["color"] = update_data.color
    
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
