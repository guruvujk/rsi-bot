@echo off
title RSI Bot Launcher
echo =======================================
echo    RSI BOT — Starting...
echo =======================================

:: Kill any existing Python process on port 5000
echo [1/3] Clearing port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000 ^| findstr LISTENING') do taskkill /PID %%a /F 2>nul

:: Activate venv
echo [2/3] Activating virtual environment...
cd C:\Users\JKRAOWIN\rsi_bot_v2\rsi_bot_v2
call venv\Scripts\activate

:: Start bot
echo [3/3] Starting RSI Bot...
echo =======================================
python main.py
