"""
Conversation Agent
Retrieves recent conversation history for maintaining context across messages
"""

from ..base import BaseAgent, AgentType
from ..cache import cache
from typing import Dict, Any, Optional, List
import os
from supabase import create_client, Client
import logging

logger = logging.getLogger(__name__)


class ConversationAgent(BaseAgent):
    """Retrieves recent conversation history with memory optimization"""
    
    # Memory optimization constants
    MAX_MESSAGES = 10
    MAX_CONTENT_MESSAGES = 5
    MAX_CONTENT_LENGTH = 200
    
    def __init__(self):
        super().__init__(
            name="conversation_agent",
            agent_type=AgentType.CONTEXT,
            description="Fetches recent chat history for context"
        )
        
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        if not supabase_url or not supabase_key:
            logger.warning("Supabase credentials not configured")
            self.supabase = None
        else:
            self.supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("Conversation Agent initialized")
    
    async def _execute_internal(
        self,
        input_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Fetch conversation history.
        
        Args:
            input_data: Must contain 'session_id' and 'user_id', optional 'limit'
            context: Optional execution context
            
        Returns:
            Dictionary with conversation messages
        """
        
        session_id = input_data.get("session_id")
        user_id = input_data.get("user_id")
        requested_limit = input_data.get("limit", 10)
        
        # HARD CAP at MAX_MESSAGES to prevent memory bloat
        limit = min(requested_limit, self.MAX_MESSAGES)
        
        if not session_id or not user_id:
            logger.debug("Conversation agent called without session_id or user_id")
            return {"messages": [], "message": "No session context"}
        
        if not self.supabase:
            logger.error("Supabase not configured")
            return {"messages": [], "error": "Database not configured"}
        
        # Check cache (5 min TTL for conversation data)
        cache_key = f"conversation_{session_id}_{limit}"
        cached = await cache.get(cache_key, ttl_minutes=5)
        if cached:
            logger.info(f"Conversation cache hit for session {session_id}")
            return cached
        
        try:
            # Fetch from database
            messages = await self._fetch_messages(session_id, user_id, limit)
            
            result = {
                "messages": messages,
                "session_id": session_id,
                "message_count": len(messages)
            }
            
            await cache.set(cache_key, result)
            logger.info(f"Fetched {len(messages)} messages for session {session_id}")
            
            return result
        
        except Exception as e:
            logger.error(f"Conversation agent error: {e}")
            return {
                "messages": [],
                "error": str(e),
                "session_id": session_id
            }
    
    async def _fetch_messages(
        self,
        session_id: str,
        user_id: str,
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Fetch conversation messages with memory optimization.
        
        Strategy:
        1. Load metadata only (id, role, created_at) - lightweight
        2. Only fetch content for most recent MAX_CONTENT_MESSAGES
        3. Truncate content to MAX_CONTENT_LENGTH chars
        
        This reduces memory by ~99% (100KB → 1KB per request)
        """
        
        try:
            # Step 1: Fetch metadata only (no content) - very lightweight
            response = self.supabase.table("conversation_messages").select(
                "id, role, created_at"
            ).eq("session_id", session_id).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            if not response.data:
                return []
            
            messages = response.data
            messages.reverse()  # Chronological order
            
            # Step 2: Only fetch content for most recent messages
            recent_count = min(self.MAX_CONTENT_MESSAGES, len(messages))
            recent_ids = [msg["id"] for msg in messages[-recent_count:]]
            
            if recent_ids:
                content_response = self.supabase.table("conversation_messages").select(
                    "id, content, metadata"
                ).in_("id", recent_ids).execute()
                
                # Create lookup map with truncated content
                content_map = {}
                for msg in content_response.data or []:
                    content = msg.get("content", "")
                    # Truncate to MAX_CONTENT_LENGTH chars
                    truncated = content[:self.MAX_CONTENT_LENGTH] if len(content) > self.MAX_CONTENT_LENGTH else content
                    content_map[msg["id"]] = {
                        "content": truncated,
                        "metadata": msg.get("metadata", {})
                    }
                
                # Merge content back into messages
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id in content_map:
                        msg["content"] = content_map[msg_id]["content"]
                        msg["metadata"] = content_map[msg_id]["metadata"]
                    else:
                        # Older messages - no content (saves memory)
                        msg["content"] = ""
                        msg["metadata"] = {}
            else:
                # No content for any messages
                for msg in messages:
                    msg["content"] = ""
                    msg["metadata"] = {}
            
            logger.debug(f"Loaded {len(messages)} messages, content for {recent_count}")
            return messages
        
        except Exception as e:
            logger.debug(f"No conversation history found (table may not exist): {e}")
            return []
