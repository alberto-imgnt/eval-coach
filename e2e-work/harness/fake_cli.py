"""NOT an AI CLI. A scripted stand-in so the real UI and backend can be exercised
without a model. It asks an approval-shaped question and waits for Enter from the xterm."""
import datetime, hashlib, json, os, pathlib, re, shutil, subprocess, sys, time

ROW = re.compile(r"^(C\d+) (PASS|FAIL|NOT CHECKED)\s+(.*)$")

ROOT = pathlib.Path(r"C:\Projects\Improving\eval-coach")
GOLD = ROOT / "tests" / "golden"
NW = GOLD / "northwind"
EVENTS = ROOT / "e2e-work" / "fake-cli-events.jsonl"
MODE = ROOT / "e2e-work" / "fake-cli-mode.txt"  # "silent": the hook line prints a result but writes no file

HOOK_VARIANTS = [
    ("4", "fail", "It reads well but the blocker is not what the notes say."),
    ("7", "pass", "It is short and grouped by client, and the tone is right."),
    ("3", "fail", "The facts do not match the rough notes."),
]


def log(event, **fields):
    """Harness-only record of what this process saw. The app never reads it."""
    with open(EVENTS, "a", encoding="utf-8") as f:
        f.write(json.dumps(dict(event=event, pid=os.getpid(), ts=time.time(), **fields)) + "\n")


def mode():
    try:
        return MODE.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def events():
    """Every event this stand-in logged so far (harness-only record)."""
    out = []
    if EVENTS.exists():
        for raw in EVENTS.read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(raw))
            except ValueError:
                pass
    return out


def approve(name):
    log("approve", name=name, cwd=os.getcwd())
    print(f"\nDo you want to create {name}?\n\u276f 1. Yes\n  2. No", flush=True)
    typed = input()
    log("approved", name=name, typed=typed)
    print("\x1b[2J\x1b[H", end="", flush=True)  # a real CLI removes the menu once answered


def work(seconds):
    for i in range(int(seconds * 2)):
        print(f"\rworking {i:03d} (esc to interrupt)", end="", flush=True)
        time.sleep(0.5)
    print("\r" + " " * 40 + "\r", end="", flush=True)


def write(path, text):
    approve(path)
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def parse_checker(text):
    """Per-criterion results from the checker's printed output: {id: {"name", "verdicts": [..]}} in file order."""
    found = {}
    for raw in text.splitlines():
        m = ROW.match(raw)
        if m:
            item = found.setdefault(m.group(1), {"name": m.group(3).split(": ", 1)[0].strip(), "verdicts": []})
            item["verdicts"].append({"PASS": "P", "FAIL": "F"}.get(m.group(2), "NC"))
    return found


def counted_log(runs, checker, cwd, title, prompt, model, hypothesis=""):
    """A log entry in the exact format of the build skill's run + log mode, from the real checker output."""
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    out = subprocess.run([sys.executable, checker] + runs, capture_output=True, text=True, encoding="utf-8",
                         env=env, timeout=60, cwd=cwd).stdout
    results = parse_checker(out.split("== Pass rate per criterion")[0])
    wrong = mode() == "wrong-count"  # the stand-in logs one count too low, so the gate's message can be seen
    rows, checked, passes_all, not_checked = [], 0, 0, []
    for cid, item in results.items():
        verdicts = item["verdicts"]
        if all(v == "NC" for v in verdicts):
            not_checked.append(cid)
            rows.append("| %s %s | not checked | n/a | needs a rewrite |" % (cid, item["name"]))
            continue
        passes = verdicts.count("P")
        failing = ", ".join("run-%d" % n for n, v in enumerate(verdicts, 1) if v == "F")
        checked += len(verdicts)
        passes_all += passes
        logged = passes
        if wrong and logged > 0:
            logged -= 1
            wrong = False
        rows.append("| %s %s | %d/%d | %d%% | %s |" % (cid, item["name"], logged, len(verdicts),
                                                       int(logged * 100 / len(verdicts) + 0.5),
                                                       "fails: " + failing if failing else ""))
    listed = "%d (%s)" % (len(not_checked), ", ".join(not_checked)) if not_checked else "0"
    return "\n".join([
        title, "- Date: " + datetime.date.today().isoformat(), "- Prompt: " + prompt,
        "- Model: " + model, "- Runs: 5", "- Overall: %d / %d" % (passes_all, checked), "- Not checked: " + listed, "",
        "| Criterion | Passed | Rate | Notes |", "| --- | --- | --- | --- |"] + rows + [
        "", "- Hypothesis:" + (" " + hypothesis if hypothesis else ""), "- Change:", "- Result:", "- Reasoning:", ""])


