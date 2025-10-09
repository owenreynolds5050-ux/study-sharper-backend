from fastapi import FastAPI
from app.api import notes, chat, upload

app = FastAPI()

app.include_router(notes.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(upload.router, prefix="/api")

@app.get("/")
def read_root():
    return {"Hello": "World"}
