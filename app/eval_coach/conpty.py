"""Stdlib-only ConPTY host for Windows. All OS-specific process code lives here.

Public surface:
    parse_command(text) -> (tokens, quoted_flags)
    command_to_argv(text) -> argv
    resolve_command(argv) -> (application_name, command_line, launch_type)
    ConPTY(argv, cwd=None, env=None, cols=120, rows=40, on_output=None)
        .write(bytes)  .type_line(text)  .read_new()  .snapshot()
        .resize(cols, rows)  .alive()  .wait(timeout)  .exit_code  .pids()  .close()
"""
from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import threading
import time
from ctypes import wintypes as w

HANDLE = w.HANDLE
LPVOID = w.LPVOID
HPCON = LPVOID
SIZE_T = ctypes.c_size_t
ULONG_PTR = ctypes.c_size_t

INVALID_HANDLE = HANDLE(-1).value
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_SUSPENDED = 0x00000004
STARTF_USESTDHANDLES = 0x00000100
PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE = 0x00020016
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectBasicProcessIdList = 3
JobObjectExtendedLimitInformation = 9
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
S_OK = 0

# Output kept for read_new()/snapshot(); callers wanting everything use on_output.
BUFFER_LIMIT = 4 * 1024 * 1024


class COORD(ctypes.Structure):
    _fields_ = [("X", w.SHORT), ("Y", w.SHORT)]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", w.DWORD), ("lpReserved", w.LPWSTR), ("lpDesktop", w.LPWSTR),
        ("lpTitle", w.LPWSTR), ("dwX", w.DWORD), ("dwY", w.DWORD),
        ("dwXSize", w.DWORD), ("dwYSize", w.DWORD), ("dwXCountChars", w.DWORD),
        ("dwYCountChars", w.DWORD), ("dwFillAttribute", w.DWORD),
        ("dwFlags", w.DWORD), ("wShowWindow", w.WORD), ("cbReserved2", w.WORD),
        ("lpReserved2", LPVOID), ("hStdInput", HANDLE), ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class STARTUPINFOEXW(ctypes.Structure):
    _fields_ = [("StartupInfo", STARTUPINFOW), ("lpAttributeList", LPVOID)]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [("hProcess", HANDLE), ("hThread", HANDLE),
                ("dwProcessId", w.DWORD), ("dwThreadId", w.DWORD)]


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", w.DWORD), ("MinimumWorkingSetSize", SIZE_T),
        ("MaximumWorkingSetSize", SIZE_T), ("ActiveProcessLimit", w.DWORD),
        ("Affinity", ULONG_PTR), ("PriorityClass", w.DWORD),
        ("SchedulingClass", w.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS), ("ProcessMemoryLimit", SIZE_T),
        ("JobMemoryLimit", SIZE_T), ("PeakProcessMemoryUsed", SIZE_T),
        ("PeakJobMemoryUsed", SIZE_T),
    ]


def _sig(fn, res, *args):
    fn.restype = res
    fn.argtypes = list(args)


