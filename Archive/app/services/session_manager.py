"""
Session State Manager
Persists conversation state to database for resumption across sessions
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class ConversationState:
    """Represents the state of a flashcard generation conversation"""
    
    def __init__(
        self,
        user_id: str,
        session_id: str,
        subject: Optional[str] = None,
        subtopic: Optional[str] = None,
        length: Optional[int] = None,
        difficulty: Optional[str] = None,
        from_notes: bool = False,
        clarification_count: int = 0,
        missing_params: Optional[List[str]] = None,
        last_message: Optional[str] = None
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.subject = subject
        self.subtopic = subtopic
        self.length = length
        self.difficulty = difficulty
        self.from_notes = from_notes
        self.clarification_count = clarification_count
        self.missing_params = missing_params or []
        self.last_message = last_message
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state to dictionary for storage"""
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "subject": self.subject,
            "subtopic": self.subtopic,
            "length": self.length,
            "difficulty": self.difficulty,
            "from_notes": self.from_notes,
            "clarification_count": self.clarification_count,
            "missing_params": self.missing_params,
            "last_message": self.last_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Create state from dictionary"""
        state = cls(
            user_id=data.get("user_id"),
            session_id=data.get("session_id"),
            subject=data.get("subject"),
            subtopic=data.get("subtopic"),
            length=data.get("length"),
            difficulty=data.get("difficulty"),
            from_notes=data.get("from_notes", False),
            clarification_count=data.get("clarification_count", 0),
            missing_params=data.get("missing_params", []),
            last_message=data.get("last_message")
        )
        
        if data.get("created_at"):
            state.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            state.updated_at = datetime.fromisoformat(data["updated_at"])
        
        return state
    
    def is_complete(self) -> bool:
        """Check if all required parameters are present"""
        return all([
            self.subject is not None,
            self.subtopic is not None,
            self.length is not None,
            self.difficulty is not None
        ])
    
    def get_missing_params(self) -> List[str]:
        """Get list of missing required parameters"""
        missing = []
        if not self.subject:
            missing.append("subject")
        if not self.subtopic:
            missing.append("subtopic")
        if not self.length:
            missing.append("length")
        if not self.difficulty:
            missing.append("difficulty")
        return missing
    
    def update_param(self, param: str, value: Any):
        """Update a single parameter"""
        if param == "subject":
            self.subject = value
        elif param == "subtopic":
            self.subtopic = value
        elif param == "length":
            self.length = int(value) if value else None
        elif param == "difficulty":
            self.difficulty = value
        elif param == "from_notes":
            self.from_notes = bool(value)
        
        self.updated_at = datetime.now()


class SessionManager:
    """Manages conversation sessions with database persistence"""
    
    def __init__(self, supabase):
        self.supabase = supabase
    
    def get_or_create_session(
        self,
        user_id: str,
        session_id: str
    ) -> ConversationState:
        """
        Get existing session state or create new one
        """
        try:
            # Try to load from chat history
            response = self.supabase.table("flashcard_chat_history").select(
                "context"
            ).eq("user_id", user_id).eq("session_id", session_id).order(
                "created_at", desc=True
            ).limit(1).execute()
            
            if response.data and len(response.data) > 0:
                context = response.data[0].get("context", {})
                if context and "state" in context:
                    logger.info(f"Loaded existing session state for {session_id}")
                    return ConversationState.from_dict(context["state"])
            
            # Create new session
            logger.info(f"Creating new session state for {session_id}")
            return ConversationState(user_id=user_id, session_id=session_id)
            
        except Exception as e:
            logger.error(f"Error loading session state: {e}")
            return ConversationState(user_id=user_id, session_id=session_id)
    
    def save_session(self, state: ConversationState, message: str, role: str = "assistant"):
        """
        Save session state to database
        """
        try:
            state.updated_at = datetime.now()
            
            # Save to chat history with state in context
            chat_entry = {
                "user_id": state.user_id,
                "session_id": state.session_id,
                "role": role,
                "message": message,
                "context": {
                    "state": state.to_dict()
                }
            }
            
            self.supabase.table("flashcard_chat_history").insert(chat_entry).execute()
            logger.info(f"Saved session state for {state.session_id}")
            
        except Exception as e:
            logger.error(f"Error saving session state: {e}")
    
    def save_user_message(self, user_id: str, session_id: str, message: str):
        """Save user message to chat history"""
        try:
            chat_entry = {
                "user_id": user_id,
                "session_id": session_id,
                "role": "user",
                "message": message,
                "context": {}
            }
            
            self.supabase.table("flashcard_chat_history").insert(chat_entry).execute()
            
        except Exception as e:
            logger.error(f"Error saving user message: {e}")
    
    def get_chat_history(
        self,
        user_id: str,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent chat history for a session
        """
        try:
            response = self.supabase.table("flashcard_chat_history").select(
                "role, message, created_at"
            ).eq("user_id", user_id).eq("session_id", session_id).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            if response.data:
                # Reverse to get chronological order
                return list(reversed(response.data))
            
            return []
            
        except Exception as e:
            logger.error(f"Error loading chat history: {e}")
            return []
    
    def clear_session(self, user_id: str, session_id: str):
        """
        Clear session state (start over)
        """
        try:
            # Delete chat history for this session
            self.supabase.table("flashcard_chat_history").delete().eq(
                "user_id", user_id
            ).eq("session_id", session_id).execute()
            
            logger.info(f"Cleared session {session_id}")
            
        except Exception as e:
            logger.error(f"Error clearing session: {e}")
    
    def check_rate_limit(self, user_id: str, is_premium: bool) -> Dict[str, Any]:
        """
        Check if user has exceeded daily generation limit
        
        Returns:
            Dict with:
            - allowed: bool
            - count_today: int
            - limit: int
            - is_premium: bool
        """
        try:
            # Get user profile
            response = self.supabase.table("profiles").select(
                "flashcard_sets_generated_today, last_generation_date, is_premium"
            ).eq("id", user_id).single().execute()
            
            if not response.data:
                return {"allowed": True, "count_today": 0, "limit": 50, "is_premium": False}
            
            profile = response.data
            count_today = profile.get("flashcard_sets_generated_today", 0)
            last_date = profile.get("last_generation_date")
            is_premium_db = profile.get("is_premium", False)
            
            # Reset count if new day
            if last_date and last_date != datetime.now().date().isoformat():
                count_today = 0
            
            # Check limit (50 per day for both free and premium)
            limit = 50
            allowed = count_today < limit
            
            return {
                "allowed": allowed,
                "count_today": count_today,
                "limit": limit,
                "is_premium": is_premium_db
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Allow on error
            return {"allowed": True, "count_today": 0, "limit": 50, "is_premium": False}
    
    def increment_generation_count(self, user_id: str) -> int:
        """
        Increment user's daily generation count
        
        Returns:
            New count
        """
        try:
            # Use RPC function
            response = self.supabase.rpc(
                "increment_generation_count",
                {"user_id_param": user_id}
            ).execute()
            
            if response.data:
                return response.data
            
            return 1
            
        except Exception as e:
            logger.error(f"Error incrementing generation count: {e}")
            return 1


def get_session_manager(supabase) -> SessionManager:
    """Factory function to create SessionManager"""
    return SessionManager(supabase)
