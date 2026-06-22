@echo off
setlocal

:: Protocol handler passes ytsum://URL — strip the prefix
set "arg=%~1"
set "url=%arg:ytsum://=%"

:: Run the Python script (located next to this .bat file)
python "%~dp0summarize_yt.py" "%url%"

:: If the script failed (no .md opened), keep the window so user can read the error
if %errorlevel% neq 0 (
    echo.
    echo Press any key to close...
    pause >nul
)
