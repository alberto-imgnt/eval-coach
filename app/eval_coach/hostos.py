"""The one place that knows which operating system the app is running on.

Everything here takes an optional `platform` (a `sys.platform` value) so tests can ask for either
system's answer. On Windows every value is exactly what the app used before this module existed.
"""
from __future__ import annotations

import os
import platform as _platform
import signal
import subprocess
import sys
import time
import uuid
from collections import namedtuple
from pathlib import Path

CREATE_NO_WINDOW = 0x08000000
MAC_MIN_VERSION = (13, 0)
MAC_NODE_MIN_VERSION = (13, 5)

NodePin = namedtuple("NodePin", "version url sha256 folder archive_ext download_bytes exe_relative npx_cli_relative needs_bytes")

_NODE_VERSION = "26.13.0"
_NODE_BASE = f"https://nodejs.org/dist/v{_NODE_VERSION}/"
NODE_PINS = {
    "windows": NodePin(
        _NODE_VERSION, _NODE_BASE + "node-v26.13.0-win-x64.zip",
        "dcc60d59a0746999f99064a01c020445d54d84228c691cdbf25b49ac3b59150a", "node-v26.13.0-win-x64", ".zip",
        41157375, ("node.exe",), ("node_modules", "npm", "bin", "npx-cli.js"), 200 * 10**6),
    "mac-arm64": NodePin(
        _NODE_VERSION, _NODE_BASE + "node-v26.13.0-darwin-arm64.tar.gz",
        "d38bd5e5a2ddce6bbb5ce45e46e208337da4d51fffe611e567fd32073d6439f6", "node-v26.13.0-darwin-arm64",
        ".tar.gz", 58334661, ("bin", "node"), ("lib", "node_modules", "npm", "bin", "npx-cli.js"), 300 * 10**6),
    "mac-x64": NodePin(
        _NODE_VERSION, _NODE_BASE + "node-v26.13.0-darwin-x64.tar.gz",
        "525c9b29bb0263d687de60a4cec0e2a6db876a8eb032369e5795eca71e7c358e", "node-v26.13.0-darwin-x64",
        ".tar.gz", 59802926, ("bin", "node"), ("lib", "node_modules", "npm", "bin", "npx-cli.js"), 300 * 10**6),
}

MAC_TOOL_DIRS = ("/opt/homebrew/bin", "/opt/homebrew/sbin", "/usr/local/bin")
MAC_HOME_TOOL_DIRS = (".local/bin", ".npm-global/bin")


def _name(platform=None):
    return sys.platform if platform is None else platform


def is_windows(platform=None):
    return _name(platform) == "win32"


def is_mac(platform=None):
    return _name(platform) == "darwin"


IS_WINDOWS = is_windows()
IS_MAC = is_mac()


def platform_key(platform=None):
    """"windows", "mac" or "other": the key content files use for a platform."""
    if is_windows(platform):
        return "windows"
    return "mac" if is_mac(platform) else "other"


def content_platform():
    """"windows" or "mac": which set of words the course text uses. `EVAL_COACH_TEST_PLATFORM` overrides it for tests."""
    forced = os.environ.get("EVAL_COACH_TEST_PLATFORM", "").strip().lower()
    if forced in ("windows", "mac"):
        return forced
    return "windows" if is_windows() else "mac"


def project_path_example():
    return "C:\\Users\\you\\eval-project" if content_platform() == "windows" else "/Users/you/eval-project"


# --- processes -----------------------------------------------------------------

def _system32():
    return os.path.join(os.environ.get("SystemRoot") or r"C:\Windows", "System32")


def tool_path(name, platform=None):
    """Full path of a system tool: curl, tar, taskkill, cmd, powershell, zsh, shasum."""
    if is_windows(platform):
        system32 = _system32()
        windows = {"curl": os.path.join(system32, "curl.exe"), "tar": os.path.join(system32, "tar.exe"),
                   "taskkill": os.path.join(system32, "taskkill.exe"), "cmd": os.path.join(system32, "cmd.exe"),
                   "powershell": os.path.join(system32, "WindowsPowerShell", "v1.0", "powershell.exe")}
        return windows[name]
    posix = {"curl": "/usr/bin/curl", "tar": "/usr/bin/tar", "shasum": "/usr/bin/shasum", "zsh": "/bin/zsh",
             "sh": "/bin/sh", "ps": "/bin/ps"}
    return posix[name]


def popen_flags(platform=None, new_group=True):
    """Keyword arguments for subprocess.Popen: no console window on Windows, a new process group on a Mac."""
    if is_windows(platform):
        return {"creationflags": CREATE_NO_WINDOW}
    return {"start_new_session": True} if new_group else {}


