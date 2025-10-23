"""
File Chat API - Conversational endpoint leveraging uploaded files.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

from app.core.auth import get_current_user, get_supabase_client
from app.services.ai_chat import retrieve_relevant_file_chunks
from app.services.open_router import get_chat_completion

router = APIRouter()


class FileChatRequest(BaseModel):
    session_id: Optional[str]
    message: str
    file_ids: Optional[List[str]] = None


class FileChatResponse(BaseModel):
    session_id: Optional[str]
    response: str
    sources: List[Dict[str, Any]]


@router.post("/chat/with-files", response_model=FileChatResponse)
async def chat_with_files(
    request: FileChatRequest,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    query = request.message.strip()

    # Step 1: Retrieve relevant chunks (optionally filtered by file_ids)
    chunk_results = await retrieve_relevant_file_chunks(
        user_id=user_id,
        query=query,
        supabase=supabase,
        top_k=5,
        file_ids=request.file_ids
    )

    system_message = chunk_results["system_message"]
    chunks = chunk_results["chunks"]

    # Step 2: Build Full Prompt
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

    # Step 3: Call OpenRouter
    response_text = get_chat_completion(messages, model="anthropic/claude-3.5-sonnet")

    # Step 4: Build Source Metadata for Response
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
        session_id=request.session_id,
        response=response_text.strip(),
        sources=sources
    )
