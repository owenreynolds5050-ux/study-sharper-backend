"""
Job dispatcher - routes jobs to appropriate handlers
File: app/services/file_processor.py (NEW)
"""

import logging
from app.services.job_queue import JobType

logger = logging.getLogger(__name__)


async def process_file(job_data: dict, job_type: JobType):
    """
    Main dispatcher - routes jobs to specific handlers based on job type.
    
    Called by: app/services/job_queue.py in the worker loop
    
    Args:
        job_data: Dictionary with file_id, user_id, and type-specific data
        job_type: JobType enum value
    
    Returns:
        Handler result (varies by job type)
    
    Raises:
        ValueError: If job_type is unknown
        Exception: Propagates handler exceptions to job_queue
    """
    
    logger.info(f"Processing job: type={job_type}, file_id={job_data.get('file_id')}")
    
    try:
        if job_type == JobType.TEXT_EXTRACTION:
            from app.services.file_extraction_handler import process_file_extraction_job
            result = await process_file_extraction_job(job_data)
            logger.info(f"TEXT_EXTRACTION complete: {result}")
            return result
        
        elif job_type == JobType.EMBEDDING_GENERATION:
            from app.services.embedding_handler import process_embedding_job
            result = await process_embedding_job(job_data)
            logger.info(f"EMBEDDING_GENERATION complete: {result}")
            return result
        
        elif job_type == JobType.OCR:
            from app.services.ocr_handler import process_ocr_job
            result = await process_ocr_job(job_data)
            logger.info(f"OCR complete: {result}")
            return result
        
        elif job_type == JobType.AUDIO_TRANSCRIPTION:
            from app.services.audio_handler import process_audio_job
            result = await process_audio_job(job_data)
            logger.info(f"AUDIO_TRANSCRIPTION complete: {result}")
            return result
        
        else:
            raise ValueError(f"Unknown job type: {job_type}")
    
    except Exception as e:
        logger.error(f"Job processing failed: {e}", exc_info=True)
        raise