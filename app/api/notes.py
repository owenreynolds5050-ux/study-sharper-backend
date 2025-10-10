from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY

router = APIRouter()

def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

class NoteFolder(BaseModel):
    id: str
    user_id: str
    name: str
    color: str

class CreateNoteFolder(BaseModel):
    name: str
    color: str

@router.get("/folders", response_model=List[NoteFolder])
def get_folders(supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("note_folders").select("*").eq("user_id", user_id).order("created_at").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/folders", response_model=NoteFolder)
async def create_folder(folder: CreateNoteFolder, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("note_folders").insert({"user_id": user_id, "name": folder.name, "color": folder.color}).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/folders/{folder_id}", response_model=NoteFolder)
async def update_folder(folder_id: str, folder: CreateNoteFolder, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("note_folders").update({"name": folder.name, "color": folder.color}).eq("id", folder_id).eq("user_id", user_id).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: str, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("note_folders").delete().eq("id", folder_id).eq("user_id", user_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class Note(BaseModel):
    id: str
    user_id: str
    title: str
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None
    file_path: Optional[str] = None

class CreateNote(BaseModel):
    title: str
    content: Optional[str] = None
    tags: Optional[List[str]] = None
    folder_id: Optional[str] = None

@router.get("/notes", response_model=List[Note])
def get_notes(supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("notes").select("*").eq("user_id", user_id).order("updated_at").execute()
        return response.data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/notes", response_model=Note)
async def create_note(note: CreateNote, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
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
async def update_note(note_id: str, folder_id: str, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        response = supabase.table("notes").update({"folder_id": folder_id}).eq("id", note_id).eq("user_id", user_id).execute()
        return response.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/notes/{note_id}")
async def delete_note(note_id: str, supabase: Client = Depends(get_supabase_client)):
    user_id = "..."  # Replace with actual user ID from auth
    try:
        # First, get the note to find the file path
        response = supabase.table("notes").select("file_path").eq("id", note_id).eq("user_id", user_id).execute()
        note = response.data[0]

        # If there's a file, delete it from storage
        if note and note.get("file_path"):
            supabase.storage.from_("notes-pdfs").remove([note["file_path"]])

        # Then, delete the note from the database
        response = supabase.table("notes").delete().eq("id", note_id).eq("user_id", user_id).execute()
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
