"""File Chat API - Conversational endpoint leveraging uploaded files with session management."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
import logging

from app.core.auth import get_current_user, get_supabase_client
from app.services.ai_chat import retrieve_relevant_file_chunks
from app.services.open_router import get_chat_completion

logger = logging.getLogger(__name__)
router = APIRouter()


class FileChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    file_ids: Optional[List[str]] = None


class FileChatResponse(BaseModel):
    session_id: str
    response: str
    sources: List[Dict[str, Any]]
    message_id: str


@router.post("/chat/with-files", response_model=FileChatResponse)
async def chat_with_files(
    request: FileChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Chat with uploaded files using RAG. Creates/resumes conversation sessions."""
    logger.info(f"=== CHAT REQUEST RECEIVED ===")
    logger.info(f"  Message: {request.message[:100]}..." if len(request.message) > 100 else f"  Message: {request.message}")
    logger.info(f"  File IDs: {request.file_ids}")
    logger.info(f"  Session ID: {request.session_id}")
    logger.info(f"  User ID: {user_id}")
    
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    query = request.message.strip()
    message_id = str(uuid.uuid4())
    
    try:
        # Step 1: Get or create conversation session
        session_id = request.session_id
        if not session_id:
            # Create new session
            session_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_type": "chat",
                "context_data": {
                    "file_ids": request.file_ids or [],
                    "created_at": datetime.utcnow().isoformat()
                },
                "started_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat()
            }
            session_result = supabase.table("conversation_sessions").insert(session_data).execute()
            if not session_result.data:
                raise Exception("Failed to create conversation session")
            session_id = session_result.data[0]["id"]
        else:
            # Update last_activity for existing session
            supabase.table("conversation_sessions").update({
                "last_activity": datetime.utcnow().isoformat()
            }).eq("id", session_id).eq("user_id", user_id).execute()
        
        # Step 2: Save user message to database
        user_msg_data = {
            "id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "user",
            "content": query,
            "metadata": {
                "file_ids": request.file_ids or [],
                "timestamp": datetime.utcnow().isoformat()
            },
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("conversation_messages").insert(user_msg_data).execute()
        
        # Step 3: Retrieve relevant chunks (optionally filtered by file_ids)
        chunk_results = await retrieve_relevant_file_chunks(
            user_id=user_id,
            query=query,
            supabase=supabase,
            top_k=5,
            file_ids=request.file_ids
        )

        system_message = chunk_results["system_message"]
        chunks = chunk_results["chunks"]

        # Step 4: Build Full Prompt
        messages = [
            {
                "role": "system",
                "content": system_message
            },
            {
                "role": "user",
                "content": query
            }
        ]

        # Step 5: Call OpenRouter
        response_text = get_chat_completion(messages, model="anthropic/claude-3.5-haiku")

        # Step 6: Save assistant response to database
        assistant_msg_data = {
            "id": message_id,
            "session_id": session_id,
            "role": "assistant",
            "content": response_text.strip(),
            "metadata": {
                "sources": [{
                    "file_id": chunk.get("file_id"),
                    "file_title": chunk.get("file_title"),
                    "chunk_id": chunk.get("chunk_id"),
                    "similarity": chunk.get("similarity")
                } for chunk in chunks],
                "timestamp": datetime.utcnow().isoformat()
            },
            "created_at": datetime.utcnow().isoformat()
        }
        supabase.table("conversation_messages").insert(assistant_msg_data).execute()

        # Step 7: Build Source Metadata for Response
        sources = []
        for chunk in chunks:
            sources.append({
                "file_id": chunk.get("file_id"),
                "file_title": chunk.get("file_title"),
                "chunk_id": chunk.get("chunk_id"),
                "similarity": chunk.get("similarity"),
                "text": chunk.get("text")
            })

        return FileChatResponse(
            session_id=session_id,
            response=response_text.strip(),
            sources=sources,
            message_id=message_id
        )
        
    except Exception as e:
        logger.error(f"Error in chat_with_files: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.get("/chat/sessions/{session_id}")
async def get_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Retrieve a conversation session with all messages."""
    try:
        # Get session
        session_result = supabase.table("conversation_sessions").select("*").eq(
            "id", session_id
        ).eq("user_id", user_id).execute()
        
        if not session_result.data:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = session_result.data[0]
        
        # Get all messages in session
        messages_result = supabase.table("conversation_messages").select("*").eq(
            "session_id", session_id
        ).order("created_at", desc=False).execute()
        
        return {
            "session": session,
            "messages": messages_result.data or []
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve session: {str(e)}")


@router.get("/chat/sessions")
async def list_sessions(
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client),
    limit: int = 20,
    offset: int = 0
):
    """List all conversation sessions for the user."""
    try:
        result = supabase.table("conversation_sessions").select("*").eq(
            "user_id", user_id
        ).order("last_activity", desc=True).range(offset, offset + limit - 1).execute()
        
        return {
            "sessions": result.data or [],
            "total": len(result.data or [])
        }
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.delete("/chat/sessions/{session_id}")
async def delete_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """Delete a conversation session and all its messages."""
    try:
        # Verify ownership
        session_result = supabase.table("conversation_sessions").select("user_id").eq(
            "id", session_id
        ).execute()
        
        if not session_result.data or session_result.data[0]["user_id"] != user_id:
            raise HTTPException(status_code=403, detail="Unauthorized")
        
        # Delete messages first (cascade)
        supabase.table("conversation_messages").delete().eq(
            "session_id", session_id
        ).execute()
        
        # Delete session
        supabase.table("conversation_sessions").delete().eq(
            "id", session_id
        ).execute()
        
        return {"success": True, "message": "Session deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")
