"""HTTP server: security checks, routes, static files, and the SSE stream."""
from __future__ import annotations

import base64
import hmac
import json
import mimetypes
import secrets
import socketserver
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote

from . import resources
from .engine import EngineError

HOST = "127.0.0.1"
MAX_BODY = 2 * 1024 * 1024
HEARTBEAT_SECONDS = 15.0
CSP = ("default-src 'self'; style-src 'self' 'unsafe-inline'; "
       "connect-src 'self'; frame-ancestors 'none'")

_MIME = {
    ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
    ".ico": "image/x-icon", ".map": "application/json", ".txt": "text/plain; charset=utf-8",
    ".woff2": "font/woff2",
}

_ROUTES = {
    "/api/setup": lambda e, b: e.setup(b),
    "/api/setup/import-check": lambda e, b: e.import_check(b),
    "/api/step/start": lambda e, b: e.step_start(b.get("step")),
    "/api/step/send": lambda e, b: e.step_send(b.get("step")),
    "/api/step/stop": lambda e, b: e.step_stop(b.get("step")),
    "/api/step/check": lambda e, b: e.step_check(b.get("step")),
    "/api/step/question": lambda e, b: e.step_question_answer(b.get("step"), b.get("option")),
    "/api/step/submit": lambda e, b: e.step_submit(b.get("step"), b.get("data", {})),
    "/api/step/run-checker": lambda e, b: e.step_run_checker(b.get("step"), b.get("which")),
    "/api/step/skip": lambda e, b: e.step_skip(b.get("step")),
    "/api/step/use-example-fixtures": lambda e, b: e.step_use_example_fixtures(b.get("step"), b.get("replace")),
    "/api/preflight/track": lambda e, b: e.preflight_track(b.get("track")),
    "/api/preflight/check": lambda e, b: e.preflight_check(),
    "/api/preflight/skip": lambda e, b: e.preflight_skip(),
    "/api/preflight/install": lambda e, b: e.preflight_install(b.get("item"), b.get("consent")),
    "/api/preflight/cli": lambda e, b: e.preflight_cli(b.get("cli_command")),
    "/api/preflight/cli/start": lambda e, b: e.preflight_cli_start(),
    "/api/preflight/cli/recipe": lambda e, b: e.preflight_recipe(b.get("recipe"), b.get("consent")),
    "/api/preflight/signin": lambda e, b: e.preflight_signin_confirm(),
    "/api/preflight/test/start": lambda e, b: e.preflight_test_start(),
    "/api/preflight/test/send": lambda e, b: e.preflight_test_send(),
    "/api/preflight/test/check": lambda e, b: e.preflight_test_check(),
    "/api/preflight/stop": lambda e, b: e.preflight_stop(),
    "/api/terminal/input": lambda e, b: e.terminal_input(b.get("data")),
    "/api/terminal/resize": lambda e, b: e.terminal_resize(b.get("cols"), b.get("rows")),
    "/api/terminal/release": lambda e, b: e.terminal_release(),
    "/api/lesson/answer": lambda e, b: e.lesson_answer(b.get("lesson"), b.get("activity"), b.get("answer")),
    "/api/lesson/complete": lambda e, b: e.lesson_complete(b.get("lesson")),
    "/api/lesson/skip": lambda e, b: e.lesson_skip(b.get("lesson")),
    "/api/lesson/cli/start": lambda e, b: e.lesson_cli_start(b.get("lesson"), b.get("activity")),
    "/api/lesson/cli/send": lambda e, b: e.lesson_cli_send(b.get("lesson"), b.get("activity")),
    "/api/lesson/cli/stop": lambda e, b: e.lesson_cli_stop(b.get("lesson"), b.get("activity")),
    "/api/lesson/rule-run": lambda e, b: e.lesson_rule_run(b.get("lesson"), b.get("activity"), b.get("rule"), b.get("text")),
    "/api/placement/answer": lambda e, b: e.placement_answer(b.get("id"), b.get("option"), b.get("accept_skip")),
    "/api/review/answer": lambda e, b: e.review_answer(b.get("item"), b.get("option")),
    "/api/review/postpone": lambda e, b: e.review_postpone(),
    "/api/reset/progress": lambda e, b: e.reset_progress(b.get("confirm")),
    "/api/reset/configuration": lambda e, b: e.reset_configuration(b.get("confirm")),
}

_GET_ROUTES = {
    "/api/lesson": lambda e, p: e.lesson_view(p.get("id", [None])[0]),
    "/api/kit": lambda e, p: e.kit_file(p.get("ref", [None])[0]),
    "/api/review": lambda e, p: e.review_get(),
}


