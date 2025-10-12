from pypdf import PdfReader
import docx
import io
from typing import Optional
import logging

# Set up logging
logger = logging.getLogger(__name__)

def extract_pdf_text(buffer: bytes) -> Optional[str]:
    """
    Extract text from PDF file bytes.
    
    Args:
        buffer: Raw PDF file bytes
        
    Returns:
        Extracted text with page breaks, or None if extraction fails
    """
    try:
        pdf_file = io.BytesIO(buffer)
        pdf_reader = PdfReader(pdf_file)
        
        if len(pdf_reader.pages) == 0:
            logger.warning("PDF has no pages")
            return None
        
        text_parts = []
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    # Add page separator for better readability
                    text_parts.append(f"--- Page {page_num} ---\n{page_text}")
            except Exception as page_error:
                logger.warning(f"Error extracting text from page {page_num}: {page_error}")
                continue
        
        if not text_parts:
            logger.warning("No text could be extracted from PDF")
            return None
            
        full_text = "\n\n".join(text_parts)
        return full_text.strip()
        
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return None

def extract_docx_text(buffer: bytes) -> Optional[str]:
    """
    Extract text from DOCX file bytes.
    
    Args:
        buffer: Raw DOCX file bytes
        
    Returns:
        Extracted text with paragraph breaks, or None if extraction fails
    """
    try:
        docx_file = io.BytesIO(buffer)
        doc = docx.Document(docx_file)
        
        text_parts = []
        for paragraph in doc.paragraphs:
            text = paragraph.text.strip()
            if text:  # Only add non-empty paragraphs
                text_parts.append(text)
        
        if not text_parts:
            logger.warning("No text could be extracted from DOCX")
            return None
            
        full_text = "\n\n".join(text_parts)
        return full_text.strip()
        
    except Exception as e:
        logger.error(f"DOCX extraction error: {e}")
        return None

def get_file_type_from_extension(filename: str) -> Optional[str]:
    """
    Determine file type from filename extension.
    
    Args:
        filename: Name of the file
        
    Returns:
        File type ('pdf', 'docx', etc.) or None if unsupported
    """
    if not filename:
        return None
        
    extension = filename.lower().split('.')[-1]
    
    file_type_map = {
        'pdf': 'pdf',
        'docx': 'docx',
        'doc': 'docx',  # Treat .doc as .docx for now
    }
    
    return file_type_map.get(extension)

def extract_text(buffer: bytes, filename: str) -> Optional[str]:
    """
    Main text extraction function that routes to appropriate extractor.
    
    Args:
        buffer: Raw file bytes
        filename: Name of the file (used to determine type)
        
    Returns:
        Extracted text or None if extraction fails
    """
    file_type = get_file_type_from_extension(filename)
    
    if file_type == 'pdf':
        return extract_pdf_text(buffer)
    elif file_type == 'docx':
        return extract_docx_text(buffer)
    else:
        logger.warning(f"Unsupported file type for: {filename}")
        return None
