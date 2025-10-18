from pypdf import PdfReader
import docx
import io
import re
import gc
from typing import Optional, Tuple
import logging
from pdfminer.high_level import extract_text as pdfminer_extract_text
from pdfminer.pdfparser import PDFSyntaxError
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

# Set up logging
logger = logging.getLogger(__name__)

# Constants
MIN_TEXT_LENGTH = 50  # Minimum characters to consider extraction successful
MAX_OCR_FILE_SIZE = 5 * 1024 * 1024  # 5MB limit for OCR
MAX_OCR_PAGES = 20  # Maximum pages to OCR
OCR_BATCH_SIZE = 5  # Process pages in batches to manage memory

def normalize_to_markdown(text: str) -> str:
    """
    Normalize extracted text to clean markdown format.
    
    Args:
        text: Raw extracted text
        
    Returns:
        Cleaned markdown text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace while preserving intentional line breaks
    # Replace 3+ newlines with 2 newlines (paragraph break)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing/leading whitespace from each line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Remove excessive spaces (2+ spaces become 1)
    text = re.sub(r' {2,}', ' ', text)
    
    # Ensure consistent paragraph breaks
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()

def extract_pdf_text_pypdf(buffer: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract text from PDF using PyPDF (primary method).
    
    Args:
        buffer: Raw PDF file bytes
        
    Returns:
        Tuple of (extracted_text, error_message)
    """
    try:
        pdf_file = io.BytesIO(buffer)
        pdf_reader = PdfReader(pdf_file)
        
        if len(pdf_reader.pages) == 0:
            return None, "PDF has no pages"
        
        text_parts = []
        for page_num, page in enumerate(pdf_reader.pages, start=1):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_parts.append(page_text)
            except Exception as page_error:
                logger.warning(f"Error extracting text from page {page_num}: {page_error}")
                continue
        
        if not text_parts:
            return None, "No text could be extracted from PDF pages"
            
        full_text = "\n\n".join(text_parts)
        normalized_text = normalize_to_markdown(full_text)
        
        # Check if extraction was meaningful (more than just whitespace/symbols)
        if len(normalized_text.strip()) < 10:
            return None, "Extracted text too short or empty"
        
        return normalized_text, None
        
    except Exception as e:
        logger.error(f"PyPDF extraction error: {e}")
        return None, f"PyPDF extraction failed: {str(e)}"

