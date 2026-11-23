"""Read bundled files, from disk or from inside a zipapp."""
from __future__ import annotations

import contextlib
import json
import posixpath
import re
import zipfile
from pathlib import Path, PurePosixPath

from . import hostos

_loader = globals().get("__loader__")
_ARCHIVE = getattr(_loader, "archive", None)
_PREFIX = getattr(_loader, "prefix", "").replace("\\", "/") if _ARCHIVE else ""
_ROOT = Path(__file__).resolve().parent if not _ARCHIVE else None


class ResourceNotFound(Exception):
    pass


def _clean(relpath):
    """Return a safe forward-slash path, or raise ResourceNotFound."""
    if not isinstance(relpath, str) or not relpath:
        raise ResourceNotFound(repr(relpath))
    if "\\" in relpath or ":" in relpath or "\0" in relpath or relpath.startswith("/"):
        raise ResourceNotFound(relpath)
    parts = relpath.split("/")
    for part in parts:
        if part in ("", ".", "..") or part[-1] in ". ":
            raise ResourceNotFound(relpath)
    return posixpath.join(*parts)


def read_bytes(relpath):
    rel = _clean(relpath)
    if _ARCHIVE:
        try:
            with zipfile.ZipFile(_ARCHIVE) as zf:
                return zf.read(_PREFIX + rel)
        except KeyError:
            raise ResourceNotFound(rel) from None
    full = _ROOT.joinpath(*PurePosixPath(rel).parts)
    try:
        resolved = full.resolve()
        resolved.relative_to(_ROOT)
        if not resolved.is_file():
            raise ResourceNotFound(rel)
        return resolved.read_bytes()
    except (ValueError, OSError):
        raise ResourceNotFound(rel) from None


def read_text(relpath):
    """Bundled text. A content file (content/*.json) has its platform tokens, such as {paste_key}, resolved first."""
    text = read_bytes(relpath).decode("utf-8")
    if relpath.startswith("content/") and relpath.endswith(".json") and relpath not in _UNRESOLVED:
        return resolve_platform_text(text)
    return text


_UNRESOLVED = ("content/platform.json", "content/cli-recipes.json")
_TOKEN = re.compile(r"\{([a-z][a-z_]*)\}")
_override = [None]


@contextlib.contextmanager
def platform_words(key):
    """Test helper: read the content as it reads on "windows" or "mac" while the block runs."""
    previous = _override[0]
    _override[0] = key
    try:
        yield
    finally:
        _override[0] = previous


def current_platform():
    return _override[0] or hostos.content_platform()


def platform_tokens(key=None):
    """{token: text} for one platform, from content/platform.json."""
    key = key or current_platform()
    data = json.loads(read_bytes("content/platform.json").decode("utf-8"))
    return {name: values[key] for name, values in data["tokens"].items()}


def resolve_platform_text(text, key=None):
    """Replace each known {token} in JSON text with this platform's words, escaped to sit inside a JSON string.

    A {placeholder} that is not a platform token (such as {path} or {label}) is left for the code that fills it.
    """
    tokens = platform_tokens(key)

    def replace(match):
        value = tokens.get(match.group(1))
        return match.group(0) if value is None else json.dumps(value, ensure_ascii=False)[1:-1]

    return _TOKEN.sub(replace, text)


def canonical(relpath):
    """The real, forward-slash path of a bundled file, with any alias (such as a Windows 8.3 short
    name or a different letter case) resolved to the name the file has on disk."""
    rel = _clean(relpath)
    if _ARCHIVE:
        return rel
    try:
        resolved = _ROOT.joinpath(*PurePosixPath(rel).parts).resolve()
        return resolved.relative_to(_ROOT).as_posix()
    except (ValueError, OSError):
        raise ResourceNotFound(rel) from None


def list_files(prefix):
    """Every bundled file under prefix, as forward-slash paths relative to the package."""
    prefix = _clean(prefix).rstrip("/") + "/"
    if _ARCHIVE:
        with zipfile.ZipFile(_ARCHIVE) as zf:
            full = _PREFIX + prefix
            return sorted(n[len(_PREFIX):] for n in zf.namelist()
                          if n.startswith(full) and not n.endswith("/"))
    base = _ROOT.joinpath(*PurePosixPath(prefix).parts)
    if not base.is_dir():
        return []
    return sorted(str(PurePosixPath(p.relative_to(_ROOT).as_posix()))
                  for p in base.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def read_web(relpath):
    """A file from web/. Raises ResourceNotFound for anything unsafe or absent."""
    return read_bytes("web/" + _clean(relpath))
