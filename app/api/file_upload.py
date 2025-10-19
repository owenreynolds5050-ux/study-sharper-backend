# app/api/file_upload.py
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from typing import Optional, List
from app.core.auth import get_current_user
from app.services.job_queue import job_queue, JobType, JobPriority
from app.services.quota_service import check_upload_quota, increment_upload_count, get_file_size_limit
from app.core.database import supabase
import uuid
import json

router = APIRouter()

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    'application/pdf': 'pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
    'text/plain': 'txt',
    'text/markdown': 'md',
    'audio/mpeg': 'audio',
    'audio/wav': 'audio',
    'audio/mp4': 'audio',
    'audio/x-m4a': 'audio',
    'audio/ogg': 'audio'
}

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    user = Depends(get_current_user)
):
    """Upload a single file and queue for processing"""
    
    # Validate file type
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")
    
    file_type = ALLOWED_MIME_TYPES[file.content_type]
    
    # Read file
    contents = await file.read()
    file_size = len(contents)
    
    # Get user's quota info to check premium status
    from app.services.quota_service import get_or_create_quota
    quota = await get_or_create_quota(user['id'])
    is_premium = quota.get('is_premium', False)
    
    # Check file size limit
    max_size = get_file_size_limit(is_premium, file_type)
    if file_size > max_size:
        max_mb = max_size / (1024 * 1024)
        raise HTTPException(400, f"File too large. Maximum size: {max_mb:.0f}MB")
    
    # Check quota (daily uploads and storage)
    try:
        await check_upload_quota(user['id'], file_size)
    except HTTPException as e:
        raise e
    
    # Generate IDs
    file_id = str(uuid.uuid4())
    storage_path = f"{user['id']}/{file_id}"
    
    # Upload to storage
    try:
        supabase.storage.from_("file-processing").upload(
            storage_path,
            contents,
            {"content-type": file.content_type}
        )
    except Exception as e:
        raise HTTPException(500, f"Storage upload failed: {str(e)}")
    
    # Create file record
    file_record = {
        "id": file_id,
        "user_id": user['id'],
        "folder_id": folder_id,
        "title": title or file.filename,
        "original_filename": file.filename,
        "file_type": file_type,
        "file_size_bytes": file_size,
        "processing_status": "pending"
    }
    
    result = supabase.table("files").insert(file_record).execute()
    
    # Update quota
    await increment_upload_count(user['id'], file_size)
    
    # Queue for processing
    job_type = JobType.AUDIO_TRANSCRIPTION if file_type == 'audio' else JobType.TEXT_EXTRACTION
    
    try:
        await job_queue.add_job(
            job_type=job_type,
            job_data={
                "file_id": file_id,
                "user_id": user['id'],
                "storage_path": storage_path,
                "file_type": file_type
            },
            priority=JobPriority.NORMAL
        )
    except MemoryError as e:
        # If memory is too high, still return success but warn user
        return {
            "success": True,
            "file": result.data[0],
            "warning": "Server is under heavy load. Your file will be processed soon."
        }
    
    return {
        "success": True,
        "file": result.data[0],
        "message": "File uploaded and queued for processing"
    }

@router.post("/upload-bulk")
async def upload_bulk_files(
    files: List[UploadFile] = File(...),
    folder_id: Optional[str] = Form(None),
    user = Depends(get_current_user)
):
    """Upload multiple files at once"""
    
    if len(files) > 20:
        raise HTTPException(400, "Maximum 20 files per bulk upload")
    
    uploaded_files = []
    errors = []
    
    for file in files:
        try:
            result = await upload_file(file=file, title=None, folder_id=folder_id, user=user)
            uploaded_files.append(result["file"])
        except HTTPException as e:
            errors.append({
                "filename": file.filename,
                "error": e.detail
            })
        except Exception as e:
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })
    
    return {
        "success": len(uploaded_files) > 0,
        "uploaded": uploaded_files,
        "uploaded_count": len(uploaded_files),
        "errors": errors,
        "error_count": len(errors)
    }

