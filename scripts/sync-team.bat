@echo off
rem 내 저장소 main을 팀 저장소(2Jaegon/LG_P3_digitaltwin) jiye 브랜치로 올린다. 팀 main에는 올리지 않는다.
chcp 65001 >nul
cd /d %~dp0..
git remote get-url team >nul 2>&1 || git remote add team https://github.com/2Jaegon/LG_P3_digitaltwin
git fetch origin main || goto :fail
git push team origin/main:refs/heads/jiye || goto :fail
echo 팀 저장소 jiye 브랜치 업데이트 완료
pause
exit /b 0
:fail
echo 실패했습니다. 위 메시지를 확인하세요.
pause
exit /b 1