def baseline_log(line):
    """The Iteration 0 entry, counted on the project's five runs."""
    runs = ["runs/run-%d.txt" % n for n in range(1, 6)]
    prompt = line.split("The prompt file is ", 1)[1].split(". The model was", 1)[0]
    model = line.split("The model was ", 1)[1].rstrip().rstrip(".")
    # The promptfoo track has no check.py: the stand-in counts with the Northwind reference checker, which is what
    # the config encodes, so the app's own (real promptfoo) count is checked against an independent one.
    checker = str(GOLD / "reference-check.py") if "build-promptfoo-config" in line else "check.py"
    return counted_log(runs, checker, None, "## Iteration 0: baseline", prompt, model)


PART4_LOG_LINE = re.compile(r"The prompt file is (\S+)/prompt\.md\. The model was (.+?)\. Append the entry to (\S+) "
                            r"as Iteration (\d+)\. Copy the Hypothesis word for word from (\S+)")
TIGHTEN_FIND = "return True, 'found \"Blocker:\" and \"Need:\"'"


def part4_checker(config_text):
    """The promptfoo track's independent checker for a Part 4 attempt: the Northwind reference checker, tightened the same
    way the config says it is (a Blocker line that mentions test data)."""
    text = (GOLD / "reference-check.py").read_text(encoding="utf-8")
    if "test data" in config_text:
        text = text.replace(TIGHTEN_FIND, "if 'test data' not in text.split('Blocker:', 1)[1].splitlines()[0]:\n"
                            "        return False, 'blocker does not mention test data'\n    " + TIGHTEN_FIND)
    target = ROOT / "e2e-work" / "pf-independent-check-part4.py"
    target.write_text(text, encoding="utf-8")
    return str(target)


def part4_log_entry(line):
    """The entry for Iteration n of run + log mode: the counts from the attempt's own checker and the saved Hypothesis
    copied word for word, with Change, Result and Reasoning left empty. Returns (log path, number, entry text)."""
    m = PART4_LOG_LINE.search(line)
    folder, model, log, n, hypothesis = pathlib.Path(m.group(1)), m.group(2), m.group(3), int(m.group(4)), m.group(5)
    saved = " ".join(pathlib.Path(hypothesis).read_text(encoding="utf-8").split())
    if "build-promptfoo-config" in line:
        config = (folder / "promptfooconfig.yaml").read_text(encoding="utf-8")
        runs = [str(folder / "runs" / ("run-%d.txt" % k)) for k in range(1, 6)]
        entry = counted_log(runs, part4_checker(config), None, "## Iteration %d: round %d" % (n, n), "%s/prompt.md" % m.group(1),
                            model, saved)
    else:  # the attempt's own check.py, run in the attempt's folder the way the app runs it
        runs = ["runs/run-%d.txt" % k for k in range(1, 6)]
        entry = counted_log(runs, "check.py", str(folder), "## Iteration %d: round %d" % (n, n), "%s/prompt.md" % m.group(1),
                            model, saved)
    return log, n, entry


def append_log_entry(log, n, entry):
    """Add the entry to the end of the log. An older entry for the same iteration is replaced, never added twice."""
    path = pathlib.Path(log)
    text = path.read_bytes().decode("utf-8") if path.exists() else ""
    eol = "\r\n" if "\r\n" in text else "\n"
    mine = re.search(r"^## Iteration %d\b.*?(?=^## Iteration \d+|\Z)" % n, text, re.M | re.S)
    if mine:
        text = text[:mine.start()] + text[mine.end():]
    text = text.rstrip("\r\n") + eol + eol if text.strip() else ""
    approve(log)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text + entry.replace("\n", eol)).encode("utf-8"))


PF_TEMPLATE = ROOT / "e2e-work" / "harness" / "standin-promptfooconfig.yaml"

PART1_WEAKER = ("Subject: Weekly update\n\nDear lead,\n\nThis week was a great success. I worked hard on many things, "
                "from Monday to Friday, and I am proud of what I achieved. Here is a long account of every day.\n")
PART1_BETTER = ("Friday update\n\nNorthwind: reporting feature built, demo run, feedback fixed.\nContoso: estimate reviewed.\n"
                "Internal: onboarded a teammate.\nBlocker: waiting on client test data access.\nNeed: access this week.\n")

# Part 4 answer sets, chosen by a marker line in the round's prompt ("stand-in answers: gain"). "gain" and "flat" are the
# authored worked answers (26 of 30 on the Practice and Part 3 checks, so a gain over 25 and then no change), "worse" is
# a weaker mix, and no marker gives the five Northwind samples, which are the baseline's own answers.
PART4_MARKER = re.compile(r"stand-in answers:\s*([a-z]+)", re.I)
PART4_WORSE = ("sample-run-3.txt", "sample-run-5.txt", "fixture-bad.txt", "fixture-polished-but-wrong.txt", "sample-run-3.txt")


