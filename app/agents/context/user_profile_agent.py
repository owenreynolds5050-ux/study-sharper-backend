"""
User Profile Agent
Fetches user preferences, learning style, and profile data
"""

from ..base import BaseAgent, AgentType
from ..cache import cache
from typing import Dict, Any, Optional
import os
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)


class UserProfileAgent(BaseAgent):
    """Fetches user preferences and profile data"""
    
    def __init__(self):
        super().__init__(
            name="user_profile_agent",
            agent_type=AgentType.CONTEXT,
            description="Retrieves user preferences and learning style"
        )
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not configured")
            self.supabase = None
        else:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("User Profile Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch user profile and preferences.
        
        Args:
            input_data: Must contain 'user_id'
            context: Optional execution context
            
        Returns:
            Dictionary with user profile data
        """
        
        user_id = input_data.get("user_id")
        if not user_id:
            logger.warning("User Profile agent called without user_id")
            return {"error": "Missing user_id"}
        
        if not self.supabase:
            logger.error("Supabase not configured")
            return {"error": "Database not configured"}
        
        # Check cache (15 min TTL for profile data)
        cache_key = f"user_profile_{user_id}"
        cached = await cache.get(cache_key, ttl_minutes=15)
        if cached:
            logger.info(f"Profile cache hit for user {user_id}")
            return cached
        
        try:
            # Fetch from database
            profile = await self._fetch_profile(user_id)
            
            # Cache and return
            await cache.set(cache_key, profile)
            logger.info(f"Fetched profile for user {user_id}")
            
            return profile
        
        except Exception as e:
            logger.error(f"User Profile agent error: {e}")
            return {"error": str(e), "user_id": user_id}
    
    async def _fetch_profile(self, user_id: str) -> Dict[str, Any]:
        """Fetch user data from Supabase"""
        
        try:
            # Get basic user info from auth.users via your users table
            user_response = self.supabase.table("users").select(
                "id, email, full_name, created_at"
            ).eq("id", user_id).execute()
            
            user_data = user_response.data[0] if user_response.data else {}
            
        except Exception as e:
            logger.warning(f"Could not fetch user data: {e}")
            user_data = {"id": user_id}
        
        # Try to get user preferences (table may not exist yet)
        preferences = {}
        try:
            prefs_response = self.supabase.table("user_agent_preferences").select(
                "preferred_detail_level, preferred_difficulty, auto_context_gathering, preferences"
            ).eq("user_id", user_id).execute()
            
            if prefs_response.data:
                preferences = prefs_response.data[0]
        
        except Exception as e:
            logger.debug(f"No preferences found (this is OK): {e}")
            preferences = {
                "preferred_detail_level": "detailed",
                "preferred_difficulty": "adaptive",
                "auto_context_gathering": True
            }
        
        return {
            "user_id": user_id,
            "email": user_data.get("email"),
            "name": user_data.get("full_name"),
            "preferences": preferences,
            "member_since": user_data.get("created_at")
        }
