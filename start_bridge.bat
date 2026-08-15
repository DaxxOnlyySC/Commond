@echo off
title LuaExec Bridge + Ngrok
echo ==========================================
echo   LuaExec Bridge Server + Ngrok
echo ==========================================
echo.

cd /d "C:\Users\daxxx\Desktop\Discord Commond"

echo [1/2] Starting Bridge Server...
start /b python bridge_server.py >nul 2>&1

timeout /t 2 >nul

echo [2/2] Starting Ngrok on port 18234...
start /b ngrok http 18234 >nul 2>&1

echo.
echo ==========================================
echo   Semua sudah jalan di satu window!
echo   Bridge Server: http://localhost:18234
echo   Buka browser ke: http://localhost:4040 
echo   untuk lihat URL ngrok
echo ==========================================
echo.
pause
