@echo off
rem launcher.cmd: the launcher for eval-coach on Windows.
rem Finds Python 3.9 or later, or installs a private copy after asking, then
rem starts the app. tools\build_pyz.py ships this script as dist\eval-coach.cmd
rem with the app archive appended after the marker line at the end, so the app
rem runs from this file itself.
rem
rem Rules for editing this file:
rem  - The script part (everything above the marker line) must keep CRLF line
rem    endings and be plain ASCII.
rem  - Never jump backward. Once the archive follows the script, a goto or call
rem    to a label defined earlier in the file silently fails, because cmd stops
rem    searching at the binary data. Write loops as "for /l" or unroll them.
rem  - Every path through the script must end in exit /b, so cmd never reads
rem    the archive.
rem  - Call Windows tools by full path. Other programs (Git Bash, for example)
rem    can shadow them on PATH.
rem  - Delayed expansion stays off, so paths with ampersands, parentheses or
rem    exclamation marks stay inert. Use "call :say VARNAME" to print a path.
rem  - Do not print a variable with a plain echo, and keep messages out of
rem    parenthesized blocks.

setlocal EnableExtensions DisableDelayedExpansion
title eval-coach setup

rem Pinned values, from spikes\phase0-preflight\runtime-manifest.json.
set "EC_PY_VERSION=3.13.17"
set "EC_PY_SHA256=9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38"
set "EC_PY_URL=https://www.python.org/ftp/python/3.13.17/python-3.13.17-embed-amd64.zip"

rem For tests: EVAL_COACH_PYTHON_URL may point at a local copy of the archive.
rem It changes where the file comes from, never the hash it must match.
if defined EVAL_COACH_PYTHON_URL set "EC_PY_URL=%EVAL_COACH_PYTHON_URL%"

set "EC_SYS=%SystemRoot%\System32"
set "EC_PYZ=%~f0"
set "EC_HOME=%USERPROFILE%\.eval-coach"
set "EC_RUNTIME=%EC_HOME%\runtime"
set "EC_PRIVATE=%EC_RUNTIME%\python\python.exe"
set "EC_ZIP=python-embed-%EC_PY_VERSION%.zip"
set "EC_PROBE_TIMEOUT=10"
set "EC_PY="
set "EC_BROKEN="
set "EC_WORK="

set "EC_WORK=%TEMP%\ec-setup-%RANDOM%%RANDOM%"
mkdir "%EC_WORK%" >nul 2>&1
if not exist "%EC_WORK%\" goto fail_temp

rem ---------------------------------------------------------------------------
rem Step 1: a working Python 3.9 or later on PATH. $PATH: keeps where.exe from
rem also matching files in the current folder.
rem ---------------------------------------------------------------------------
echo Looking for Python 3.9 or later...

set "EC_KIND=direct"
set "EC_ARGS=-B"
for %%N in (python python3) do (
  for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:%%N 2^>nul') do (
    set "EC_CAND=%%P"
    if not defined EC_PY call :probe
  )
)

set "EC_KIND=py"
set "EC_ARGS=-3 -B"
if not defined EC_PY (
  for /f "delims=" %%P in ('%SystemRoot%\System32\where.exe $PATH:py 2^>nul') do (
    set "EC_CAND=%%P"
    if not defined EC_PY call :probe
  )
)

if defined EC_PY goto launch

rem ---------------------------------------------------------------------------
rem Step 2: the private copy from an earlier run.
rem ---------------------------------------------------------------------------
if not exist "%EC_PRIVATE%" goto install

set "EC_KIND=direct"
set "EC_ARGS=-B"
set "EC_CAND=%EC_PRIVATE%"
call :probe
if defined EC_PY goto launch
set "EC_BROKEN=1"

rem ---------------------------------------------------------------------------
rem Step 3: ask, then download, verify and extract the private copy.
rem ---------------------------------------------------------------------------
:install
if not exist "%EC_SYS%\curl.exe" goto fail_tools
if not exist "%EC_SYS%\tar.exe" goto fail_tools
if not exist "%EC_SYS%\certutil.exe" goto fail_tools

