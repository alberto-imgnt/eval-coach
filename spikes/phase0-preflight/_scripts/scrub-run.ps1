# Runs one command line in a child cmd.exe with a fully rebuilt environment.
# Nothing is inherited from the caller; the profile folders point inside the spike.
param(
  [Parameter(Mandatory)][string[]]$PathDirs,
  [Parameter(Mandatory)][string]$Cwd,
  [Parameter(Mandatory)][string]$CommandLine,
  [Parameter(Mandatory)][string]$LogPrefix,
  [int]$TimeoutSec = 900,
  [hashtable]$ExtraEnv = @{}
)
$spike = 'C:\Projects\Improving\eval-coach\spikes\phase0-preflight'
$prof  = "$spike\sandbox-home"
foreach ($d in "$prof", "$prof\AppData\Roaming", "$prof\AppData\Local", "$prof\Temp", "$spike\logs") {
  New-Item -ItemType Directory -Force -Path $d | Out-Null
}
$psi = [Diagnostics.ProcessStartInfo]::new('C:\Windows\System32\cmd.exe')
$out = "$LogPrefix.out.txt"; $err = "$LogPrefix.err.txt"
$psi.Arguments = "/d /s /c `"$CommandLine <NUL >`"$out`" 2>`"$err`"`""
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$psi.WorkingDirectory = $Cwd
$psi.Environment.Clear()
$base = @{
  SystemRoot='C:\Windows'; windir='C:\Windows'; SystemDrive='C:'; ComSpec='C:\Windows\System32\cmd.exe'
  PATHEXT='.COM;.EXE;.BAT;.CMD'; OS='Windows_NT'; PROCESSOR_ARCHITECTURE='AMD64'
  ProgramData='C:\ProgramData'; ProgramFiles='C:\Program Files'
  USERPROFILE=$prof; HOME=$prof; HOMEDRIVE='C:'; HOMEPATH=$prof.Substring(2)
  APPDATA="$prof\AppData\Roaming"; LOCALAPPDATA="$prof\AppData\Local"
  TEMP="$prof\Temp"; TMP="$prof\Temp"
  Path=($PathDirs -join ';')
}
foreach ($k in $base.Keys)     { $psi.Environment[$k] = $base[$k] }
foreach ($k in $ExtraEnv.Keys) { $psi.Environment[$k] = [string]$ExtraEnv[$k] }
$sw = [Diagnostics.Stopwatch]::StartNew()
$p = [Diagnostics.Process]::Start($psi)
$done = $p.WaitForExit($TimeoutSec * 1000)
if (-not $done) {
  & C:\Windows\System32\taskkill.exe /T /F /PID $p.Id | Out-Null
  $p.WaitForExit(15000) | Out-Null
  "TIMEOUT after ${TimeoutSec}s (process tree killed)"
  exit 124
}
"exit=$($p.ExitCode) secs=$([math]::Round($sw.Elapsed.TotalSeconds,1))"
exit $p.ExitCode