@router.post("/upload-folder")
async def upload_folder(
    files: List[UploadFile] = File(...),
    folder_structure: str = Form(...),
    parent_folder_id: Optional[str] = Form(None),
    user = Depends(get_current_user)
):
    """
    Upload multiple files with folder structure preserved.
    
    folder_structure should be JSON string like:
    {
        "folders": ["folder1", "folder1/subfolder"],
        "files": [
            {"index": 0, "folder_path": "folder1", "title": "file1.pdf"},
            {"index": 1, "folder_path": "folder1/subfolder", "title": "file2.txt"}
        ]
    }
    """
    
    try:
        structure = json.loads(folder_structure)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid folder_structure JSON")
    
    created_folders = {}
    uploaded_files = []
    
    # Create folder hierarchy
    for folder_path in structure.get('folders', []):
        parts = folder_path.split('/')
        current_parent = parent_folder_id
        current_path = ""
        
        for part in parts:
            current_path = f"{current_path}/{part}" if current_path else part
            
            if current_path in created_folders:
                current_parent = created_folders[current_path]
                continue
            
            # Calculate depth
            depth = len(parts) - 1
            if depth > 3:
                raise HTTPException(400, f"Folder depth exceeds maximum (3 levels): {folder_path}")
            
            # Create folder
            folder_result = supabase.table("file_folders").insert({
                "user_id": user["id"],
                "name": part,
                "parent_folder_id": current_parent,
                "depth": depth
            }).execute()
            
            folder_id = folder_result.data[0]["id"]
            created_folders[current_path] = folder_id
            current_parent = folder_id
    
    # Upload files to respective folders
    for file_info in structure.get('files', []):
        file_index = file_info['index']
        folder_path = file_info.get('folder_path')
        title = file_info.get('title')
        
        if file_index >= len(files):
            continue
        
        target_folder_id = created_folders.get(folder_path, parent_folder_id)
        
        try:
            result = await upload_file(
                file=files[file_index],
                title=title,
                folder_id=target_folder_id,
                user=user
            )
            uploaded_files.append(result["file"])
        except Exception as e:
            print(f"Error uploading {files[file_index].filename}: {e}")
    
    return {
        "success": True,
        "folders_created": len(created_folders),
        "files_uploaded": len(uploaded_files),
        "folders": list(created_folders.values()),
        "files": uploaded_files
    }

@router.post("/upload-youtube")
async def upload_youtube_transcript(
    url: str = Form(...),
    title: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    user = Depends(get_current_user)
):
    """Upload YouTube video transcript via n8n workflow"""
    from app.services.youtube_transcript import fetch_youtube_transcript
    
    # Check quota
    await check_upload_quota(user['id'], 0)  # YouTube transcripts don't count toward storage
    
    # Fetch transcript from n8n workflow
    try:
        transcript_data = await fetch_youtube_transcript(url)
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch YouTube transcript: {str(e)}")
    
    file_id = str(uuid.uuid4())
    
    # Create file record with transcript
    file_data = {
        "id": file_id,
        "user_id": user['id'],
        "folder_id": folder_id,
        "title": title or transcript_data.get('title', 'YouTube Transcript'),
        "original_filename": url,
        "file_type": "youtube",
        "content": transcript_data['transcript'],
        "processing_status": "completed",
        "extraction_method": "youtube"
    }
    
    result = supabase.table("files").insert(file_data).execute()
    
    # Queue embedding generation
    await job_queue.add_job(
        job_type=JobType.EMBEDDING_GENERATION,
        job_data={"file_id": file_id, "user_id": user['id']},
        priority=JobPriority.LOW
    )
    
    await increment_upload_count(user['id'], 0)
    
    return {
        "success": True,
        "file": result.data[0]
    }

@router.post("/files/{file_id}/retry")
async def retry_processing(
    file_id: str,
    user = Depends(get_current_user)
):
    """Retry processing a failed file"""
    # Get file
    file_result = supabase.table("files").select("*").eq("id", file_id).eq("user_id", user["id"]).execute()
    
    if not file_result.data:
        raise HTTPException(404, "File not found")
    
    file_data = file_result.data[0]
    
    if file_data["processing_status"] not in ["failed", "pending"]:
        raise HTTPException(400, "File is not in a retriable state")
    
    # Reset status
    supabase.table("files").update({
        "processing_status": "pending",
        "error_message": None
    }).eq("id", file_id).execute()
    
    # Re-queue
    job_type = JobType.AUDIO_TRANSCRIPTION if file_data["file_type"] == "audio" else JobType.TEXT_EXTRACTION
    
    await job_queue.add_job(
        job_type=job_type,
        job_data={
            "file_id": file_id,
            "user_id": user["id"],
            "storage_path": file_data.get("original_preview_path", f"{user['id']}/{file_id}"),
            "file_type": file_data["file_type"]
        },
        priority=JobPriority.HIGH  # Retries get higher priority
    )
    
    return {
        "success": True,
        "message": "File requeued for processing"
    }
