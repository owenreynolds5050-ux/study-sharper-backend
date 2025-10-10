from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.core.auth import get_current_user
from app.services.embeddings import get_embedding_for_text, hash_note_content
import json

router = APIRouter()

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


class GenerateEmbeddingRequest(BaseModel):
    noteId: str


class GenerateBatchEmbeddingRequest(BaseModel):
    noteIds: List[str]


class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5
    threshold: Optional[float] = 0.7


@router.post("/embeddings/generate")
async def generate_embedding(
    request: GenerateEmbeddingRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Generate and store embedding for a single note.
    """
    try:
        # Fetch the note
        response = supabase.table("notes").select(
            "id, user_id, title, content, extracted_text"
        ).eq("id", request.noteId).eq("user_id", user_id).single().execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note = response.data
        
        # Prepare text for embedding
        text_parts = []
        if note.get("title"):
            text_parts.append(f"Title: {note['title']}")
        if note.get("content"):
            text_parts.append(note["content"])
        if note.get("extracted_text"):
            text_parts.append(note["extracted_text"])
        
        full_text = "\n\n".join(text_parts)
        
        if not full_text.strip():
            raise HTTPException(status_code=400, detail="Note has no content to embed")
        
        # Truncate if too long
        max_chars = 8000
        text_to_embed = full_text[:max_chars] if len(full_text) > max_chars else full_text
        
        # Generate embedding
        result = get_embedding_for_text(text_to_embed)
        model = result["model"]
        embedding = result["embedding"]
        
        # Calculate content hash
        content_hash = hash_note_content(full_text)
        
        # Check if embedding exists
        existing = supabase.table("note_embeddings").select("id, content_hash").eq(
            "note_id", request.noteId
        ).execute()
        
        if existing.data and len(existing.data) > 0:
            # Update existing embedding
            supabase.table("note_embeddings").update({
                "embedding": json.dumps(embedding),
                "content_hash": content_hash,
                "model": model
            }).eq("id", existing.data[0]["id"]).execute()
            
            return {
                "success": True,
                "action": "updated",
                "noteId": request.noteId,
                "model": model
            }
        else:
            # Insert new embedding
            supabase.table("note_embeddings").insert({
                "note_id": request.noteId,
                "user_id": user_id,
                "embedding": json.dumps(embedding),
                "content_hash": content_hash,
                "model": model
            }).execute()
            
            return {
                "success": True,
                "action": "created",
                "noteId": request.noteId,
                "model": model
            }
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings/generate-batch")
async def generate_batch_embeddings(
    request: GenerateBatchEmbeddingRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Generate embeddings for multiple notes.
    """
    try:
        # Fetch all notes
        response = supabase.table("notes").select(
            "id, user_id, title, content, extracted_text"
        ).in_("id", request.noteIds).eq("user_id", user_id).execute()
        
        if not response.data:
            raise HTTPException(status_code=404, detail="No notes found")
        
        results = {
            "success": [],
            "failed": []
        }
        
        for note in response.data:
            try:
                # Prepare text
                text_parts = []
                if note.get("title"):
                    text_parts.append(f"Title: {note['title']}")
                if note.get("content"):
                    text_parts.append(note["content"])
                if note.get("extracted_text"):
                    text_parts.append(note["extracted_text"])
                
                full_text = "\n\n".join(text_parts)
                
                if not full_text.strip():
                    results["failed"].append({
                        "noteId": note["id"],
                        "error": "No content"
                    })
                    continue
                
                # Truncate if needed
                max_chars = 8000
                text_to_embed = full_text[:max_chars] if len(full_text) > max_chars else full_text
                
                # Generate embedding
                result = get_embedding_for_text(text_to_embed)
                model = result["model"]
                embedding = result["embedding"]
                content_hash = hash_note_content(full_text)
                
                # Upsert embedding
                supabase.table("note_embeddings").insert({
                    "note_id": note["id"],
                    "user_id": user_id,
                    "embedding": json.dumps(embedding),
                    "content_hash": content_hash,
                    "model": model
                }, upsert=True).execute()
                
                results["success"].append(note["id"])
                
            except Exception as e:
                results["failed"].append({
                    "noteId": note["id"],
                    "error": str(e)
                })
        
        return {
            "success": True,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embeddings/search")
async def search_notes(
    request: SearchRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Perform semantic search on notes.
    """
    try:
        if not request.query or not request.query.strip():
            raise HTTPException(status_code=400, detail="Query is required")
        
        # Generate embedding for query
        result = get_embedding_for_text(request.query)
        query_embedding = result["embedding"]
        
        # Call database function for similarity search
        response = supabase.rpc(
            "search_similar_notes",
            {
                "query_embedding": json.dumps(query_embedding),
                "user_id_param": user_id,
                "match_threshold": request.threshold,
                "match_count": request.limit
            }
        ).execute()
        
        return {
            "success": True,
            "query": request.query,
            "results": response.data or []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/embeddings/related/{note_id}")
async def get_related_notes(
    note_id: str,
    limit: int = 5,
    user_id: str = Depends(get_current_user)
):
    """
    Find notes related to a specific note.
    """
    try:
        # Verify note belongs to user
        note_response = supabase.table("notes").select("id").eq(
            "id", note_id
        ).eq("user_id", user_id).execute()
        
        if not note_response.data:
            raise HTTPException(status_code=404, detail="Note not found")
        
        # Find related notes
        response = supabase.rpc(
            "find_related_notes",
            {
                "source_note_id": note_id,
                "match_count": limit
            }
        ).execute()
        
        return {
            "success": True,
            "noteId": note_id,
            "results": response.data or []
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
