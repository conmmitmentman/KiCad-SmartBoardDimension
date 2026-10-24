@echo off
chcp 65001 >nul
setlocal
powershell.exe -NoProfile -File "%~dp0scripts\installer.ps1" -Mode Update
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" echo 更新に失敗しました。上の内容をご確認ください。
pause
exit /b %CODE%
