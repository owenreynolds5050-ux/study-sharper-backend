from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import notes, chat, upload, embeddings, folders, flashcards, ai_chat, flashcards_chat, flashcard_chatbot
from app.core.config import ALLOWED_ORIGINS_LIST
from app.core.startup import run_startup_checks
from app.agents.orchestrator import MainOrchestrator
from app.agents.models import AgentRequest
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
    Test endpoint for new multi-agent system (Phase 1).
    Does not affect existing endpoints - purely for testing agent infrastructure.
    
    This endpoint demonstrates:
    - Base agent architecture
    - Request routing and intent classification
    - Execution plan generation
    - Progress tracking capability
    
    Future phases will add actual subagent execution and LLM integration.
    """
    try:
        # Create orchestrator instance
        orchestrator = MainOrchestrator()
        
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
            "message": "Phase 1 test successful - agent infrastructure working",
            "phase": 1,
            "note": "This is a test endpoint. Existing endpoints remain unchanged."
        }
    
    except Exception as e:
        logging.error(f"Agent test endpoint error: {e}")
        return {
            "status": "error",
            "error": str(e),
            "message": "Agent system test failed",
            "phase": 1
        }
