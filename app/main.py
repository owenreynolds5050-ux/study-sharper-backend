from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.api import notes, chat, embeddings, folders, flashcards, ai_chat
# Old upload disabled - using new file_upload API
from app.api.files import router as files_router
from app.api.file_upload import router as file_upload_router
from app.core.config import ALLOWED_ORIGINS_LIST
from app.core.startup import run_startup_checks
from app.agents.orchestrator import MainOrchestrator
from app.agents.models import AgentRequest
from app.agents.context.rag_agent import RAGAgent
from app.agents.context.user_profile_agent import UserProfileAgent
from app.agents.context.progress_agent import ProgressAgent
from app.agents.context.conversation_agent import ConversationAgent
from app.agents.tasks.flashcard_agent import FlashcardAgent
from app.agents.tasks.quiz_agent import QuizAgent
from app.agents.tasks.summary_agent import SummaryAgent
from app.agents.tasks.chat_agent import ChatAgent
from app.agents.validation.accuracy_agent import AccuracyAgent
from app.agents.validation.safety_agent import SafetyAgent
from app.agents.validation.quality_agent import QualityAgent
from app.agents.sse import sse_manager
from app.agents.content_saver import ContentSaver
from app.agents.monitoring import AgentMonitor
from app.core.database import supabase
from app.services.job_queue import job_queue
from app.core.websocket import ws_manager
from app.core.auth import get_current_user_from_token
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import asyncio
import json
import logging
import os

# Initialize services
content_saver = ContentSaver(supabase)
agent_monitor = AgentMonitor(supabase)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Run startup checks
run_startup_checks()

app = FastAPI(title="StudySharper API", version="1.0.0")

# Configure CORS FIRST - MUST be before routers
# This ensures CORS headers are added to all responses, including errors
logging.info("Configuring CORS with wildcard for all origins")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False with wildcard
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)
logging.info("CORS middleware configured with wildcard")

