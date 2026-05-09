@echo off
setlocal
cd /d "%~dp0"

set AUTO_START=true
set AUTO_STOP_AFTER_SECONDS=7200
set PLAYWRIGHT_HEADLESS=true

echo Sporbot 2 saatlik otomatik kontrol baslatiliyor...
echo Pencereyi kapatirsan bot durur.
echo.

python app.py

echo.
echo Sporbot kapandi.
pause
