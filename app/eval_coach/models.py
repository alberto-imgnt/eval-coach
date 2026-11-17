"""The Sonnet or Haiku choice: the launch option each supported AI needs, and the hidden read of its model list.

All tool-specific facts come from the `models` data of a recipe in cli-recipes.json (decision 1 of the
`model-preference` change). Nothing here is decided by what a tool prints, with one scoped exception: where a tool
needs an exact model ID, `Models.discover` reads the tool's own `/model` list in memory to get that ID, and the text
shown before it only to avoid typing into a question. The text never decides a pass or a fail, never reaches a file
and is dropped when the process stops. Any failure means the shipped fallback ID, never an error for the participant.
"""
from __future__ import annotations

import os
import re
import shutil
import threading
import time
from pathlib import Path

from . import state as store
from .terminal import EXIT, OUTPUT, TerminalManager

CHOICES = ("sonnet", "haiku")
DEFAULT = "sonnet"
CACHE_NAME = "model-cache.json"
SCRATCH_NAME = "cli-models"

_CONTROL = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[@-Z\\-_]|[\x00-\x08\x0b-\x1f\x7f]")
_QUOTED = re.compile(r'^"([^"]+)"')


def program_names(command):
    """Names that could be the program in a command string, shortest first.

    A quoted path is one name. Otherwise the leading words are tried one more at a time, because an unquoted path may
    hold spaces (the terminal accepts one that exists).
    """
    text = (command or "").strip()
    quoted = _QUOTED.match(text)
    if quoted:
        return [quoted.group(1)]
    words = text.split()
    return [" ".join(words[:k]) for k in range(1, len(words) + 1)]


def program_stem(name):
    return Path((name or "").replace("\\", "/")).stem.lower()


def own_model(argv_or_command):
    """The model a participant's own command already names with --model, or None."""
    tokens = argv_or_command.split() if isinstance(argv_or_command, str) else list(argv_or_command)
    for i, token in enumerate(tokens):
        if token == "--model":
            return tokens[i + 1] if i + 1 < len(tokens) else ""
        if token.startswith("--model="):
            return token[len("--model="):]
    return None


def strip_control(text):
    return _CONTROL.sub("", text)


def version_key(model_id):
    return tuple(int(n) for n in re.findall(r"\d+", model_id))


def newest_id(text, keyword, pattern):
    """The highest-version token in `text` that contains the keyword and a digit, or None."""
    best = None
    for token in re.findall(pattern, strip_control(text)):
        token = token.strip(".-_")
        if keyword.lower() in token.lower() and any(c.isdigit() for c in token):
            if best is None or version_key(token) > version_key(best):
                best = token
    return best


