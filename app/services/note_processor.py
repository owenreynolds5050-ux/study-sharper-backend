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
from app.services.text_extraction import extract_pdf_text, extract_docx_text
from io import BytesIO

logger = logging.getLogger(__name__)


class NoteProcessingError(Exception):
    """Custom exception for note processing errors"""
    pass


async def process_note_extraction(
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
        extracted_text = None
        extraction_method = None
        ocr_used = False
        
        if file_extension == 'pdf':
            # Try PDF extraction with cascading fallback (PyPDF → pdfminer → OCR)
            file_size = len(file_data)
            extracted_text, extraction_method, ocr_used = extract_pdf_text(file_data, file_size)
            
            if extracted_text and extraction_method:
                logger.info(f"Successfully extracted {len(extracted_text)} chars using {extraction_method}")
                if ocr_used:
                    logger.info(f"OCR was required for this document")
            else:
                # All extraction methods failed
                raise NoteProcessingError(
                    "This PDF appears to be encrypted, corrupted, or contains no readable text. "
                    "Please try a different file or ensure the PDF is not password-protected."
                )
                
        elif file_extension in ['docx', 'doc']:
            # Try DOCX extraction
            extracted_text = extract_docx_text(file_data)
            if extracted_text:
                extraction_method = 'docx'
                logger.info(f"Successfully extracted {len(extracted_text)} chars using docx")
            else:
                raise NoteProcessingError(
                    "DOCX text extraction failed. The file may be corrupted or in an unsupported format."
                )
        else:
            raise NoteProcessingError(
                f"Unsupported file type: .{file_extension}. Please upload PDF or DOCX files only."
            )
        
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


async def retry_note_processing(
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
        return await process_note_extraction(
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
