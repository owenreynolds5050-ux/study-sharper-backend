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
    user = Depends(get_current_user)
):
    """
    List user's files (lightweight - no content).
    Optionally filter by folder.
    """
    # Build query - select only needed fields for performance
    query = supabase.table("files").select(
        "id, title, file_type, file_size_bytes, processing_status, "
        "extraction_method, has_images, folder_id, created_at, updated_at, last_accessed_at"
    ).eq("user_id", user["id"]).order("updated_at", desc=True)
    
    # Filter by folder if specified
    if folder_id:
        query = query.eq("folder_id", folder_id)
    
    # Add pagination
    query = query.range(offset, offset + limit - 1)
    
    result = query.execute()
    
    # Get total count
    count_result = supabase.table("files").select("id", count="exact").eq("user_id", user["id"])
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
    user = Depends(get_current_user)
):
    """Get full file details including content"""
    result = supabase.table("files").select("*").eq("id", file_id).eq("user_id", user["id"]).execute()
    
    if not result.data:
        raise HTTPException(404, "File not found")
    
    # Update last accessed
    supabase.table("files").update({
        "last_accessed_at": "now()"
    }).eq("id", file_id).execute()
    
    return result.data[0]


@router.post("/files")
async def create_file(
    file_data: FileCreate,
    user = Depends(get_current_user)
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
        "user_id": user["id"],
        "folder_id": file_data.folder_id,
        "title": file_data.title.strip() or "Untitled",
        "file_type": file_type,
        "content": content,
        "file_size_bytes": file_size_bytes,
        "processing_status": "completed",
        "extraction_method": "manual",
        "has_images": False,
        "original_filename": f"{(file_data.title.strip() or 'note')}.{file_type}",
        "edited_manually": True,
    }

    try:
        result = supabase.table("files").insert(record).execute()
    except Exception as exc:
        raise HTTPException(500, f"Failed to create note: {exc}")

    if not result.data:
        raise HTTPException(500, "Failed to create note")

    # Update quota / counts
    from app.services.quota_service import increment_upload_count

    await increment_upload_count(user["id"], file_size_bytes)

    # Trigger embedding generation for contentful notes
    if content:
        from app.services.job_queue import job_queue, JobType, JobPriority

        await job_queue.add_job(
            job_type=JobType.EMBEDDING_GENERATION,
            job_data={"file_id": file_id, "user_id": user["id"]},
            priority=JobPriority.NORMAL,
        )

    return {"file": result.data[0]}

@router.patch("/files/{file_id}")
async def update_file(
    file_id: str,
    update_data: FileUpdate,
    user = Depends(get_current_user)
):
    """Update file metadata or content"""
    # Check ownership
    existing = supabase.table("files").select("id").eq("id", file_id).eq("user_id", user["id"]).execute()
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
            job_data={"file_id": file_id, "user_id": user["id"]},
            priority=JobPriority.NORMAL
        )
    
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    
    result = supabase.table("files").update(updates).eq("id", file_id).execute()
    
    return result.data[0]

@router.delete("/files/{file_id}")
async def delete_file(
    file_id: str,
    user = Depends(get_current_user)
):
    """Delete a file"""
    from app.services.quota_service import decrement_file_count
    
    # Get file info
    file_result = supabase.table("files").select("file_size_bytes, original_preview_path").eq("id", file_id).eq("user_id", user["id"]).execute()
    
    if not file_result.data:
        raise HTTPException(404, "File not found")
    
    file_data = file_result.data[0]
    
    # Delete from storage if preview exists
    if file_data.get("original_preview_path"):
        try:
            supabase.storage.from_("file-processing").remove([file_data["original_preview_path"]])
        except Exception as e:
            print(f"Warning: Could not delete file from storage: {e}")
    
    # Delete from database (cascades to embeddings)
    supabase.table("files").delete().eq("id", file_id).execute()
    
    # Update quota
    await decrement_file_count(user["id"], file_data.get("file_size_bytes", 0))
    
    return {"success": True}

@router.get("/folders")
async def list_folders(user = Depends(get_current_user)):
    """List all user's folders in tree structure"""
    result = supabase.table("file_folders").select("*").eq("user_id", user["id"]).order("position").execute()
    
    return {"folders": result.data}

@router.post("/folders")
async def create_folder(
    folder_data: FolderCreate,
    user = Depends(get_current_user)
):
    """Create a new folder"""
    # Calculate depth
    depth = 0
    if folder_data.parent_folder_id:
        parent = supabase.table("file_folders").select("depth").eq("id", folder_data.parent_folder_id).execute()
        if parent.data:
            depth = parent.data[0]["depth"] + 1
            if depth > 3:
                raise HTTPException(400, "Maximum folder depth (3 levels) exceeded")
    
    result = supabase.table("file_folders").insert({
        "user_id": user["id"],
        "name": folder_data.name,
        "color": folder_data.color,
        "parent_folder_id": folder_data.parent_folder_id,
        "depth": depth
    }).execute()
    
    return result.data[0]

@router.patch("/folders/{folder_id}")
async def update_folder(
    folder_id: str,
    update_data: FolderUpdate,
    user = Depends(get_current_user)
):
    """Update folder name or color"""
    # Check ownership
    existing = supabase.table("file_folders").select("id").eq("id", folder_id).eq("user_id", user["id"]).execute()
    if not existing.data:
        raise HTTPException(404, "Folder not found")
    
    updates = {}
    if update_data.name is not None:
        updates["name"] = update_data.name
    if update_data.color is not None:
        updates["color"] = update_data.color
    
    if not updates:
        raise HTTPException(400, "No valid fields to update")
    
    result = supabase.table("file_folders").update(updates).eq("id", folder_id).execute()
    
    return result.data[0]

@router.delete("/folders/{folder_id}")
async def delete_folder(
    folder_id: str,
    user = Depends(get_current_user)
):
    """Delete a folder (files will have folder_id set to NULL)"""
    # Check ownership
    existing = supabase.table("file_folders").select("id").eq("id", folder_id).eq("user_id", user["id"]).execute()
    if not existing.data:
        raise HTTPException(404, "Folder not found")
    
    # Delete (ON DELETE SET NULL for files)
    supabase.table("file_folders").delete().eq("id", folder_id).execute()
    
    return {"success": True}

@router.get("/quota")
async def get_quota(user = Depends(get_current_user)):
    """Get user's current quota status"""
    from app.services.quota_service import get_quota_info
    
    return await get_quota_info(user["id"])
