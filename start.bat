@echo off
title LuaExec Discord Bot
echo ==========================================
echo   LuaExec Discord Bot Auto Launcher
echo ==========================================
echo.

:: Install dependencies
echo [1/3] Installing dependencies...
pip install discord.py pywin32 psutil >nul 2>&1
echo Dependencies ready!
echo.

:: Start Bridge (creates pipes + injects DLL)
echo [2/3] Starting Bridge...
cd /d "C:\Users\daxxx\Desktop\Discord Commond"
start "Bridge" python bridge.py
timeout /t 2 /nobreak >nul
echo Bridge started!
echo.

:: Start Discord Bot
echo [3/3] Starting Discord Bot...
cd /d "C:\Users\daxxx\Desktop\Discord Commond"
start "Discord Bot" python main.py
echo Discord Bot started!
echo.

echo ==========================================
echo   All running! No LuaExecV4 app needed.
echo   Bot commands: !kick, !kickpc, !banplayer
echo ==========================================
pause