def _content_type(path):
    for ext, value in _MIME.items():
        if path.lower().endswith(ext):
            return value
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _constant_time_equal(given, expected):
    return hmac.compare_digest(given.encode("utf-8", "surrogatepass"),
                               expected.encode("utf-8", "surrogatepass"))


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "eval-coach"
    sys_version = ""
    timeout = 120

    def log_message(self, format, *args):  # noqa: A002 - tokens must never reach a log
        pass

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    # --- responses ---------------------------------------------------------

    def _send_json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _reject(self, status, code, message):
        """Refuse and close, because an unread body would desync a reused connection."""
        self.close_connection = True
        self._send_json(status, {"ok": False, "error": {"code": code, "message": message}})
        self._drain_body()

    def _drain_body(self):
        """Consume an unread body: Windows resets a socket closed with data unread,
        and the reset can destroy the response that was just sent."""
        raw = self.headers.get("Content-Length") or ""
        if self.command != "POST" or self._body_consumed or not (raw.isascii() and raw.isdigit()):
            return
        remaining = min(int(raw), MAX_BODY)
        try:
            self.connection.settimeout(0.5)
            while remaining > 0:
                chunk = self.rfile.read1(min(remaining, 65536))
                if not chunk:
                    return
                remaining -= len(chunk)
        except OSError:
            pass  # the client never sent it; the connection is closing anyway

    # --- security ----------------------------------------------------------

    def _host_origin_ok(self):
        hosts = self.headers.get_all("Host") or []
        if len(hosts) != 1 or hosts[0] != self.server.host_header:
            self._reject(403, "bad_host", "This address is not allowed.")
            return False
        for origin in self.headers.get_all("Origin") or []:
            if origin != self.server.origin:
                self._reject(403, "bad_origin", "This origin is not allowed.")
                return False
        return True

    def _token_ok(self, supplied):
        if not supplied or not _constant_time_equal(supplied, self.server.token):
            self._reject(401, "bad_token", "The access token is missing or wrong.")
            return False
        return True

    def _split_target(self):
        path, _, query = self.path.partition("?")
        return path, query

    # --- GET ---------------------------------------------------------------

    def do_GET(self):
        if not self._host_origin_ok():
            return
        path, query = self._split_target()
        params = parse_qs(query, keep_blank_values=True)
        if path == "/api/terminal/stream":
            if self._token_ok(params.get("t", [""])[0]):
                self._stream(params)
            return
        if path == "/api/state":
            if self._token_ok(self.headers.get("X-Eval-Token", "")):
                self._get_state(params)
            return
        if path in _GET_ROUTES:
            if self._token_ok(self.headers.get("X-Eval-Token", "")):
                self._get_route(path, params)
            return
        if path.startswith("/api/"):
            if self._token_ok(self.headers.get("X-Eval-Token", "")):
                self._reject(404, "not_found", "There is no such route.")
            return
        self._static(path)

    def _get_route(self, path, params):
        engine = self.server.engine
        try:
            self._send_json(200, dict({"ok": True}, **_GET_ROUTES[path](engine, params)))
        except EngineError as exc:
            self._send_json(400, {"ok": False, "error": {"code": exc.code, "message": exc.message},
                                  "state": self._safe_state(None)})
        except Exception as exc:  # the contract promises a JSON answer
            self._send_json(400, {"ok": False,
                                  "error": {"code": "internal",
                                            "message": f"The app hit an unexpected error: {type(exc).__name__}: {exc}"},
                                  "state": self._safe_state(None)})

    def _get_state(self, params):
        step = params.get("step", [None])[0] or None
        part = params.get("part", [None])[0] or None
        try:
            self._send_json(200, self.server.engine.get_state(step, part))
        except EngineError as exc:
            self._send_json(400, {"ok": False, "error": {"code": exc.code, "message": exc.message},
                                  "state": self._safe_state(None)})

    def _static(self, path):
        rel = unquote(path)[1:] or "index.html"
        try:
            data = resources.read_web(rel) if rel != "reference-data.json" else self._reference_data()
        except resources.ResourceNotFound:
            self._reject(404, "not_found", "There is no such file.")
            return
        self.send_response(200)
        self.send_header("Content-Type", _content_type(rel))
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    @staticmethod
    def _reference_data():
        """Glossary and reference wording for reference.html and the glossary panel.

        Static like any page: it holds no answers and no participant data.
        """
        glossary = json.loads(resources.read_text("content/glossary.json"))
        text = json.loads(resources.read_text("content/lesson-ui.json"))["reference"]
        return json.dumps({"glossary": glossary.get("terms", []), "reference": text}).encode("utf-8")

    # --- SSE ---------------------------------------------------------------

    def _write_event(self, name, payload):
        text = f"event: {name}\ndata: {json.dumps(payload)}\n\n"
        self.wfile.write(text.encode("utf-8"))
        self.wfile.flush()

    def _stream(self, params):
        terminal = self.server.engine.terminal
        try:
            cursor = max(0, int(params.get("after", ["0"])[0] or 0))
        except ValueError:
            cursor = 0
        gen = terminal.state_generation
        self.close_connection = True
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Connection", "close")
        self.end_headers()
        heartbeat = self.server.heartbeat
        last_beat = time.monotonic()
        try:
            while not self.server.stopping.is_set():
                events, cursor, new_gen = terminal.wait_events(cursor, gen, min(1.0, heartbeat))
                for seq, kind, payload in events:
                    if kind == "output":
                        self._write_event("output", {"seq": seq, "data": base64.b64encode(payload).decode("ascii")})
                    else:
                        self._write_event("exit", {"code": payload})
                if new_gen != gen:
                    gen = new_gen
                    self._write_event("state", {})
                if time.monotonic() - last_beat >= heartbeat:
                    last_beat = time.monotonic()
                    self.wfile.write(b": heartbeat\n\n")
                    self.wfile.flush()
        except OSError:
            pass  # the page went away

    # --- POST --------------------------------------------------------------

    def do_POST(self):
        self._body_consumed = False
        if not self._host_origin_ok():
            return
        path, _ = self._split_target()
        if not self._token_ok(self.headers.get("X-Eval-Token", "")):
            return
        body = self._read_json()
        if body is None:
            return
        if path == "/api/quit":
            self._quit()
            return
        route = _ROUTES.get(path)
        if route is None:
            self._reject(404, "not_found", "There is no such route.")
            return
        step = body.get("step") if isinstance(body.get("step"), str) else None
        part = body.get("part") if isinstance(body.get("part"), str) else None
        engine = self.server.engine
        try:
            result = route(engine, body)
            payload = {"ok": True, "state": self._safe_state(step, part)}
            if result is not None:
                payload["result"] = result
            self._send_json(200, payload)
        except EngineError as exc:
            self._send_json(400, {"ok": False, "error": {"code": exc.code, "message": exc.message},
                                  "state": self._safe_state(step, part)})
        except Exception as exc:  # the contract promises a JSON answer
            self._send_json(400, {"ok": False,
                                  "error": {"code": "internal",
                                            "message": f"The app hit an unexpected error: {type(exc).__name__}: {exc}"},
                                  "state": self._safe_state(step, part)})

    def _safe_state(self, step, part=None):
        """The state sent back after a request: the step's Part, else the Part the page named, else Part 3."""
        engine = self.server.engine
        for attempt in ((step, part), (None, part), (None, None)):
            try:
                return engine.get_state(*attempt)
            except EngineError:
                continue
        return engine.get_state(None)

    def _read_json(self):
        ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if ctype != "application/json":
            self._reject(415, "bad_content_type", "Send JSON with Content-Type: application/json.")
            return None
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or not (raw_length.isascii() and raw_length.isdigit()):
            self._reject(411, "length_required", "A Content-Length header is required.")
            return None
        length = int(raw_length)
        if length > MAX_BODY:
            self._reject(413, "too_large", "The request body is over the 2 MB limit.")
            return None
        raw = self.rfile.read(length)
        self._body_consumed = True
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            self._reject(400, "bad_json", "The request body is not valid JSON.")
            return None
        if not isinstance(value, dict):
            self._reject(400, "bad_json", "The request body must be a JSON object.")
            return None
        return value

    def _quit(self):
        engine = self.server.engine
        engine.shutdown()
        self._send_json(200, {"ok": True, "state": self._safe_state(None)})
        self.close_connection = True
        threading.Thread(target=self.server.stop, daemon=True).start()


class AppServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False  # on Windows this would let another process share the port
    request_queue_size = 64

    def __init__(self, engine, port=0, token=None, heartbeat=HEARTBEAT_SECONDS):
        self.engine = engine
        self.token = token or secrets.token_urlsafe(32)
        self.heartbeat = heartbeat
        self.stopping = threading.Event()
        super().__init__((HOST, port), Handler)
        self.port = self.server_address[1]
        self.host_header = f"{HOST}:{self.port}"
        self.origin = f"http://{HOST}:{self.port}"

    def handle_error(self, request, client_address):
        # A browser dropping a connection is routine; anything else stays visible.
        if isinstance(sys.exc_info()[1], OSError):
            return
        super().handle_error(request, client_address)

    def server_bind(self):
        # HTTPServer.server_bind does a name lookup that can stall for seconds.
        socketserver.TCPServer.server_bind(self)
        self.server_name = HOST
        self.server_port = self.server_address[1]

    @property
    def url(self):
        return f"http://{HOST}:{self.port}/?t={self.token}"

    def stop(self):
        self.stopping.set()
        self.shutdown()
