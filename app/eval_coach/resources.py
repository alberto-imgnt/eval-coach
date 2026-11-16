"""Read bundled files, from disk or from inside a zipapp."""
from __future__ import annotations

import posixpath
import zipfile
from pathlib import Path, PurePosixPath

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
    return read_bytes(relpath).decode("utf-8")


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
