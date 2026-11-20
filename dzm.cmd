@echo off
rem AI Company DayZMods CLI launcher for PowerShell and CMD on Windows: .\dzm.cmd -h
setlocal
set "PYTHONUTF8=1"
set "CLI=%~dp0AI_Company_DayZMods\Company\Tools\company.py"
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%CLI%" %*
  exit /b
)
where python >nul 2>nul
if not errorlevel 1 (
  python "%CLI%" %*
  exit /b
)
echo dzm: Python 3 not found. Install it: winget install Python.Python.3.13 1>&2
exit /b 127
