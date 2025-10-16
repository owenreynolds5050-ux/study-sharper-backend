"""
RAG Service - Retrieval-Augmented Generation
Handles vector search and context retrieval from user notes
"""

from typing import List, Dict, Any, Optional
from app.services.embeddings import get_embedding_for_text
import logging
import json

logger = logging.getLogger(__name__)


class RAGService:
    """Handles retrieval of relevant notes for flashcard generation"""
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.max_context_tokens = 6000  # Approximate token limit for context
    
    async def retrieve_relevant_notes(
        self,
        user_id: str,
        query: str,
        subject_filter: Optional[str] = None,
        top_k: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant notes using vector similarity search
        
        Args:
            user_id: User ID
            query: Search query (user's message)
            subject_filter: Optional subject to filter by
            top_k: Number of results to return
            similarity_threshold: Minimum similarity score (0-1)
        
        Returns:
            List of note dicts with id, title, content, similarity
        """
        try:
            # Generate embedding for query
            embedding_result = get_embedding_for_text(query)

            if not embedding_result or "embedding" not in embedding_result:
                logger.error("Failed to generate query embedding")
                return []

            query_embedding = embedding_result["embedding"]

            # Convert to JSONB format for RPC call
            embedding_json = json.dumps(query_embedding)
            
            # Call RPC function for vector search
            response = self.supabase.rpc(
                "search_similar_notes",
                {
                    "query_embedding": embedding_json,
                    "user_id_param": user_id,
                    "match_threshold": similarity_threshold,
                    "match_count": top_k
                }
            ).execute()
            
            if not response.data:
                logger.info("No similar notes found")
                return []
            
            notes = response.data
            
            # Filter by subject if provided
            if subject_filter:
                notes = [
                    note for note in notes
                    if subject_filter.lower() in note.get("title", "").lower()
                    or subject_filter.lower() in note.get("content", "").lower()
                ]
            
            # Sort by similarity (highest first)
            notes.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            
            logger.info(f"Retrieved {len(notes)} relevant notes (threshold: {similarity_threshold})")
            
            return notes[:top_k]
            
        except Exception as e:
            logger.error(f"Error retrieving notes: {e}")
            return []
    
    def get_notes_by_ids(
        self,
        user_id: str,
        note_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Get specific notes by their IDs
        """
        try:
            if not note_ids:
                return []
            
            response = self.supabase.table("notes").select(
                "id, title, content, extracted_text"
            ).eq("user_id", user_id).in_("id", note_ids).execute()
            
            if not response.data:
                return []
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching notes by IDs: {e}")
            return []
    
    def get_all_user_notes(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all notes for a user (for "use all notes" requests)
        """
        try:
            query = self.supabase.table("notes").select(
                "id, title, content, extracted_text, created_at"
            ).eq("user_id", user_id).order("created_at", desc=True)
            
            if limit:
                query = query.limit(limit)
            
            response = query.execute()
            
            if not response.data:
                return []
            
            return response.data
            
        except Exception as e:
            logger.error(f"Error fetching all notes: {e}")
            return []
    
    def combine_notes_content(
        self,
        notes: List[Dict[str, Any]],
        max_length: Optional[int] = None
    ) -> str:
        """
        Combine multiple notes into a single context string
        
        Args:
            notes: List of note dicts
            max_length: Maximum character length (truncates if exceeded)
        
        Returns:
            Combined text content
        """
        if not notes:
            return ""
        
        combined_parts = []
        
        for note in notes:
            title = note.get("title", "Untitled")
            content = note.get("content") or note.get("extracted_text") or ""
            
            if content.strip():
                combined_parts.append(f"## {title}\n\n{content}")
        
        combined_text = "\n\n---\n\n".join(combined_parts)
        
        # Truncate if too long
        if max_length and len(combined_text) > max_length:
            combined_text = combined_text[:max_length] + "\n\n[Content truncated...]"
            logger.info(f"Truncated combined content to {max_length} characters")
        
        return combined_text
    
    def get_note_count(self, user_id: str) -> int:
        """Get total number of notes for user"""
        try:
            response = self.supabase.table("notes").select(
                "id", count="exact"
            ).eq("user_id", user_id).execute()
            
            return response.count or 0
            
        except Exception as e:
            logger.error(f"Error getting note count: {e}")
            return 0
    
    def infer_subject_from_notes(
        self,
        notes: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        Attempt to infer subject from note titles/content
        Uses simple keyword matching
        """
        if not notes:
            return None
        
        # Common subjects and their keywords
        subject_keywords = {
            "Biology": ["biology", "cell", "dna", "organism", "evolution", "photosynthesis"],
            "Chemistry": ["chemistry", "molecule", "atom", "reaction", "compound", "element"],
            "Physics": ["physics", "force", "energy", "motion", "velocity", "acceleration"],
            "Mathematics": ["math", "equation", "algebra", "calculus", "geometry", "theorem"],
            "History": ["history", "war", "revolution", "century", "empire", "civilization"],
            "English": ["literature", "novel", "poem", "shakespeare", "essay", "writing"],
            "Computer Science": ["programming", "algorithm", "code", "software", "computer"],
            "Psychology": ["psychology", "behavior", "cognitive", "mental", "brain"],
            "Economics": ["economics", "market", "supply", "demand", "trade", "finance"]
        }
        
        # Count keyword matches
        subject_scores = {subject: 0 for subject in subject_keywords}
        
        for note in notes:
            text = f"{note.get('title', '')} {note.get('content', '')}".lower()
            
            for subject, keywords in subject_keywords.items():
                for keyword in keywords:
                    if keyword in text:
                        subject_scores[subject] += 1
        
        # Return subject with highest score
        if max(subject_scores.values()) > 0:
            inferred_subject = max(subject_scores, key=subject_scores.get)
            logger.info(f"Inferred subject: {inferred_subject}")
            return inferred_subject
        
        return None


def get_rag_service(supabase) -> RAGService:
    """Factory function to create RAGService"""
    return RAGService(supabase)
