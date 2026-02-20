@echo off
REM Celery Beat Scheduler Startup Script

echo ========================================
echo Starting Celery Beat Scheduler
echo ========================================
echo.

call .venv\Scripts\activate.bat

echo Starting Celery beat scheduler...
echo This schedules periodic tasks (news refresh every 2 minutes)
echo.

celery -A celeryapp beat --loglevel=info

pause
