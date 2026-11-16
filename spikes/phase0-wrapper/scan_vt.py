"""Count terminal control sequences the CLIs emit, from raw transcripts."""
import glob
import os
import re
import sys

PATTERNS = [
    ("DSR cursor query", rb"\x1b\[6n"), ("DA primary", rb"\x1b\[0?c"), ("DA secondary", rb"\x1b\[>0?c"),
    ("kitty kbd query", rb"\x1b\[\?u"), ("bracketed paste on", rb"\x1b\[\?2004h"),
    ("win32-input-mode on", rb"\x1b\[\?9001h"), ("focus reporting on", rb"\x1b\[\?1004h"),
    ("alt screen on", rb"\x1b\[\?1049h"), ("OSC color query", rb"\x1b\]1[01];\?"),
    ("sync output", rb"\x1b\[\?2026[hl]"), ("mouse on", rb"\x1b\[\?100[0236]h"),
]
here = os.path.dirname(os.path.abspath(__file__))
for f in sorted(glob.glob(os.path.join(here, "transcripts", sys.argv[1] if len(sys.argv) > 1 else "*.log"))):
    b = open(f, "rb").read()
    hits = [f"{n}={len(re.findall(p, b))}" for n, p in PATTERNS if re.search(p, b)]
    print(os.path.basename(f), len(b), "bytes;", ", ".join(hits) or "none")
