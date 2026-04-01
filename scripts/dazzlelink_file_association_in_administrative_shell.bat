@echo off
setlocal enabledelayedexpansion

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

:: Determine Python path
for /f "tokens=*" %%a in ('where python 2^>nul') do (
    set PYTHON_PATH=%%a
    goto :found_python
)

:: Python not found in PATH, try common locations
if exist "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python310\python.exe
    goto :found_python
)

if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python39\python.exe
    goto :found_python
)

if exist "%LOCALAPPDATA%\Programs\Python\Python38\python.exe" (
    set PYTHON_PATH=%LOCALAPPDATA%\Programs\Python\Python38\python.exe
    goto :found_python
)

echo Python installation not found. Please make sure Python is installed.
echo.
pause
exit /b 1

:found_python
echo Found Python at: %PYTHON_PATH%

:: Find pythonw.exe (windowless Python -- no console flash on double-click)
set PYTHONW_PATH=%PYTHON_PATH:python.exe=pythonw.exe%
if not exist "%PYTHONW_PATH%" (
    set PYTHONW_PATH=%PYTHON_PATH%
    echo Note: pythonw.exe not found, using python.exe (console window will flash)
) else (
    echo Found pythonw at: %PYTHONW_PATH%
)

:: Determine script location
:: Prefer the monolith dazzlelink.py (most reliable, always up to date)
set SCRIPT_DIR=%~dp0
set DAZZLELINK_SCRIPT=%SCRIPT_DIR%..\dazzlelink.py

if not exist "%DAZZLELINK_SCRIPT%" (
    set DAZZLELINK_SCRIPT=%SCRIPT_DIR%dazzlelink.py
)

if exist "%DAZZLELINK_SCRIPT%" (
    echo Using dazzlelink script: %DAZZLELINK_SCRIPT%
    set "OPEN_CMD="%PYTHONW_PATH%" "%DAZZLELINK_SCRIPT%" execute "%%1""
    set "INFO_CMD=cmd.exe /c ""%PYTHON_PATH%" "%DAZZLELINK_SCRIPT%" execute --mode info "%%1" ^& pause""
    set "IMPORT_CMD="%PYTHON_PATH%" "%DAZZLELINK_SCRIPT%" import "%%1""
    goto :register
)

:: Fall back to pip-installed package
where dazzlelink >nul 2>&1
if %errorLevel% equ 0 (
    echo Using installed dazzlelink package
    set "OPEN_CMD="%PYTHONW_PATH%" -m dazzlelink execute "%%1""
    set "INFO_CMD=cmd.exe /c ""%PYTHON_PATH%" -m dazzlelink execute --mode info "%%1" ^& pause""
    set "IMPORT_CMD="%PYTHON_PATH%" -m dazzlelink import "%%1""
    goto :register
)

echo.
echo dazzlelink.py not found. Checked:
echo   %SCRIPT_DIR%..\dazzlelink.py
echo   %SCRIPT_DIR%dazzlelink.py
echo   pip package: not installed
echo.
set /p DAZZLELINK_SCRIPT=Please enter the full path to dazzlelink.py:

if not exist "!DAZZLELINK_SCRIPT!" (
    echo File not found: !DAZZLELINK_SCRIPT!
    pause
    exit /b 1
)

echo Using dazzlelink script: %DAZZLELINK_SCRIPT%
set "OPEN_CMD="%PYTHON_PATH%" "%DAZZLELINK_SCRIPT%" execute "%%1""
set "INFO_CMD=cmd.exe /c ""%PYTHON_PATH%" "%DAZZLELINK_SCRIPT%" execute --mode info "%%1" ^& pause""
set "IMPORT_CMD="%PYTHON_PATH%" "%DAZZLELINK_SCRIPT%" import "%%1""

:register
echo.

:: Register file type using reg add (more reliable than .reg file import)
echo Registering .dazzlelink file type...

reg add "HKCR\.dazzlelink" /ve /d "DazzlelinkFile" /f >nul 2>&1
if %errorLevel% neq 0 (
    reg add "HKEY_CLASSES_ROOT\.dazzlelink" /ve /d "DazzlelinkFile" /f >nul 2>&1
)

reg add "HKCR\DazzlelinkFile" /ve /d "Dazzlelink Symbolic Link" /f >nul 2>&1
if %errorLevel% neq 0 (
    reg add "HKEY_CLASSES_ROOT\DazzlelinkFile" /ve /d "Dazzlelink Symbolic Link" /f >nul 2>&1
)

reg add "HKCR\DazzlelinkFile" /v "FriendlyTypeName" /d "Dazzlelink Symbolic Link" /f >nul 2>&1

:: Default icon (Python icon)
reg add "HKCR\DazzlelinkFile\DefaultIcon" /ve /d "%PYTHON_PATH%,0" /f >nul 2>&1

:: Open command (double-click action -- opens the target)
reg add "HKCR\DazzlelinkFile\shell\open\command" /ve /d "%OPEN_CMD%" /f >nul 2>&1
if %errorLevel% neq 0 (
    reg add "HKEY_CLASSES_ROOT\DazzlelinkFile\shell\open\command" /ve /d "%OPEN_CMD%" /f >nul 2>&1
)

:: Context menu: Show Information
reg add "HKCR\DazzlelinkFile\shell\info" /ve /d "Show Information" /f >nul 2>&1
reg add "HKCR\DazzlelinkFile\shell\info\command" /ve /d "%INFO_CMD%" /f >nul 2>&1

:: Context menu: Recreate Symlink
reg add "HKCR\DazzlelinkFile\shell\recreate" /ve /d "Recreate Symlink" /f >nul 2>&1
reg add "HKCR\DazzlelinkFile\shell\recreate\command" /ve /d "%IMPORT_CMD%" /f >nul 2>&1

echo.
echo File association created successfully!
echo.
echo You can now:
echo   - Double-click .dazzlelink files to open their targets
echo   - Right-click for "Show Information" or "Recreate Symlink"

echo.
pause
exit /b