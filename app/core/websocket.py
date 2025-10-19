# app/core/websocket.py
from fastapi import WebSocket
from typing import Dict, Set
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Manages WebSocket connections for real-time file processing updates.
    Replaces polling system for better performance.
    """
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        
    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        
        async with self._lock:
            if user_id not in self.active_connections:
                self.active_connections[user_id] = set()
            self.active_connections[user_id].add(websocket)
        
        logger.info(f"WebSocket connected for user {user_id}")
        
    async def disconnect(self, websocket: WebSocket, user_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if user_id in self.active_connections:
                self.active_connections[user_id].discard(websocket)
                if not self.active_connections[user_id]:
                    del self.active_connections[user_id]
        
        logger.info(f"WebSocket disconnected for user {user_id}")
    
    async def send_file_update(self, user_id: str, file_id: str, update_data: dict):
        """
        Send real-time update to user about file processing.
        
        Args:
            user_id: User to send update to
            file_id: File being updated
            update_data: Update payload (status, progress, etc.)
        """
        if user_id not in self.active_connections:
            return
        
        message = json.dumps({
            "type": "file_update",
            "file_id": file_id,
            "data": update_data,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        dead_connections = set()
        
        # Send to all user's connections
        for connection in list(self.active_connections.get(user_id, [])):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send to connection: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        if dead_connections:
            async with self._lock:
                for connection in dead_connections:
                    await self.disconnect(connection, user_id)
    
    async def send_bulk_update(self, user_id: str, updates: list):
        """Send multiple updates at once"""
        if user_id not in self.active_connections:
            return
        
        message = json.dumps({
            "type": "bulk_update",
            "updates": updates,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        dead_connections = set()
        
        for connection in list(self.active_connections.get(user_id, [])):
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Failed to send bulk update: {e}")
                dead_connections.add(connection)
        
        if dead_connections:
            async with self._lock:
                for connection in dead_connections:
                    await self.disconnect(connection, user_id)
    
    async def broadcast_to_user(self, user_id: str, message_type: str, data: dict):
        """Broadcast a general message to all user's connections"""
        if user_id not in self.active_connections:
            return
        
        message = json.dumps({
            "type": message_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        })
        
        for connection in list(self.active_connections.get(user_id, [])):
            try:
                await connection.send_text(message)
            except Exception:
                pass
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(connections) for connections in self.active_connections.values())
    
    def get_user_connection_count(self, user_id: str) -> int:
        """Get number of connections for a specific user"""
        return len(self.active_connections.get(user_id, set()))

# Global WebSocket manager instance
ws_manager = WebSocketManager()
