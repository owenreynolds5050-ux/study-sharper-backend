"""
Progress Agent
Fetches user's study progress, performance history, and activity metrics
"""

from ..base import BaseAgent, AgentType
from ..cache import cache
from typing import Dict, Any, Optional
import os
from supabase import create_client, Client
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ProgressAgent(BaseAgent):
    """Fetches user's study progress and performance history"""
    
    def __init__(self):
        super().__init__(
            name="progress_agent",
            agent_type=AgentType.CONTEXT,
            description="Retrieves study history and performance metrics"
        )
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not configured")
            self.supabase = None
        else:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("Progress Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch progress data.
        
        Args:
            input_data: Must contain 'user_id', optional 'days_back'
            context: Optional execution context
            
        Returns:
            Dictionary with progress metrics
        """
        
        user_id = input_data.get("user_id")
        days_back = input_data.get("days_back", 30)
        
        if not user_id:
            logger.warning("Progress agent called without user_id")
            return {"error": "Missing user_id"}
        
        if not self.supabase:
            logger.error("Supabase not configured")
            return {"error": "Database not configured"}
        
        # Check cache (10 min TTL for progress data)
        cache_key = f"progress_{user_id}_{days_back}"
        cached = await cache.get(cache_key, ttl_minutes=10)
        if cached:
            logger.info(f"Progress cache hit for user {user_id}")
            return cached
        
        try:
            # Fetch progress metrics
            progress = await self._fetch_progress(user_id, days_back)
            
            await cache.set(cache_key, progress)
            logger.info(f"Fetched progress for user {user_id}")
            
            return progress
        
        except Exception as e:
            logger.error(f"Progress agent error: {e}")
            return {"error": str(e), "user_id": user_id}
    
    async def _fetch_progress(self, user_id: str, days_back: int) -> Dict[str, Any]:
        """Fetch study sessions and activity metrics"""
        
        cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
        
        # Get flashcard study sessions (if table exists)
        flashcard_sessions = []
        try:
            sessions_response = self.supabase.table("flashcard_sessions").select(
                "id, cards_studied, correct_count, created_at"
            ).eq("user_id", user_id).gte(
                "created_at", cutoff_date
            ).execute()
            
            flashcard_sessions = sessions_response.data if sessions_response.data else []
        except Exception as e:
            logger.debug(f"No flashcard sessions (this is OK): {e}")
        
        # Get note count
        note_count = 0
        try:
            notes_response = self.supabase.table("notes").select(
                "id", count="exact"
            ).eq("user_id", user_id).execute()
            
            note_count = notes_response.count if notes_response.count else 0
        except Exception as e:
            logger.debug(f"Could not count notes: {e}")
        
        # Get folder count
        folder_count = 0
        try:
            folders_response = self.supabase.table("folders").select(
                "id", count="exact"
            ).eq("user_id", user_id).execute()
            
            folder_count = folders_response.count if folders_response.count else 0
        except Exception as e:
            logger.debug(f"Could not count folders: {e}")
        
        # Calculate metrics
        total_cards_studied = sum(s.get("cards_studied", 0) for s in flashcard_sessions)
        total_correct = sum(s.get("correct_count", 0) for s in flashcard_sessions)
        accuracy = (total_correct / total_cards_studied * 100) if total_cards_studied > 0 else 0
        
        return {
            "total_cards_studied": total_cards_studied,
            "total_correct": total_correct,
            "accuracy_percentage": round(accuracy, 1),
            "session_count": len(flashcard_sessions),
            "note_count": note_count,
            "folder_count": folder_count,
            "recent_sessions": flashcard_sessions[:5],  # Last 5
            "days_analyzed": days_back
        }
