"""Command-line entry point: python -m eval_coach [--port N] [--home DIR] [--no-browser]."""
from __future__ import annotations

import argparse
import sys
import webbrowser

from .engine import Engine
from .lessons import LessonError, load_bundled
from .project import default_home
from .server import AppServer
from .terminal import TerminalManager


def main(argv=None):
    parser = argparse.ArgumentParser(prog="eval-coach", description="Learn to run evals with your own AI CLI.")
    parser.add_argument("--port", type=int, default=0, help="Port to use (default: a random free port).")
    parser.add_argument("--home", default=None, help="Storage folder (default: %%USERPROFILE%%\\.eval-coach).")
    parser.add_argument("--no-browser", action="store_true", help="Print the URL but do not open a browser.")
    parser.add_argument("--python", default=None, help="Path of the Python that launched the app (setup.cmd sets this).")
    args = parser.parse_args(argv)

    try:
        course = load_bundled()
        engine = Engine(args.home or default_home(), TerminalManager(), lessons=course)
    except LessonError as exc:
        print(f"eval-coach could not load its course content: {exc}", file=sys.stderr)
        return 1

    engine.python_path = args.python or sys.executable
    engine.preflight.python_path = engine.python_path
    try:
        server = AppServer(engine, port=args.port)
    except OSError as exc:
        print(f"eval-coach could not listen on port {args.port}: {exc}", file=sys.stderr)
        return 1

    print(server.url, flush=True)
    if not args.no_browser:
        webbrowser.open(server.url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        engine.shutdown()
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
