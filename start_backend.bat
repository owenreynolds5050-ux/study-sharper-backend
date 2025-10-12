@echo off
echo.
echo ====================================
echo  Study Sharper Backend Server
echo ====================================
echo.
echo Starting FastAPI server...
echo Backend will run on: http://localhost:8000
echo API docs available at: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop the server
echo.

cd /d "%~dp0"
call venv\Scripts\activate.bat
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
