"""Drive one CLI through ConPTY and detect the file it writes (throwaway spike).

    python test_cli.py probe <cli>          launch, observe, type nothing, answer nothing
    python test_cli.py run <cli> [--single-write]

Terminal output is treated as untrusted data: it only selects from the fixed
policy in choose_option(), which refuses anything but a single-use approval of
an action in this task folder.
"""
import codecs
import ctypes
import json
import os
import re
import shutil
import sys
import time
from ctypes import wintypes

from conpty import ConPTY

HERE = os.path.dirname(os.path.abspath(__file__))
TRANSCRIPTS = os.path.join(HERE, "transcripts")
ATTEMPTS = os.path.join(TRANSCRIPTS, "attempts.json")
LINE = "Read input.txt and write its contents in uppercase to output.txt. Do nothing else."
EXPECTED = "HELLO FROM EVAL COACH"
TIMEOUT = 180
COLS, ROWS = 120, 40
MAX_SUCCESS, MAX_ATTEMPTS = 2, 5  # 2 successful + 3 retries

# Per-CLI step list: what "ready for input" looks like on screen.
CLIS = {
    "copilot": {"cmd": "copilot", "ready": r"type @ to mention|shift\+tab|ctrl\+c\s+exit|/ commands"},
    "claude": {"cmd": "claude", "ready": r"\? for shortcuts|shift\+tab to cycle|try \"",
               # First-run offer unrelated to this task: declined, accepting would widen capabilities.
               "decline": r"Claude in Chrome extension detected"},
    "devin": {"cmd": "devin", "ready": r"ask devin|type a message|ctrl\+c|shift\+tab|/help"},
}

# Variables of the session running this test; a participant's app would not have them.
STRIP_ENV = re.compile(r"^(CLAUDE|ANTHROPIC_|VSCODE_|ELECTRON_|COPILOT_OTEL)", re.I)
# The hard rules forbid updates; these only affect this child process.
CHILD_ENV = {"DISABLE_AUTOUPDATER": "1", "COPILOT_AUTO_UPDATE": "false"}


def child_env():
    env = {k: v for k, v in os.environ.items() if not STRIP_ENV.match(k)}
    env.update(CHILD_ENV)
    return env


