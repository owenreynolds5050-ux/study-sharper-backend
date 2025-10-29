"""
RAG Service - Unified service for Retrieval-Augmented Generation with conversation management.
Consolidates retrieval logic, conversation history, and context management.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

from app.services.ai_chat import retrieve_relevant_file_chunks
from app.services.open_router import get_chat_completion
from app.services.embeddings import get_embedding_for_text

logger = logging.getLogger(__name__)


class RAGService:
    """Service for managing RAG operations with conversation context."""
    
    def __init__(self, supabase):
        self.supabase = supabase
    
    async def create_session(
        self,
        user_id: str,
        session_type: str = "chat",
        file_ids: Optional[List[str]] = None
    ) -> str:
        """Create a new conversation session."""
        try:
            session_data = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "session_type": session_type,
                "context_data": {
                    "file_ids": file_ids or [],
                    "created_at": datetime.utcnow().isoformat()
                },
                "started_at": datetime.utcnow().isoformat(),
                "last_activity": datetime.utcnow().isoformat()
            }
            result = self.supabase.table("conversation_sessions").insert(session_data).execute()
            if not result.data:
                raise Exception("Failed to create session")
            return result.data[0]["id"]
        except Exception as e:
            logger.error(f"Error creating session: {str(e)}")
            raise
    
    async def get_session(self, session_id: str, user_id: str) -> Dict[str, Any]:
        """Retrieve session with all messages."""
        try:
            session_result = self.supabase.table("conversation_sessions").select("*").eq(
                "id", session_id
            ).eq("user_id", user_id).execute()
            
            if not session_result.data:
                return None
            
            session = session_result.data[0]
            
            # Get all messages
            messages_result = self.supabase.table("conversation_messages").select("*").eq(
                "session_id", session_id
            ).order("created_at", desc=False).execute()
            
            return {
                "session": session,
                "messages": messages_result.data or []
            }
        except Exception as e:
            logger.error(f"Error retrieving session: {str(e)}")
            raise
    
    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save a message to conversation history."""
        try:
            message_data = {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": datetime.utcnow().isoformat()
            }
            result = self.supabase.table("conversation_messages").insert(message_data).execute()
            if not result.data:
                raise Exception("Failed to save message")
            return result.data[0]["id"]
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            raise
    
    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages from a session for context."""
        try:
            result = self.supabase.table("conversation_messages").select("*").eq(
                "session_id", session_id
            ).order("created_at", desc=True).limit(limit).execute()
            
            messages = result.data or []
            # Reverse to get chronological order
            return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error retrieving conversation history: {str(e)}")
            return []
    
    async def retrieve_context(
        self,
        user_id: str,
        query: str,
        file_ids: Optional[List[str]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Retrieve relevant context for a query."""
        try:
            chunk_results = await retrieve_relevant_file_chunks(
                user_id=user_id,
                query=query,
                supabase=self.supabase,
                top_k=top_k,
                file_ids=file_ids
            )
            return chunk_results
        except Exception as e:
            logger.error(f"Error retrieving context: {str(e)}")
            return {
                "chunks": [],
                "system_message": "You have access to these relevant notes:\nNo relevant notes found."
            }
    
    async def generate_response(
        self,
        query: str,
        system_message: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        model: str = "anthropic/claude-3.5-sonnet"
    ) -> str:
        """Generate AI response with conversation context."""
        try:
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Add conversation history (last 5 exchanges)
            if conversation_history:
                for msg in conversation_history[-10:]:
                    messages.append({
                        "role": msg.get("role", "user"),
                        "content": msg.get("content", "")
                    })
            
            # Add current query
            messages.append({"role": "user", "content": query})
            
            response = get_chat_completion(messages, model=model)
            return response.strip()
        except Exception as e:
            logger.error(f"Error generating response: {str(e)}")
            raise
    
    async def chat_with_files(
        self,
        user_id: str,
        query: str,
        session_id: Optional[str] = None,
        file_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Complete RAG chat flow: retrieve context, generate response, save to history."""
        try:
            # Step 1: Get or create session
            if not session_id:
                session_id = await self.create_session(user_id, "chat", file_ids)
            else:
                # Update last activity
                self.supabase.table("conversation_sessions").update({
                    "last_activity": datetime.utcnow().isoformat()
                }).eq("id", session_id).eq("user_id", user_id).execute()
            
            # Step 2: Save user message
            await self.save_message(
                session_id,
                "user",
                query,
                {"file_ids": file_ids or [], "timestamp": datetime.utcnow().isoformat()}
            )
            
            # Step 3: Retrieve relevant context
            context = await self.retrieve_context(user_id, query, file_ids, top_k=5)
            
            # Step 4: Get conversation history for context
            history = await self.get_conversation_history(session_id, limit=5)
            
            # Step 5: Generate response
            response_text = await self.generate_response(
                query,
                context["system_message"],
                history
            )
            
            # Step 6: Save assistant response with sources
            sources_metadata = [{
                "file_id": chunk.get("file_id"),
                "file_title": chunk.get("file_title"),
                "chunk_id": chunk.get("chunk_id"),
                "similarity": chunk.get("similarity")
            } for chunk in context["chunks"]]
            
            message_id = await self.save_message(
                session_id,
                "assistant",
                response_text,
                {
                    "sources": sources_metadata,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            # Step 7: Format response with sources
            sources = []
            for chunk in context["chunks"]:
                sources.append({
                    "file_id": chunk.get("file_id"),
                    "file_title": chunk.get("file_title"),
                    "chunk_id": chunk.get("chunk_id"),
                    "similarity": chunk.get("similarity"),
                    "text": chunk.get("text")
                })
            
            return {
                "session_id": session_id,
                "message_id": message_id,
                "response": response_text,
                "sources": sources
            }
        except Exception as e:
            logger.error(f"Error in chat_with_files: {str(e)}", exc_info=True)
            raise
    
    async def list_sessions(
        self,
        user_id: str,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """List user's conversation sessions."""
        try:
            result = self.supabase.table("conversation_sessions").select("*").eq(
                "user_id", user_id
            ).order("last_activity", desc=True).range(offset, offset + limit - 1).execute()
            
            return {
                "sessions": result.data or [],
                "total": len(result.data or [])
            }
        except Exception as e:
            logger.error(f"Error listing sessions: {str(e)}")
            raise
    
    async def delete_session(self, session_id: str, user_id: str) -> bool:
        """Delete a session and all its messages."""
        try:
            # Verify ownership
            session_result = self.supabase.table("conversation_sessions").select("user_id").eq(
                "id", session_id
            ).execute()
            
            if not session_result.data or session_result.data[0]["user_id"] != user_id:
                return False
            
            # Delete messages
            self.supabase.table("conversation_messages").delete().eq(
                "session_id", session_id
            ).execute()
            
            # Delete session
            self.supabase.table("conversation_sessions").delete().eq(
                "id", session_id
            ).execute()
            
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {str(e)}")
            raise
