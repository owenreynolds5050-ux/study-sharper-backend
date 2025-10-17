"""
Server-Sent Events (SSE) Manager
Handles real-time streaming updates to frontend
"""

from fastapi import Request
from typing import AsyncGenerator, Dict, Any
import json
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages Server-Sent Events for real-time updates with bounded queues"""
    
    def __init__(self, max_queue_size: int = 100, connection_timeout_minutes: int = 10):
        self.connections: Dict[str, Dict[str, Any]] = {}
        self.max_queue_size = max_queue_size
        self.connection_timeout_minutes = connection_timeout_minutes
        logger.info(f"SSE Manager initialized (max_queue_size={max_queue_size}, timeout={connection_timeout_minutes}min)")
    
    async def create_connection(self, session_id: str) -> asyncio.Queue:
        """
        Create new SSE connection with bounded queue.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Queue for sending updates
        """
        queue = asyncio.Queue(maxsize=self.max_queue_size)  # BOUNDED
        self.connections[session_id] = {
            "queue": queue,
            "created_at": datetime.now(),
            "last_activity": datetime.now()
        }
        logger.info(f"SSE connection created for session: {session_id}")
        return queue
    
    async def send_update(self, session_id: str, data: Dict[str, Any]):
        """
        Send update to specific session with queue overflow handling.
        
        Args:
            session_id: Session to send update to
            data: Update data to send
        """
        if session_id in self.connections:
            try:
                # Try to add to queue
                self.connections[session_id]["queue"].put_nowait(data)
                self.connections[session_id]["last_activity"] = datetime.now()
                logger.debug(f"Update sent to session {session_id}: {data.get('type')}")
            except asyncio.QueueFull:
                # Drop oldest, add new
                try:
                    self.connections[session_id]["queue"].get_nowait()
                    self.connections[session_id]["queue"].put_nowait(data)
                    self.connections[session_id]["last_activity"] = datetime.now()
                    logger.warning(f"Queue full for {session_id}, dropped oldest message")
                except Exception as e:
                    logger.error(f"Failed to handle queue overflow for {session_id}: {e}")
            except Exception as e:
                logger.error(f"Failed to send update to {session_id}: {e}")
        else:
            logger.warning(f"Attempted to send update to non-existent session: {session_id}")
    
    async def close_connection(self, session_id: str):
        """
        Close SSE connection and drain queue to free memory.
        
        Args:
            session_id: Session to close
        """
        if session_id in self.connections:
            try:
                # Drain queue before closing
                queue = self.connections[session_id]["queue"]
                drained = 0
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        drained += 1
                    except:
                        break
                
                if drained > 0:
                    logger.debug(f"Drained {drained} messages from queue for {session_id}")
                
                # Signal end
                try:
                    await queue.put(None)
                except asyncio.QueueFull:
                    pass  # Queue full, but we're closing anyway
                
                del self.connections[session_id]
                logger.info(f"SSE connection closed for session: {session_id}")
            except Exception as e:
                logger.error(f"Error closing connection {session_id}: {e}")
    
    async def event_generator(
        self,
        session_id: str,
        request: Request
    ) -> AsyncGenerator[str, None]:
        """
        Generate SSE events.
        
        Args:
            session_id: Session identifier
            request: FastAPI request object
            
        Yields:
            SSE formatted event strings
        """
        queue = await self.create_connection(session_id)
        
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    logger.info(f"Client disconnected: {session_id}")
                    break
                
                # Get next update from queue with timeout
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)
                    
                    if data is None:  # End signal
                        logger.info(f"End signal received for session: {session_id}")
                        break
                    
                    # Format as SSE
                    event_data = json.dumps(data)
                    yield f"data: {event_data}\n\n"
                
                except asyncio.TimeoutError:
                    # Send keepalive to prevent connection timeout
                    keepalive = {
                        "type": "keepalive",
                        "timestamp": datetime.now().isoformat()
                    }
                    yield f"data: {json.dumps(keepalive)}\n\n"
                    logger.debug(f"Keepalive sent to session: {session_id}")
        
        except Exception as e:
            logger.error(f"Error in event generator for {session_id}: {e}")
        
        finally:
            await self.close_connection(session_id)
    
    def get_active_connections(self) -> int:
        """Get count of active connections"""
        return len(self.connections)
    
    async def cleanup_stale_connections(self) -> int:
        """
        Remove connections inactive for > timeout.
        
        Returns:
            Number of connections cleaned up
        """
        now = datetime.now()
        timeout = timedelta(minutes=self.connection_timeout_minutes)
        stale_sessions = []
        
        for session_id, conn in self.connections.items():
            if now - conn["last_activity"] > timeout:
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            logger.info(f"Cleaning up stale connection: {session_id}")
            await self.close_connection(session_id)
        
        return len(stale_sessions)
    
    def get_stats(self) -> dict:
        """
        Get SSE manager statistics.
        
        Returns:
            Dictionary with connection stats
        """
        if not self.connections:
            return {
                "active_connections": 0,
                "oldest_connection_age_seconds": 0
            }
        
        now = datetime.now()
        oldest_age = max(
            (now - conn["created_at"]).total_seconds()
            for conn in self.connections.values()
        )
        
        return {
            "active_connections": len(self.connections),
            "oldest_connection_age_seconds": oldest_age
        }


# Global SSE manager instance
sse_manager = SSEManager()