if sys.platform == "win32":
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _sig(k32.CreatePipe, w.BOOL, ctypes.POINTER(HANDLE), ctypes.POINTER(HANDLE), LPVOID, w.DWORD)
    _sig(k32.CloseHandle, w.BOOL, HANDLE)
    _sig(k32.ReadFile, w.BOOL, HANDLE, LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), LPVOID)
    _sig(k32.WriteFile, w.BOOL, HANDLE, LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), LPVOID)
    _sig(k32.CancelIoEx, w.BOOL, HANDLE, LPVOID)
    _sig(k32.CreatePseudoConsole, ctypes.c_long, COORD, HANDLE, HANDLE, w.DWORD, ctypes.POINTER(HPCON))
    _sig(k32.ResizePseudoConsole, ctypes.c_long, HPCON, COORD)
    _sig(k32.ClosePseudoConsole, None, HPCON)
    _sig(k32.InitializeProcThreadAttributeList, w.BOOL, LPVOID, w.DWORD, w.DWORD, ctypes.POINTER(SIZE_T))
    _sig(k32.UpdateProcThreadAttribute, w.BOOL, LPVOID, w.DWORD, ULONG_PTR, LPVOID, SIZE_T, LPVOID, LPVOID)
    _sig(k32.DeleteProcThreadAttributeList, None, LPVOID)
    _sig(k32.CreateProcessW, w.BOOL, w.LPCWSTR, w.LPWSTR, LPVOID, LPVOID, w.BOOL, w.DWORD,
         LPVOID, w.LPCWSTR, ctypes.POINTER(STARTUPINFOEXW), ctypes.POINTER(PROCESS_INFORMATION))
    _sig(k32.ResumeThread, w.DWORD, HANDLE)
    _sig(k32.WaitForSingleObject, w.DWORD, HANDLE, w.DWORD)
    _sig(k32.GetExitCodeProcess, w.BOOL, HANDLE, ctypes.POINTER(w.DWORD))
    _sig(k32.TerminateProcess, w.BOOL, HANDLE, w.UINT)
    _sig(k32.CreateJobObjectW, HANDLE, LPVOID, w.LPCWSTR)
    _sig(k32.SetInformationJobObject, w.BOOL, HANDLE, ctypes.c_int, LPVOID, w.DWORD)
    _sig(k32.QueryInformationJobObject, w.BOOL, HANDLE, ctypes.c_int, LPVOID, w.DWORD, ctypes.POINTER(w.DWORD))
    _sig(k32.AssignProcessToJobObject, w.BOOL, HANDLE, HANDLE)
    _sig(k32.TerminateJobObject, w.BOOL, HANDLE, w.UINT)
else:  # pragma: no cover - Mac is deferred; parsing helpers stay importable.
    k32 = None


def _check(ok, what):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error(), what)


# --- command strings -------------------------------------------------------

def _unescaped_quotes(s, start):
    """Count double quotes in s[start:] that are not preceded by a backslash."""
    return sum(1 for i in range(start, len(s)) if s[i] == '"' and s[i - 1] != "\\")


def parse_command(text):
    """Split a command string into (tokens, quoted_flags), Windows style.

    Backslashes are ordinary path characters. Double quotes group text, and
    single quotes group text only when they open a token, so an apostrophe in
    a path survives. Inside double quotes, \\" is a literal quote, unless it
    ends the token and treating it as literal would leave the quotes
    unbalanced: that is how a quoted folder ending in a backslash reads
    ("C:\\Tools\\").
    """
    s = text.strip()
    if not s:
        raise ValueError("The CLI command is empty.")
    tokens, flags = [], []
    i, n = 0, len(s)
    while i < n:
        while i < n and s[i].isspace():
            i += 1
        if i >= n:
            break
        buf = []
        quoted = False
        while i < n and not s[i].isspace():
            c = s[i]
            if c == '"':
                quoted = True
                i += 1
                while True:
                    if i >= n:
                        raise ValueError("The CLI command has a quote that is never closed.")
                    ch = s[i]
                    if ch == '"':
                        i += 1
                        break
                    if ch == "\\" and i + 1 < n and s[i + 1] == '"':
                        after = s[i + 2] if i + 2 < n else ""
                        ends_token = after == "" or after.isspace()
                        if ends_token and _unescaped_quotes(s, i + 2) % 2 == 0:
                            buf.append("\\")  # the quote closes on the next pass
                            i += 1
                        else:
                            buf.append('"')
                            i += 2
                        continue
                    buf.append(ch)
                    i += 1
                continue
            if c == "'" and not buf and not quoted:
                end = s.find("'", i + 1)
                if end != -1:
                    buf.append(s[i + 1:end])
                    quoted = True
                    i = end + 1
                    continue
            buf.append(c)
            i += 1
        tokens.append("".join(buf))
        flags.append(quoted)
    return tokens, flags


def _lookup(name, path=None):
    return bool(shutil.which(name, path=path)) or os.path.isfile(name)


def command_to_argv(text, path=None):
    """Parse a command string. An unquoted path with spaces is recognized if it exists."""
    tokens, flags = parse_command(text)
    if _lookup(tokens[0], path) or flags[0]:
        return tokens
    for k in range(2, len(tokens) + 1):
        if any(flags[:k]):
            break
        candidate = " ".join(tokens[:k])
        if _lookup(candidate, path):
            return [candidate] + tokens[k:]
    return tokens


