@echo off
echo ========================================
echo   Building UniPlanner Pro Executable
echo ========================================
echo.

REM Install PyInstaller if not installed
python -c "import PyInstaller" 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    echo.
)

echo Building executable (this may take a few minutes)...
echo.

REM Build the executable
pyinstaller ^
    --name UniPlannerPro ^
    --onefile ^
    --hidden-import sqlite3 ^
    --hidden-import flask ^
    --hidden-import werkzeug ^
    --clean ^
    --noconfirm ^
    app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Executable location: dist\UniPlannerPro.exe
echo.
echo You can now distribute this .exe file to any Windows machine.
echo No Python installation required!
echo.
pause

