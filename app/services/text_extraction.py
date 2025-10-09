import PyPDF2
import docx
import io

def extract_pdf_text(buffer: bytes) -> str:
    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(buffer))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()
        return text
    except Exception as e:
        print(f"Error extracting PDF text: {e}")
        return None

def extract_docx_text(buffer: bytes) -> str:
    try:
        doc = docx.Document(io.BytesIO(buffer))
        text = ""
        for para in doc.paragraphs:
            text += para.text + "\n"
        return text
    except Exception as e:
        print(f"Error extracting DOCX text: {e}")
        return None
