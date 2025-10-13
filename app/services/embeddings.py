import hashlib
import requests
from typing import List, Dict, Any
from app.core.config import OPENROUTER_API_KEY
import os

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
DEFAULT_EMBEDDING_MODEL = "openai/text-embedding-3-small"

# Try to import sentence-transformers for local embeddings
try:
    from sentence_transformers import SentenceTransformer
    _local_model = None
    USE_LOCAL_EMBEDDINGS = True
except ImportError:
    USE_LOCAL_EMBEDDINGS = False


def get_embedding_for_text(text: str, model: str = None) -> Dict[str, Any]:
    """
    Generate embedding for text.
    Uses local sentence-transformers model as primary method.
    Falls back to OpenRouter API if available (currently not supported by OpenRouter).
    
    Args:
        text: The text to embed
        model: Optional model name (defaults to text-embedding-3-small)
        
    Returns:
        Dict with 'model' and 'embedding' keys
    """
    # Use local embeddings with sentence-transformers
    if USE_LOCAL_EMBEDDINGS:
        global _local_model
        if _local_model is None:
            # Load model once and cache it
            # Using all-MiniLM-L6-v2: fast, 384 dimensions, good quality
            _local_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        embedding = _local_model.encode(text, convert_to_numpy=True)
        # Convert to list for JSON serialization
        embedding_list = embedding.tolist()
        
        return {
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "embedding": embedding_list
        }
    
    # Fallback to OpenRouter (note: OpenRouter doesn't currently support embeddings API)
    if not OPENROUTER_API_KEY:
        raise ValueError("No embedding method available: install sentence-transformers or provide OpenRouter API key")
    
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
        error_msg = error_detail.get("error", {}).get("message", response.text[:200])
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
