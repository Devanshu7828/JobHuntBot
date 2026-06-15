@echo off
REM ─── JobHuntBot Daily Runner ───────────────────────────────────────────────
REM Double-click this file to run the bot manually any time.
REM ───────────────────────────────────────────────────────────────────────────

cd /d "%~dp0\.."
echo Running JobHuntBot from %CD%
echo.

py main.py

if errorlevel 1 (
    echo.
    echo ERROR: Bot run failed. Check logs\ folder for details.
    pause
    exit /b 1
)

echo.
echo Done. Report opened in your browser.
pause
