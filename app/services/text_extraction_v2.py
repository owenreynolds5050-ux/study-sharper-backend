# app/services/text_extraction.py
import io
import re
import gc
import psutil
from typing import Dict, Any
from pypdf import PdfReader
from pdfminer.high_level import extract_text as pdfminer_extract
from docx import Document
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

def extract_text_from_file(file_data: bytes, file_type: str, file_id: str) -> Dict[str, Any]:
    """
    Extract text from file using cascading fallback method.
    Priority: Direct extraction → PDF parser → OCR
    
    Returns:
        dict: {
            "text": extracted text,
            "method": extraction method used,
            "has_images": whether file contains images (for PDFs)
        }
    """
    
    if file_type == "txt":
        return {
            "text": file_data.decode("utf-8", errors="ignore"),
            "method": "direct",
            "has_images": False
        }
    
    if file_type == "md":
        return {
            "text": file_data.decode("utf-8", errors="ignore"),
            "method": "direct",
            "has_images": False
        }
    
    if file_type == "docx":
        return extract_from_docx(file_data)
    
    if file_type == "pdf":
        return extract_from_pdf(file_data, file_id)
    
    raise ValueError(f"Unsupported file type: {file_type}")

def extract_from_docx(file_data: bytes) -> Dict[str, Any]:
    """Extract text from DOCX and convert to markdown"""
    doc = Document(io.BytesIO(file_data))
    
    markdown_lines = []
    
    for paragraph in doc.paragraphs:
        text = paragraph.text.strip()
        
        if not text:
            continue
        
        # Convert headings to markdown
        if paragraph.style.name.startswith('Heading'):
            level = int(paragraph.style.name.replace('Heading ', ''))
            markdown_lines.append(f"{'#' * level} {text}")
        else:
            markdown_lines.append(text)
        
        markdown_lines.append("")  # Add blank line
    
    text = "\n".join(markdown_lines)
    normalized = normalize_to_markdown(text)
    
    return {
        "text": normalized,
        "method": "docx",
        "has_images": False
    }

def extract_from_pdf(file_data: bytes, file_id: str) -> Dict[str, Any]:
    """
    Extract text from PDF using cascading method.
    Tier 1: PyPDF → Tier 2: pdfminer → Tier 3: OCR
    """
    
    # Tier 1: Try PyPDF (fastest)
    try:
        result = extract_with_pypdf(file_data)
        if result["text"] and len(result["text"].strip()) > 50:
            print(f"✓ File {file_id}: Extracted with PyPDF")
            return result
    except Exception as e:
        print(f"PyPDF failed for {file_id}: {e}")
    
    # Tier 2: Try pdfminer (more robust)
    try:
        result = extract_with_pdfminer(file_data)
        if result["text"] and len(result["text"].strip()) > 50:
            print(f"✓ File {file_id}: Extracted with pdfminer")
            return result
    except Exception as e:
        print(f"pdfminer failed for {file_id}: {e}")
    
    # Tier 3: Try OCR (slowest, most resource-intensive)
    try:
        print(f"⚠ File {file_id}: Attempting OCR (scanned document)")
        result = extract_text_with_ocr(file_data, file_id)
        return result
    except Exception as e:
        print(f"OCR failed for {file_id}: {e}")
        raise ValueError("Could not extract text from PDF. File may be corrupted or empty.")

def extract_with_pypdf(file_data: bytes) -> Dict[str, Any]:
    """Extract text using PyPDF"""
    pdf = PdfReader(io.BytesIO(file_data))
    
    text_parts = []
    has_images = False
    
    for page in pdf.pages:
        # Check for images
        if '/XObject' in page['/Resources']:
            xobject = page['/Resources']['/XObject'].get_object()
            for obj in xobject:
                if xobject[obj]['/Subtype'] == '/Image':
                    has_images = True
        
        # Extract text
        text = page.extract_text()
        if text:
            text_parts.append(text)
    
    combined_text = "\n\n".join(text_parts)
    normalized = normalize_to_markdown(combined_text)
    
    return {
        "text": normalized,
        "method": "pypdf",
        "has_images": has_images
    }

def extract_with_pdfminer(file_data: bytes) -> Dict[str, Any]:
    """Extract text using pdfminer.six"""
    text = pdfminer_extract(io.BytesIO(file_data))
    normalized = normalize_to_markdown(text)
    
    # Check if PDF likely has images (pdfminer doesn't easily detect this)
    # Simple heuristic: if text is very sparse, likely has images
    has_images = len(normalized.strip()) < 100
    
    return {
        "text": normalized,
        "method": "pdfminer",
        "has_images": has_images
    }

def extract_text_with_ocr(file_data: bytes, file_id: str) -> Dict[str, Any]:
    """
    Extract text from scanned PDF using OCR.
    MEMORY INTENSIVE - Limited to 2 concurrent jobs by job queue.
    """
    
    # Check file size (max 5MB for OCR)
    if len(file_data) > 5 * 1024 * 1024:
        raise ValueError("File too large for OCR (max 5MB)")
    
    try:
        # Convert PDF to images (limit pages)
        images = convert_from_bytes(
            file_data,
            dpi=200,  # Balance between quality and memory
            fmt='jpeg',  # Less memory than PNG
            thread_count=1,  # Single-threaded to limit memory
            first_page=1,
            last_page=10  # Max 10 pages
        )
        
        if len(images) > 10:
            print(f"⚠ File {file_id}: Truncated to 10 pages for OCR")
            images = images[:10]
        
        text_parts = []
        memory_limit_hit = False
        
        # Process in batches of 2 to manage memory
        batch_size = 2
        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            
            for page_num, image in enumerate(batch, start=i + 1):
                try:
                    # Run OCR
                    text = pytesseract.image_to_string(image)
                    if text.strip():
                        text_parts.append(f"--- Page {page_num} ---\n{text}")
                except Exception as e:
                    print(f"OCR failed on page {page_num}: {e}")
                    text_parts.append(f"--- Page {page_num} ---\n[OCR failed]")
                finally:
                    del image
                    gc.collect()
                    memory_usage = psutil.virtual_memory().percent
                    if memory_usage > 80:
                        print(f"⚠ File {file_id}: Stopping OCR early due to high memory usage ({memory_usage:.1f}% used)")
                        memory_limit_hit = True
                        break
            
            # Clear batch from memory
            del batch
            gc.collect()
            if memory_limit_hit:
                break

        # Clear all images
        del images
        gc.collect()
        
        combined_text = "\n\n".join(text_parts)
        normalized = normalize_to_markdown(combined_text)
        
        return {
            "text": normalized,
            "method": "ocr",
            "has_images": True
        }
        
    except Exception as e:
        gc.collect()  # Ensure cleanup on error
        raise

def normalize_to_markdown(text: str) -> str:
    """
    Normalize extracted text to clean markdown format.
    Removes excessive whitespace and standardizes formatting.
    """
    
    # Remove excessive newlines (3+ → 2)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Remove trailing/leading whitespace per line
    lines = [line.rstrip() for line in text.split('\n')]
    text = '\n'.join(lines)
    
    # Collapse multiple spaces to single space
    text = re.sub(r' {2,}', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text
