@echo off
REM Celery Worker Startup Script

echo ========================================
echo Starting Celery Worker
echo ========================================
echo.

call .venv\Scripts\activate.bat

echo Starting Celery worker...
echo This will process background tasks like news fetching
echo.

celery -A celeryapp worker --loglevel=info --pool=solo

pause
