@echo off
REM Vedant Daily News - Development Server Startup Script

echo ========================================
echo Vedant Daily News - Starting Server
echo ========================================
echo.

REM Activate virtual environment
call .venv\Scripts\activate.bat

REM Check if Redis is needed
echo Checking for Redis...
echo Note: For auto-refresh, Redis must be running separately
echo.

REM Start Django development server
echo Starting Django development server...
echo Access the application at: http://127.0.0.1:8000
echo Access admin panel at: http://127.0.0.1:8000/admin
echo.
echo Press Ctrl+C to stop the server
echo.

python manage.py runserver

pause
