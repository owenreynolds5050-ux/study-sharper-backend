from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from typing import List, Optional
from app.core.auth import get_current_user, get_supabase_client
import logging

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for request/response validation
class FolderCreate(BaseModel):
    name: str
    color: str
    parent_folder_id: Optional[str] = None

class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    parent_folder_id: Optional[str] = None

class Folder(BaseModel):
    id: str
    user_id: str
    name: str
    color: str
    parent_folder_id: Optional[str] = None
    depth: int = 0
    created_at: str

@router.get("/folders", response_model=List[Folder])
async def get_folders(
    http_response: Response,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get all folders for the authenticated user.
    Returns folders ordered by creation date.
    Cached for 60 seconds (folders change infrequently).
    """
    try:
        logger.info(f"Fetching folders for user: {user_id}")
        
        # Add cache headers (60 second cache - folders change infrequently)
        http_response.headers["Cache-Control"] = "private, max-age=60"
        
        response = supabase.table("note_folders")\
            .select("*")\
            .eq("user_id", user_id)\
            .order("created_at")\
            .execute()
        
        logger.info(f"Found {len(response.data)} folders for user: {user_id}")
        return response.data
        
    except Exception as e:
        logger.error(f"Error fetching folders: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch folders")

@router.get("/folders/{folder_id}", response_model=Folder)
async def get_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get a specific folder by ID.
    Ensures user owns the folder.
    """
    try:
        logger.info(f"Fetching folder {folder_id} for user: {user_id}")
        
        response = supabase.table("note_folders")\
            .select("*")\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        return response.data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch folder")

@router.post("/folders", response_model=Folder, status_code=201)
async def create_folder(
    folder: FolderCreate,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Create a new folder for the authenticated user.
    Supports folder nesting with parent_folder_id.
    """
    try:
        logger.info(f"Creating folder '{folder.name}' for user: {user_id}")
        
        # Validate color format (basic validation)
        if not folder.color.startswith('#') or len(folder.color) not in [4, 7]:
            raise HTTPException(
                status_code=400, 
                detail="Invalid color format. Use hex format like #FF5733"
            )
        
        # Calculate depth based on parent folder
        depth = 0
        if folder.parent_folder_id:
            # Fetch parent folder to get its depth
            parent_response = supabase.table("note_folders")\
                .select("depth")\
                .eq("id", folder.parent_folder_id)\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if not parent_response.data:
                raise HTTPException(
                    status_code=404,
                    detail="Parent folder not found"
                )
            
            parent_depth = parent_response.data.get("depth", 0)
            depth = parent_depth + 1
            
            # Enforce max depth of 2
            if depth > 2:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot create folder: maximum nesting depth is 2 (Folder -> Subfolder -> File)"
                )
        
        response = supabase.table("note_folders").insert({
            "user_id": user_id,
            "name": folder.name,
            "color": folder.color,
            "parent_folder_id": folder.parent_folder_id,
            "depth": depth
        }).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to create folder")
        
        logger.info(f"Created folder with ID: {response.data[0]['id']}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to create folder")

@router.put("/folders/{folder_id}", response_model=Folder)
async def update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Update a folder's name or color.
    User must own the folder.
    """
    try:
        logger.info(f"Updating folder {folder_id} for user: {user_id}")
        
        # Check folder exists and user owns it
        check_response = supabase.table("note_folders")\
            .select("id")\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not check_response.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Build update data
        update_data = {}
        if folder_update.name is not None:
            update_data["name"] = folder_update.name
        if folder_update.color is not None:
            # Validate color format
            if not folder_update.color.startswith('#') or len(folder_update.color) not in [4, 7]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid color format. Use hex format like #FF5733"
                )
            update_data["color"] = folder_update.color
        if folder_update.parent_folder_id is not None:
            # Validate parent folder exists and belongs to user
            parent_response = supabase.table("note_folders")\
                .select("depth")\
                .eq("id", folder_update.parent_folder_id)\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if not parent_response.data:
                raise HTTPException(
                    status_code=404,
                    detail="Parent folder not found"
                )
            
            # Prevent moving folder into itself
            if folder_id == folder_update.parent_folder_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move folder into itself"
                )
            
            # Calculate new depth
            parent_depth = parent_response.data.get("depth", 0)
            new_depth = parent_depth + 1
            
            # Enforce max depth of 2
            if new_depth > 2:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move folder: maximum nesting depth is 2 (Folder -> Subfolder -> File)"
                )
            
            update_data["parent_folder_id"] = folder_update.parent_folder_id
            update_data["depth"] = new_depth
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Perform update
        response = supabase.table("note_folders")\
            .update(update_data)\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        # If parent_folder_id was updated, also update depth of all child folders
        if "parent_folder_id" in update_data and "depth" in update_data:
            new_depth = update_data["depth"]
            # Update all direct children
            supabase.table("note_folders")\
                .update({"depth": new_depth + 1})\
                .eq("parent_folder_id", folder_id)\
                .execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update folder")
        
        logger.info(f"Updated folder {folder_id}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to update folder")

