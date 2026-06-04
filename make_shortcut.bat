@echo off
REM Double-click to (re)create "Twitch Playground.lnk" for THIS computer.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1"
pause