class Screen:
    """Just enough VT parsing to read what is on screen right now."""

    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.decoder = codecs.getincrementaldecoder("utf-8")("replace")
        self.pending = ""
        self.top, self.bottom = 0, rows - 1
        self.x = self.y = 0
        self.saved = (0, 0)
        self.wrap = False
        self.clear()

    def blank(self):
        return [" "] * self.cols

    def clear(self):
        self.grid = [self.blank() for _ in range(self.rows)]

    def scroll_up(self, n=1):
        for _ in range(n):
            del self.grid[self.top]
            self.grid.insert(self.bottom, self.blank())

    def scroll_down(self, n=1):
        for _ in range(n):
            del self.grid[self.bottom]
            self.grid.insert(self.top, self.blank())

    def index(self):
        if self.y == self.bottom:
            self.scroll_up()
        elif self.y < self.rows - 1:
            self.y += 1

    def put(self, ch):
        if self.wrap:
            self.x, self.wrap = 0, False
            self.index()
        self.grid[self.y][self.x] = ch
        if self.x == self.cols - 1:
            self.wrap = True
        else:
            self.x += 1

    def feed(self, data):
        text = self.pending + self.decoder.decode(data)
        self.pending = ""
        i, n = 0, len(text)
        while i < n:
            c = text[i]
            if c != "\x1b":
                if c == "\r":
                    self.x, self.wrap = 0, False
                elif c == "\n":
                    self.index()
                    self.wrap = False
                elif c == "\b":
                    self.x, self.wrap = max(self.x - 1, 0), False
                elif c == "\t":
                    self.x = min((self.x // 8 + 1) * 8, self.cols - 1)
                elif c >= " " and c != "\x7f":
                    self.put(c)
                i += 1
                continue
            if i + 1 >= n:
                self.pending = text[i:]
                return
            k = text[i + 1]
            if k == "[":
                m = re.compile(r"\x1b\[([0-?]*)[ -/]*([@-~])").match(text, i)
                if not m:
                    if n - i < 64:
                        self.pending = text[i:]
                        return
                    i += 2
                    continue
                self.csi(m.group(1), m.group(2))
                i = m.end()
            elif k in "]PX^_":
                end = re.compile(r"\x07|\x1b\\").search(text, i + 2)
                if not end:
                    self.pending = text[i:]
                    return
                i = end.end()
            elif k in "()*+":
                i += 3
            elif k == "7":
                self.saved = (self.x, self.y)
                i += 2
            elif k == "8":
                self.x, self.y = self.saved
                i += 2
            elif k == "M":
                if self.y == self.top:
                    self.scroll_down()
                elif self.y > 0:
                    self.y -= 1
                i += 2
            else:
                i += 2

    def csi(self, params, final):
        private = params[:1] in ("?", ">", "=", "<")
        nums = [int(p) if p.isdigit() else 0 for p in re.split("[;:]", params.lstrip("?>=<"))]
        a = nums[0] if nums else 0
        b = nums[1] if len(nums) > 1 else 0
        one = max(a, 1)
        if private:
            if final in "hl" and a in (1049, 47, 1047):
                self.clear()
                self.x = self.y = 0
            return
        if final != "m":
            self.wrap = False
        if final in "Hf":
            self.y, self.x = min(max(a, 1), self.rows) - 1, min(max(b, 1), self.cols) - 1
        elif final == "A":
            self.y = max(self.y - one, 0)
        elif final in "Be":
            self.y = min(self.y + one, self.rows - 1)
        elif final in "Ca":
            self.x = min(self.x + one, self.cols - 1)
        elif final == "D":
            self.x = max(self.x - one, 0)
        elif final == "E":
            self.x, self.y = 0, min(self.y + one, self.rows - 1)
        elif final == "F":
            self.x, self.y = 0, max(self.y - one, 0)
        elif final in "G`":
            self.x = min(one, self.cols) - 1
        elif final == "d":
            self.y = min(one, self.rows) - 1
        elif final == "J":
            cells = range(self.y + 1, self.rows) if a == 0 else range(0, self.y)
            if a in (2, 3):
                self.clear()
            else:
                for r in cells:
                    self.grid[r] = self.blank()
                self.erase_line(a)
        elif final == "K":
            self.erase_line(a)
        elif final == "X":
            for c in range(self.x, min(self.x + one, self.cols)):
                self.grid[self.y][c] = " "
        elif final == "P":
            del self.grid[self.y][self.x:self.x + one]
            self.grid[self.y] += [" "] * (self.cols - len(self.grid[self.y]))
        elif final == "@":
            self.grid[self.y][self.x:self.x] = [" "] * one
            del self.grid[self.y][self.cols:]
        elif final == "L" and self.top <= self.y <= self.bottom:
            for _ in range(one):
                del self.grid[self.bottom]
                self.grid.insert(self.y, self.blank())
        elif final == "M" and self.top <= self.y <= self.bottom:
            for _ in range(one):
                del self.grid[self.y]
                self.grid.insert(self.bottom, self.blank())
        elif final == "S":
            self.scroll_up(one)
        elif final == "T":
            self.scroll_down(one)
        elif final == "r":
            self.top, self.bottom = max(a, 1) - 1, (b or self.rows) - 1
            self.x = self.y = 0
        elif final == "s":
            self.saved = (self.x, self.y)
        elif final == "u":
            self.x, self.y = self.saved

    def erase_line(self, mode):
        row = self.grid[self.y]
        if mode == 0:
            row[self.x:] = [" "] * (self.cols - self.x)
        elif mode == 1:
            row[: self.x + 1] = [" "] * (self.x + 1)
        else:
            row[:] = self.blank()

    def lines(self):
        return ["".join(r).rstrip() for r in self.grid]

    def text(self):
        return "\n".join(self.lines()).rstrip()


OPTION = re.compile(r"^[\s│┃║|]*([❯›❭>▶➤●→])?[\s·]*(\d+)[.)]?\s+(.+?)[\s│┃║|]*$")
PERSISTENT = re.compile(r"always|don'?t ask|remember|session|all |every|future|permanent", re.I)
RISKY = re.compile(r"\b(rm|del|erase|remove-item|curl|wget|invoke-webrequest|iwr|git|npm|pip)\b|https?:", re.I)
FOREIGN_PATH = re.compile(r"[A-Za-z]:[\\/][^\s\"']*")


def find_menu(lines):
    """Return {'start','options':[{n,label,selected}]} for a numbered menu near the bottom."""
    last = max((i for i, l in enumerate(lines) if l.strip()), default=-1)
    found = []
    for i in range(last, max(last - 16, -1), -1):
        m = OPTION.match(lines[i])
        if m:
            found.insert(0, (i, m))
        elif found and int(found[0][1].group(2)) == 1:
            break
    run = []
    for i, m in found:
        if int(m.group(2)) == len(run) + 1:
            run.append((i, m))
    if len(run) < 2 or not any(re.match(r"(yes|no)\b", m.group(3), re.I) for _, m in run):
        return None
    return {"start": run[0][0],
            "options": [{"n": int(m.group(2)), "label": m.group(3), "selected": bool(m.group(1))}
                        for _, m in run]}


def choose_option(menu, lines, folder, decline=None):
    """Fixed approval policy. Returns (kind, option or None, reason)."""
    ctx_lines = [l for l in lines[max(menu["start"] - 16, 0):menu["start"]] if "Do nothing else" not in l]
    ctx = "\n".join(ctx_lines)
    labels = [o["label"] for o in menu["options"]]
    if decline and re.search(decline, ctx):
        no = [o for o in menu["options"] if re.match(r"no\b", o["label"], re.I)]
        return ("declined", no[0], "per-CLI step: decline") if no else ("declined", None, "no 'No' option")
    is_trust = re.search(r"\btrust\b", ctx + " ".join(labels), re.I)
    yes = [o for o in menu["options"] if re.match(r"yes\b", o["label"], re.I)]
    single = [o for o in yes if not PERSISTENT.search(o["label"])]
    if is_trust:
        # Claude's only affirmative is "Yes, I trust this folder".
        return ("trust", single[0], "single-use trust") if single else ("trust", None, f"no affirmative: {labels}")
    if not re.search(r"input\.txt|output\.txt", ctx, re.I):
        return ("unknown", None, "menu does not name this task's files")
    if RISKY.search(ctx):
        return ("approval", None, "menu context has a command outside this task")
    outside = [p for p in FOREIGN_PATH.findall(ctx)
               if not p.lower().replace("/", "\\").startswith(folder.lower())]
    if outside:
        return ("approval", None, f"menu names path outside folder: {outside}")
    if not single:
        return ("approval", None, f"no single-use option: {labels}")
    return ("approval", single[0], "single-use approval")


def read_output(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return None


def load_attempts():
    try:
        with open(ATTEMPTS) as f:
            return json.load(f)
    except OSError:
        return {}


def image_names(pids):
    """Executable path of each pid (no command lines: those can hold secrets)."""
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                               ctypes.POINTER(wintypes.DWORD)]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    names = set()
    for pid in pids:
        h = k32.OpenProcess(0x1000, False, pid)
        if not h:
            continue
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            names.add(buf.value)
        k32.CloseHandle(h)
    return names


class Run:
    def __init__(self, cli, label):
        self.cli, self.label = cli, label
        os.makedirs(TRANSCRIPTS, exist_ok=True)
        self.raw = open(os.path.join(TRANSCRIPTS, f"{label}.log"), "wb")
        self.events = open(os.path.join(TRANSCRIPTS, f"{label}.events.txt"), "w", encoding="utf-8")
        self.screen = Screen(COLS, ROWS)
        self.t0 = time.time()
        self.last_text = ""
        self.last_change = time.time()
        self.pids = set()
        self.images = set()
        self.imaged = 0
        self.pty = None

    def log(self, msg, screen=False):
        stamp = f"[{time.time() - self.t0:7.2f}s] {msg}"
        print(stamp, flush=True)
        self.events.write(stamp + "\n")
        if screen:
            self.events.write("--- screen ---\n" + self.screen.text() + "\n--------------\n")
        self.events.flush()

    def start(self, cmd, cwd):
        self.pty = ConPTY([cmd], cwd=cwd, env=child_env(), cols=COLS, rows=ROWS)
        self.log(f"launched pid={self.pty.pid} type={self.pty.launch_type} app={self.pty.app}")

    def pump(self):
        data = self.pty.read_new()
        if data:
            self.raw.write(data)
            self.raw.flush()
            self.screen.feed(data)
            text = self.screen.text()
            if text != self.last_text:
                self.last_text = text
                self.last_change = time.time()
        pids = self.pty.pids()
        self.pids.update(pids)
        if time.time() - self.imaged > 2:
            self.imaged = time.time()
            self.images.update(image_names(pids))

    def stable(self):
        return time.time() - self.last_change

    def sleep(self, seconds):
        end = time.time() + seconds
        while time.time() < end:
            self.pump()
            time.sleep(0.05)

    def finish(self):
        if self.pty:
            self.pump()
            self.log("final screen", screen=True)
            self.pty.close()
        self.raw.close()
        self.events.write(f"pids: {sorted(self.pids)}\n")
        self.events.write("images:\n" + "\n".join(sorted(self.images)) + "\n")
        self.events.close()


def probe(cli):
    existing = [f for f in os.listdir(TRANSCRIPTS)] if os.path.isdir(TRANSCRIPTS) else []
    n = sum(1 for f in existing if f.startswith(f"{cli}-probe") and f.endswith(".log")) + 1
    folder = os.path.join(HERE, "work", cli)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "input.txt"), "w") as f:
        f.write("hello from eval coach")
    r = Run(cli, f"{cli}-probe{n}")
    try:
        r.start(CLIS[cli]["cmd"], folder)
        end = time.time() + 40
        while time.time() < end and r.pty.alive():
            r.pump()
            if r.last_text and r.stable() > 8:
                break
            time.sleep(0.1)
        r.log(f"alive={r.pty.alive()} pids={r.pty.pids()} stable={r.stable():.1f}s", screen=True)
    finally:
        r.finish()


