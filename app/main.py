from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import notes, chat, upload, embeddings, folders, flashcards, ai_chat, flashcards_chat, flashcard_chatbot
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
from pydantic import BaseModel
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Run startup checks
run_startup_checks()

app = FastAPI(title="StudySharper API", version="1.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS_LIST,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")
app.include_router(embeddings.router, prefix="/api")
app.include_router(folders.router, prefix="/api")
app.include_router(flashcards.router, prefix="/api")
app.include_router(ai_chat.router, prefix="/api")
app.include_router(flashcards_chat.router, prefix="/api")
app.include_router(flashcard_chatbot.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "StudySharper API", "version": "1.0.0", "status": "healthy"}

@app.get("/health")
def health_check():
    """Comprehensive health check endpoint"""
    return {
        "status": "healthy",
        "service": "studysharper_backend",
        "version": "1.0.0",
        "endpoints": {
            "folders": "/api/folders",
            "notes": "/api/notes",
            "ai_chat": "/api/ai/chat",
            "flashcards": "/api/flashcards",
            "flashcard_chatbot": "/api/flashcards/chatbot",
            "agent_test": "/api/ai/agent-test"
        }
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
