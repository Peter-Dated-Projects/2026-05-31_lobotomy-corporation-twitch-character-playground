@echo off
REM Launcher for the Lobotomy Corporation Twitch character playground.
REM Runs: uv run playground  from the project directory.

cd /d "%~dp0"

uv run playground

REM Keep the window open if the program exits with an error so logs are visible.
if errorlevel 1 (
    echo.
    echo Playground exited with an error. Press any key to close.
    pause >nul
)
