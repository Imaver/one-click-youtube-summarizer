@echo off
setlocal

:: Protocol handler passes ytsum://URL — strip the prefix
set "arg=%~1"
set "url=%arg:ytsum://=%"

:: Run the Python script (located next to this .bat file)
python "%~dp0summarize_yt.py" "%url%"

echo.
echo Press any key to close...
pause >nul