# Characters cmd.exe re-interprets even inside quotes (the "BatBadBut" class).
_CMD_UNSAFE = set('%!"\r\n')
# Characters that only need quoting to stay inert on a cmd.exe command line.
_CMD_SPECIAL = set(" \t&|<>^(),;=")


def _cmd_quote(arg):
    if arg == "" or (_CMD_SPECIAL & set(arg)):
        return '"' + arg + '"'
    return arg


def resolve_command(argv, path=None):
    """Return (application_name, command_line, launch_type) for CreateProcessW.

    Plain CreateProcess only runs PE files, so anything else is routed through
    its interpreter. Arguments to batch files are refused if cmd.exe could
    re-interpret them.
    """
    if not argv:
        raise ValueError("The CLI command is empty.")
    target = shutil.which(argv[0], path=path)
    if not target and os.path.isfile(argv[0]):  # which() rejects extensionless paths
        target = os.path.abspath(argv[0])
    if not target:
        raise FileNotFoundError(f"Could not find the command {argv[0]!r}. "
                                "Check the spelling, or enter its full path.")
    args = list(argv[1:])
    ext = os.path.splitext(target)[1].lower()

    if ext == "":  # extensionless shim: prefer a real sibling, then its shebang
        for sibling_ext in (".exe", ".cmd", ".bat"):
            if os.path.isfile(target + sibling_ext):
                target += sibling_ext
                ext = sibling_ext
                break

    if ext in (".exe", ".com"):
        return target, subprocess.list2cmdline([target] + args), ext[1:]

    if ext in (".cmd", ".bat"):
        for a in [target] + args:
            if _CMD_UNSAFE & set(a):
                raise ValueError(f"The command cannot safely include {a!r}: "
                                 "it has a character that Windows reads specially.")
        comspec = os.environ.get("ComSpec") or shutil.which("cmd.exe")
        inner = " ".join(['"' + target + '"'] + [_cmd_quote(a) for a in args])
        return comspec, f'"{comspec}" /d /s /c "{inner}"', ext[1:]

    if ext == ".ps1":
        ps = shutil.which("pwsh", path=path) or shutil.which("powershell", path=path)
        if not ps:
            raise FileNotFoundError("PowerShell was not found, and this command needs it.")
        return ps, subprocess.list2cmdline([ps, "-NoProfile", "-File", target] + args), "ps1"

    with open(target, "rb") as f:
        head = f.read(2)
    if head == b"#!":
        sh = shutil.which("sh", path=path)
        if not sh:
            raise FileNotFoundError(f"This command needs sh.exe, which was not found: {target}")
        return sh, subprocess.list2cmdline([sh, target] + args), "sh-script"
    raise OSError(f"Windows does not know how to run this file: {target}")


def _env_block(env):
    if env is None:
        return None
    # Windows expects the block sorted without regard to case.
    items = [f"{k}={env[k]}" for k in sorted(env, key=str.upper)]
    return ctypes.create_unicode_buffer("\0".join(items) + "\0\0")


# --- pseudo console --------------------------------------------------------

