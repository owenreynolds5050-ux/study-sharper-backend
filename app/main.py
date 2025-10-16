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
    Test endpoint for multi-agent system (Phase 2: Context Gathering).
    Does not affect existing endpoints - purely for testing agent infrastructure.
    
    This endpoint demonstrates:
    - Base agent architecture
    - Request routing and intent classification
    - Context gathering from multiple sources
    - Parallel agent execution
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
            "message": "Phase 2 test successful - context gathering working",
            "phase": 2
        }
    
    except Exception as e:
        logging.error(f"Agent test endpoint error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Agent system test failed",
            "phase": 2
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
