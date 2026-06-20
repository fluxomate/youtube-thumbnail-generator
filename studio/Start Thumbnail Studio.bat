@echo off
title Thumbnail Studio
cd /d "%~dp0"
echo.
echo   Starting Thumbnail Studio...
echo   It will open in your browser at http://127.0.0.1:5005
echo.
start "" http://127.0.0.1:5005
python server.py
pause
