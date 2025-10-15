from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import notes, chat, upload, embeddings, folders, flashcards, ai_chat, flashcards_chat, flashcard_chatbot
from app.core.config import ALLOWED_ORIGINS_LIST
from app.core.startup import run_startup_checks
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
            "flashcard_chatbot": "/api/flashcards/chatbot"
        }
    }