def extract_pdf_text_pdfminer(buffer: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract text from PDF using pdfminer.six (secondary method).
    
    Args:
        buffer: Raw PDF file bytes
        
    Returns:
        Tuple of (extracted_text, error_message)
    """
    try:
        pdf_file = io.BytesIO(buffer)
        text = pdfminer_extract_text(pdf_file)
        
        if not text or len(text.strip()) < MIN_TEXT_LENGTH:
            return None, f"Extracted text too short: {len(text.strip()) if text else 0} characters"
        
        normalized_text = normalize_to_markdown(text)
        return normalized_text, None
        
    except PDFSyntaxError as e:
        logger.error(f"PDFMiner syntax error: {e}")
        return None, f"PDF syntax error: {str(e)}"
    except Exception as e:
        logger.error(f"PDFMiner extraction error: {e}")
        return None, f"PDFMiner extraction failed: {str(e)}"

def extract_pdf_text_ocr(buffer: bytes, file_size: int) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Extract text from PDF using OCR (tertiary method for scanned documents).
    Includes memory optimization and batch processing.
    
    Args:
        buffer: Raw PDF file bytes
        file_size: Size of the file in bytes
        
    Returns:
        Tuple of (extracted_text, error_message, ocr_used)
    """
    # Check file size before attempting OCR
    if file_size > MAX_OCR_FILE_SIZE:
        error_msg = f"File too large for OCR processing ({file_size / 1024 / 1024:.1f}MB). Please upload a text-based PDF or smaller file (max 5MB for OCR)."
        logger.warning(error_msg)
        return None, error_msg, False
    
    try:
        logger.info(f"Starting OCR extraction for {file_size / 1024:.1f}KB file")
        
        # Convert PDF to images (limit to MAX_OCR_PAGES)
        try:
            images = convert_from_bytes(
                buffer,
                first_page=1,
                last_page=MAX_OCR_PAGES,
                dpi=200,  # Balance between quality and memory
                fmt='jpeg',  # JPEG uses less memory than PNG
                thread_count=1  # Single thread to control memory
            )
            logger.info(f"Converted PDF to {len(images)} images")
        except Exception as convert_error:
            logger.error(f"PDF to image conversion failed: {convert_error}")
            return None, f"Failed to convert PDF to images: {str(convert_error)}", False
        
        if not images:
            return None, "No images could be extracted from PDF", False
        
        # Process images in batches to manage memory
        all_text_parts = []
        total_images = len(images)
        
        for batch_start in range(0, total_images, OCR_BATCH_SIZE):
            batch_end = min(batch_start + OCR_BATCH_SIZE, total_images)
            batch_images = images[batch_start:batch_end]
            
            logger.info(f"Processing OCR batch {batch_start + 1}-{batch_end} of {total_images}")
            
            # OCR each image in the batch
            for idx, image in enumerate(batch_images, start=batch_start + 1):
                try:
                    # Perform OCR
                    page_text = pytesseract.image_to_string(image, lang='eng')
                    
                    if page_text and page_text.strip():
                        all_text_parts.append(f"--- Page {idx} ---\n{page_text.strip()}")
                    
                    # Clear image from memory
                    image.close()
                    del image
                    
                except Exception as ocr_error:
                    logger.warning(f"OCR failed for page {idx}: {ocr_error}")
                    continue
            
            # Clear batch from memory
            del batch_images
            gc.collect()  # Hint to garbage collector
        
        # Clear all images from memory
        del images
        gc.collect()
        
        if not all_text_parts:
            return None, "OCR completed but no text could be extracted", True
        
        # Combine all page text
        full_text = "\n\n".join(all_text_parts)
        normalized_text = normalize_to_markdown(full_text)
        
        if len(normalized_text.strip()) < MIN_TEXT_LENGTH:
            return None, f"OCR extracted text too short: {len(normalized_text.strip())} characters", True
        
        logger.info(f"OCR extraction successful: {len(normalized_text)} characters from {len(all_text_parts)} pages")
        return normalized_text, None, True
        
    except Exception as e:
        logger.exception(f"OCR extraction error: {e}")
        # Force garbage collection on error
        gc.collect()
        return None, f"OCR extraction failed: {str(e)}", False

def extract_pdf_text(buffer: bytes, file_size: Optional[int] = None) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Extract text from PDF file bytes with cascading fallback.
    Tries PyPDF → pdfminer.six → OCR in sequence.
    
    Args:
        buffer: Raw PDF file bytes
        file_size: Size of the file in bytes (required for OCR size check)
        
    Returns:
        Tuple of (extracted_text, extraction_method, ocr_used)
        extraction_method will be 'native_pdf', 'pdfminer', or 'ocr'
    """
    if file_size is None:
        file_size = len(buffer)
    
    # Try PyPDF first (primary method)
    text, error = extract_pdf_text_pypdf(buffer)
    if text and len(text.strip()) >= MIN_TEXT_LENGTH:
        logger.info("Successfully extracted PDF text using PyPDF")
        return text, 'native_pdf', False
    
    logger.warning(f"PyPDF extraction insufficient: {error}")
    
    # Try pdfminer.six (secondary method)
    text, error = extract_pdf_text_pdfminer(buffer)
    if text and len(text.strip()) >= MIN_TEXT_LENGTH:
        logger.info("Successfully extracted PDF text using pdfminer.six")
        return text, 'pdfminer', False
    
    logger.warning(f"PDFMiner extraction insufficient: {error}")
    
    # Try OCR (tertiary method for scanned documents)
    text, error, ocr_attempted = extract_pdf_text_ocr(buffer, file_size)
    if text:
        logger.info("Successfully extracted PDF text using OCR")
        return text, 'ocr', True
    
    # All methods failed
    if ocr_attempted:
        final_error = error or "All extraction methods failed including OCR"
    else:
        final_error = error or "All extraction methods failed. OCR was not attempted."
    
    logger.error(f"PDF extraction completely failed: {final_error}")
    return None, None, False

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
                # Preserve basic formatting if detectable
                if paragraph.style and paragraph.style.name.startswith('Heading'):
                    # Convert headings to markdown
                    level = paragraph.style.name.replace('Heading ', '')
                    if level.isdigit():
                        text = '#' * int(level) + ' ' + text
                text_parts.append(text)
        
        if not text_parts:
            logger.warning("No text could be extracted from DOCX")
            return None
            
        full_text = "\n\n".join(text_parts)
        normalized_text = normalize_to_markdown(full_text)
        return normalized_text
        
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
