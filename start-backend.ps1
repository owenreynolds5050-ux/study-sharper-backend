# Study Sharper Backend Startup Script
# This script starts the FastAPI backend server using uvicorn

Write-Host "Starting Study Sharper Backend Server..." -ForegroundColor Green
Write-Host "Make sure you're in the backend directory and have activated your virtual environment!" -ForegroundColor Yellow
Write-Host ""

# Check if .env.local exists
if (-Not (Test-Path ".env.local")) {
    Write-Host "WARNING: .env.local file not found!" -ForegroundColor Red
    Write-Host "Please create .env.local from .env.example and add your credentials." -ForegroundColor Yellow
    exit 1
}

# Check if uvicorn is installed
try {
    $uvicornCheck = python -m uvicorn --version 2>&1
    Write-Host "Uvicorn found: $uvicornCheck" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Uvicorn not found. Installing dependencies..." -ForegroundColor Red
    pip install -r requirements.txt
}

Write-Host ""
Write-Host "Starting server on http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""

# Start the FastAPI server with reload enabled for development
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