@router.patch("/folders/{folder_id}", response_model=Folder)
async def patch_update_folder(
    folder_id: str,
    folder_update: FolderUpdate,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Partially update a folder (PATCH method).
    User must own the folder.
    """
    try:
        logger.info(f"Patching folder {folder_id} for user: {user_id}")
        
        # Check folder exists and user owns it
        check_response = supabase.table("note_folders")\
            .select("id")\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not check_response.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Build update data
        update_data = {}
        if folder_update.name is not None:
            update_data["name"] = folder_update.name
        if folder_update.color is not None:
            # Validate color format
            if not folder_update.color.startswith('#') or len(folder_update.color) not in [4, 7]:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid color format. Use hex format like #FF5733"
                )
            update_data["color"] = folder_update.color
        if folder_update.parent_folder_id is not None:
            # Validate parent folder exists and belongs to user
            parent_response = supabase.table("note_folders")\
                .select("depth")\
                .eq("id", folder_update.parent_folder_id)\
                .eq("user_id", user_id)\
                .single()\
                .execute()
            
            if not parent_response.data:
                raise HTTPException(
                    status_code=404,
                    detail="Parent folder not found"
                )
            
            # Prevent moving folder into itself
            if folder_id == folder_update.parent_folder_id:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move folder into itself"
                )
            
            # Calculate new depth
            parent_depth = parent_response.data.get("depth", 0)
            new_depth = parent_depth + 1
            
            # Enforce max depth of 2
            if new_depth > 2:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot move folder: maximum nesting depth is 2 (Folder -> Subfolder -> File)"
                )
            
            update_data["parent_folder_id"] = folder_update.parent_folder_id
            update_data["depth"] = new_depth
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No update data provided")
        
        # Perform update
        response = supabase.table("note_folders")\
            .update(update_data)\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        # If parent_folder_id was updated, also update depth of all child folders
        if "parent_folder_id" in update_data and "depth" in update_data:
            new_depth = update_data["depth"]
            # Update all direct children
            supabase.table("note_folders")\
                .update({"depth": new_depth + 1})\
                .eq("parent_folder_id", folder_id)\
                .execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to update folder")
        
        logger.info(f"Patched folder {folder_id}")
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error patching folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to update folder")

@router.delete("/folders/{folder_id}", status_code=204)
async def delete_folder(
    folder_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Delete a folder.
    User must own the folder.
    Notes in the folder will have folder_id set to NULL (per FK constraint).
    """
    try:
        logger.info(f"Deleting folder {folder_id} for user: {user_id}")
        
        # Check folder exists and user owns it
        check_response = supabase.table("note_folders")\
            .select("id")\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not check_response.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Delete the folder (notes will automatically have folder_id set to NULL)
        supabase.table("note_folders")\
            .delete()\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        logger.info(f"Deleted folder {folder_id}")
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete folder")

@router.get("/folders/{folder_id}/notes-count")
async def get_folder_notes_count(
    folder_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get the count of notes in a specific folder.
    Useful for UI to show how many notes are in each folder.
    """
    try:
        logger.info(f"Counting notes in folder {folder_id} for user: {user_id}")
        
        # Verify folder exists and user owns it
        folder_response = supabase.table("note_folders")\
            .select("id")\
            .eq("id", folder_id)\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        
        if not folder_response.data:
            raise HTTPException(status_code=404, detail="Folder not found")
        
        # Count notes in folder
        notes_response = supabase.table("notes")\
            .select("id", count="exact")\
            .eq("folder_id", folder_id)\
            .eq("user_id", user_id)\
            .execute()
        
        count = notes_response.count if hasattr(notes_response, 'count') else len(notes_response.data)
        
        logger.info(f"Folder {folder_id} has {count} notes")
        return {"folder_id": folder_id, "notes_count": count}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error counting notes in folder: {e}")
        raise HTTPException(status_code=500, detail="Failed to count notes")

@router.get("/folders/health")
async def folders_health_check():
    """Health check endpoint for folders API"""
    return {
        "status": "healthy",
        "service": "folders",
        "version": "1.0.0"
    }
