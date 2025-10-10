from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import notes, chat, upload

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notes.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

@app.get("/")
def read_root():
    return {"Hello": "World"}