def kill_tree(proc, platform=None, wait_seconds=3.0):
    """End a process and everything it started. Never raises."""
    if is_windows(platform):
        try:
            subprocess.run([tool_path("taskkill", platform), "/T", "/F", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                           timeout=15, creationflags=CREATE_NO_WINDOW)
        except (OSError, subprocess.SubprocessError):
            proc.kill()
        return
    kill_group(proc.pid, wait_seconds, reap=proc.poll)
    try:
        proc.kill()
    except OSError:
        pass


def kill_group(pgid, wait_seconds=3.0, reap=None):
    """POSIX: polite stop of the whole process group, then a forced one after a short wait.

    `reap` (for example `proc.poll`) is called while waiting, so an exited group leader is not left as a zombie
    that keeps the group looking alive.
    """
    for sig in (signal.SIGHUP, signal.SIGTERM):
        if not _signal_group(pgid, sig):
            return
        deadline = time.monotonic() + wait_seconds / 2
        while time.monotonic() < deadline:
            if reap is not None:
                reap()
            if not group_alive(pgid):
                return
            time.sleep(0.05)
    _signal_group(pgid, signal.SIGKILL)
    if reap is not None:
        deadline = time.monotonic() + 1.0
        while time.monotonic() < deadline and (reap() is None or group_alive(pgid)):
            time.sleep(0.02)


def _signal_group(pgid, sig):
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return False
    except OSError:
        return False
    return True


def group_alive(pgid):
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


# --- downloads, installs, recipes -----------------------------------------------

def download_argv(output_name, url, max_time, platform=None):
    argv = [tool_path("curl", platform), "--fail", "--location"]
    if is_windows(platform):
        argv.append("--ssl-no-revoke")
    argv += ["--connect-timeout", "30", "--max-time", str(max_time), "--retry", "2", "--retry-delay", "3",
             "--silent", "--show-error", "--output", output_name, url]
    return argv


def extract_argv(archive_name, destination_name, platform=None):
    flag = "-xf" if is_windows(platform) else "-xzf"
    return [tool_path("tar", platform), flag, archive_name, "-C", destination_name]


def recipe_shell_argv(shell, command, platform=None):
    """The argv that runs an install recipe. `shell` is the recipe's own value (cmd, powershell, zsh)."""
    if is_windows(platform):
        if shell == "powershell":
            return [tool_path("powershell", platform), "-NoProfile", "-Command", command]
        return [tool_path("cmd", platform), "/d", "/s", "/c", command]
    return [tool_path("zsh", platform), "-lc", command]


def recipe_shells(platform=None):
    """The recipe shell names that mean something on this platform."""
    return ("cmd", "powershell", "none") if not is_mac(platform) else ("zsh", "none")


# --- PATH ---------------------------------------------------------------------

def read_registry_paths():
    """Windows PATH entries a new terminal would get, so a CLI installed a minute ago can be found. Read only."""
    if sys.platform != "win32":
        return []
    import winreg

    found = []
    for root, key_path in ((winreg.HKEY_LOCAL_MACHINE,
                            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                           (winreg.HKEY_CURRENT_USER, "Environment")):
        try:
            with winreg.OpenKey(root, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        found.extend(os.path.expandvars(part) for part in str(value).split(os.pathsep) if part.strip())
    return found


def mac_tool_dirs(home=None, extra=()):
    """Folders Mac installers put commands in, then `extra` (folders under the home folder, from the recipes).

    Only folders that exist are returned.
    """
    base = Path(home) if home is not None else Path(os.path.expanduser("~"))
    candidates = [str(base / part) for part in MAC_HOME_TOOL_DIRS] + list(MAC_TOOL_DIRS)
    candidates += [str(base / part) for part in extra]
    return [folder for folder in candidates if os.path.isdir(folder)]


def extra_path_dirs(platform=None, home=None, extra=()):
    """PATH entries beyond the running process's own, so a tool installed a minute ago is found."""
    if is_windows(platform):
        return read_registry_paths()
    if is_mac(platform):
        return mac_tool_dirs(home, extra)
    return []


# --- Node.js ------------------------------------------------------------------

def mac_chip(machine=None):
    """"arm64" or "x64", the build of the app's own process."""
    machine = (machine or _platform.machine()).lower()
    return "arm64" if machine in ("arm64", "aarch64") else "x64"


def node_pin(platform=None, machine=None):
    if is_mac(platform):
        return NODE_PINS["mac-" + mac_chip(machine)]
    return NODE_PINS["windows"]


def node_root(node_exe, pin):
    """The folder a Node.js distribution unpacks to, given the path of its node executable."""
    return Path(node_exe).parents[len(pin.exe_relative) - 1]


def mac_version(text=None):
    """(major, minor) of macOS, or None when it cannot be told."""
    text = _platform.mac_ver()[0] if text is None else text
    parts = str(text).split(".")
    try:
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return None


def node_supported(platform=None, version_text=None):
    """False only on a Mac whose macOS is too old for the pinned Node.js build."""
    if not is_mac(platform):
        return True
    version = mac_version(version_text)
    return version is None or version >= MAC_NODE_MIN_VERSION


def default_home_label(platform=None):
    """How the default storage folder is written in help text."""
    return "%USERPROFILE%\\.eval-coach" if is_windows(platform) else "~/.eval-coach"


def private_python_relative(platform=None):
    return ("runtime", "python", "python.exe") if not is_mac(platform) else ("runtime", "python", "bin", "python3")


def python_command_names(platform=None):
    """The command names that mean Python on this platform, in the order to try."""
    return ("python",) if not is_mac(platform) else ("python3", "python")


def terminal_marker(hints, platform=None):
    """(variable, value) that names a terminal the listed AIs know, or (None, None)."""
    if is_mac(platform):
        variable = hints.get("marker_variable_mac")
        return (variable, str(hints.get("marker_value_mac", ""))) if variable else (None, None)
    variable = hints.get("marker_variable")
    return (variable, str(uuid.uuid4())) if variable else (None, None)
