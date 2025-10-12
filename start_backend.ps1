# Study Sharper Backend Startup Script
# This script activates the virtual environment and starts the FastAPI server

Write-Host "🚀 Starting Study Sharper Backend..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment
Write-Host "📦 Activating virtual environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Start the server
Write-Host "🔥 Starting FastAPI server on http://localhost:8000" -ForegroundColor Green
Write-Host "📝 API docs will be available at http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host 'Press Ctrl+C to stop the server' -ForegroundColor Yellow
Write-Host ""

# Run uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
