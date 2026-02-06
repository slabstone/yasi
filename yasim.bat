@echo off
if "%1"=="" (
    powershell.exe -ExecutionPolicy Bypass -File "%~dp0yasim.ps1"
) else (
    powershell.exe -ExecutionPolicy Bypass -File "%~dp0yasim.ps1" -FilePath "%1"
)
