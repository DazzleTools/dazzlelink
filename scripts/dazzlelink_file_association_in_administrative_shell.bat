@echo off
setlocal

echo Dazzlelink File Association Setup
echo ================================
echo.

:: Check for administrative rights
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo This script requires administrative privileges.
    echo Please right-click and select "Run as administrator".
    echo.
    pause
    exit /b 1
)

:: Registry work belongs in PowerShell: the shell-verb command values embed
:: quotes AND an ampersand, both of which cmd.exe re-parses at reg add time
:: (the ampersand split the command; the quote dance stripped quoting from
:: the stored values -- see the v0.11.0 fix notes). This wrapper only keeps
:: the admin check and a pause for double-clickers; the single registration
:: implementation lives in the companion .ps1.
set "PS1=%~dp0dazzlelink_file_association_in_administrative_shell.ps1"
if not exist "%PS1%" (
    echo Companion script not found: %PS1%
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS1%"
set EXITCODE=%errorLevel%

echo.
pause
exit /b %EXITCODE%
