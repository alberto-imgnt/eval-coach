$root = 'C:\Projects\Improving\eval-coach\spikes\phase0-preflight'
$run  = "$root\_scripts\scrub-run.ps1"
$det  = "$root\detect-python.cmd"
$embed = "$root\runtime\python-embed-3.13.17"
$sys  = 'C:\Windows\System32'
$wa   = 'C:\Users\AlbertoSalazar\AppData\Local\Microsoft\WindowsApps'
$fk   = "$root\_scripts\pytest\fakes"
$cwd  = "$root\work"
New-Item -ItemType Directory -Force $cwd, "$fk\hang", "$fk\old", "$fk\junk" | Out-Null
Set-Content -Encoding ascii "$fk\hang\python.bat" "@ping -n 40 127.0.0.1 >nul`r`n@exit /b 0"
Set-Content -Encoding ascii "$fk\old\python.bat"  "@exit /b 1"
Set-Content -Encoding ascii "$fk\junk\python.bat" "@echo Python 2.7.18`r`n@exit /b 0"
$odd = "$root\sandbox-home\py (x86) & co"
if (-not (Test-Path "$odd\python.exe")) { New-Item -ItemType Directory -Force $odd | Out-Null; Copy-Item "$embed\*" $odd -Recurse }

function Store { @(Get-Process -ErrorAction SilentlyContinue | Where-Object ProcessName -match 'WinStore|AppInstaller').Count }
function Case($id, $dirs, $expectRc, $expectPath, $extra) {
  $before = Store
  $params = @{ PathDirs=$dirs; Cwd=$cwd; CommandLine="`"$det`""; LogPrefix="$root\logs\detect-$id"; TimeoutSec=120 }
  if ($extra) { $params.ExtraEnv = $extra }
  $r = & $run @params
  $o = (Get-Content "$root\logs\detect-$id.out.txt" -ErrorAction SilentlyContinue | Out-String).Trim()
  $e = (Get-Content "$root\logs\detect-$id.err.txt" -ErrorAction SilentlyContinue | Out-String).Trim()
  $rc = [regex]::Match([string]$r,'exit=(\d+)').Groups[1].Value
  $pass = ($rc -eq "$expectRc") -and ($(if ($expectPath) { $o -eq $expectPath } else { $o -eq '' }))
  "[$(if($pass){'PASS'}else{'FAIL'})] $id :: $r :: stdout=[$o] stderr=[$e] storeProcsAddedBy=$((Store)-$before)"
}
Case system32only  @($sys)                             1 $null
Case stubonly      @($wa,$sys)                         1 $null @{ LOCALAPPDATA='C:\Users\AlbertoSalazar\AppData\Local' }
Case private       @($embed,$sys)                      0 "$embed\python.exe"
Case oddpath       @($odd,$sys)                        0 "$odd\python.exe"
Case oldfirst      @("$fk\old",$embed,$sys)            0 "$embed\python.exe"
Case junkfirst     @("$fk\junk",$embed,$sys)           0 "$embed\python.exe"
Case hangfirst     @("$fk\hang",$embed,$sys)           0 "$embed\python.exe"
"--- leftover hung children from hangfirst (want 0): $(@(Get-CimInstance Win32_Process -Filter "Name='ping.exe'" | Where-Object CommandLine -match '-n 40').Count)"
"--- real user PATH (inherited, not scrubbed)"
$sw=[Diagnostics.Stopwatch]::StartNew()
$o = & cmd /d /c "`"$det`""
"rc=$LASTEXITCODE secs=$([math]::Round($sw.Elapsed.TotalSeconds,1)) stdout=[$o]"
"leftover temp folders in sandbox-home\Temp: $(@(Get-ChildItem "$root\sandbox-home\Temp" -Filter 'ec-detect-*' -ErrorAction SilentlyContinue).Count)"
