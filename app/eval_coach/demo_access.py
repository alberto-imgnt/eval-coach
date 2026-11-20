"""Hidden demo access: a salted, slow hash of a password kept in the app. A deterrent, not a security feature."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

from . import resources

HASH_FILE = "demo_hash.json"
ITERATIONS = 200_000
SALT_BYTES = 16


def make_record(password, iterations=ITERATIONS, salt=None):
    """The record to store for a password: a salt, the iteration count and the hash. Never the password."""
    salt = salt if salt is not None else secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {"salt": salt.hex(), "hash": digest.hex(), "iterations": iterations}


def valid_record(record):
    """True when `record` holds a usable salt, hash and iteration count."""
    if not isinstance(record, dict):
        return False
    iterations = record.get("iterations")
    if not isinstance(iterations, int) or isinstance(iterations, bool) or iterations < 1:
        return False
    try:
        return bool(bytes.fromhex(record["salt"])) and bool(bytes.fromhex(record["hash"]))
    except (KeyError, TypeError, ValueError):
        return False


def verify(password, record):
    """Check a password against a record in constant time. A wrong, empty or unusable one is False."""
    if not isinstance(password, str) or not password or not valid_record(record):
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(record["salt"]),
                                 record["iterations"])
    return hmac.compare_digest(digest, bytes.fromhex(record["hash"]))


def load_record(path=None):
    """The shipped record, or the one at `path`. None when there is none or it is unusable."""
    try:
        if path is not None:
            with open(path, "rb") as handle:
                data = json.loads(handle.read().decode("utf-8-sig"))
        else:
            data = json.loads(resources.read_text(HASH_FILE))
    except (OSError, ValueError, resources.ResourceNotFound):
        return None
    return data if valid_record(data) else None
