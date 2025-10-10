import hashlib
import requests
from typing import List, Dict, Any
from app.core.config import OPENROUTER_API_KEY

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"


def get_embedding_for_text(text: str, model: str = None) -> Dict[str, Any]:
    """
    Generate embedding for text using OpenRouter API.
    
    Args:
        text: The text to embed
        model: Optional model name (defaults to text-embedding-3-small)
        
    Returns:
        Dict with 'model' and 'embedding' keys
    """
    if not OPENROUTER_API_KEY:
        raise ValueError("OpenRouter API key not configured")
    
    model = model or DEFAULT_EMBEDDING_MODEL
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    payload = {
        "model": model,
        "input": text
    }
    
    response = requests.post(
        f"{OPENROUTER_BASE}/embeddings",
        headers=headers,
        json=payload
    )
    
    if response.status_code != 200:
        error_detail = response.json() if response.content else {}
        error_msg = error_detail.get("error", {}).get("message", response.text)
        raise Exception(f"OpenRouter embeddings failed: {error_msg}")
    
    data = response.json()
    embedding = data.get("data", [{}])[0].get("embedding")
    
    if not embedding:
        raise Exception("No embedding returned from OpenRouter")
    
    return {
        "model": data.get("model", model),
        "embedding": embedding
    }


def hash_note_content(content: str) -> str:
    """
    Generate SHA-256 hash of content to detect changes.
    
    Args:
        content: The content to hash
        
    Returns:
        Hex string of SHA-256 hash
    """
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
