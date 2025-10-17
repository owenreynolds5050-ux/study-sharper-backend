from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from app.core.auth import get_current_user, get_supabase_client
from app.services.text_extraction import extract_pdf_text, extract_docx_text
import uuid
import logging

router = APIRouter()

logger = logging.getLogger(__name__)

async def process_file_extraction(note_id: str, file_content: bytes, content_type: str, user_id: str, supabase):
    """Background task to extract text from uploaded file"""
    try:
        extracted_text = None
        if content_type == "application/pdf":
            extracted_text = extract_pdf_text(file_content)
        elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            extracted_text = extract_docx_text(file_content)
        
        if extracted_text:
            # Update note with extracted text
            supabase.table("notes").update({
                "extracted_text": extracted_text,
                "content": extracted_text
            }).eq("id", note_id).eq("user_id", user_id).execute()
            logger.info(f"Extracted text for note {note_id}")
    except Exception as e:
        logger.error(f"Failed to extract text for note {note_id}: {e}")

@router.post("/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str = Form(None),
    skip_ai: bool = Form(False),
    skipAI: str = Form(None),
    folder_id: str = Form(None),
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):

    # Generate unique ID
    note_id = str(uuid.uuid4())
    file_extension = file.filename.split(".")[-1]
    file_path = f"{user_id}/{note_id}.{file_extension}"

    # Read file content
    buffer = await file.read()

    # Check if we should skip AI processing
    should_skip_ai = skip_ai or (skipAI and skipAI.lower() == 'true')
    
    # Initial note content (will be updated by background task if processing)
    note_content = "Processing..." if not should_skip_ai else "File uploaded successfully."

    # Ensure profile exists for this user (needed due to foreign key constraint)
    try:
        profile_response = supabase.table("profiles").select("id").eq("id", user_id).execute()
        if not profile_response.data:
            try:
                user_response = supabase.auth.admin.get_user_by_id(user_id)
                email = getattr(getattr(user_response, "user", None), "email", "") or ""
            except Exception as admin_error:
                logger.warning("Failed to fetch user info for %s: %s", user_id, admin_error)
                email = ""

            supabase.table("profiles").upsert({
                "id": user_id,
                "email": email,
            }).execute()
    except Exception as profile_error:
        logger.warning("Could not ensure profile exists for %s: %s", user_id, profile_error)

    # Upload file to storage
    try:
        supabase.storage.from_("notes-pdfs").upload(file_path, buffer, file_options={"content-type": file.content_type})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save to database with initial content
    new_note = {
        "id": note_id,
        "user_id": user_id,
        "title": title if title else file.filename,
        "content": note_content,
        "file_path": file_path,
        "extracted_text": None,  # Will be updated by background task
        "file_size": len(buffer),
        "folder_id": folder_id,
    }

    try:
        response = supabase.table("notes").insert(new_note).execute()
    except Exception as e:
        # Clean up storage if db insert fails
        supabase.storage.from_("notes-pdfs").remove([file_path])
        raise HTTPException(status_code=500, detail=str(e))
    
    # Queue background task for text extraction (non-blocking)
    if not should_skip_ai and file.content_type in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ]:
        background_tasks.add_task(
            process_file_extraction,
            note_id,
            buffer,
            file.content_type,
            user_id,
            supabase
        )
        logger.info(f"Queued text extraction for note {note_id}")

    return {
        "success": True,
        "note": response.data[0],
        "processing": not should_skip_ai  # Indicates if background processing is happening
    }
