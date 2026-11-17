"""No-AI-calls scan of check.py. A warning mechanism, not a sandbox."""
from __future__ import annotations

import ast
import re
from pathlib import Path

from .parsers import parse_live_config, parse_promptfoo_config
BLOCKED = (
    "socket", "http", "urllib", "requests", "httpx", "aiohttp", "ftplib", "smtplib",
    "openai", "anthropic", "google.generativeai", "langchain", "litellm", "boto3",
    "subprocess",
)


def _blocked_name(module):
    for name in BLOCKED:
        if module == name or module.startswith(name + "."):
            return name
    return None


def _message(name):
    return (f'check.py imports "{name}", which can reach the network, an AI model, or '
            "other programs. A checker uses rules only. Ask your AI to remove it, "
            "and check again.")


def scan_source(source):
    """Return a list of {"message": str}; an empty list means the scan passed."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return [{"message": "check.py is not valid Python, so it could not be scanned. "
                            "Ask your AI to fix the error, without changing any threshold."}]
    found = []

    def note(module):
        name = _blocked_name(module)
        if name and name not in found:
            found.append(name)

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                note(alias.name)
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            note(node.module)
            for alias in node.names:
                note(f"{node.module}.{alias.name}")
        elif isinstance(node, ast.Call) and node.args:
            func = node.func
            called = func.id if isinstance(func, ast.Name) else (
                func.attr if isinstance(func, ast.Attribute) else "")
            first = node.args[0]
            if called in ("__import__", "import_module") and isinstance(first, ast.Constant) \
                    and isinstance(first.value, str):
                note(first.value)
    return [{"message": _message(name)} for name in found]


def scan_file(path):
    """Scan check.py on disk. Bytes are passed so the file's own encoding is honored."""
    return scan_source(Path(path).read_bytes())


# --- promptfooconfig.yaml ----------------------------------------------------------------

# Assertions that need a model, an API key or the network. The checks must be rules only.
MODEL_GRADED = (
    "llm-rubric", "similar", "factuality", "select-best", "answer-relevance", "g-eval", "moderation",
    "classifier", "pi", "search-rubric", "conversation-relevance", "webhook",
)
MODEL_GRADED_PREFIXES = ("model-graded-", "context-", "llm-")


def _graded_type(assert_type):
    name = assert_type.strip().lower()
    if name.startswith("not-"):
        name = name[4:]
    if name in MODEL_GRADED or name.startswith(MODEL_GRADED_PREFIXES):
        return assert_type.strip()
    return None


def scan_config_source(source):
    """Scan promptfooconfig.yaml text. Returns a list of {"message": str}; empty means the scan passed.

    It reads the file without a YAML library, so it is a warning mechanism, not a sandbox.
    """
    config = parse_promptfoo_config(source if isinstance(source, str) else source.decode("utf-8-sig", "replace"))
    found = []
    seen = set()
    for kind in config["assert_types"]:
        graded = _graded_type(kind)
        if graded and graded not in seen:
            seen.add(graded)
            found.append({"message": (
                f'promptfooconfig.yaml uses the "{graded}" check, which needs an AI model or the network. '
                "The checks must be rules only. Ask your AI to replace it with a rule, or to mark that "
                "criterion NOT CHECKED, without changing any other threshold, then check again.")})
    for provider in config["providers"]:
        if provider.strip().lower() != "echo":
            found.append({"message": (
                f'promptfooconfig.yaml uses the provider "{provider}". Only the "echo" provider is allowed, '
                "because it hands each saved file to the checks unchanged. Ask your AI to change the "
                "provider back to echo, and check again.")})
    if config["provider_keys"] and not found:
        found.append({"message": (
            "promptfooconfig.yaml names a provider inside a check, which means a model would grade the "
            "output. The checks must be rules only. Ask your AI to remove it, and check again.")})
    if not config["providers"]:
        found.append({"message": (
            "promptfooconfig.yaml does not name the echo provider. Ask your AI to add "
            "'providers: - echo', and check again.")})
    return found


def scan_config_file(path):
    return scan_config_source(Path(path).read_bytes().decode("utf-8-sig", "replace"))


# --- promptfooconfig.live.yaml (optional live mode) ----------------------------------------------------

# The one provider live mode may use: the bundled helper, started the way the build skill's Mode 4 writes it.
LIVE_PROVIDER = re.compile(r"^exec:\s*node\s+\.[/\\]agent-provider\.js$")
LIVE_FILE = "promptfooconfig.live.yaml"


def scan_live_config_source(source, allowed_clis=()):
    """Scan promptfooconfig.live.yaml text. Returns a list of {"message": str}; empty means the scan passed.

    The same rule as the main config (rules only, no model-graded check) with one difference: the provider must
    be the bundled agent-provider.js and nothing else. `allowed_clis` is the list of CLI names live mode offers.
    Read without a YAML library, so it is a warning mechanism, not a sandbox.
    """
    config = parse_live_config(source if isinstance(source, str) else source.decode("utf-8-sig", "replace"))
    found, seen = [], set()
    for kind in config["assert_types"]:
        graded = _graded_type(kind)
        if graded and graded not in seen:
            seen.add(graded)
            found.append({"message": (
                f'{LIVE_FILE} uses the "{graded}" check, which needs an AI model or the network. '
                "The checks must be rules only, and the AI only writes the outputs. Ask your AI to copy the "
                "checks from promptfooconfig.yaml unchanged, then check again.")})
    for provider in config["providers"]:
        if not LIVE_PROVIDER.match(provider.strip()):
            found.append({"message": (
                f'{LIVE_FILE} uses the provider "{provider}". Live mode may use only the helper, written as '
                "'exec: node ./agent-provider.js'. Ask your AI to use exactly that provider, and check again.")})
    if not config["providers"]:
        found.append({"message": (
            f"{LIVE_FILE} does not name a provider. Ask your AI to add the helper, "
            "'exec: node ./agent-provider.js', and check again.")})
    if config["secret_keys"]:
        found.append({"message": (
            f"{LIVE_FILE} sets an API key or an API address ({', '.join(config['secret_keys'])}). "
            "Live mode uses your AI's own sign-in and needs no API key. Ask your AI to remove it, "
            "and check again.")})
    if config["provider_keys"] and not any("names a provider inside a check" in f["message"] for f in found):
        found.append({"message": (
            f"{LIVE_FILE} names a provider inside a check, which means a model would grade the output. "
            "The checks must be rules only. Ask your AI to remove it, and check again.")})
    if allowed_clis:
        for cli in config["clis"]:
            if cli not in allowed_clis:
                found.append({"message": (
                    f'{LIVE_FILE} names the AI tool "{cli}", and live mode supports only {", ".join(allowed_clis)}. '
                    "Choose one of those in the list, ask your AI to use it on the cli: line, and check again.")})
    return found


def scan_live_config_file(path, allowed_clis=()):
    return scan_live_config_source(Path(path).read_bytes().decode("utf-8-sig", "replace"), allowed_clis)
