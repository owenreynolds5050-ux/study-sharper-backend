from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.core.auth import get_current_user, get_supabase_client
from app.services.note_processor import process_note_extraction, retry_note_processing
import uuid
import logging

router = APIRouter()

# Response models

logger = logging.getLogger(__name__)

class NoteStatusResponse(BaseModel):
    id: str
    processing_status: str
    extraction_method: Optional[str] = None
    error_message: Optional[str] = None

class ProcessResponse(BaseModel):
    success: bool
    message: str
    note_id: str

class OcrCheckResponse(BaseModel):
    needs_ocr: bool
    file_type: str
    message: Optional[str] = None

def background_process_note(note_id: str, user_id: str, file_path: str, original_filename: str, supabase):
    """Background task to process note extraction"""
    try:
        # Check if note still exists (user may have deleted it)
        check_response = supabase.table("notes").select("id").eq("id", note_id).eq("user_id", user_id).execute()
        if not check_response.data or len(check_response.data) == 0:
            logger.info(f"Note {note_id} was deleted, cancelling processing")
            return
        
        result = process_note_extraction(
            note_id=note_id,
            user_id=user_id,
            file_path=file_path,
            original_filename=original_filename,
            supabase=supabase
        )
        if result['success']:
            logger.info(f"Background processing completed for note {note_id}")
        else:
            logger.error(f"Background processing failed for note {note_id}: {result.get('error_message')}")
    except Exception as e:
        logger.exception(f"Background processing error for note {note_id}: {e}")

@router.post("/check-ocr", response_model=OcrCheckResponse)
async def check_if_ocr_needed(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Check if a file will require OCR processing.
    This allows frontend to show premium gate before upload.
    """
    try:
        # Only check PDFs (DOCX doesn't need OCR)
        if file.content_type != "application/pdf":
            return OcrCheckResponse(
                needs_ocr=False,
                file_type=file.content_type or "unknown",
                message="File type does not require OCR"
            )
        
        # Read first 500KB to check if PDF has extractable text
        buffer = await file.read(512000)  # 500KB sample
        await file.seek(0)  # Reset file pointer for potential upload
        
        # Try quick text extraction with PyPDF
        from pypdf import PdfReader
        from io import BytesIO
        
        try:
            pdf = PdfReader(BytesIO(buffer))
            
            # Check first 3 pages for text
            text_found = False
            pages_to_check = min(3, len(pdf.pages))
            
            for i in range(pages_to_check):
                page_text = pdf.pages[i].extract_text()
                if page_text and len(page_text.strip()) > 50:
                    text_found = True
                    break
            
            if text_found:
                return OcrCheckResponse(
                    needs_ocr=False,
                    file_type="application/pdf",
                    message="PDF contains extractable text"
                )
            else:
                return OcrCheckResponse(
                    needs_ocr=True,
                    file_type="application/pdf",
                    message="PDF appears to be scanned and requires OCR"
                )
                
        except Exception as e:
            logger.warning(f"Could not analyze PDF for OCR check: {e}")
            # If we can't determine, assume OCR might be needed
            return OcrCheckResponse(
                needs_ocr=True,
                file_type="application/pdf",
                message="Could not determine if OCR is needed"
            )
            
    except Exception as e:
        logger.exception(f"Error checking OCR requirement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
    
    # Initial note content
    note_content = "Processing..." if not should_skip_ai else "File uploaded successfully."
    
    # Initial processing status
    processing_status = "pending" if not should_skip_ai else "completed"

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
        "original_filename": file.filename,
        "extracted_text": None,  # Will be updated by background task
        "file_size_bytes": len(buffer),
        "folder_id": folder_id,
        "processing_status": processing_status,
        "extraction_method": None,
        "error_message": None,
        "ocr_processed": False,  # Will be updated if OCR is used
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
            background_process_note,
            note_id,
            user_id,
            file_path,
            file.filename,
            supabase
        )
        logger.info(f"Queued text extraction for note {note_id}")

    return {
        "success": True,
        "note": response.data[0],
        "processing": not should_skip_ai  # Indicates if background processing is happening
    }

@router.post("/notes/{note_id}/process", response_model=ProcessResponse)
async def process_note(
    note_id: str,
    background_tasks: BackgroundTasks,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Process or retry processing for a note.
    Downloads file from storage, extracts text, updates database.
    """
    try:
        # Get note details
        response = supabase.table("notes").select(
            "file_path, original_filename, processing_status"
        ).eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note = response.data[0]
        
        # Check if note has a file to process
        if not note.get('file_path'):
            raise HTTPException(status_code=400, detail="Note has no file to process")
        
        # Check if already processing
        if note.get('processing_status') == 'processing':
            return ProcessResponse(
                success=False,
                message="Note is already being processed",
                note_id=note_id
            )
        
        # Queue background processing
        background_tasks.add_task(
            background_process_note,
            note_id,
            user_id,
            note['file_path'],
            note.get('original_filename', 'unknown.pdf'),
            supabase
        )
        
        # Update status to pending
        supabase.table("notes").update({
            "processing_status": "pending"
        }).eq("id", note_id).eq("user_id", user_id).execute()
        
        logger.info(f"Queued processing for note {note_id}")
        
        return ProcessResponse(
            success=True,
            message="Processing started",
            note_id=note_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error processing note {note_id}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/notes/{note_id}/status", response_model=NoteStatusResponse)
async def get_note_status(
    note_id: str,
    user_id: str = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get processing status for a note.
    Lightweight endpoint for polling.
    """
    try:
        response = supabase.table("notes").select(
            "id, processing_status, extraction_method, error_message"
        ).eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail="Note not found")
        
        note = response.data[0]
        
        return NoteStatusResponse(
            id=note['id'],
            processing_status=note.get('processing_status', 'completed'),
            extraction_method=note.get('extraction_method'),
            error_message=note.get('error_message')
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting status for note {note_id}")
        raise HTTPException(status_code=500, detail=str(e))
