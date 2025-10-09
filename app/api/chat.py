from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from supabase import create_client, Client
from app.core.config import SUPABASE_URL, SUPABASE_KEY
from app.services.open_router import get_chat_completion

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequestBody(BaseModel):
    messages: List[ChatMessage]
    note_ids: Optional[List[str]] = None
    model: Optional[str] = None

def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

@router.post("/chat")
async def chat(
    body: ChatRequestBody,
    supabase: Client = Depends(get_supabase_client)
):
        user_id = "..."  # Replace with actual user ID from auth

    context = ""
    sources = []

    if body.note_ids:
        try:
            data, count = supabase.table("notes").select("id,title,summary,content,extracted_text").in_("id", body.note_ids).eq("user_id", user_id).execute()
            notes = data[1]

            if notes:
                note_snippets = []
                for i, note in enumerate(notes[:4]):
                    body_text = note.get("extracted_text") or note.get("content") or ""
                    trimmed = body_text[:2000] + "..." if len(body_text) > 2000 else body_text
                    lines = [f"Note {i + 1}: {note.get('title')}"]
                    if note.get("summary"):
                        lines.append(f"Summary: {note.get('summary')}")
                    if trimmed:
                        lines.append(f"Content:\n{trimmed}")
                    note_snippets.append("\n".join(lines))
                
                context = "\n\n".join(note_snippets)
                sources = [{"id": note["id"], "title": note["title"]} for note in notes]

        except Exception as e:
            raise HTTPException(status_code=500, detail="Failed to load notes for context")

    system_prompt_parts = [
        "You are Study Sharper’s AI assistant.",
        "Use the provided notes context when answering. If the notes do not contain the answer, respond honestly and suggest helpful next steps.",
        "Return well-structured, clear explanations tailored to students.",
    ]
    if context:
        system_prompt_parts.append(f"Notes context:\n{context}")

    system_prompt = "\n\n".join(system_prompt_parts)

    messages = [{"role": "system", "content": system_prompt}] + [msg.dict() for msg in body.messages]

    try:
        completion_message = get_chat_completion(messages, body.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"message": completion_message, "sources": sources}