call :free_space

echo(
echo eval-coach needs Python 3.9 or later, and no working copy was found.
if defined EC_BROKEN echo A private copy from an earlier run is damaged, so it will be replaced.
echo(
echo It can install a private copy of Python that only eval-coach uses:
echo(
echo   What:  Python %EC_PY_VERSION%, the embeddable package from python.org
echo   Size:  about 11 MB to download, about 22 MB once installed
echo   Where:
call :say EC_RUNTIME
echo   Download address:
call :say EC_PY_URL
if defined EC_FREE_MB echo   Free space on this drive: %EC_FREE_MB% MB
echo(
echo No administrator rights are needed. PATH, the registry and your other
echo programs are not changed.
echo(

if defined EC_FREE_MB if %EC_FREE_MB% lss 50 goto fail_disk

set "EC_TRIES=0"
set "EC_REPLY=other"
for /l %%I in (1,1,3) do call :ask_once
if "%EC_REPLY%"=="yes" goto download
goto declined

:download
if not exist "%EC_RUNTIME%\" mkdir "%EC_RUNTIME%" >nul 2>&1
if not exist "%EC_RUNTIME%\" goto fail_folder
rem Work inside the runtime folder and use short relative names, so the Windows
rem tools never have to handle unusual characters in the profile path.
pushd "%EC_RUNTIME%" || goto fail_folder

del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo Downloading Python %EC_PY_VERSION%...
"%EC_SYS%\curl.exe" --fail --location --ssl-no-revoke --connect-timeout 30 --max-time 900 --retry 2 --retry-delay 3 --progress-bar --output "%EC_ZIP%" "%EC_PY_URL%"
set "EC_RC=%errorlevel%"
if not "%EC_RC%"=="0" goto download_failed

if not exist "%EC_ZIP%" goto fail_removed

echo Checking the download against its pinned SHA-256 fingerprint...
set "EC_ACTUAL="
for /f "skip=1 delims=" %%H in ('%SystemRoot%\System32\certutil.exe -hashfile "%EC_ZIP%" SHA256 2^>nul') do (
  if not defined EC_ACTUAL set "EC_ACTUAL=%%H"
)
if not defined EC_ACTUAL goto fail_cannot_verify
rem Older Windows versions print the hash with spaces between the bytes.
set "EC_ACTUAL=%EC_ACTUAL: =%"
if /i not "%EC_ACTUAL%"=="%EC_PY_SHA256%" goto fail_hash

echo Unpacking...
if exist "python.new\" rmdir /s /q "python.new" >nul 2>&1
mkdir "python.new" >nul 2>&1
"%EC_SYS%\tar.exe" -xf "%EC_ZIP%" -C "python.new" >nul 2>&1
if errorlevel 1 goto fail_extract
if not exist "python.new\python.exe" goto fail_removed
del /f /q "python.new\python313._pth" >nul 2>&1
if exist "python.new\python313._pth" goto fail_removed

rem Run the new copy before putting it in place.
set "EC_KIND=direct"
set "EC_ARGS=-B"
set "EC_CAND=%EC_RUNTIME%\python.new\python.exe"
set "EC_PY="
call :probe
if not defined EC_PY goto fail_removed

set "EC_PY="
if exist "python\" rmdir /s /q "python" >nul 2>&1
if exist "python\" goto fail_replace
for /l %%I in (1,1,15) do call :rename_try
if not exist "%EC_PRIVATE%" goto fail_removed
del /f /q "%EC_ZIP%" >nul 2>&1
popd

set "EC_PY=%EC_PRIVATE%"
echo Python %EC_PY_VERSION% is installed.

rem ---------------------------------------------------------------------------
rem Step 4: start the app.
rem ---------------------------------------------------------------------------
:launch
if defined EC_WORK rmdir /s /q "%EC_WORK%" >nul 2>&1
echo(
echo Starting eval-coach. Keep this window open while you use it.
echo(
"%EC_PY%" -B "%EC_PYZ%" --python "%EC_PY%" %*
set "EC_RC=%errorlevel%"
if "%EC_RC%"=="0" exit /b 0

echo(
echo eval-coach stopped because of a problem (code %EC_RC%).
echo The lines above this message say what went wrong.
echo(
echo What to do next: close this window and start eval-coach again.
call :hold
exit /b %EC_RC%

rem ---------------------------------------------------------------------------
rem Declined.
rem ---------------------------------------------------------------------------
:declined
if defined EC_WORK rmdir /s /q "%EC_WORK%" >nul 2>&1
echo(
echo Nothing was installed and nothing on this computer changed.
echo(
echo eval-coach cannot start without Python. What to do next, either:
echo   - start eval-coach again and answer Y to install the private copy, or
echo   - install Python 3.9 or later from your company's software portal
echo     (Company Portal or Software Center), then start eval-coach again.
call :hold
exit /b 0

rem ---------------------------------------------------------------------------
rem Failures. Each one says what happened and what to do next.
rem ---------------------------------------------------------------------------
:download_failed
del /f /q "%EC_ZIP%" >nul 2>&1
if "%EC_RC%"=="28" goto fail_timeout
if "%EC_RC%"=="23" goto fail_disk_write
goto fail_network

:fail_network
echo(
echo Python could not be downloaded (download tool code %EC_RC%).
echo This computer is probably offline, or the company network or a proxy is
echo blocking python.org. Nothing was installed.
echo(
echo What to do next:
echo   1. Check your internet connection, then start eval-coach again.
echo   2. If it still fails, the network is blocking the download. Install
echo      Python 3.9 or later from your company's software portal
echo      (Company Portal or Software Center), then start eval-coach again.
goto stop

:fail_timeout
echo(
echo The Python download took too long and timed out. Nothing was installed.
echo(
echo What to do next:
echo   1. Start eval-coach again, ideally on a faster or more stable connection.
echo   2. If it times out again, install Python 3.9 or later from your
echo      company's software portal (Company Portal or Software Center), then
echo      start eval-coach again.
goto stop

:fail_hash
del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo The downloaded Python file failed its safety check.
echo Its SHA-256 fingerprint does not match the value built into eval-coach, so
echo the file is damaged or was changed on the way. It has been deleted and
echo nothing was installed. This check cannot be turned off.
echo(
echo What to do next:
echo   1. Start eval-coach again to download a fresh copy.
echo   2. If it fails again, the network is altering the download. Install
echo      Python 3.9 or later from your company's software portal
echo      (Company Portal or Software Center), then start eval-coach again.
goto stop

:fail_cannot_verify
del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo The downloaded Python file could not be checked, so it was deleted and
echo nothing was installed. Unchecked files are never used.
echo(
echo What to do next:
echo   1. Start eval-coach again.
echo   2. If it fails again, install Python 3.9 or later from your company's
echo      software portal (Company Portal or Software Center), then start
echo      eval-coach again.
goto stop

:fail_extract
rmdir /s /q "python.new" >nul 2>&1
del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo The Python files could not be unpacked. The drive may be full, or
echo security software may be blocking the files. Nothing was installed.
echo(
echo What to do next:
echo   1. Free up at least 50 MB on this drive, then start eval-coach again.
echo   2. If it fails again, install Python 3.9 or later from your company's
echo      software portal (Company Portal or Software Center), then start
echo      eval-coach again.
goto stop

:fail_removed
rmdir /s /q "python.new" >nul 2>&1
del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo A Python file disappeared or would not run right after it was saved.
echo Antivirus or other security software on this computer most likely removed
echo or blocked it. Python was not installed.
echo(
echo What to do next:
echo   1. Start eval-coach again.
echo   2. If it fails again, install Python 3.9 or later from your company's
echo      software portal (Company Portal or Software Center), then start
echo      eval-coach again.
goto stop

:fail_replace
rmdir /s /q "python.new" >nul 2>&1
del /f /q "%EC_ZIP%" >nul 2>&1
echo(
echo The old private copy of Python could not be replaced because something is
echo still using it. It is in this folder:
call :say EC_RUNTIME
echo(
echo What to do next: close every eval-coach window, then start eval-coach again.
goto stop

:fail_disk_write
echo(
echo The Python download could not be saved. The drive is probably full.
echo Nothing was installed.
echo(
echo What to do next: free up at least 50 MB on this drive, then start
echo eval-coach again.
goto stop

:fail_disk
echo Not enough free disk space. Python needs about 34 MB in total and this
echo drive has only %EC_FREE_MB% MB free. Nothing was installed.
echo(
echo What to do next: free up at least 50 MB on this drive, then start
echo eval-coach again.
goto stop

:fail_folder
echo(
echo This folder could not be created, so Python could not be installed:
call :say EC_RUNTIME
echo(
echo What to do next: check that the drive is not full, then start eval-coach
echo again. If it still fails, install Python 3.9 or later from your company's
echo software portal (Company Portal or Software Center), then start
echo eval-coach again.
goto stop

:fail_temp
echo(
echo eval-coach could not create a temporary folder here:
call :say TEMP
echo(
echo What to do next: free up some space on this drive, then start eval-coach
echo again.
goto stop

:fail_tools
echo(
echo This version of Windows does not include the download tools eval-coach
echo needs (curl, tar and certutil). Nothing was installed.
echo(
echo What to do next: install Python 3.9 or later from your company's software
echo portal (Company Portal or Software Center), then start eval-coach again.
goto stop
:stop
if defined EC_WORK rmdir /s /q "%EC_WORK%" >nul 2>&1
call :hold
exit /b 1

rem ---------------------------------------------------------------------------
rem Subroutines.
rem ---------------------------------------------------------------------------

:hold
rem Keeps a double-clicked window open so the message can be read.
echo(
echo Press any key to close this window.
pause >nul
exit /b 0

:say
rem Prints the variable named in %1 safely, whatever characters it contains.
setlocal EnableDelayedExpansion
echo(         !%~1!
endlocal
exit /b 0

:ask_once
rem One try at the install question. Does nothing once a clear answer is in.
if not "%EC_REPLY%"=="other" exit /b 0
set /a EC_TRIES+=1
set "EC_ANSWER="
set /p "EC_ANSWER=Install it now? Type Y or N, then press Enter: "
call :read_answer
if not "%EC_REPLY%"=="other" exit /b 0
if %EC_TRIES% lss 3 echo Please type Y for yes or N for no.
exit /b 0

:rename_try
rem Security software can hold the new files for a moment after the probe ran them.
if exist "%EC_PRIVATE%" exit /b 0
ren "python.new" "python" >nul 2>&1
if not exist "%EC_PRIVATE%" "%EC_SYS%\ping.exe" -n 2 127.0.0.1 >nul
exit /b 0

:read_answer
rem Sets EC_REPLY to yes, no or other. Delayed expansion keeps whatever was
rem typed from being treated as a command.
setlocal EnableDelayedExpansion
set "EC_R=other"
if /i "!EC_ANSWER!"=="Y" set "EC_R=yes"
if /i "!EC_ANSWER!"=="YES" set "EC_R=yes"
if /i "!EC_ANSWER!"=="N" set "EC_R=no"
if /i "!EC_ANSWER!"=="NO" set "EC_R=no"
endlocal & set "EC_REPLY=%EC_R%"
exit /b 0

:free_space
rem Sets EC_FREE_MB when the free space can be read from the dir summary line.
rem Leaves it undefined otherwise, and the install then simply goes ahead.
set "EC_FREE_MB="
set "EC_FREE="
set "EC_LAST="
for /f "tokens=*" %%L in ('dir /-c "%USERPROFILE%\" 2^>nul') do set "EC_LAST=%%L"
if not defined EC_LAST exit /b 0
for /f "tokens=3" %%T in ("%EC_LAST%") do set "EC_FREE=%%T"
if not defined EC_FREE exit /b 0
for /f "delims=0123456789" %%X in ("%EC_FREE%") do set "EC_FREE="
if not defined EC_FREE exit /b 0
rem Drop six digits rather than dividing: drives can exceed 32-bit arithmetic.
set "EC_FREE_MB=%EC_FREE:~0,-6%"
if not defined EC_FREE_MB set "EC_FREE_MB=0"
exit /b 0

:probe
rem Tests the candidate in EC_CAND with the arguments in EC_ARGS. Sets EC_PY on
rem success. Logic comes from spikes\phase0-preflight\detect-python.cmd:
rem  1. Anything under \Microsoft\WindowsApps\ is skipped without running it, so
rem     the Microsoft Store can never open.
rem  2. Every other candidate runs only with arguments, stdin from NUL, from an
rem     empty folder, and must print a per-run random token.
rem  3. Each probe has a hard timeout.
if /i not "%EC_CAND:\Microsoft\WindowsApps\=%"=="%EC_CAND%" exit /b 0

set "EC_TOKEN=EC%RANDOM%%RANDOM%"
rem The path is printed in the OEM code page because that is how for /f reads it.
set "EC_CODE=import sys,ctypes;sys.version_info>=(3,9) or sys.exit(1);sys.stdout.reconfigure(encoding='oem');print('%EC_TOKEN%');print(sys.executable)"
set "EC_OUT=%EC_WORK%\%EC_TOKEN%.out"
set "EC_DONE=%EC_WORK%\%EC_TOKEN%.done"

rem The child expands its !variables! only after parsing, so characters such as
rem ampersands and parentheses in a path stay inert. The trailing rem carries the
rem token so a hung probe can be found and stopped.
start "" /b /d "%EC_WORK%" "%SystemRoot%\System32\cmd.exe" /d /v:on /c ^""!EC_CAND!" !EC_ARGS! -c "!EC_CODE!" ^<nul ^>"!EC_OUT!" 2^>nul ^& echo done^>"!EC_DONE!" ^& rem %EC_TOKEN%^"

for /l %%I in (1,1,%EC_PROBE_TIMEOUT%) do if not exist "%EC_DONE%" "%EC_SYS%\ping.exe" -n 2 127.0.0.1 >nul
if exist "%EC_DONE%" goto probe_finished
goto probe_hung

:probe_hung
"%EC_SYS%\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -Command "Get-CimInstance Win32_Process -Filter \"Name='cmd.exe' AND CommandLine LIKE '%%%EC_TOKEN%%%'\" | ForEach-Object { %SystemRoot%\System32\taskkill.exe /T /F /PID $_.ProcessId | Out-Null }" >nul 2>&1
exit /b 0

:probe_finished
if not exist "%EC_OUT%" exit /b 0
set "L1="
set "L2="
for /f "usebackq delims=" %%A in ("%EC_OUT%") do (
  if not defined L1 (set "L1=%%A") else if not defined L2 set "L2=%%A"
)
setlocal EnableDelayedExpansion
set "EC_PASS="
set "EC_EXISTS="
if "!L1!"=="!EC_TOKEN!" set "EC_PASS=1"
if defined L2 if exist "!L2!" set "EC_EXISTS=1"
endlocal & set "EC_PASS=%EC_PASS%" & set "EC_EXISTS=%EC_EXISTS%"
if not defined EC_PASS exit /b 0
rem Prefer the interpreter's own report of its path. If that could not be read,
rem the candidate path works too, except for py.exe, which is only a launcher.
if defined EC_EXISTS (
  set "EC_PY=%L2%"
) else (
  if /i not "%EC_KIND%"=="py" set "EC_PY=%EC_CAND%"
)
exit /b 0
rem ===== eval-coach.pyz follows =====
