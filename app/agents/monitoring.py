"""
Agent Monitoring and Analytics
Tracks agent executions, performance metrics, and system health
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from supabase import Client
import json
import logging

logger = logging.getLogger(__name__)


class AgentMonitor:
    """Monitor and log agent executions"""
    
    def __init__(self, supabase: Client):
        self.supabase = supabase
        logger.info("Agent Monitor initialized")
    
    async def log_execution(
        self,
        user_id: str,
        session_id: Optional[str],
        request_id: str,
        agent_name: str,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
        execution_time_ms: int,
        tokens_used: int,
        model_used: str,
        status: str,
        error_message: Optional[str] = None
    ):
        """
        Log agent execution to database.
        
        Args:
            user_id: User ID
            session_id: Session ID (optional)
            request_id: Unique request ID
            agent_name: Name of agent executed
            input_data: Input data to agent
            output_data: Output from agent
            execution_time_ms: Execution time in milliseconds
            tokens_used: Number of tokens consumed
            model_used: Model identifier
            status: Execution status (success/failure/timeout)
            error_message: Error message if failed
        """
        try:
            self.supabase.table("agent_executions").insert({
                "user_id": user_id,
                "session_id": session_id,
                "request_id": request_id,
                "agent_name": agent_name,
                "input_data": json.dumps(input_data),
                "output_data": json.dumps(output_data),
                "execution_time_ms": execution_time_ms,
                "tokens_used": tokens_used,
                "model_used": model_used,
                "status": status,
                "error_message": error_message,
                "created_at": datetime.now().isoformat()
            }).execute()
            
            logger.debug(f"Logged execution for {agent_name}: {status}")
        
        except Exception as e:
            # Don't fail the request if logging fails
            logger.error(f"Failed to log execution: {e}")
    
    async def get_performance_metrics(
        self,
        time_window_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Get performance metrics for time window.
        
        Args:
            time_window_hours: Hours to look back
            
        Returns:
            Dictionary with performance metrics
        """
        try:
            cutoff = datetime.now() - timedelta(hours=time_window_hours)
            
            response = self.supabase.table("agent_executions").select(
                "agent_name, execution_time_ms, tokens_used, status"
            ).gte("created_at", cutoff.isoformat()).execute()
            
            data = response.data
            
            if not data:
                return {
                    "total_requests": 0,
                    "message": "No data in time window"
                }
            
            # Calculate overall metrics
            total_requests = len(data)
            successful = len([d for d in data if d["status"] == "success"])
            failed = len([d for d in data if d["status"] == "failure"])
            
            avg_execution_time = sum(d["execution_time_ms"] for d in data) / total_requests
            total_tokens = sum(d["tokens_used"] for d in data)
            
            # Per-agent metrics
            agent_metrics = {}
            for agent_name in set(d["agent_name"] for d in data):
                agent_data = [d for d in data if d["agent_name"] == agent_name]
                agent_metrics[agent_name] = {
                    "count": len(agent_data),
                    "avg_time_ms": sum(d["execution_time_ms"] for d in agent_data) / len(agent_data),
                    "success_rate": len([d for d in agent_data if d["status"] == "success"]) / len(agent_data),
                    "total_tokens": sum(d["tokens_used"] for d in agent_data)
                }
            
            return {
                "total_requests": total_requests,
                "successful": successful,
                "failed": failed,
                "success_rate": successful / total_requests if total_requests > 0 else 0,
                "avg_execution_time_ms": avg_execution_time,
                "total_tokens_used": total_tokens,
                "agent_metrics": agent_metrics,
                "time_window_hours": time_window_hours,
                "timestamp": datetime.now().isoformat()
            }
        
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}
    
    async def get_recent_errors(
        self,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent error logs.
        
        Args:
            limit: Maximum number of errors to return
            
        Returns:
            List of recent errors
        """
        try:
            response = self.supabase.table("agent_executions").select(
                "agent_name, error_message, created_at, user_id, request_id"
            ).eq("status", "failure").order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            return response.data
        
        except Exception as e:
            logger.error(f"Failed to get recent errors: {e}")
            return []
    
    async def get_user_activity(
        self,
        user_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get user's recent agent activity.
        
        Args:
            user_id: User ID
            limit: Maximum number of records
            
        Returns:
            List of user's recent executions
        """
        try:
            response = self.supabase.table("agent_executions").select(
                "agent_name, status, execution_time_ms, tokens_used, created_at"
            ).eq("user_id", user_id).order(
                "created_at", desc=True
            ).limit(limit).execute()
            
            return response.data
        
        except Exception as e:
            logger.error(f"Failed to get user activity: {e}")
            return []
