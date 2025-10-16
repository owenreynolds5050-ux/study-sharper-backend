"""
Session Management
Manages conversation sessions and message history
"""

from supabase import Client
from typing import Dict, Any, Optional, List
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages conversation sessions"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        logger.info("Session Manager initialized")
    
    async def create_session(
        self,
        user_id: str,
        session_type: str = "chat"
    ) -> str:
        """
        Create new conversation session.
        
        Args:
            user_id: User ID
            session_type: Type of session (chat, flashcard_generation, etc.)
            
        Returns:
            Session ID
        """
        try:
            response = self.supabase.table("conversation_sessions").insert({
                "user_id": user_id,
                "session_type": session_type,
                "started_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }).execute()
            
            session_id = response.data[0]["id"]
            logger.info(f"Session created: {session_id} for user: {user_id}")
            return session_id
        
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            raise
    
    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Add message to session.
        
        Args:
            session_id: Session ID
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (validation scores, etc.)
        """
        try:
            self.supabase.table("conversation_messages").insert({
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": json.dumps(metadata or {}),
                "created_at": datetime.now().isoformat()
            }).execute()
            
            # Update last activity
            self.supabase.table("conversation_sessions").update({
                "last_activity": datetime.now().isoformat()
            }).eq("id", session_id).execute()
            
            logger.debug(f"Message added to session: {session_id}")
        
        except Exception as e:
            logger.error(f"Failed to add message to session {session_id}: {e}")
            raise
    
    async def get_session_messages(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get messages from session.
        
        Args:
            session_id: Session ID
            limit: Maximum number of messages to retrieve
            
        Returns:
            List of messages
        """
        try:
            response = self.supabase.table("conversation_messages").select(
                "role, content, metadata, created_at"
            ).eq("session_id", session_id).order(
                "created_at", desc=False
            ).limit(limit).execute()
            
            messages = response.data
            logger.info(f"Retrieved {len(messages)} messages from session: {session_id}")
            return messages
        
        except Exception as e:
            logger.error(f"Failed to get messages from session {session_id}: {e}")
            return []
    
    async def get_user_sessions(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get user's recent sessions.
        
        Args:
            user_id: User ID
            limit: Maximum number of sessions to retrieve
            
        Returns:
            List of sessions
        """
        try:
            response = self.supabase.table("conversation_sessions").select(
                "id, session_type, started_at, last_activity, ended_at"
            ).eq("user_id", user_id).order(
                "last_activity", desc=True
            ).limit(limit).execute()
            
            sessions = response.data
            logger.info(f"Retrieved {len(sessions)} sessions for user: {user_id}")
            return sessions
        
        except Exception as e:
            logger.error(f"Failed to get sessions for user {user_id}: {e}")
            return []
    
    async def end_session(self, session_id: str):
        """
        Mark session as ended.
        
        Args:
            session_id: Session ID
        """
        try:
            self.supabase.table("conversation_sessions").update({
                "ended_at": datetime.now().isoformat()
            }).eq("id", session_id).execute()
            
            logger.info(f"Session ended: {session_id}")
        
        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}")
            raise
    
    async def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session information.
        
        Args:
            session_id: Session ID
            
        Returns:
            Session info or None if not found
        """
        try:
            response = self.supabase.table("conversation_sessions").select(
                "*"
            ).eq("id", session_id).execute()
            
            if response.data:
                return response.data[0]
            return None
        
        except Exception as e:
            logger.error(f"Failed to get session info for {session_id}: {e}")
            return None
