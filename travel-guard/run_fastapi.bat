@echo off
setlocal
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8

if not exist "requirements.txt" (
    echo requirements.txt was not found.
    exit /b 1
)

echo Starting the complete Travel Guard FastAPI application...
echo Web app: http://127.0.0.1:8000/
echo API docs: http://127.0.0.1:8000/docs
python -m uvicorn fastapi_app:app --host 0.0.0.0 --port 8000
endlocal
