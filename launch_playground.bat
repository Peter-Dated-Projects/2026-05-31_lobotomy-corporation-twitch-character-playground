@echo off
REM Launcher for the Lobotomy Corporation Twitch character playground + robot.
REM Starts the robot face renderer (+ TTS control-panel backend) in its own
REM window, then runs the playground (crowd sim) in this window.

cd /d "%~dp0"

REM Robot face renderer + TTS control-panel/redemption backend, in a separate
REM window. --group robot pulls in the harness deps (fastapi/uvicorn). The
REM "|| pause" keeps that window open if the robot crashes so its logs stay visible.
start "Robot" cmd /c "uv run --group robot robot || pause"

REM Playground (crowd sim) runs in this window.
uv run playground

REM Keep the window open if the program exits with an error so logs are visible.
if errorlevel 1 (
    echo.
    echo Playground exited with an error. Press any key to close.
    pause >nul
)
