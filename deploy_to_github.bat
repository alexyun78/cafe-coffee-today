@echo off
cls

echo ======================================
echo GitHub Upload Script
echo ======================================
echo.

REM Check Git installation
git --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed.
    echo Please install Git from: https://git-scm.com/downloads
    pause
    exit /b 1
)

echo [OK] Git is installed.
echo.

REM Check if Git repository exists
if not exist .git (
    echo [INFO] Initializing Git repository...
    git init
    echo.
)

REM Get GitHub information
echo Please enter your GitHub information:
echo.
set /p username="GitHub Username: "
set /p repo_name="Repository Name (example: cafe-today-coffee): "

REM Setup remote repository
echo.
echo [INFO] Connecting to remote repository...
git remote remove origin 2>nul
git remote add origin "https://github.com/%username%/%repo_name%.git"

REM Add files
echo [INFO] Adding files...
git add .

REM Commit
echo [INFO] Committing...
git commit -m "Initial commit: Cafe Today Coffee Web App"

REM Push
echo [INFO] Pushing to GitHub...
git branch -M main
git push -u origin main

echo.
echo ======================================
echo [SUCCESS] Upload Complete!
echo ======================================
echo.
echo Next Steps:
echo 1. Go to https://render.com
echo 2. Connect your GitHub repository
echo 3. Set environment variables: NOTION_TOKEN, DATABASE_ID
echo 4. Deploy!
echo.
echo For details, see RENDER_DEPLOY.md
echo.
pause
