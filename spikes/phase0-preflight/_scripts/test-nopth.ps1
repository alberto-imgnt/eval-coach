$root = 'C:\Projects\Improving\eval-coach\spikes\phase0-preflight'
$run  = "$root\_scripts\scrub-run.ps1"
$cwd  = "$root\_scripts\pytest"
$src  = "$root\runtime\python-embed-3.13.17"
$dst  = "$root\runtime\python-embed-3.13.17-nopth"
if (-not (Test-Path $dst)) {
  New-Item -ItemType Directory -Force $dst | Out-Null
  Copy-Item "$src\*" $dst -Recurse
  Remove-Item "$dst\python313._pth"
}
$path = @($dst, 'C:\Windows\System32')
function T($id, $cmd, $extra) {
  "== [nopth] $id :: $cmd"
  $params = @{ PathDirs=$path; Cwd=$cwd; CommandLine=$cmd; LogPrefix="$root\logs\py-nopth-$id"; TimeoutSec=120 }
  if ($extra) { $params.ExtraEnv = $extra }
  & $run @params
  Get-Content "$root\logs\py-nopth-$id.out.txt" -ErrorAction SilentlyContinue
  Get-Content "$root\logs\py-nopth-$id.err.txt" -ErrorAction SilentlyContinue | Select-Object -Last 6
}
T version 'python --version'
T checks  'python checks.py'
T sibling 'python sibling_main.py'
T pythonpath 'python -c "import sibling_mod; print(sibling_mod.V)"' @{ PYTHONPATH = $cwd }
T runzip  "python `"$root\sandbox-home\test-embed.pyz`""
T badhome 'python -c "import ctypes; print(1)"' @{ PYTHONHOME = 'C:\nonexistent' }
T badhomeE 'python -E -c "import ctypes; print(1)"' @{ PYTHONHOME = 'C:\nonexistent' }
T badhomeSib 'python -E sibling_main.py' @{ PYTHONHOME = 'C:\nonexistent' }