class Models:
    """Looks up a tool's model data, builds the launch option, and finds exact IDs by keyword."""

    def __init__(self, home, recipes, default_label, terminal_factory=None, clock=None, sleep=None):
        self.home = Path(home)
        self._recipes = recipes  # a function returning the recipe list, so a reloaded override is seen
        self.default_label = default_label
        self._factory = terminal_factory or TerminalManager
        self._clock = clock or time.monotonic
        self._lock = threading.RLock()  # one discovery at a time
        self._tried = set()  # (command, program marker, keyword) already tried in this run

    # --- data --------------------------------------------------------------

    def _match(self, command):
        """(program name, `models` data) of the first recipe whose program is in this command, else (None, None)."""
        for name in program_names(command):
            stem = program_stem(name)
            if not stem:
                continue
            for recipe in self._recipes():
                if program_stem(recipe.get("cli_command", "")) == stem and isinstance(recipe.get("models"), dict):
                    return name, recipe["models"]
        return None, None

    def data_for(self, command):
        """The `models` object of the first recipe for this command's program, or None."""
        return self._match(command)[1]

    def _key(self, command):
        return program_stem(self._match(command)[0])

    def _entry(self, data, preference):
        entry = data.get(preference) if data else None
        return entry if isinstance(entry, dict) and isinstance(entry.get("launch"), list) else None

    def options(self, command):
        """[{id, label}] for the choices this command can offer. Empty when there is no model data."""
        data = self.data_for(command)
        if data is None or own_model(command) is not None:
            return []
        return [{"id": c, "label": str(data[c].get("label") or c.title())} for c in CHOICES
                if self._entry(data, c) is not None]

    # --- resolving ---------------------------------------------------------

    def resolve(self, command, preference, env=None, can_discover=None):
        """(extra argv, label recorded). No model data, or a model named in the command itself, adds nothing."""
        named = own_model(command)
        if named is not None:
            return [], named or self.default_label
        data = self.data_for(command)
        entry = self._entry(data, preference)
        if entry is None:
            return [], self.default_label
        keyword = entry.get("keyword")
        if not keyword:
            launch = [str(a) for a in entry["launch"]]
            return launch, str(preference)
        model_id = self._id_for(command, data, preference, entry, env, can_discover)
        return [str(a).replace("{id}", model_id) for a in entry["launch"]], model_id

    def _id_for(self, command, data, preference, entry, env, can_discover):
        marker = self.program_marker(command, env)
        ids = self._cached_ids(command, marker)
        if ids.get(preference):
            return ids[preference]
        if marker and isinstance(data.get("discover"), dict) and (can_discover is None or can_discover()):
            found = self.discover(command, data, marker, env)
            if found.get(preference):
                return found[preference]
        return str(entry.get("fallback_id", ""))

    def ensure(self, command, env=None, can_discover=None):
        """Run discovery now if a tool needs it and has no saved result. Never raises."""
        try:
            data = self.data_for(command)
            if data is None or own_model(command) is not None:
                return
            for preference in CHOICES:
                entry = self._entry(data, preference)
                if entry is not None and entry.get("keyword"):
                    self._id_for(command, data, preference, entry, env, can_discover)
                    return
        except Exception:  # noqa: BLE001 - discovery must never reach the participant
            return

    def prefetch(self, command, env=None, can_discover=None):
        """`ensure` on a background thread, so the first AI window does not wait for it."""
        thread = threading.Thread(target=self.ensure, args=(command, env, can_discover), daemon=True)
        thread.start()
        return thread

    # --- saved results -----------------------------------------------------

    @property
    def cache_path(self):
        return self.home / CACHE_NAME

    def program_marker(self, command, env=None):
        """Path, size and modified time of the program file, from the file system only. "" when it is not found."""
        name = self._match(command)[0] or next(iter(program_names(command)), "")
        if not name:
            return ""
        found = shutil.which(name, path=env.get("PATH") if env else None)
        if not found and os.path.isfile(name):
            found = os.path.abspath(name)
        if not found:
            return ""
        try:
            info = os.stat(found)
        except OSError:
            return ""
        return f"{os.path.normcase(found)}|{info.st_size}|{int(info.st_mtime)}"

    def _read_cache(self):
        try:
            data = store.read_json(self.cache_path)
        except (FileNotFoundError, store.CorruptStateError, OSError):
            return {}
        return data if isinstance(data, dict) else {}

    def _cached_ids(self, command, marker):
        entry = self._read_cache().get(self._key(command))
        if not marker or not isinstance(entry, dict) or entry.get("program") != marker:
            return {}
        ids = entry.get("ids")
        return {k: v for k, v in ids.items() if k in CHOICES and isinstance(v, str)} if isinstance(ids, dict) else {}

    def _save_ids(self, command, marker, ids):
        cache = self._read_cache()
        stem = self._key(command)
        old = cache.get(stem)
        merged = dict(old.get("ids", {})) if isinstance(old, dict) and old.get("program") == marker else {}
        merged.update(ids)
        cache[stem] = {"program": marker, "ids": merged}
        try:
            store.write_json_atomic(self.cache_path, cache)
        except OSError:
            pass  # a result that cannot be saved is found again next time

    # --- discovery ---------------------------------------------------------

    def discover(self, command, data, marker, env=None):
        """Read the tool's model list once and save the IDs found. Returns {preference: id}; {} on any failure."""
        with self._lock:
            keywords = {c: data[c]["keyword"] for c in CHOICES
                        if self._entry(data, c) is not None and data[c].get("keyword")}
            wanted = {c: k for c, k in keywords.items() if (self._key(command), marker, k) not in self._tried}
            if not wanted:
                return self._cached_ids(command, marker)
            for keyword in wanted.values():
                self._tried.add((self._key(command), marker, keyword))
            try:
                text = self._read_list(command, data["discover"], env)
            except Exception:  # noqa: BLE001 - any failure falls back to the shipped ID
                text = None
            if text is None:
                return {}
            pattern = str(data["discover"].get("id_pattern") or r"[A-Za-z0-9][A-Za-z0-9._-]*")
            found = {c: newest_id(text, k, pattern) for c, k in wanted.items()}
            found = {c: i for c, i in found.items() if i}
            if found:
                self._save_ids(command, marker, found)
            return self._cached_ids(command, marker) or found

    def _read_list(self, command, spec, env):
        """The text the tool showed for its list command, or None. Held in memory only."""
        folder = self.home / SCRATCH_NAME
        folder.mkdir(parents=True, exist_ok=True)
        ready_quiet = float(spec.get("ready_quiet_seconds", 3))
        read_quiet = float(spec.get("read_quiet_seconds", 2))
        deadline = self._clock() + float(spec.get("max_seconds", 45))
        stop_words = [str(w).lower() for w in spec.get("stop_words", [])]
        terminal = self._factory()
        chunks = []
        try:
            terminal.start(command, str(folder), "model list", env=env, owner="models")
            cursor = [0]
            if not self._read_quiet(terminal, cursor, chunks, ready_quiet, deadline, need_output=True):
                return None
            before = strip_control("".join(chunks)).lower()
            if any(word in before for word in stop_words):
                return None  # a question is on screen: type nothing
            mark = len(chunks)
            terminal.type_line(str(spec.get("command", "/model")))
            if not self._read_quiet(terminal, cursor, chunks, read_quiet, deadline, need_output=True):
                return None
            return "".join(chunks[mark:])
        finally:
            try:
                terminal.stop()
            finally:
                chunks.clear()

    def _read_quiet(self, terminal, cursor, chunks, quiet, deadline, need_output):
        """Collect output until it has been quiet for `quiet` seconds. False on exit, time limit or no output."""
        seen = False
        while True:
            remaining = deadline - self._clock()
            if remaining <= 0:
                return False
            events, new_cursor, _ = terminal.wait_events(cursor[0], terminal.state_generation,
                                                         min(quiet, remaining) if (seen or not need_output) else remaining)
            fresh = [e for e in events if e[0] > cursor[0]]
            cursor[0] = new_cursor
            for _seq, kind, payload in fresh:
                if kind == EXIT:
                    return False
                if kind == OUTPUT:
                    chunks.append(payload.decode("utf-8", "replace") if isinstance(payload, (bytes, bytearray)) else payload)
                    seen = True
            if not fresh and (seen or not need_output):
                return True