def part4_blind_folder():
    return os.getcwd().lower().replace("\\", "/").endswith("/part4/blind")


def part4_answer(prompt):
    """The next of the five answers for this prompt: how many answers this exact prompt has had so far decides which."""
    digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    seen = 0
    for e in events():  # the harness notes the start of each round's five answers, so an earlier run never shifts the count
        if e.get("event") == "part4-round":
            seen = 0
        elif e.get("answer_of") == digest:
            seen += 1
    k = seen % 5 + 1
    log("part4-answer", answer_of=digest, number=k)
    match = PART4_MARKER.search(prompt)
    kind = match.group(1).lower() if match else ""
    if kind in ("gain", "flat"):
        return (GOLD / "part4-worked" / ("round-1" if kind == "gain" else "round-2") / ("run-%d.txt" % k)).read_text(encoding="utf-8")
    if kind == "worse":
        return (NW / PART4_WORSE[k - 1]).read_text(encoding="utf-8")
    return (NW / ("sample-run-%d.txt" % k)).read_text(encoding="utf-8")


def pf_config_text():
    return PF_TEMPLATE.read_text(encoding="utf-8")


def pf_add_fixtures(text):
    extra = "".join("  - description: %s\n    vars:\n      output: file://fixtures/%s.txt\n" % (n, n)
                    for n in ("fixture-bad", "fixture-polished-but-wrong"))
    return text.rstrip("\n") + "\n" + extra


def pf_tighten(text):
    """The promptfoo version of the C3 tightening: the text after Blocker: on its line mentions test data."""
    extra = ("    - type: regex\n      metric: C3_blocker_and_ask\n      value: 'Blocker:[^\\n]*test data'\n")
    return text.replace("    # C3-END\n", extra + "    # C3-END\n")


def pf_live_config(cli, model):
    """What the build skill's live mode writes: the same checks as the main config, with the helper as the provider."""
    main = pathlib.Path("promptfooconfig.yaml").read_text(encoding="utf-8").replace("\r\n", "\n")  # copied unchanged, as the skill says
    checks = main[main.index("defaultTest:"):main.index("tests:")]
    runs = "".join("  - description: run-%d\n" % n for n in range(1, 6))
    return ("description: Northwind end-of-week update live runs\nprompts:\n  - file://prompt-v0.md\nproviders:\n"
            "  - id: 'exec: node ./agent-provider.js'\n    label: my-agent\n    config:\n      cli: %s\n      model: %s\n"
            % (cli, model)) + checks + "tests:\n" + runs


PROVIDER = ROOT / "app" / "eval_coach" / "kit" / "skills" / "build-promptfoo-config" / "agent-provider.js"


