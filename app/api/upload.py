from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from app.core.auth import get_current_user, get_supabase_client
from app.services.text_extraction import extract_pdf_text, extract_docx_text
import uuid

router = APIRouter()

@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    title: str = Form(None),
    skip_ai: bool = Form(False),
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

    # Extract text
    extracted_text = None
    if not skip_ai:
        if file.content_type == "application/pdf":
            extracted_text = extract_pdf_text(buffer)
        elif file.content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            extracted_text = extract_docx_text(buffer)

    note_content = extracted_text if extracted_text else "File uploaded successfully."

    # Upload file to storage
    try:
        supabase.storage.from_("notes-pdfs").upload(file_path, buffer, file_options={"content-type": file.content_type})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Save to database
    new_note = {
        "id": note_id,
        "user_id": user_id,
        "title": title if title else file.filename,
        "content": note_content,
        "file_path": file_path,
        "extracted_text": extracted_text,
        "file_size": len(buffer),
        "folder_id": folder_id,
    }

    try:
        response = supabase.table("notes").insert(new_note).execute()
    except Exception as e:
        # Clean up storage if db insert fails
        supabase.storage.from_("notes-pdfs").remove([file_path])
        raise HTTPException(status_code=500, detail=str(e))

    return {"success": True, "note": response.data[0]}
