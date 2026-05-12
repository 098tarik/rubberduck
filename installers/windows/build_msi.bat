@echo off
setlocal

set VERSION=%1
if "%VERSION%"=="" set VERSION=1.0.0

powershell -ExecutionPolicy Bypass -File "%~dp0build_msi.ps1" -Version "%VERSION%"
if errorlevel 1 exit /b 1

echo MSI build completed.
endlocal
