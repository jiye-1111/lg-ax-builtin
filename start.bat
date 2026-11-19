@echo off
chcp 65001 >nul
title LG 빌트인 서버 (이 창은 닫지 마세요)
cd /d "%~dp0"
set PORT=8000
for /f "tokens=2 delims==" %%p in ('findstr /b "API_PORT=" .env 2^>nul') do set PORT=%%p
echo 서버를 켭니다. 이 창은 닫지 말고 안을 클릭하지도 마세요.
echo 잠시 뒤 브라우저가 열립니다: http://localhost:%PORT%
start "" cmd /c "timeout /t 4 >nul & start http://localhost:%PORT%"
uv run lgb-api
echo.
echo 서버가 멈췄습니다. 위 오류를 캡처해 두세요.
pause
