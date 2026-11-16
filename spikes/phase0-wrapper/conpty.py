"""Stdlib-only ConPTY host for Windows (throwaway feasibility spike).

Public surface:
    resolve_command(argv) -> (application_name, command_line, launch_type)
    ConPTY(argv, cwd=None, env=None, cols=120, rows=40)
        .write(bytes)  .read_new()  .snapshot()  .resize(cols, rows)
        .alive()  .wait(timeout)  .exit_code  .pids()  .close()
"""
import ctypes
import os
import shutil
import subprocess
import threading
from ctypes import wintypes as w

k32 = ctypes.WinDLL("kernel32", use_last_error=True)

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
INFINITE = 0xFFFFFFFF
STILL_ACTIVE = 259
ERROR_BROKEN_PIPE = 109
S_OK = 0


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


_sig(k32.CreatePipe, w.BOOL, ctypes.POINTER(HANDLE), ctypes.POINTER(HANDLE), LPVOID, w.DWORD)
_sig(k32.CloseHandle, w.BOOL, HANDLE)
_sig(k32.ReadFile, w.BOOL, HANDLE, LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), LPVOID)
_sig(k32.WriteFile, w.BOOL, HANDLE, LPVOID, w.DWORD, ctypes.POINTER(w.DWORD), LPVOID)
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


def _check(ok, what):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error(), what)


# Characters cmd.exe re-interprets even inside quotes (the "BatBadBut" class).
_CMD_UNSAFE = set('%!"\r\n')


def resolve_command(argv):
    """Return (application_name, command_line, launch_type) for CreateProcessW.

    Plain CreateProcess only runs PE files, so anything else is routed through
    its interpreter. Arguments to batch files are refused if cmd.exe could
    re-interpret them; the real app starts CLIs with no arguments.
    """
    target = shutil.which(argv[0])
    if not target and os.path.isfile(argv[0]):  # which() rejects extensionless paths
        target = os.path.abspath(argv[0])
    if not target:
        raise FileNotFoundError(f"command not found on PATH: {argv[0]!r}")
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
                raise ValueError(f"unsafe character for cmd.exe in {a!r}")
        comspec = os.environ.get("ComSpec") or shutil.which("cmd.exe")
        inner = subprocess.list2cmdline([target] + args)
        return comspec, f'"{comspec}" /d /s /c "{inner}"', ext[1:]

    if ext == ".ps1":
        ps = shutil.which("pwsh") or shutil.which("powershell")
        if not ps:
            raise FileNotFoundError("no PowerShell found for .ps1 shim")
        return ps, subprocess.list2cmdline([ps, "-NoProfile", "-File", target] + args), "ps1"

    with open(target, "rb") as f:
        head = f.read(2)
    if head == b"#!":
        sh = shutil.which("sh")
        if not sh:
            raise FileNotFoundError(f"no sh.exe to run shebang shim: {target}")
        return sh, subprocess.list2cmdline([sh, target] + args), "sh-script"
    raise OSError(f"don't know how to launch {target}")


def _env_block(env):
    if env is None:
        return None
    items = sorted(f"{k}={v}" for k, v in env.items())
    return ctypes.create_unicode_buffer("\0".join(items) + "\0\0")


class ConPTY:
    def __init__(self, argv, cwd=None, env=None, cols=120, rows=40):
        self.app, self.cmdline, self.launch_type = resolve_command(argv)
        self.exit_code = None
        self._buf = bytearray()
        self._pos = 0
        self._lock = threading.Lock()
        self._closed = False
        self._hpc = None
        self._proc = None
        self._job = None
        self._in_w = self._out_r = None
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
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    def _read_loop(self):
        chunk = ctypes.create_string_buffer(65536)
        n = w.DWORD()
        while True:
            ok = k32.ReadFile(self._out_r, chunk, 65536, ctypes.byref(n), None)
            if not ok or n.value == 0:
                return
            with self._lock:
                self._buf += chunk.raw[: n.value]

    def write(self, data):
        view = ctypes.create_string_buffer(data, len(data))
        n = w.DWORD()
        _check(k32.WriteFile(self._in_w, view, len(data), ctypes.byref(n), None), "WriteFile")
        return n.value

    def read_new(self):
        with self._lock:
            data = bytes(self._buf[self._pos:])
            self._pos = len(self._buf)
        return data

    def snapshot(self):
        with self._lock:
            return bytes(self._buf)

    def resize(self, cols, rows):
        hr = k32.ResizePseudoConsole(self._hpc, COORD(cols, rows))
        if hr != S_OK:
            raise OSError(f"ResizePseudoConsole failed: 0x{hr & 0xFFFFFFFF:08x}")

    def alive(self):
        return k32.WaitForSingleObject(self._proc, 0) != WAIT_OBJECT_0

    def wait(self, timeout=None):
        ms = INFINITE if timeout is None else int(timeout * 1000)
        if k32.WaitForSingleObject(self._proc, ms) != WAIT_OBJECT_0:
            return None
        code = w.DWORD()
        k32.GetExitCodeProcess(self._proc, ctypes.byref(code))
        self.exit_code = code.value
        return self.exit_code

    def pids(self):
        """Every live process in this host's job (root plus descendants)."""
        if not self._job:
            return []
        count = 1024
        buf = ctypes.create_string_buffer(8 + count * ctypes.sizeof(ULONG_PTR))
        if not k32.QueryInformationJobObject(self._job, JobObjectBasicProcessIdList, buf, len(buf), None):
            return []
        listed = ctypes.cast(buf, ctypes.POINTER(w.DWORD))[1]
        ids = ctypes.cast(ctypes.byref(buf, 8), ctypes.POINTER(ULONG_PTR))
        return [ids[i] for i in range(listed)]

    def close(self):
        """Kill the whole tree, then tear down the console. Safe to call twice."""
        if self._closed:
            return
        self._closed = True
        if self._job:
            k32.TerminateJobObject(self._job, 1)
        if self._proc:
            self.wait(5)
        if self._in_w:
            k32.CloseHandle(self._in_w)
        if self._hpc:
            # Can block until output is drained, so the reader must still be running
            # and this must not be allowed to hang shutdown.
            t = threading.Thread(target=k32.ClosePseudoConsole, args=(self._hpc,), daemon=True)
            t.start()
            t.join(5)
        reader = getattr(self, "_reader", None)
        if reader:
            reader.join(5)
        if self._out_r and not (reader and reader.is_alive()):
            k32.CloseHandle(self._out_r)
        if self._proc:
            k32.CloseHandle(self._proc)
        if self._job:
            k32.CloseHandle(self._job)
            self._job = None
