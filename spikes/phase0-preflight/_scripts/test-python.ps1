$root = 'C:\Projects\Improving\eval-coach\spikes\phase0-preflight'
$run  = "$root\_scripts\scrub-run.ps1"
$cwd  = "$root\_scripts\pytest"
$targets = @{
  embed = "$root\runtime\python-embed-3.13.17"
  pbs   = "$root\runtime\python-pbs-3.13.18\python"
}
foreach ($name in 'embed','pbs') {
  $py = $targets[$name]
  $path = @($py, 'C:\Windows\System32')
  $log = "$root\logs\py-$name"
  New-Item -ItemType Directory -Force "$root\logs" | Out-Null
  function T($id, $cmd, $extra) {
    "== [$name] $id :: $cmd"
    $params = @{ PathDirs=$path; Cwd=$cwd; CommandLine=$cmd; LogPrefix="$log-$id"; TimeoutSec=120 }
    if ($extra) { $params.ExtraEnv = $extra }
    & $run @params
    Get-Content "$log-$id.out.txt" -ErrorAction SilentlyContinue
    Get-Content "$log-$id.err.txt" -ErrorAction SilentlyContinue | Select-Object -Last 8
  }
  T version  'python --version'
  T checks   'python checks.py'
  T viapath  'python check.py'
  T sibling  'python sibling_main.py'
  T pythonpath 'python -c "import sibling_mod; print(sibling_mod.V)"' @{ PYTHONPATH = $cwd }
  T mkzip    "python -m zipapp zipsrc -o `"$root\sandbox-home\test-$name.pyz`""
  T runzip   "python `"$root\sandbox-home\test-$name.pyz`""
  T venv     "python -m venv --without-pip `"$root\sandbox-home\venv-$name`""
  T venvrun  "`"$root\sandbox-home\venv-$name\Scripts\python.exe`" -c `"import sys; print('venv python OK', sys.prefix)`""
  T pipver   'python -m pip --version'
}
