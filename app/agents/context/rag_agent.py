"""
RAG (Retrieval-Augmented Generation) Agent
Retrieves relevant notes using semantic search and text matching
"""

from ..base import BaseAgent, AgentType
from ..cache import cache
from typing import Dict, Any, Optional, List
import os
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)


class RAGAgent(BaseAgent):
    """Retrieves relevant notes using vector similarity search and text matching"""
    
    def __init__(self):
        super().__init__(
            name="rag_agent",
            agent_type=AgentType.CONTEXT,
            model="anthropic/claude-3.5-haiku",
            description="Searches user's notes for relevant content"
        )
        
        # Initialize Supabase client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not configured")
            self.supabase = None
        else:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("RAG Agent initialized with Supabase")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Search for relevant notes.
        
        Args:
            input_data: Must contain 'query' and 'user_id'
                       Optional: 'top_k', 'note_ids'
            context: Optional execution context
            
        Returns:
            Dictionary with notes array and metadata
        """
        
        query = input_data.get("query")
        user_id = input_data.get("user_id")
        top_k = input_data.get("top_k", 5)
        explicit_note_ids = input_data.get("note_ids", [])
        
        if not query or not user_id:
            logger.warning("RAG agent called without query or user_id")
            return {"notes": [], "message": "Missing query or user_id"}
        
        if not self.supabase:
            logger.error("Supabase not configured")
            return {"notes": [], "error": "Database not configured"}
        
        # Check cache first
        cache_key = f"rag_{user_id}_{hash(query)}_{top_k}"
        cached_result = await cache.get(cache_key, ttl_minutes=30)
        if cached_result:
            logger.info(f"RAG cache hit for user {user_id}")
            return cached_result
        
        try:
            # If explicit note IDs provided, fetch those
            if explicit_note_ids:
                logger.info(f"Fetching {len(explicit_note_ids)} explicit notes")
                notes = await self._fetch_notes_by_ids(user_id, explicit_note_ids)
            else:
                # Otherwise do text search
                logger.info(f"Searching notes for user {user_id}: '{query[:50]}...'")
                notes = await self._text_search(user_id, query, top_k)
            
            result = {
                "notes": notes,
                "count": len(notes),
                "search_query": query,
                "search_type": "explicit_ids" if explicit_note_ids else "text_search"
            }
            
            # Cache result
            await cache.set(cache_key, result)
            logger.info(f"RAG found {len(notes)} notes for user {user_id}")
            
            return result
        
        except Exception as e:
            logger.error(f"RAG agent error: {e}")
            return {
                "notes": [],
                "error": str(e),
                "search_query": query
            }
    
    async def _text_search(
        self,
        user_id: str,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform text-based search on notes.
        Uses PostgreSQL full-text search.
        
        Args:
            user_id: User ID
            query: Search query
            top_k: Number of results to return
            
        Returns:
            List of note dictionaries
        """
        
        try:
            # Use ilike for simple text matching
            # TODO: Upgrade to vector search when embeddings are ready
            response = self.supabase.table("notes").select(
                "id, title, content, created_at, updated_at, folder_id"
            ).eq("user_id", user_id).or_(
                f"title.ilike.%{query}%,content.ilike.%{query}%"
            ).limit(top_k).execute()
            
            notes = response.data if response.data else []
            
            # Truncate content for context (keep first 500 chars)
            for note in notes:
                if note.get("content") and len(note["content"]) > 500:
                    note["content"] = note["content"][:500] + "..."
                    note["truncated"] = True
            
            return notes
        
        except Exception as e:
            logger.error(f"Text search failed: {e}")
            return []
    
    async def _fetch_notes_by_ids(
        self,
        user_id: str,
        note_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch specific notes by ID.
        
        Args:
            user_id: User ID for security check
            note_ids: List of note IDs to fetch
            
        Returns:
            List of note dictionaries
        """
        
        try:
            response = self.supabase.table("notes").select(
                "id, title, content, created_at, updated_at, folder_id"
            ).eq("user_id", user_id).in_("id", note_ids).execute()
            
            notes = response.data if response.data else []
            
            # Truncate content
            for note in notes:
                if note.get("content") and len(note["content"]) > 500:
                    note["content"] = note["content"][:500] + "..."
                    note["truncated"] = True
            
            return notes
        
        except Exception as e:
            logger.error(f"Fetch by IDs failed: {e}")
            return []
