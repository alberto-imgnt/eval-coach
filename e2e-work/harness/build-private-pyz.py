"""Builds a private copy of the app archive for the end-to-end run, so the run does not depend on
dist/ (other work may rebuild it). Usage: python build-private-pyz.py  ->  e2e-work/eval-coach-e2e.pyz
Run the harness with E2E_PYZ set to that path."""
import pathlib
import zipapp

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
TARGET = ROOT / "e2e-work" / "eval-coach-e2e.pyz"


def keep(path):
    return "__pycache__" not in path.parts and path.suffix != ".pyc"


zipapp.create_archive(str(ROOT / "app"), str(TARGET), main="eval_coach.__main__:main", filter=keep, compressed=True)
print(TARGET, TARGET.stat().st_size)
