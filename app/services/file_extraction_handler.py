"""
Background job handler for file extraction with LangChain
Processes TEXT_EXTRACTION jobs from the job queue

File: app/services/file_extraction_handler.py (NEW)
"""

import logging
import uuid
from pathlib import Path
import numpy as np

from app.core.database import supabase
from app.services.langchain_processor import langchain_processor

logger = logging.getLogger(__name__)


async def process_file_extraction_job(job_data: dict) -> dict:
    """
    Process a file extraction job from the queue.
    
    Called by: app/services/job_queue.py when TEXT_EXTRACTION job is processed
    
    Args:
        job_data: Dictionary with keys:
            - file_id: UUID of file record
            - user_id: UUID of user
            - file_path: Path to temporary file
            - file_type: File extension (pdf, docx, txt)
            - original_filename: Original filename
    
    Returns:
        Dictionary with:
            - status: "success" | "error"
            - message: Status message
            - chunk_count: Number of chunks created (if success)
    """
    
    file_id = job_data.get("file_id")
    user_id = job_data.get("user_id")
    file_path = job_data.get("file_path")
    file_type = job_data.get("file_type")
    original_filename = job_data.get("original_filename")
    
    logger.info(
        f"Starting file extraction: file_id={file_id}, type={file_type}, "
        f"user_id={user_id}"
    )
    
    try:
        # Step 1: Process file with LangChain
        logger.debug(f"Processing file with LangChain: {file_path}")
        result = await langchain_processor.process_file(
            file_path=file_path,
            file_type=file_type,
            file_id=file_id,
            user_id=user_id,
        )
        
        if result["status"] != "success":
            error_msg = result.get("error_message", "Unknown error")
            logger.error(f"LangChain processing failed: {error_msg}")
            raise Exception(error_msg)
        
        full_text = result["full_text"]
        chunks = result["chunks"]
        embeddings = result["embeddings"]
        content_hash = result["content_hash"]
        
        logger.info(
            f"LangChain processing complete: {len(chunks)} chunks, "
            f"{len(full_text)} characters"
        )
        
        # Step 2: Update files table with extracted text
        logger.debug(f"Updating files table for {file_id}")
        
        # Convert full_text to markdown for Tiptap display
        # (already plain text, so just store as-is)
        files_update = supabase.table("files").update({
            "extracted_text": full_text,
            "content": full_text,  # For Tiptap display
            "processing_status": "completed"
        }).eq("id", file_id).execute()
        
        if not files_update.data:
            logger.warning(f"Failed to update files table for {file_id}")
        
        # Step 3: Store chunks in file_chunks table
        logger.debug(f"Storing {len(chunks)} chunks in database")
        
        chunks_to_insert = []
        for idx, chunk in enumerate(chunks):
            chunks_to_insert.append({
                "id": str(uuid.uuid4()),
                "file_id": file_id,
                "user_id": user_id,
                "chunk_index": idx,
                "content": chunk.page_content,
                "start_position": 0,  # Could calculate real positions if needed
                "end_position": len(chunk.page_content),
                "embedding": embeddings[idx],  # pgvector handles serialization
            })
        
        # Insert chunks in batches (Supabase has limits)
        batch_size = 50
        for i in range(0, len(chunks_to_insert), batch_size):
            batch = chunks_to_insert[i : i + batch_size]
            logger.debug(f"Inserting chunk batch {i//batch_size + 1}")
            
            chunks_result = supabase.table("file_chunks").insert(batch).execute()
            
            if not chunks_result.data:
                logger.warning(f"Failed to insert chunk batch at index {i}")
        
        logger.info(f"Successfully stored {len(chunks_to_insert)} chunks")
        
        # Step 4: Store file-level embedding (average of all chunk embeddings)
        logger.debug(f"Computing and storing file-level embedding")
        
        if embeddings:
            file_embedding = np.mean(embeddings, axis=0).tolist()
        else:
            file_embedding = [0.0] * 384  # Default 384-dim zero vector
        
        embedding_update = supabase.table("file_embeddings").update({
            "embedding": file_embedding,
            "content_hash": content_hash,
            "model": "sentence-transformers/all-MiniLM-L6-v2",
        }).eq("file_id", file_id).execute()
        
        if not embedding_update.data:
            logger.warning(f"Failed to update file_embeddings for {file_id}")
        
        # Step 5: Clean up temporary file
        try:
            temp_path = Path(file_path)
            if temp_path.exists():
                temp_path.unlink()
                logger.debug(f"Cleaned up temporary file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up temporary file: {e}")
        
        logger.info(
            f"File extraction complete: file_id={file_id}, "
            f"chunks={len(chunks)}, chars={len(full_text)}"
        )
        
        return {
            "status": "success",
            "message": f"Successfully extracted {len(chunks)} chunks from {original_filename}",
            "chunk_count": len(chunks),
        }
        
    except Exception as e:
        logger.error(
            f"Error processing file {file_id}: {str(e)}", exc_info=True
        )
        
        # Update file status to failed
        try:
            supabase.table("files").update({
                "processing_status": "failed",
                "error_message": str(e),
            }).eq("id", file_id).execute()
            logger.info(f"Marked file {file_id} as failed in database")
        except Exception as update_err:
            logger.error(f"Failed to update file status: {update_err}")
        
        return {
            "status": "error",
            "message": str(e),
            "chunk_count": 0,
        }