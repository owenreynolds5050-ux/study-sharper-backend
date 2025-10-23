# app/services/embedding_service.py
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Optional
import numpy as np

# Initialize embedding model (singleton pattern)
_embedding_model = None

def get_embedding_model():
    """Get or initialize sentence-transformers model"""
    global _embedding_model
    
    if _embedding_model is None:
        # all-MiniLM-L6-v2: 384 dimensions, fast, good quality
        _embedding_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        print("✓ Embedding model loaded (384 dimensions)")
    
    return _embedding_model

def generate_embedding(text: str) -> List[float]:
    """
    Generate 384-dimensional embedding for text.
    
    Args:
        text: Input text to embed
        
    Returns:
        List of 384 floats representing the embedding
    """
    
    if not text or not text.strip():
        raise ValueError("Cannot generate embedding for empty text")
    
    model = get_embedding_model()
    
    # Generate embedding
    embedding = model.encode(text, convert_to_numpy=True)
    
    # Convert to list for JSON serialization
    return embedding.tolist()

def generate_embeddings_batch(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts at once (more efficient).
    
    Args:
        texts: List of texts to embed
        
    Returns:
        List of embeddings (each embedding is 384 floats)
    """
    
    if not texts:
        return []
    
    model = get_embedding_model()
    
    # Batch encoding is faster than one-by-one
    embeddings = model.encode(texts, convert_to_numpy=True, batch_size=32)
    
    return [emb.tolist() for emb in embeddings]


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into overlapping character chunks."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be greater than overlap")

    if not text:
        return []

    cleaned = text.strip()
    if not cleaned:
        return []

    chunks: List[str] = []
    step = chunk_size - overlap
    start = 0
    text_length = len(cleaned)

    while start < text_length:
        end = min(text_length, start + chunk_size)
        chunk = cleaned[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= text_length:
            break
        start += step

    return chunks


def average_embeddings(embeddings: List[List[float]]) -> List[float]:
    """Compute element-wise average for a list of embeddings."""
    if not embeddings:
        raise ValueError("Cannot average empty embedding list")

    array = np.array(embeddings, dtype=float)
    return array.mean(axis=0).tolist()


def prepare_chunk_embeddings(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 200
) -> Tuple[List[str], List[List[float]], Optional[List[float]]]:
    """Generate chunk-level embeddings and aggregate embedding for text."""
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    if not chunks:
        return [], [], None

    embeddings = generate_embeddings_batch(chunks)
    if not embeddings:
        return [], [], None

    aggregated = average_embeddings(embeddings)
    return chunks, embeddings, aggregated