# Background task for SSE cleanup
async def start_sse_cleanup():
    """Background task to cleanup stale SSE connections"""
    while True:
        await asyncio.sleep(60)  # Every minute
        try:
            cleaned = await sse_manager.cleanup_stale_connections()
            if cleaned > 0:
                logging.info(f"Cleaned up {cleaned} stale SSE connections")
        except Exception as e:
            logging.error(f"Error in SSE cleanup task: {e}")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    job_queue.start_workers()
    asyncio.create_task(start_sse_cleanup())
    logging.info("Background tasks started: SSE cleanup")
    print("✓ Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await job_queue.stop_workers()
    print("✓ Application shutdown complete")


@app.websocket("/ws/files")
async def websocket_endpoint(websocket: WebSocket, token: str):
    """WebSocket endpoint for real-time file processing updates"""
    try:
        # Authenticate user from token
        user = await get_current_user_from_token(token)
        user_id = user["id"]

        # Connect
        await ws_manager.connect(websocket, user_id)

        try:
            # Keep connection alive
            while True:
                # Wait for messages (ping/pong)
                data = await websocket.receive_text()

                # Echo back as heartbeat
                if data == "ping":
                    await websocket.send_text("pong")

        except WebSocketDisconnect:
            await ws_manager.disconnect(websocket, user_id)

    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close()

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(notes.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
# app.include_router(upload.router, prefix="/api", tags=["upload"])  # Old upload disabled
app.include_router(embeddings.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(flashcards.router, prefix="/api")
app.include_router(ai_chat.router, prefix="/api")
app.include_router(files_router, prefix="/api", tags=["files"])
app.include_router(file_upload_router, prefix="/api", tags=["upload"])

@app.get("/")
def read_root():
    return {"message": "StudySharper API", "version": "1.0.0", "status": "healthy"}

@app.get("/health")
async def health_check():
    """
    Comprehensive health check endpoint for monitoring and load balancers.
    Returns system status, version, and component health.
    """
    try:
        # Test database connection
        db_healthy = True
        try:
            supabase.table("flashcards").select("id").limit(1).execute()
        except:
            db_healthy = False
        
        # Check if monitoring is working
        monitoring_healthy = agent_monitor is not None
        
        # Overall status
        overall_status = "healthy" if db_healthy else "degraded"
        
        return {
            "status": overall_status,
            "service": "studysharper_backend",
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": "healthy" if db_healthy else "unhealthy",
                "monitoring": "healthy" if monitoring_healthy else "disabled",
                "rate_limiting": "enabled",
                "sse_streaming": "enabled"
            },
            "endpoints": {
                "ai_streaming": "/api/ai/process-stream",
                "ai_stream": "/api/ai/stream/{session_id}",
                "generated_content": "/api/ai/generated-content/{type}",
                "admin_metrics": "/api/admin/metrics",
                "notes": "/api/notes",
                "flashcards": "/api/flashcards"
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/health/queue")
async def queue_health():
    """Get job queue status"""
    return {
        "status": "healthy",
        "queues": job_queue.get_queue_status(),
        "memory_ok": job_queue.check_memory()
    }


@app.post("/api/ai/agent-test")
async def test_agent_system(request: AgentRequest):
    """
    Test endpoint for multi-agent system (Phase 4: Validation & Safety).
    Does not affect existing endpoints - purely for testing agent infrastructure.
    
    This endpoint demonstrates:
    - Base agent architecture
    - Request routing and intent classification
    - Context gathering from multiple sources
    - Task execution with LLM
    - Content generation (flashcards, quizzes, summaries, chat)
    - Validation (safety, quality, accuracy)
    - Retry logic with corrections
    - Progress tracking capability
    """
    try:
        # Create orchestrator instance
        orchestrator = MainOrchestrator()
        
        # Track progress updates
        progress_updates = []
        
        async def progress_callback(progress):
            progress_updates.append(progress.dict())
        
        orchestrator.add_progress_callback(progress_callback)
        
        # Execute request through agent system
        result = await orchestrator.execute(
            input_data=request.dict()
        )
        
        # Return standardized response
        return {
            "status": "success" if result.success else "error",
            "result": result.data,
            "execution_time_ms": result.execution_time_ms,
            "model_used": result.model_used,
            "progress_updates": progress_updates,
            "message": "Phase 4 test successful - validation working",
            "phase": 4
        }
    
    except Exception as e:
        logging.error(f"Agent test endpoint error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Agent system test failed",
            "phase": 4
        }


# Individual agent test endpoints for debugging

@app.post("/api/ai/test-rag")
async def test_rag_agent(user_id: str, query: str, top_k: int = 5):
    """Test RAG agent individually"""
    try:
        agent = RAGAgent()
        result = await agent.execute({
            "user_id": user_id,
            "query": query,
            "top_k": top_k
        })
        return result.dict()
    except Exception as e:
        logging.error(f"RAG test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-profile")
async def test_profile_agent(user_id: str):
    """Test profile agent individually"""
    try:
        agent = UserProfileAgent()
        result = await agent.execute({"user_id": user_id})
        return result.dict()
    except Exception as e:
        logging.error(f"Profile test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-progress")
async def test_progress_agent(user_id: str, days_back: int = 30):
    """Test progress agent individually"""
    try:
        agent = ProgressAgent()
        result = await agent.execute({
            "user_id": user_id,
            "days_back": days_back
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Progress test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-conversation")
async def test_conversation_agent(user_id: str, session_id: str, limit: int = 10):
    """Test conversation agent individually"""
    try:
        agent = ConversationAgent()
        result = await agent.execute({
            "user_id": user_id,
            "session_id": session_id,
            "limit": limit
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Conversation test error: {e}")
        return {"error": str(e)}


# Task agent test endpoints (Phase 3)

class FlashcardTestRequest(BaseModel):
    content: str
    count: int = 10
    difficulty: str = "medium"

class QuizTestRequest(BaseModel):
    content: str
    question_count: int = 10
    difficulty: str = "medium"

class SummaryTestRequest(BaseModel):
    content: str
    length: str = "medium"
    style: str = "bullet_points"

class ChatTestRequest(BaseModel):
    message: str

@app.post("/api/ai/test-flashcards")
async def test_flashcards(request: FlashcardTestRequest):
    """Test flashcard generation directly"""
    try:
        agent = FlashcardAgent()
        result = await agent.execute({
            "content": request.content,
            "count": request.count,
            "difficulty": request.difficulty
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Flashcard test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-quiz")
async def test_quiz(request: QuizTestRequest):
    """Test quiz generation directly"""
    try:
        agent = QuizAgent()
        result = await agent.execute({
            "content": request.content,
            "question_count": request.question_count,
            "difficulty": request.difficulty
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Quiz test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-summary")
async def test_summary(request: SummaryTestRequest):
    """Test summary generation directly"""
    try:
        agent = SummaryAgent()
        result = await agent.execute({
            "content": request.content,
            "length": request.length,
            "style": request.style
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Summary test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-chat")
async def test_chat(request: ChatTestRequest):
    """Test chat agent directly"""
    try:
        agent = ChatAgent()
        result = await agent.execute({
            "message": request.message
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Chat test error: {e}")
        return {"error": str(e)}


# Validation agent test endpoints (Phase 4)

class SafetyTestRequest(BaseModel):
    content: Dict[str, Any]
    content_type: str
    age_group: str = "high_school"

class AccuracyTestRequest(BaseModel):
    generated_content: Dict[str, Any]
    source_material: str
    content_type: str

class QualityTestRequest(BaseModel):
    content: Dict[str, Any]
    content_type: str

class FullValidationRequest(BaseModel):
    content: Dict[str, Any]
    content_type: str
    source_material: Optional[str] = None

@app.post("/api/ai/test-safety")
async def test_safety_agent(request: SafetyTestRequest):
    """Test safety agent directly"""
    try:
        agent = SafetyAgent()
        result = await agent.execute({
            "content": request.content,
            "content_type": request.content_type,
            "age_group": request.age_group
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Safety test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-accuracy")
async def test_accuracy_agent(request: AccuracyTestRequest):
    """Test accuracy agent directly"""
    try:
        agent = AccuracyAgent()
        result = await agent.execute({
            "generated_content": request.generated_content,
            "source_material": request.source_material,
            "content_type": request.content_type
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Accuracy test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-quality")
async def test_quality_agent(request: QualityTestRequest):
    """Test quality agent directly"""
    try:
        agent = QualityAgent()
        result = await agent.execute({
            "content": request.content,
            "content_type": request.content_type
        })
        return result.dict()
    except Exception as e:
        logging.error(f"Quality test error: {e}")
        return {"error": str(e)}


@app.post("/api/ai/test-full-validation")
async def test_full_validation(request: FullValidationRequest):
    """Test complete validation pipeline"""
    try:
        safety_agent = SafetyAgent()
        quality_agent = QualityAgent()
        accuracy_agent = AccuracyAgent()
        
        # Run safety check
        safety_result = await safety_agent.execute({
            "content": request.content,
            "content_type": request.content_type
        })
        
        # Run quality check
        quality_result = await quality_agent.execute({
            "content": request.content,
            "content_type": request.content_type
        })
        
        # Run accuracy check if source material provided
        accuracy_result = None
        if request.source_material:
            accuracy_result = await accuracy_agent.execute({
                "generated_content": request.content,
                "source_material": request.source_material,
                "content_type": request.content_type
            })
        
        # Determine overall pass/fail
        overall_passed = (
            safety_result.data.get("is_safe", False) and
            quality_result.data.get("quality_score", 0) > 0.6 and
            (not accuracy_result or accuracy_result.data.get("accuracy_score", 0) > 0.7)
        )
        
        return {
            "safety": safety_result.dict(),
            "quality": quality_result.dict(),
            "accuracy": accuracy_result.dict() if accuracy_result else None,
            "overall_passed": overall_passed,
            "summary": {
                "safety_score": safety_result.data.get("safety_score", 0),
                "quality_score": quality_result.data.get("quality_score", 0),
                "accuracy_score": accuracy_result.data.get("accuracy_score", 0) if accuracy_result else None
            }
        }
    except Exception as e:
        logging.error(f"Full validation test error: {e}")
        return {"error": str(e)}


# SSE Streaming endpoints (Phase 5)

@app.get("/api/ai/stream/{session_id}")
async def stream_progress(session_id: str, request: Request):
    """
    SSE endpoint for real-time progress updates.
    
    Connect to this endpoint to receive real-time updates for a processing session.
    Events are sent in Server-Sent Events format.
    """
    logging.info(f"SSE stream connection requested for session: {session_id}")
    
    return StreamingResponse(
        sse_manager.event_generator(session_id, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@app.post("/api/ai/process-stream")
@limiter.limit("10/minute")
async def process_with_streaming(request: Request, ai_request: AgentRequest):
    """
    Process AI request with real-time streaming updates.
    
    This endpoint:
    1. Starts processing immediately
    2. Returns a session_id and stream URL
    3. Sends progress updates via SSE
    4. Sends final result when complete
    
    Connect to the returned stream_url to receive updates.
    """
    
    # Generate session ID if not provided
    if not ai_request.session_id:
        ai_request.session_id = str(uuid.uuid4())
    
    logging.info(f"Stream processing started for session: {ai_request.session_id}")
    
    # Define background execution task
    async def execute_and_stream():
        try:
            # Send start event
            await sse_manager.send_update(
                ai_request.session_id,
                {
                    "type": "start",
                    "timestamp": datetime.now().isoformat(),
                    "session_id": ai_request.session_id
                }
            )
            
            # Create orchestrator
            orchestrator = MainOrchestrator()
            
            # Add progress callback that sends SSE updates
            async def progress_callback(progress):
                await sse_manager.send_update(
                    ai_request.session_id,
                    {
                        "type": "progress",
                        "data": progress.dict()
                    }
                )
            
            orchestrator.add_progress_callback(progress_callback)
            
            # Execute orchestrator with request_id for monitoring
            input_data = ai_request.dict()
            input_data["request_id"] = str(uuid.uuid4())
            result = await orchestrator.execute(input_data=input_data)
            
            # Save generated content if successful
            save_result = None
            if result.success and ai_request.user_id:
                try:
                    save_result = await content_saver.save_generated_content(
                        ai_request.user_id,
                        ai_request.type,
                        result.data
                    )
                    logging.info(f"Content saved: {save_result}")
                except Exception as save_error:
                    logging.error(f"Failed to save content: {save_error}")
            
            # Send result
            await sse_manager.send_update(
                ai_request.session_id,
                {
                    "type": "complete",
                    "data": result.data if result.success else {"error": result.error},
                    "success": result.success,
                    "execution_time_ms": result.execution_time_ms,
                    "validation": result.data.get("validation") if result.success else None,
                    "saved": save_result
                }
            )
            
            logging.info(f"Stream processing completed for session: {ai_request.session_id}")
        
        except Exception as e:
            logging.error(f"Stream processing error for session {ai_request.session_id}: {e}")
            await sse_manager.send_update(
                ai_request.session_id,
                {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        finally:
            # Signal completion
            await sse_manager.close_connection(ai_request.session_id)
    
    # Start execution in background
    asyncio.create_task(execute_and_stream())
    
    return {
        "status": "processing",
        "session_id": ai_request.session_id,
        "stream_url": f"/api/ai/stream/{ai_request.session_id}",
        "message": "Processing started. Connect to stream_url for real-time updates."
    }


@app.get("/api/ai/stream-status")
async def get_stream_status():
    """Get status of SSE streaming system"""
    return {
        "active_connections": sse_manager.get_active_connections(),
        "status": "operational"
    }


# Content retrieval and feedback endpoints (Phase 5)

class FeedbackRequest(BaseModel):
    content_type: str
    content_id: str
    rating: int
    feedback_text: Optional[str] = None
    issues: Optional[List[str]] = None

@app.post("/api/ai/feedback")
async def submit_feedback(feedback: FeedbackRequest, user_id: str):
    """
    Collect user feedback on generated content.
    
    Args:
        feedback: Feedback data
        user_id: User ID (from auth)
        
    Returns:
        Success status
    """
    try:
        supabase.table("content_feedback").insert({
            "user_id": user_id,
            "content_type": feedback.content_type,
            "content_id": feedback.content_id,
            "rating": feedback.rating,
            "feedback_text": feedback.feedback_text,
            "issues": json.dumps(feedback.issues or []),
            "created_at": datetime.now().isoformat()
        }).execute()
        
        logging.info(f"Feedback recorded: {feedback.content_type} - {feedback.rating}/5")
        return {
            "status": "success",
            "message": "Feedback recorded"
        }
    
    except Exception as e:
        logging.error(f"Failed to record feedback: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/ai/generated-content/{content_type}")
@limiter.limit("30/minute")
async def get_generated_content(
    request: Request,
    content_type: str,
    user_id: str,
    limit: int = 20
):
    """
    Retrieve user's generated content.
    
    Args:
        content_type: Type of content (flashcards, quizzes, exams, summaries)
        user_id: User ID (from auth)
        limit: Maximum number of items
        
    Returns:
        List of generated content items
    """
    try:
        items = await content_saver.get_user_content(user_id, content_type, limit)
        
        return {
            "status": "success",
            "content_type": content_type,
            "items": items,
            "count": len(items)
        }
    
    except Exception as e:
        logging.error(f"Failed to get generated content: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/ai/content-stats/{user_id}")
async def get_content_stats(user_id: str):
    """
    Get statistics about user's generated content.
    
    Args:
        user_id: User ID
        
    Returns:
        Content statistics
    """
    try:
        stats = {}
        
        # Count each content type
        for content_type in ["flashcards", "quizzes", "exams", "summaries"]:
            items = await content_saver.get_user_content(user_id, content_type, limit=1000)
            stats[content_type] = len(items)
        
        return {
            "status": "success",
            "stats": stats,
            "total_items": sum(stats.values())
        }
    
    except Exception as e:
        logging.error(f"Failed to get content stats: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


# Monitoring and Admin endpoints (Phase 6)

@app.get("/api/admin/metrics")
async def get_system_metrics(hours: int = 24, admin_token: Optional[str] = None):
    """
    Get system performance metrics.
    
    Args:
        hours: Time window in hours (default: 24)
        admin_token: Admin authentication token
        
    Returns:
        Performance metrics
    """
    # Verify admin authentication
    expected_token = os.getenv("ADMIN_TOKEN")
    if not expected_token or admin_token != expected_token:
        return {"error": "Unauthorized", "status": 403}
    
    try:
        metrics = await agent_monitor.get_performance_metrics(hours)
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        logging.error(f"Failed to get metrics: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/admin/errors")
async def get_recent_errors(limit: int = 10, admin_token: Optional[str] = None):
    """
    Get recent error logs.
    
    Args:
        limit: Maximum number of errors to return
        admin_token: Admin authentication token
        
    Returns:
        Recent error logs
    """
    # Verify admin authentication
    expected_token = os.getenv("ADMIN_TOKEN")
    if not expected_token or admin_token != expected_token:
        return {"error": "Unauthorized", "status": 403}
    
    try:
        errors = await agent_monitor.get_recent_errors(limit)
        return {
            "status": "success",
            "errors": errors,
            "count": len(errors)
        }
    except Exception as e:
        logging.error(f"Failed to get errors: {e}")
        return {
            "status": "error",
            "error": str(e)
        }


@app.get("/api/admin/user-activity/{user_id}")
async def get_user_activity(user_id: str, limit: int = 20, admin_token: Optional[str] = None):
    """
    Get user's recent agent activity.
    
    Args:
        user_id: User ID
        limit: Maximum number of records
        admin_token: Admin authentication token
        
    Returns:
        User's recent activity
    """
    # Verify admin authentication
    expected_token = os.getenv("ADMIN_TOKEN")
    if not expected_token or admin_token != expected_token:
        return {"error": "Unauthorized", "status": 403}
    
    try:
        activity = await agent_monitor.get_user_activity(user_id, limit)
        return {
            "status": "success",
            "activity": activity,
            "count": len(activity)
        }
    except Exception as e:
        logging.error(f"Failed to get user activity: {e}")
        return {
            "status": "error",
            "error": str(e)
        }
