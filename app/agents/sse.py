"""
Server-Sent Events (SSE) Manager
Handles real-time streaming updates to frontend
"""

from fastapi import Request
from typing import AsyncGenerator, Dict, Any
import json
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SSEManager:
    """Manages Server-Sent Events for real-time updates"""
    
    def __init__(self):
        self.connections: Dict[str, asyncio.Queue] = {}
        logger.info("SSE Manager initialized")
    
    async def create_connection(self, session_id: str) -> asyncio.Queue:
        """
        Create new SSE connection.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            Queue for sending updates
        """
        queue = asyncio.Queue()
        self.connections[session_id] = queue
        logger.info(f"SSE connection created for session: {session_id}")
        return queue
    
    async def send_update(self, session_id: str, data: Dict[str, Any]):
        """
        Send update to specific session.
        
        Args:
            session_id: Session to send update to
            data: Update data to send
        """
        if session_id in self.connections:
            try:
                await self.connections[session_id].put(data)
                logger.debug(f"Update sent to session {session_id}: {data.get('type')}")
            except Exception as e:
                logger.error(f"Failed to send update to {session_id}: {e}")
        else:
            logger.warning(f"Attempted to send update to non-existent session: {session_id}")
    
    async def close_connection(self, session_id: str):
        """
        Close SSE connection.
        
        Args:
            session_id: Session to close
        """
        if session_id in self.connections:
            try:
                await self.connections[session_id].put(None)  # Signal end
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
    
    async def cleanup_stale_connections(self, max_age_seconds: int = 600):
        """
        Clean up stale connections older than max_age.
        
        Args:
            max_age_seconds: Maximum age in seconds before cleanup
        """
        # Note: This is a basic implementation
        # In production, you'd track connection timestamps
        stale_sessions = []
        
        for session_id in list(self.connections.keys()):
            # Check if queue is empty and hasn't been used
            if self.connections[session_id].empty():
                stale_sessions.append(session_id)
        
        for session_id in stale_sessions:
            logger.info(f"Cleaning up stale connection: {session_id}")
            await self.close_connection(session_id)


# Global SSE manager instance
sse_manager = SSEManager()