class ConPTY:
    def __init__(self, argv, cwd=None, env=None, cols=120, rows=40, on_output=None):
        self.app, self.cmdline, self.launch_type = resolve_command(argv, env.get("PATH") if env else None)
        self.exit_code = None
        self.pid = 0
        self._on_output = on_output
        self._buf = bytearray()
        self._pos = 0
        self._buf_lock = threading.Lock()
        # Guards every handle except the two pipe ends blocked in ReadFile/WriteFile.
        self._h_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closing = False
        self._closed = False
        self._hpc = None
        self._proc = None
        self._job = None
        self._in_w = self._out_r = None
        self._reader = None
        attr = None
        in_r = HANDLE()
        in_w = HANDLE()
        out_r = HANDLE()
        out_w = HANDLE()
        try:
            _check(k32.CreatePipe(ctypes.byref(in_r), ctypes.byref(in_w), None, 0), "CreatePipe(in)")
            _check(k32.CreatePipe(ctypes.byref(out_r), ctypes.byref(out_w), None, 0), "CreatePipe(out)")
            self._in_w, self._out_r = in_w.value, out_r.value

            hpc = HPCON()
            hr = k32.CreatePseudoConsole(COORD(cols, rows), in_r, out_w, 0, ctypes.byref(hpc))
            if hr != S_OK:
                raise OSError(f"CreatePseudoConsole failed: 0x{hr & 0xFFFFFFFF:08x}")
            self._hpc = hpc.value

            size = SIZE_T(0)
            k32.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
            attr = ctypes.create_string_buffer(size.value)
            _check(k32.InitializeProcThreadAttributeList(attr, 1, 0, ctypes.byref(size)),
                   "InitializeProcThreadAttributeList")
            _check(k32.UpdateProcThreadAttribute(attr, 0, PROC_THREAD_ATTRIBUTE_PSEUDOCONSOLE,
                                                 self._hpc, ctypes.sizeof(HPCON), None, None),
                   "UpdateProcThreadAttribute")

            si = STARTUPINFOEXW()
            si.StartupInfo.cb = ctypes.sizeof(STARTUPINFOEXW)
            si.lpAttributeList = ctypes.cast(attr, LPVOID)
            # Without this the child can inherit a redirected parent's stdio
            # handles instead of attaching to the pseudo console.
            si.StartupInfo.dwFlags = STARTF_USESTDHANDLES
            si.StartupInfo.hStdInput = INVALID_HANDLE
            si.StartupInfo.hStdOutput = INVALID_HANDLE
            si.StartupInfo.hStdError = INVALID_HANDLE

            self._job = k32.CreateJobObjectW(None, None)
            _check(self._job, "CreateJobObjectW")
            info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
            info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            _check(k32.SetInformationJobObject(self._job, JobObjectExtendedLimitInformation,
                                               ctypes.byref(info), ctypes.sizeof(info)),
                   "SetInformationJobObject")

            pi = PROCESS_INFORMATION()
            cmd_buf = ctypes.create_unicode_buffer(self.cmdline)
            env_buf = _env_block(env)
            flags = EXTENDED_STARTUPINFO_PRESENT | CREATE_SUSPENDED | CREATE_UNICODE_ENVIRONMENT
            _check(k32.CreateProcessW(self.app, cmd_buf, None, None, False, flags,
                                      ctypes.cast(env_buf, LPVOID) if env_buf else None,
                                      cwd, ctypes.byref(si), ctypes.byref(pi)),
                   f"CreateProcessW({self.cmdline})")
            self._proc = pi.hProcess
            self.pid = pi.dwProcessId
            try:
                # Assigned while suspended so no descendant can escape the job.
                _check(k32.AssignProcessToJobObject(self._job, pi.hProcess), "AssignProcessToJobObject")
                k32.ResumeThread(pi.hThread)
            finally:
                k32.CloseHandle(pi.hThread)
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
        except BaseException:
            self.close()
            raise
        finally:
            # conhost holds its own duplicates; ours must go or EOF never arrives.
            if in_r.value:
                k32.CloseHandle(in_r)
            if out_w.value:
                k32.CloseHandle(out_w)
            if attr is not None:
                k32.DeleteProcThreadAttributeList(attr)

    def _read_loop(self):
        chunk = ctypes.create_string_buffer(65536)
        n = w.DWORD()
        while True:
            ok = k32.ReadFile(self._out_r, chunk, 65536, ctypes.byref(n), None)
            if not ok:
                return  # broken pipe after the console closed, or cancelled I/O
            if n.value == 0:
                continue  # a zero-byte write is not end of stream on a pipe
            data = chunk.raw[: n.value]
            with self._buf_lock:
                self._buf += data
                excess = len(self._buf) - BUFFER_LIMIT
                if excess > 0:
                    del self._buf[:excess]
                    self._pos = max(0, self._pos - excess)
            if self._on_output is not None:
                try:
                    self._on_output(data)
                except Exception:
                    pass  # a broken consumer must not stop the drain

    def write(self, data):
        """Write all of data, or raise. Refused once closing has begun."""
        view = ctypes.create_string_buffer(data, len(data))
        total = 0
        with self._write_lock:
            if self._closing or not self._in_w:
                raise OSError("The terminal is closed.")
            while total < len(data):
                n = w.DWORD()
                _check(k32.WriteFile(self._in_w, ctypes.byref(view, total), len(data) - total,
                                     ctypes.byref(n), None), "WriteFile")
                total += n.value
        return total

    def type_line(self, text, delay=0.4):
        """Type text, wait, then press Enter as a separate write."""
        self.write(text.encode("utf-8"))
        time.sleep(delay)
        self.write(b"\r")

    def read_new(self):
        with self._buf_lock:
            data = bytes(self._buf[self._pos:])
            self._pos = len(self._buf)
        return data

    def snapshot(self):
        with self._buf_lock:
            return bytes(self._buf)

    def resize(self, cols, rows):
        with self._h_lock:
            if self._closing or not self._hpc:
                return
            hr = k32.ResizePseudoConsole(self._hpc, COORD(cols, rows))
        if hr != S_OK:
            raise OSError(f"ResizePseudoConsole failed: 0x{hr & 0xFFFFFFFF:08x}")

    def alive(self):
        with self._h_lock:
            if self._closing or not self._proc:
                return False
            return k32.WaitForSingleObject(self._proc, 0) == WAIT_TIMEOUT

    def wait(self, timeout=None):
        """Return the exit code once the process has exited, else None on timeout."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            with self._h_lock:
                if not self._proc:
                    return self.exit_code
                if k32.WaitForSingleObject(self._proc, 0) == WAIT_OBJECT_0:
                    code = w.DWORD()
                    if k32.GetExitCodeProcess(self._proc, ctypes.byref(code)):
                        self.exit_code = code.value
                    return self.exit_code
            if deadline is not None and time.monotonic() >= deadline:
                return None
            time.sleep(0.03)

    def pids(self):
        """Every live process in this host's job (root plus descendants)."""
        count = 1024
        buf = ctypes.create_string_buffer(8 + count * ctypes.sizeof(ULONG_PTR))
        with self._h_lock:
            if self._closed or not self._job:
                return []
            if not k32.QueryInformationJobObject(self._job, JobObjectBasicProcessIdList,
                                                 buf, len(buf), None):
                return []
        listed = ctypes.cast(buf, ctypes.POINTER(w.DWORD))[1]
        ids = ctypes.cast(ctypes.byref(buf, 8), ctypes.POINTER(ULONG_PTR))
        return [ids[i] for i in range(listed)]

    def close(self):
        """Kill the whole tree, then tear down the console. Safe to call twice.

        A concurrent caller blocks until the first close has finished.
        """
        with self._close_lock:
            if self._closed:
                return
            with self._h_lock:
                self._closing = True
                job, proc, hpc = self._job, self._proc, self._hpc
            if job:
                k32.TerminateJobObject(job, 1)
            if proc:
                k32.TerminateProcess(proc, 1)  # also covers a failed job assignment
                self.wait(5)

            # Blocks until output is drained, so the reader must still be
            # running here, and it must not be allowed to hang shutdown.
            if hpc:
                self._hpc = None
                t = threading.Thread(target=k32.ClosePseudoConsole, args=(hpc,), daemon=True)
                t.start()
                t.join(5)
            reader = self._reader
            if reader is not None:
                reader.join(5)
                if reader.is_alive() and self._out_r:
                    k32.CancelIoEx(self._out_r, None)
                    reader.join(2)

            # With the console gone, a writer stuck on a full pipe has failed by now.
            got_writer = self._write_lock.acquire(timeout=5)
            try:
                if self._in_w:
                    k32.CloseHandle(self._in_w)
                    self._in_w = None
            finally:
                if got_writer:
                    self._write_lock.release()
            if self._out_r and not (reader is not None and reader.is_alive()):
                k32.CloseHandle(self._out_r)
                self._out_r = None

            with self._h_lock:
                self._closed = True
                if proc:
                    code = w.DWORD()
                    if self.exit_code is None and k32.GetExitCodeProcess(proc, ctypes.byref(code)):
                        self.exit_code = code.value
                    k32.CloseHandle(proc)
                    self._proc = None
                if job:
                    k32.CloseHandle(job)
                    self._job = None
