@echo off
rem detect-python.cmd
rem Prints the full path of a working Python >= 3.9 (with ctypes) and exits 0.
rem Exits 1 if none is found, 2 if a temporary folder cannot be created.
rem
rem How it tells a real Python from the Microsoft Store alias stub:
rem  1. Anything under \Microsoft\WindowsApps\ is skipped without running it, so
rem     the Store can never open. This also skips genuine Store and Python
rem     Install Manager aliases; those machines get the private runtime instead.
rem  2. Every other candidate runs only WITH arguments, stdin from NUL, from an
rem     empty folder, and must print a per-run random token. A stub, a shim or
rem     an old Python cannot produce that output, whatever its exit code.
rem  3. Each probe has a hard timeout. PowerShell is used only to kill a hung probe.
rem Candidate order: python, python3, py -3.

setlocal EnableExtensions DisableDelayedExpansion
set "PROBE_TIMEOUT=10"
set "EC_WORK=%TEMP%\ec-detect-%RANDOM%%RANDOM%"
mkdir "%EC_WORK%" >nul 2>&1
if not exist "%EC_WORK%\" exit /b 2

set "FOUND="
for %%N in (python python3) do (
  for /f "delims=" %%P in ('where %%N 2^>nul') do (
    if not defined FOUND call :try "%%P" "-B"
  )
)
if not defined FOUND (
  for /f "delims=" %%P in ('where py 2^>nul') do (
    if not defined FOUND call :try "%%P" "-3 -B"
  )
)

rmdir /s /q "%EC_WORK%" >nul 2>&1
if not defined FOUND exit /b 1
for /f "delims=" %%F in ("%FOUND%") do (
  endlocal
  echo(%%F
  exit /b 0
)
exit /b 1

:try
rem %~1 = candidate path, %~2 = interpreter arguments. The arguments must be
rem non-empty: an empty variable stays as literal text in the cmd /c line below.
set "EC_CAND=%~1"
set "EC_ARGS=%~2"
rem Skip the alias folder without executing anything in it.
if /i not "%EC_CAND:\Microsoft\WindowsApps\=%"=="%EC_CAND%" exit /b 0

set "EC_TOKEN=EC%RANDOM%%RANDOM%"
set "EC_CODE=import sys,ctypes;sys.version_info>=(3,9) or sys.exit(1);print('%EC_TOKEN%');print(sys.executable)"
rem Per-probe file names, so a hung probe cannot block the next candidate.
set "EC_OUT=%EC_WORK%\%EC_TOKEN%.out"
set "EC_DONE=%EC_WORK%\%EC_TOKEN%.done"

rem The child expands its !variables! only after parsing, so characters such as
rem ampersands and parentheses in a path stay inert. The trailing rem carries the
rem token so a hung probe can be found and killed.
start "" /b /d "%EC_WORK%" cmd /d /v:on /c ^""!EC_CAND!" !EC_ARGS! -c "!EC_CODE!" ^<nul ^>"!EC_OUT!" 2^>nul ^& echo done^>"!EC_DONE!" ^& rem %EC_TOKEN%^"

set /a EC_T=0
:wait
if exist "%EC_DONE%" goto finished
if %EC_T% geq %PROBE_TIMEOUT% goto hung
ping -n 2 127.0.0.1 >nul
set /a EC_T+=1
goto wait

:hung
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process -Filter \"Name='cmd.exe' AND CommandLine LIKE '%%%EC_TOKEN%%%'\" | ForEach-Object { taskkill /T /F /PID $_.ProcessId | Out-Null }" >nul 2>&1
exit /b 0

:finished
if not exist "%EC_OUT%" exit /b 0
set "L1="
set "L2="
for /f "usebackq delims=" %%A in ("%EC_OUT%") do (
  if not defined L1 (set "L1=%%A") else if not defined L2 set "L2=%%A"
)
if "%L1%"=="%EC_TOKEN%" if defined L2 set "FOUND=%L2%"
exit /b 0
