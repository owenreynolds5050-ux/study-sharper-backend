"""
Note Processing Service
Handles the complete pipeline for processing uploaded notes:
- Downloads files from Supabase Storage
- Extracts text with cascading fallback methods
- Normalizes to markdown
- Updates database with results
- Manages file cleanup
"""

import logging
from typing import Optional, Dict, Any
from app.services.text_extraction_v2 import extract_text_from_file
from io import BytesIO

logger = logging.getLogger(__name__)


class NoteProcessingError(Exception):
    """Custom exception for note processing errors"""
    pass


def process_note_extraction(
    note_id: str,
    user_id: str,
    file_path: str,
    original_filename: str,
    supabase
) -> Dict[str, Any]:
    """
    Process a note file: download, extract text, update database.
    
    Args:
        note_id: UUID of the note
        user_id: UUID of the user
        file_path: Path to file in Supabase Storage
        original_filename: Original filename for determining file type
        supabase: Supabase client instance
        
    Returns:
        Dict with processing results: {
            'success': bool,
            'extracted_text': str or None,
            'extraction_method': str or None,
            'error_message': str or None
        }
    """
    
    result = {
        'success': False,
        'extracted_text': None,
        'extraction_method': None,
        'error_message': None
    }
    
    try:
        # Update status to 'processing'
        logger.info(f"Starting processing for note {note_id}")
        supabase.table("notes").update({
            "processing_status": "processing"
        }).eq("id", note_id).eq("user_id", user_id).execute()
        
        # Download file from Supabase Storage
        try:
            file_data = supabase.storage.from_("notes-pdfs").download(file_path)
            if not file_data:
                raise NoteProcessingError("Failed to download file from storage")
            logger.info(f"Downloaded file {file_path} ({len(file_data)} bytes)")
        except Exception as download_error:
            raise NoteProcessingError(f"Storage download failed: {str(download_error)}")
        
        # Determine file type and extract text
        file_extension = original_filename.lower().split('.')[-1]
        
        # Use unified extraction function
        result = extract_text_from_file(file_data, file_extension, note_id)
        
        extracted_text = result.get('text')
        extraction_method = result.get('method')
        ocr_used = extraction_method == 'ocr'
        
        if not extracted_text or len(extracted_text.strip()) < 10:
            raise NoteProcessingError(
                f"Could not extract readable text from {file_extension.upper()} file. "
                "The file may be encrypted, corrupted, or empty."
            )
        
        logger.info(f"Successfully extracted {len(extracted_text)} chars using {extraction_method}")
        
        if not extracted_text:
            raise NoteProcessingError("Text extraction returned empty result")
        
        # Update database with extracted text
        supabase.table("notes").update({
            "processing_status": "completed",
            "extracted_text": extracted_text,
            "content": extracted_text,  # Also update content field
            "extraction_method": extraction_method,
            "ocr_processed": ocr_used,  # Track if OCR was used
            "error_message": None
        }).eq("id", note_id).eq("user_id", user_id).execute()
        
        # Delete original file from storage after successful extraction
        try:
            supabase.storage.from_("notes-pdfs").remove([file_path])
            logger.info(f"Deleted original file {file_path} from storage")
        except Exception as cleanup_error:
            # Log but don't fail - file cleanup is not critical
            logger.warning(f"Failed to delete original file {file_path}: {cleanup_error}")
        
        result['success'] = True
        result['extracted_text'] = extracted_text
        result['extraction_method'] = extraction_method
        logger.info(f"Successfully processed note {note_id}")
        
    except NoteProcessingError as e:
        # Expected processing errors
        error_msg = str(e)
        logger.error(f"Processing failed for note {note_id}: {error_msg}")
        
        # Update database with error status
        try:
            supabase.table("notes").update({
                "processing_status": "failed",
                "error_message": error_msg
            }).eq("id", note_id).eq("user_id", user_id).execute()
        except Exception as db_error:
            logger.error(f"Failed to update error status in database: {db_error}")
        
        result['error_message'] = error_msg
        
    except Exception as e:
        # Unexpected errors
        error_msg = f"Unexpected error: {str(e)}"
        logger.exception(f"Unexpected error processing note {note_id}")
        
        # Update database with error status
        try:
            supabase.table("notes").update({
                "processing_status": "failed",
                "error_message": error_msg
            }).eq("id", note_id).eq("user_id", user_id).execute()
        except Exception as db_error:
            logger.error(f"Failed to update error status in database: {db_error}")
        
        result['error_message'] = error_msg
    
    return result


def retry_note_processing(
    note_id: str,
    user_id: str,
    supabase
) -> Dict[str, Any]:
    """
    Retry processing for a failed note.
    
    Args:
        note_id: UUID of the note
        user_id: UUID of the user
        supabase: Supabase client instance
        
    Returns:
        Dict with processing results
    """
    
    # Get note details
    try:
        response = supabase.table("notes").select(
            "file_path, original_filename, processing_status"
        ).eq("id", note_id).eq("user_id", user_id).execute()
        
        if not response.data or len(response.data) == 0:
            return {
                'success': False,
                'error_message': 'Note not found'
            }
        
        note = response.data[0]
        
        # Check if note has a file to process
        if not note.get('file_path'):
            return {
                'success': False,
                'error_message': 'Note has no file to process'
            }
        
        # Check if note is already completed
        if note.get('processing_status') == 'completed':
            return {
                'success': False,
                'error_message': 'Note already processed successfully'
            }
        
        # Process the note
        return process_note_extraction(
            note_id=note_id,
            user_id=user_id,
            file_path=note['file_path'],
            original_filename=note.get('original_filename', 'unknown.pdf'),
            supabase=supabase
        )
        
    except Exception as e:
        logger.exception(f"Error retrying note processing for {note_id}")
        return {
            'success': False,
            'error_message': f'Retry failed: {str(e)}'
        }
