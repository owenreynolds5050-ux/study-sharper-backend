# app/services/file_processor.py
import asyncio
from app.core.database import supabase
from app.core.websocket import ws_manager
from app.services.job_queue import JobType
import traceback
import hashlib

async def process_file(job_data: dict, job_type: JobType):
    """
    Main file processing function called by job queue.
    Routes to appropriate handler based on job type.
    """
    file_id = job_data["file_id"]
    user_id = job_data["user_id"]
    
    try:
        # Update file status to processing
        supabase.table("files").update({
            "processing_status": "processing"
        }).eq("id", file_id).execute()

        extraction_job_types = {
            JobType.TEXT_EXTRACTION,
            JobType.OCR,
            JobType.AUDIO_TRANSCRIPTION
        }

        initial_message = "Processing started..."
        if job_type in extraction_job_types:
            initial_message = "Extracting text..."
        elif job_type == JobType.EMBEDDING_GENERATION:
            initial_message = "Generating embeddings..."

        await ws_manager.send_file_update(user_id, file_id, {
            "status": "processing",
            "message": initial_message
        })

        # Route to appropriate processor
        if job_type == JobType.TEXT_EXTRACTION:
            await process_text_extraction(job_data)
            await ws_manager.send_file_update(user_id, file_id, {
                "status": "processing",
                "message": "Text extracted, generating embeddings..."
            })
        elif job_type == JobType.OCR:
            await process_ocr(job_data)
            await ws_manager.send_file_update(user_id, file_id, {
                "status": "processing",
                "message": "Text extracted, generating embeddings..."
            })
        elif job_type == JobType.AUDIO_TRANSCRIPTION:
            await process_audio(job_data)
            await ws_manager.send_file_update(user_id, file_id, {
                "status": "processing",
                "message": "Text extracted, generating embeddings..."
            })
        elif job_type == JobType.EMBEDDING_GENERATION:
            await process_embedding(job_data)

        # Mark as completed
        supabase.table("files").update({
            "processing_status": "completed"
        }).eq("id", file_id).execute()

        success_message = "Processing completed successfully"
        if job_type == JobType.EMBEDDING_GENERATION:
            success_message = "Complete"

        # Send success update
        await ws_manager.send_file_update(user_id, file_id, {
            "status": "completed",
            "message": success_message
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"Error processing file {file_id}: {error_msg}")
        print(traceback.format_exc())
        
        # Mark as failed
        supabase.table("files").update({
            "processing_status": "failed",
            "error_message": error_msg
        }).eq("id", file_id).execute()
        
        # Send error update
        await ws_manager.send_file_update(user_id, file_id, {
            "status": "failed",
            "message": f"Processing failed: {error_msg}"
        })
        
        raise

async def process_text_extraction(job_data: dict):
    """Extract text from PDF, DOCX, TXT, or MD files"""
    from app.services.text_extraction_v2 import extract_text_from_file
    
    file_id = job_data["file_id"]
    user_id = job_data["user_id"]
    storage_path = job_data["storage_path"]
    file_type = job_data["file_type"]
    
    # Download file from storage
    file_data = supabase.storage.from_("file-processing").download(storage_path)
    
    # Extract text using cascading method
    result = extract_text_from_file(file_data, file_type, file_id)
    
    # Check if PDF has images
    has_images = False
    original_preview_path = None
    
    if file_type == "pdf" and result.get("has_images"):
        has_images = True
        # Keep original file for preview
        original_preview_path = storage_path
    else:
        # Delete original file to save storage
        try:
            supabase.storage.from_("file-processing").remove([storage_path])
        except Exception as e:
            print(f"Warning: Could not delete file {storage_path}: {e}")
    
    # Update file record with extracted content
    supabase.table("files").update({
        "content": result["text"],
        "extraction_method": result["method"],
        "has_images": has_images,
        "original_preview_path": original_preview_path
    }).eq("id", file_id).execute()
    
    # Queue embedding generation
    from app.services.job_queue import job_queue, JobPriority
    await job_queue.add_job(
        job_type=JobType.EMBEDDING_GENERATION,
        job_data={"file_id": file_id, "user_id": user_id},
        priority=JobPriority.LOW
    )

async def process_ocr(job_data: dict):
    """Process scanned PDFs with OCR"""
    from app.services.text_extraction_v2 import extract_text_with_ocr
    
    file_id = job_data["file_id"]
    user_id = job_data["user_id"]
    storage_path = job_data["storage_path"]
    
    # Download file
    file_data = supabase.storage.from_("file-processing").download(storage_path)
    
    # Run OCR
    result = extract_text_with_ocr(file_data, file_id)
    
    # Keep original file for preview (OCR PDFs usually have images)
    supabase.table("files").update({
        "content": result["text"],
        "extraction_method": "ocr",
        "has_images": True,
        "original_preview_path": storage_path
    }).eq("id", file_id).execute()
    
    # Queue embedding generation
    from app.services.job_queue import job_queue, JobPriority
    await job_queue.add_job(
        job_type=JobType.EMBEDDING_GENERATION,
        job_data={"file_id": file_id, "user_id": user_id},
        priority=JobPriority.LOW
    )

async def process_audio(job_data: dict):
    """Transcribe audio files using Whisper"""
    from app.services.audio_transcription import transcribe_audio
    
    file_id = job_data["file_id"]
    user_id = job_data["user_id"]
    storage_path = job_data["storage_path"]
    
    # Download file
    file_data = supabase.storage.from_("file-processing").download(storage_path)
    
    # Transcribe
    transcript = await transcribe_audio(file_data)
    
    # Delete original audio file (save storage)
    try:
        supabase.storage.from_("file-processing").remove([storage_path])
    except Exception as e:
        print(f"Warning: Could not delete audio file {storage_path}: {e}")
    
    # Update file record
    supabase.table("files").update({
        "content": transcript,
        "extraction_method": "whisper"
    }).eq("id", file_id).execute()
    
    # Queue embedding generation
    from app.services.job_queue import job_queue, JobPriority
    await job_queue.add_job(
        job_type=JobType.EMBEDDING_GENERATION,
        job_data={"file_id": file_id, "user_id": user_id},
        priority=JobPriority.LOW
    )

async def process_embedding(job_data: dict):
    """Generate embeddings for file content"""
    from app.services.embedding_service import generate_embedding
    
    file_id = job_data["file_id"]
    user_id = job_data["user_id"]
    
    # Get file content
    file_result = supabase.table("files").select("title, content").eq("id", file_id).execute()
    
    if not file_result.data:
        raise ValueError(f"File {file_id} not found")
    
    file_data = file_result.data[0]
    
    # Combine title and content
    text = f"{file_data['title']}\n\n{file_data['content'] or ''}"
    
    # Limit to 8000 characters for performance
    if len(text) > 8000:
        text = text[:8000]
    
    # Generate embedding
    embedding = generate_embedding(text)
    
    # Calculate content hash
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    
    # Check if embedding exists
    existing = supabase.table("file_embeddings").select("id").eq("file_id", file_id).execute()
    
    if existing.data:
        # Update existing
        supabase.table("file_embeddings").update({
            "embedding": embedding,
            "content_hash": content_hash
        }).eq("file_id", file_id).execute()
    else:
        # Insert new
        supabase.table("file_embeddings").insert({
            "file_id": file_id,
            "user_id": user_id,
            "embedding": embedding,
            "content_hash": content_hash
        }).execute()
