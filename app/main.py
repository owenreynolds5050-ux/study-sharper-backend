from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import notes, chat, upload, embeddings, folders, flashcards, ai_chat
from app.core.config import ALLOWED_ORIGINS_LIST

app = FastAPI()

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

@app.get("/")
def read_root():
    return {"Hello": "World"}