def press_option(r, option, menu):
    """Move the highlight to the option with arrow keys, confirm it moved, press Enter."""
    current = next((o["n"] for o in menu["options"] if o["selected"]), 1)
    delta = option["n"] - current
    for _ in range(abs(delta)):
        r.pty.write(b"\x1b[B" if delta > 0 else b"\x1b[A")
        r.sleep(0.25)
    r.sleep(0.4)
    after = find_menu(r.screen.lines())
    if after and next((o["n"] for o in after["options"] if o["selected"]), None) not in (option["n"], None):
        raise RuntimeError(f"highlight did not reach option {option['n']}")
    r.pty.write(b"\r")
    r.log(f"KEYS arrows={delta} then Enter -> {option['n']}. {option['label']!r}")


def run(cli, single_write):
    attempts = load_attempts()
    rec = attempts.setdefault(cli, {"attempts": 0, "success": 0})
    if rec["success"] >= MAX_SUCCESS or rec["attempts"] >= MAX_ATTEMPTS:
        print("attempt limit reached:", rec)
        return
    n = rec["attempts"] + 1
    folder = os.path.join(HERE, "work", cli)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, "input.txt"), "w") as f:
        f.write("hello from eval coach")
    output = os.path.join(folder, "output.txt")
    if os.path.exists(output):
        os.remove(output)

    r = Run(cli, f"{cli}-{n}")
    result = {"cli": cli, "n": n, "single_write": single_write, "typed": False, "prompts": [],
              "outcome": "timeout", "time_to_file_s": None, "output": None}
    typed_at = None
    answered_at = 0
    last_menu = None
    ready_re = re.compile(CLIS[cli]["ready"], re.I)
    rec["attempts"] += 1
    with open(ATTEMPTS, "w") as f:
        json.dump(attempts, f)
    try:
        r.start(CLIS[cli]["cmd"], folder)
        result["launch_type"], result["app"] = r.pty.launch_type, r.pty.app
        deadline = r.t0 + TIMEOUT
        while time.time() < deadline:
            r.pump()
            if not r.pty.alive():
                r.sleep(0.5)
                result["outcome"] = f"exited code={r.pty.wait(1)}"
                break

            body = read_output(output)
            if typed_at and body is not None and body.strip():
                if result["time_to_file_s"] is None:
                    result["time_to_file_s"] = round(time.time() - typed_at, 1)
                    r.log(f"output.txt appeared after {result['time_to_file_s']}s", screen=True)
                r.sleep(2)
                body = read_output(output)
                result["output"] = body
                result["outcome"] = "correct" if body.strip() == EXPECTED else "wrong-content"
                r.sleep(2)
                break

            lines = r.screen.lines()
            menu = find_menu(lines)
            if menu and r.stable() > 0.7 and time.time() - answered_at > 1.5:
                sig = [o["label"] for o in menu["options"]]
                kind, option, why = choose_option(menu, lines, folder, CLIS[cli].get("decline"))
                result["prompts"].append({"kind": kind, "options": sig, "why": why,
                                          "answer": option and option["label"], "at": round(time.time() - r.t0, 1)})
                r.log(f"PROMPT {kind}: {sig} -> {why}", screen=True)
                if option is None:
                    result["outcome"] = f"refused-prompt: {why}"
                    break
                if last_menu == sig and time.time() - answered_at < 8:
                    result["outcome"] = "prompt-did-not-clear"
                    break
                press_option(r, option, menu)
                answered_at = time.time()
                last_menu = sig
                r.last_change = time.time()
                continue

            marker = ready_re.search(r.last_text) and r.stable() > 1.5
            if not typed_at and not menu and r.last_text and (marker or r.stable() > 6):
                r.log(f"ready via {'marker' if marker else 'settle-6s'}", screen=True)
                if single_write:
                    r.pty.write(LINE.encode() + b"\r")
                else:
                    r.pty.write(LINE.encode())
                    r.sleep(0.4)
                    r.log("typed, before Enter", screen=True)
                    r.pty.write(b"\r")
                typed_at = time.time()
                result["typed"] = True
                r.log(f"sent line (single_write={single_write})")
                r.last_change = time.time()
                continue

            if (typed_at and single_write and not result.get("enter_resent") and r.stable() > 6
                    and LINE in r.last_text):
                r.pty.write(b"\r")
                typed_at = time.time()
                result["enter_resent"] = True
                r.log("line still on screen after 6s idle: Enter from the single write was not taken, sent \\r again",
                      screen=True)
                r.last_change = time.time()
                continue

            if not typed_at and r.stable() > 30:
                result["outcome"] = "never-ready"
                r.log("no ready marker and screen idle 30s", screen=True)
                break
            if typed_at and r.stable() > 45:
                result["outcome"] = "stuck-screen-idle-45s"
                r.log("screen idle 45s after typing", screen=True)
                break
            time.sleep(0.1)
    except Exception as exc:
        result["outcome"] = f"harness-error: {exc}"
        r.log(result["outcome"])
    finally:
        r.finish()
    if result["outcome"] == "correct":
        rec["success"] += 1
    with open(ATTEMPTS, "w") as f:
        json.dump(attempts, f)
    result["pids"] = sorted(r.pids)
    with open(os.path.join(TRANSCRIPTS, f"{cli}-{n}.result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in result.items() if k != "pids"}, ensure_ascii=False))


if __name__ == "__main__":
    mode, cli = sys.argv[1], sys.argv[2]
    if cli not in CLIS:
        sys.exit("unknown cli")
    if mode == "probe":
        probe(cli)
    else:
        run(cli, "--single-write" in sys.argv)
