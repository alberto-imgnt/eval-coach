"""No-AI checks of conpty.py: .exe/.cmd/.bat/shebang launch, write, resize, tree kill."""
import os
import shutil
import sys
import time

from conpty import ConPTY

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "work", "shim test")
shutil.rmtree(D, ignore_errors=True)
os.makedirs(D)


def run(argv, needle, send=None, timeout=15, **kw):
    p = ConPTY(argv, cwd=D, **kw)
    try:
        if send:
            time.sleep(1.5)
            p.write(send)
        end = time.time() + timeout
        while time.time() < end and needle.encode() not in p.snapshot():
            time.sleep(0.1)
        ok = needle.encode() in p.snapshot()
        print(f"{'PASS' if ok else 'FAIL'} [{p.launch_type}] {argv[0]} -> {needle!r}")
        if not ok:
            print("   raw:", p.snapshot()[-400:])
        return ok
    finally:
        p.close()


results = []
for name, ext in (("hello shim", ".cmd"), ("hello2", ".bat")):
    path = os.path.join(D, name + ext)
    with open(path, "w") as f:
        f.write("@echo off\r\necho GOT-%1-%2\r\n")
    results.append(run([path, "two words", "b"], "GOT-"))

sh = os.path.join(D, "shebang")
with open(sh, "w", newline="\n") as f:
    f.write('#!/bin/sh\necho "SH-RAN-$1"\n')
results.append(run([sh, "arg"], "SH-RAN-arg"))

# PATHEXT resolution of a bare command name.
results.append(run(["cmd"], "ECHO-OK", send=b"echo ECHO-OK\r"))

# isatty-equivalent: a console API call only succeeds on a real console.
results.append(run(["cmd"], "ConPTY-COLS", send=b"mode con | find \"Columns\" && echo ConPTY-COLS\r"))

p = ConPTY(["cmd"], cwd=D, cols=100, rows=30)
try:
    time.sleep(1)
    p.resize(77, 20)
    time.sleep(0.5)
    p.write(b"mode con\r")
    time.sleep(1.5)
    ok = b"77" in p.snapshot()
    print(f"{'PASS' if ok else 'FAIL'} resize to 77 cols")
    results.append(ok)
finally:
    p.close()

# Tree kill: cmd -> ping child must both die with the job.
p = ConPTY(["cmd", "/c", "ping -n 60 127.0.0.1"], cwd=D)
time.sleep(2)
pids = p.pids()
p.close()
time.sleep(0.5)
tasks = os.popen("tasklist /FO CSV /NH").read()
left = [x for x in pids if f'"{x}"' in tasks]
ok = len(pids) >= 2 and not left
print(f"{'PASS' if ok else 'FAIL'} tree kill: job pids {pids}, still alive {left}")
results.append(ok)

print("ALL PASS" if all(results) else "SOME FAILED")
sys.exit(0 if all(results) else 1)
