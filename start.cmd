@echo off
setlocal
rem 一键启动包装：自动定位 PowerShell 7 并执行 start.ps1
set "SCRIPT_DIR=%~dp0"
set "PWSH="

where pwsh >nul 2>&1 && set "PWSH=pwsh"
if not defined PWSH if exist "%ProgramFiles%\PowerShell\7\pwsh.exe" set "PWSH=%ProgramFiles%\PowerShell\7\pwsh.exe"
if not defined PWSH if exist "%ProgramFiles%\PowerShell\7-preview\pwsh.exe" set "PWSH=%ProgramFiles%\PowerShell\7-preview\pwsh.exe"

if not defined PWSH (
  echo [ERROR] 未找到 PowerShell 7+(pwsh)。请安装: https://aka.ms/powershell
  pause
  exit /b 1
)

"%PWSH%" -NoLogo -ExecutionPolicy Bypass -File "%SCRIPT_DIR%start.ps1" %*
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 pause
exit /b %EXIT_CODE%