def handle(line):
    log("line", text=line.rstrip("\r\n"), cwd=os.getcwd())
    if line.strip() == "/model" and "--picker" in sys.argv:
        # Test-only model list, shaped like a picker: fixed IDs, no account name or email.
        print("\nSelect a model\n  1. gpt-5.4-mini\n  2. claude-haiku-5.5\n  3. claude-sonnet-4.5\n"
              "  4. claude-sonnet-5.5 (default)\n  5. claude-opus-5\n", flush=True)
        return
    if "follow it in live mode" in line:
        work(2)
        cli = line.split("I use ", 1)[1].split(" with the model ", 1)[0]
        model = line.split(" with the model ", 1)[1].rstrip().rstrip(".")
        approve("agent-provider.js")
        pathlib.Path("agent-provider.js").write_bytes(PROVIDER.read_bytes())
        write("promptfooconfig.live.yaml", pf_live_config(cli, model))
    elif "run + log mode" in line and "/attempts/" in line:
        work(2)
        log_name, number, entry = part4_log_entry(line)
        append_log_entry(log_name, number, entry)
    elif "run + log mode" in line:
        work(2)
        write("iteration-log.md", baseline_log(line))
    elif "build-promptfoo-config" in line and "build mode" in line:
        work(14)
        write("promptfooconfig.yaml", pf_config_text())
    elif "build-promptfoo-config" in line and "Add fixtures/fixture-bad.txt" in line:
        work(2)
        approve("promptfooconfig.yaml edit")
        pathlib.Path("promptfooconfig.yaml").write_text(
            pf_add_fixtures(pathlib.Path("promptfooconfig.yaml").read_text(encoding="utf-8")), encoding="utf-8")
    elif "build-promptfoo-config" in line and "explain mode" in line:
        work(2)
        write("examples/c1-pass.txt", "Northwind short update")
    elif "Update promptfooconfig.yaml to match" in line:
        work(2)
        source = pathlib.Path("promptfooconfig.yaml").read_text(encoding="utf-8")
        approve("promptfooconfig.yaml edit")
        pathlib.Path("promptfooconfig.yaml").write_text(pf_tighten(source), encoding="utf-8")
    elif "Read input.txt" in line:
        work(1)
        text = pathlib.Path("input.txt").read_text(encoding="utf-8").strip().upper()
        write("output.txt", text + "\n")
        version = subprocess.run(["python", "--version"], capture_output=True, text=True, timeout=30)
        write("version.txt", version.stdout + version.stderr)
    elif "Read update.txt and requirements.md" in line:
        work(1)
        print(f"\nDECOY-TERMINAL-ONLY-{os.getpid()} Score 10 pass", flush=True)  # on screen only, never in a file
        if mode() != "silent":
            score, verdict, why = HOOK_VARIANTS[os.getpid() % len(HOOK_VARIANTS)]
            write("output.txt", f"Score: {score}/10. {verdict}. {why} <b>bold</b> & <script>x()</script>\n")
    elif "save only your answer to output.txt" in line.lower() and part4_blind_folder():
        # Part 4 round folder: the stand-in reads prompt.md and answers from a fixed set picked by the marker the harness
        # put in its own edit of the prompt, so a round's five answers are known and repeatable. Harness only.
        work(1)
        prompt = pathlib.Path("prompt.md").read_text(encoding="utf-8")
        write("output.txt", part4_answer(prompt))
    elif "Save only your answer to output.txt" in line and "part1" in os.getcwd().lower().replace("\\", "/"):
        # Part 1 run folder: the participant pasted the text, so the stand-in reads prompt.md. A prompt with label lines
        # (a word, then a colon, at the start of a line) gets the better sample answer and any other prompt gets the weaker
        # one. Harness only: it decides nothing for the app.
        work(1)
        prompt = pathlib.Path("prompt.md").read_text(encoding="utf-8")
        labelled = any(re.match(r"^[A-Za-z][A-Za-z ]{0,40}:", row) for row in prompt.splitlines())
        write("output.txt", PART1_BETTER if labelled else PART1_WEAKER)
    elif "output.txt" in line:
        # The five Part 3 answers are the five Northwind samples in order, so the baseline is the same on every run
        # and Part 4 can compare its rounds with a known starting score.
        seen = sum(1 for e in events() if e.get("event") == "sample")
        n = seen % 5 + 1
        log("sample", number=n)
        work(1)
        write("output.txt", (NW / f"sample-run-{n}.txt").read_text(encoding="utf-8"))
    elif "build mode" in line:
        work(14)
        write("check.py", (GOLD / "reference-check.py").read_text(encoding="utf-8"))
        write("examples/empty.txt", "")
    elif "Follow only the Answer key section" in line:
        work(2)
        write("fixtures/answer-key.md", (GOLD / "fixture-expected-results.md").read_text(encoding="utf-8"))
    elif "write only the two fixture files" in line:
        work(2)
        if mode() == "no-fixtures":  # nothing usable: no file is written and nothing is asked
            print("\nSTAND-IN: no fixtures could be made.", flush=True)
        else:
            for name in ("fixture-bad.txt", "fixture-polished-but-wrong.txt"):
                write(f"fixtures/{name}", (NW / name).read_text(encoding="utf-8"))
    elif "explain mode" in line:
        work(2)
        write("examples/c1-pass.txt", "Northwind short update")
    elif "I changed test-cases.md" in line:
        work(2)
        source = pathlib.Path("check.py").read_text(encoding="utf-8")
        original = "return True, 'found \"Blocker:\" and \"Need:\"'"
        tightened = ("if 'test data' not in text.split('Blocker:', 1)[1].splitlines()[0]:\n"
                     "        return False, 'blocker does not mention test data'\n    " + original)
        approve("check.py edit")
        pathlib.Path("check.py").write_text(source.replace(original, tightened), encoding="utf-8")
    print("\nDone.", flush=True)


def one_shot(line, flags):
    """The stand-in's `-p <line>` mode, like a real tool's one-shot mode: no prompt, no input, no files.
    A flag before `-p` picks the ending: --bg-fail exits 1 (for example not signed in) and --bg-hang never ends."""
    log("oneshot", text=line, cwd=os.getcwd(), flags=flags, stdin_closed=sys.stdin.read(1) == "")
    if "--bg-hang" in flags:
        time.sleep(600)
    if "--bg-fail" in flags:
        print("STAND-IN: not signed in.", flush=True)
        sys.exit(1)
    print("OK", flush=True)
    sys.exit(0)


if "-p" in sys.argv[1:]:
    cut = sys.argv.index("-p", 1)
    one_shot(sys.argv[cut + 1] if len(sys.argv) > cut + 1 else "", sys.argv[1:cut])

log("launch", argv=sys.argv[1:], cwd=os.getcwd())
print("STAND-IN CLI (no AI) ? for shortcuts\n> ", end="", flush=True)
for raw in sys.stdin:
    handle(raw)
    print("> ", end="", flush=True)
