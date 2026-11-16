# Runs each Python candidate with arguments only (never bare) under a hard timeout,
# using the caller's real PATH, and records whether a Store window process appeared.
$root = 'C:\Projects\Improving\eval-coach\spikes\phase0-preflight'
$log  = "$root\logs"
New-Item -ItemType Directory -Force $log | Out-Null
function StoreProcs { Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'WinStore|AppInstaller' } | ForEach-Object { "$($_.ProcessName):$($_.Id)" } }

$probe = 'import sys,ctypes;print(sys.version_info[:3],sys.executable)'
$cases = @(
  @{ id='python-version';  cmd='python';  args='--version' },
  @{ id='python-probe';    cmd='python';  args="-c `"$probe`"" },
  @{ id='py3-version';     cmd='py';      args='-3 --version' },
  @{ id='py3-probe';       cmd='py';      args="-3 -c `"$probe`"" },
  @{ id='python3-version'; cmd='python3'; args='--version' },
  @{ id='python3-probe';   cmd='python3'; args="-c `"$probe`"" }
)
"PATH entries matching python/WindowsApps:"
($env:Path -split ';') | Where-Object { $_ -match 'python|WindowsApps' }
"where: "
foreach ($n in 'python','py','python3') { "[$n]"; & C:\Windows\System32\where.exe $n 2>&1 }
$before = StoreProcs
"store-related before: $before"
foreach ($c in $cases) {
  $out = "$log\cand-$($c.id).out.txt"; $err = "$log\cand-$($c.id).err.txt"
  $psi = [Diagnostics.ProcessStartInfo]::new('C:\Windows\System32\cmd.exe')
  $psi.Arguments = "/d /s /c `"$($c.cmd) $($c.args) <NUL >`"$out`" 2>`"$err`"`""
  $psi.UseShellExecute = $false; $psi.CreateNoWindow = $true
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $p = [Diagnostics.Process]::Start($psi)
  if ($p.WaitForExit(20000)) { $ec = $p.ExitCode } else { & C:\Windows\System32\taskkill.exe /T /F /PID $p.Id | Out-Null; $ec = 'TIMEOUT' }
  $o = (Get-Content $out -Raw -ErrorAction SilentlyContinue); $e = (Get-Content $err -Raw -ErrorAction SilentlyContinue)
  "[$($c.id)] exit=$ec secs=$([math]::Round($sw.Elapsed.TotalSeconds,2))"
  "  stdout: $o"
  "  stderr: $e"
}
Start-Sleep -Milliseconds 800
$after = StoreProcs
"store-related after: $after"
