"""A real server on a random port, with a real TerminalManager over a fake pseudo console."""
from __future__ import annotations

import base64
import http.client
import json
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import helpers
from helpers import FakePty, wait_until

from eval_coach.engine import Engine
from eval_coach.server import CSP, MAX_BODY, AppServer
from eval_coach.terminal import TerminalManager


class ServerCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-http-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        FakePty.created = []
        self.terminal = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: c.split(),
                                        command_checker=lambda c, env=None: None)
        helpers.write_passed_preflight(self.tmp / "home")
        self.engine = Engine(self.tmp / "home", self.terminal, poll_interval=0.01)
        self.server = AppServer(self.engine, port=0, heartbeat=0.2)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.port = self.server.port
        self.token = self.server.token

    def stop_server(self):
        self.engine.shutdown()
        self.server.stop()
        self.server.server_close()
        self.thread.join(5)

    def connection(self):
        return http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)

    def request(self, method, path, body=None, headers=None, token=True):
        conn = self.connection()
        self.addCleanup(conn.close)
        hdrs = dict(headers or {})
        if token and "X-Eval-Token" not in hdrs:
            hdrs["X-Eval-Token"] = self.token
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs.setdefault("Content-Type", "application/json")
        conn.request(method, path, body=data, headers=hdrs)
        res = conn.getresponse()
        return res.status, dict(res.getheaders()), res.read()

    def post(self, path, body=None, **kw):
        status, headers, raw = self.request("POST", path, body if body is not None else {}, **kw)
        return status, json.loads(raw)

    def setup_project(self):
        status, body = self.post("/api/setup", {"project_path": str(self.tmp / "project"),
                                                "cli_command": "cli", "starter": "northwind"})
        self.assertEqual(status, 200, body)
        return body


class Binding(ServerCase):
    def test_binds_loopback_only(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.port, 0)

    def test_url_shape(self):
        self.assertEqual(self.server.url, f"http://127.0.0.1:{self.port}/?t={self.token}")
        self.assertGreaterEqual(len(self.token), 32)


class Token(ServerCase):
    def test_api_needs_the_token(self):
        for token in (None, "wrong", ""):
            headers = {} if token is None else {"X-Eval-Token": token}
            with self.subTest(token=token):
                status, _, raw = self.request("GET", "/api/state", headers=headers, token=False)
                self.assertEqual(status, 401)
                self.assertNotIn(b"configured", raw)

    def test_right_token(self):
        status, _, raw = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertIn("configured", json.loads(raw))

    def test_post_needs_the_token(self):
        status, body = self.post("/api/quit", {}, token=False)
        self.assertEqual(status, 401)
        self.assertNotIn("state", body)
        self.assertFalse(self.server.stopping.is_set())

    def test_query_token_is_not_accepted_for_api(self):
        status, _, _ = self.request("GET", f"/api/state?t={self.token}", token=False)
        self.assertEqual(status, 401)

    def test_stream_needs_the_query_token(self):
        status, _, _ = self.request("GET", "/api/terminal/stream?after=0", token=True)
        self.assertEqual(status, 401)

    def test_comparison_is_constant_time(self):
        with mock.patch("eval_coach.server.hmac.compare_digest", wraps=__import__("hmac").compare_digest) as spy:
            self.request("GET", "/api/state")
        self.assertTrue(spy.called)

    def test_static_needs_no_token(self):
        status, _, _ = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)

    def test_non_ascii_token_does_not_crash(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.putrequest("GET", "/api/state")
        conn.putheader("X-Eval-Token", b"\xc3\xa9t\xc3\xa9")
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 401)


class HostAndOrigin(ServerCase):
    def test_host_must_match_exactly(self):
        for host in ("evil.example", f"localhost:{self.port}", "127.0.0.1", f"127.0.0.1:{self.port + 1}",
                     f"evil.example:{self.port}"):
            with self.subTest(host=host):
                status, _, _ = self.request("GET", "/", headers={"Host": host}, token=False)
                self.assertEqual(status, 403)
                status, _, _ = self.request("GET", "/api/state", headers={"Host": host})
                self.assertEqual(status, 403)

    def test_missing_host_is_rejected(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.putrequest("GET", "/", skip_host=True)
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 403)

    def test_origin_must_match_exactly(self):
        for origin in ("http://evil.example", "null", f"http://localhost:{self.port}",
                       f"https://127.0.0.1:{self.port}", f"http://127.0.0.1:{self.port}/x"):
            with self.subTest(origin=origin):
                status, _, _ = self.request("GET", "/api/state", headers={"Origin": origin})
                self.assertEqual(status, 403)
                status, _, _ = self.request("GET", "/", headers={"Origin": origin}, token=False)
                self.assertEqual(status, 403)
                status, body = self.post("/api/setup", {}, headers={"Origin": origin})
                self.assertEqual(status, 403)

    def test_correct_origin_is_allowed(self):
        status, _, _ = self.request("GET", "/api/state", headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)


class Body(ServerCase):
    def test_content_type_is_required(self):
        status, body = self.post("/api/quit", {}, headers={"Content-Type": "text/plain"})
        self.assertEqual(status, 415)

    def test_rejected_post_with_a_body_still_gets_its_response(self):
        for _ in range(20):  # the connection reset this guards against was intermittent
            status, _, raw = self.request("POST", "/api/setup", {"pad": "x" * 200000},
                                          headers={"Content-Type": "text/plain"})
            self.assertEqual(status, 415, raw[:100])

    def test_form_post_is_refused(self):
        status, _ = self.post("/api/quit", {}, headers={"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 415)

    def test_body_limit(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/setup")
        conn.putheader("X-Eval-Token", self.token)
        conn.putheader("Content-Type", "application/json")
        conn.putheader("Content-Length", str(MAX_BODY + 1))
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 413)

    def test_exactly_the_limit_is_allowed(self):
        padding = "x" * (MAX_BODY - len('{"a":""}'))
        raw = ('{"a":"%s"}' % padding).encode("ascii")
        self.assertEqual(len(raw), MAX_BODY)
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("POST", "/api/terminal/input", body=raw,
                     headers={"X-Eval-Token": self.token, "Content-Type": "application/json"})
        # {"a":...} has no "data" field, so this is a 400 from the route, not a 413.
        self.assertEqual(conn.getresponse().status, 400)

    def test_missing_length(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.putrequest("POST", "/api/quit")
        conn.putheader("X-Eval-Token", self.token)
        conn.putheader("Content-Type", "application/json")
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 411)

    def test_invalid_json(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("POST", "/api/setup", body=b"{nope",
                     headers={"X-Eval-Token": self.token, "Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 400)

    def test_json_must_be_an_object(self):
        status, body = self.post("/api/setup", [1, 2, 3])
        self.assertEqual(status, 400)


class Headers(ServerCase):
    def test_csp_is_exact_on_static_and_api(self):
        expected = "default-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'"
        self.assertEqual(CSP, expected)
        for path, token in (("/", False), ("/api/state", True)):
            _, headers, _ = self.request("GET", path, token=token)
            self.assertEqual(headers["Content-Security-Policy"], expected)

    def test_no_cors_headers(self):
        for method, path in (("GET", "/"), ("GET", "/api/state"), ("OPTIONS", "/api/state")):
            with self.subTest(method=method, path=path):
                _, headers, _ = self.request(method, path, headers={"Origin": f"http://127.0.0.1:{self.port}"})
                self.assertFalse([h for h in headers if h.lower().startswith("access-control")])


class Traversal(ServerCase):
    def test_paths_cannot_escape_web(self):
        for path in ("/../server.py", "/..%2fserver.py", "/%2e%2e/server.py", "/%2e%2e%2fserver.py",
                     "/js/../../server.py", "/..\\server.py", "/%5c..%5cserver.py", "/..%5cserver.py",
                     "/%252e%252e/server.py", "/C:%5cWindows%5cwin.ini", "/C:/Windows/win.ini",
                     "/index.html%00.txt", "/index.html::$DATA", "/index.html.", "/index.html%20",
                     "//server.py", "/./index.html", "/js//app.js"):
            with self.subTest(path=path):
                status, _, raw = self.request("GET", path, token=False)
                self.assertEqual(status, 404, raw[:100])
                self.assertNotIn(b"import ", raw)

    def test_no_directory_listing(self):
        status, _, _ = self.request("GET", "/js", token=False)
        self.assertEqual(status, 404)

    def test_index_is_served_with_a_type(self):
        status, headers, raw = self.request("GET", "/", token=False)
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertTrue(raw)

    def test_nested_file_is_served(self):
        status, headers, _ = self.request("GET", "/js/app.js", token=False)
        self.assertEqual(status, 200)
        self.assertIn("javascript", headers["Content-Type"])


class Routes(ServerCase):
    def test_state_shape_before_setup(self):
        _, _, raw = self.request("GET", "/api/state")
        state = json.loads(raw)
        self.assertEqual(set(state), {"configured", "setup", "current_step", "steps", "step", "terminal", "preflight",
                                      "course", "optional_steps", "current_item", "review", "course_text",
                                      "series", "settings"})
        self.assertEqual([(i["kind"], i["id"], i["status"]) for i in state["course"]],
                         [("step", s, "locked") for s in
                          ("generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline")])
        self.assertIsNone(state["current_item"])
        self.assertEqual(state["review"], {"due": 0, "postponed": False})
        self.assertIn("continue", state["course_text"])
        self.assertFalse(state["configured"])
        self.assertEqual(state["terminal"], {"running": False, "label": "", "exit_code": None, "owner": None})
        self.assertEqual([s["id"] for s in state["steps"]],
                         ["generate", "build", "fixtures", "readback", "predict", "key", "run", "fix", "baseline"])

    def test_ok_and_error_envelopes(self):
        body = self.setup_project()
        self.assertEqual(set(body), {"ok", "state"})
        self.assertTrue(body["state"]["configured"])
        status, body = self.post("/api/step/start", {"step": "build"})
        self.assertEqual(status, 400)
        self.assertEqual(set(body), {"ok", "error", "state"})
        self.assertEqual(body["error"]["code"], "step_locked")
        self.assertFalse(body["ok"])
        self.assertTrue(body["state"]["configured"])

    def test_state_selects_a_step(self):
        self.setup_project()
        _, _, raw = self.request("GET", "/api/state?step=predict")
        detail = json.loads(raw)["step"]
        self.assertEqual(detail["id"], "predict")
        self.assertEqual(set(detail), {"id", "title", "status", "track", "goal", "why", "instructions", "cli",
                                       "checklist", "last_check", "question", "troubleshooting", "ui", "data",
                                       "preview", "held_by"})  # a locked step is a words-only preview

    def test_unknown_step_in_state(self):
        status, _, _ = self.request("GET", "/api/state?step=bogus")
        self.assertEqual(status, 400)

    def test_resets_are_refused_without_confirmation_and_run_with_it(self):
        self.setup_project()
        for path in ("/api/reset/progress", "/api/reset/configuration"):
            status, body = self.post(path, {})
            self.assertEqual((status, body["error"]["code"]), (400, "confirm_required"))
            self.assertTrue(body["state"]["configured"])
        status, body = self.post("/api/reset/progress", {"confirm": True})
        self.assertEqual(status, 200)
        self.assertIn("reset-backup", body["result"]["backup_folder"])
        self.assertTrue(body["state"]["configured"])
        status, body = self.post("/api/reset/configuration", {"confirm": True})
        self.assertEqual(status, 200)
        self.assertFalse(body["state"]["configured"])

    def test_step_response_keeps_the_body_step(self):
        self.setup_project()
        status, body = self.post("/api/step/submit", {"step": "generate", "data": {"model_name": "m"}})
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["step"]["id"], "generate")
        self.assertEqual(body["state"]["step"]["data"]["model_name"], "m")

    def test_response_without_a_step_returns_the_current_step(self):
        self.setup_project()
        status, body = self.post("/api/terminal/resize", {"cols": 90, "rows": 25})
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["step"]["id"], "generate")

    def test_response_keeps_a_locked_step_named_in_the_request(self):
        self.setup_project()
        status, body = self.post("/api/step/check", {"step": "predict"})
        self.assertEqual(status, 400)
        self.assertEqual(body["state"]["step"]["id"], "predict")

    def test_resize_with_no_cli_is_remembered_for_the_next_start(self):
        self.setup_project()
        status, body = self.post("/api/terminal/resize", {"cols": 91, "rows": 27})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["ok"])
        self.post("/api/step/start", {"step": "generate"})
        pty = FakePty.created[-1]
        self.assertEqual((pty.cols, pty.rows), (91, 27))

    def test_terminal_input_and_resize(self):
        self.setup_project()
        self.post("/api/step/start", {"step": "generate"})
        pty = FakePty.created[-1]
        status, _ = self.post("/api/terminal/input", {"data": base64.b64encode(b"hi").decode("ascii")})
        self.assertEqual(status, 200)
        self.assertEqual(pty.written, [b"hi"])
        status, _ = self.post("/api/terminal/resize", {"cols": 90, "rows": 25})
        self.assertEqual(status, 200)
        self.assertEqual((pty.cols, pty.rows), (90, 25))

    def test_bad_terminal_input(self):
        status, body = self.post("/api/terminal/input", {"data": "not base64!"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "bad_input")

    def test_bad_resize(self):
        status, _ = self.post("/api/terminal/resize", {"cols": "wide", "rows": 25})
        self.assertEqual(status, 400)

    def test_step_lifecycle_over_http(self):
        self.setup_project()
        status, body = self.post("/api/step/start", {"step": "generate"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["state"]["terminal"]["running"])
        self.assertTrue(body["state"]["step"]["cli"]["started"])
        status, body = self.post("/api/step/send", {"step": "generate"})
        self.assertTrue(body["state"]["step"]["cli"]["sent"])
        pty = FakePty.created[-1]
        self.assertEqual(pty.lines[-1], body["state"]["step"]["cli"]["line"])
        status, body = self.post("/api/step/stop", {"step": "generate"})
        self.assertFalse(body["state"]["terminal"]["running"])
        self.assertTrue(pty.closed)

    def test_only_one_cli_runs(self):
        self.setup_project()
        self.post("/api/step/start", {"step": "generate"})
        first = FakePty.created[-1]
        self.post("/api/step/start", {"step": "generate"})
        self.assertTrue(first.closed)
        self.assertIsNot(FakePty.created[-1], first)

    def test_preflight_routes_use_the_contract_envelopes(self):
        status, body = self.post("/api/preflight/track", {"track": "promptfoo"})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["state"]["preflight"]["track"], "promptfoo")
        self.assertIn("Script track", body["state"]["preflight"]["track_note"])
        status, body = self.post("/api/preflight/track", {"track": "nonsense"})
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "track_required")
        self.assertIn("state", body)

    def test_install_without_consent_is_refused_over_http(self):
        self.post("/api/preflight/track", {"track": "promptfoo"})
        for payload in ({"item": "node"}, {"item": "node", "consent": False}, {"item": "node", "consent": "yes"}):
            with self.subTest(payload=payload):
                status, body = self.post("/api/preflight/install", payload)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], "consent_required")
                self.assertIsNone(body["state"]["preflight"]["job"])

    def test_preflight_routes_need_the_token(self):
        status, body = self.post("/api/preflight/track", {"track": "script"}, token=False)
        self.assertEqual(status, 401)

    def test_quit_stops_the_cli_and_the_server(self):
        self.setup_project()
        self.post("/api/step/start", {"step": "generate"})
        pty = FakePty.created[-1]
        status, body = self.post("/api/quit", {})
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertTrue(pty.closed)
        self.assertTrue(wait_until(self.server.stopping.is_set))


class Stream(ServerCase):
    def open_stream(self, after):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("GET", f"/api/terminal/stream?t={self.token}&after={after}")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        self.assertEqual(res.getheader("Content-Type"), "text/event-stream")
        return res

    def next_event(self, res, kinds=("output", "exit", "state")):
        """Read until a named event arrives."""
        name = None
        while True:
            line = res.readline().decode("utf-8").rstrip("\n")
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: ") and name in kinds:
                return name, json.loads(line[6:])

    def start_pty(self):
        self.terminal.start("cli", str(self.tmp), "Test")
        return FakePty.created[-1]

    def test_replays_only_after_the_given_seq(self):
        pty = self.start_pty()
        for chunk in (b"one", b"two", b"three"):
            pty.feed(chunk)
        res = self.open_stream(after=1)
        name, data = self.next_event(res)
        self.assertEqual((name, data["seq"], base64.b64decode(data["data"])), ("output", 2, b"two"))
        name, data = self.next_event(res)
        self.assertEqual((data["seq"], base64.b64decode(data["data"])), (3, b"three"))

    def test_missing_after_replays_everything(self):
        pty = self.start_pty()
        pty.feed(b"alpha")
        pty.feed(b"beta")
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("GET", f"/api/terminal/stream?t={self.token}")
        res = conn.getresponse()
        self.assertEqual(res.status, 200)
        seen = [base64.b64decode(self.next_event(res)[1]["data"]) for _ in range(2)]
        self.assertEqual(seen, [b"alpha", b"beta"])

    def test_seq_from_an_earlier_cli_still_works_as_after(self):
        first = self.start_pty()
        first.feed(b"old")
        res = self.open_stream(after=0)
        old_seq = self.next_event(res)[1]["seq"]
        first.finish(0)
        self.assertTrue(wait_until(lambda: not self.terminal.running))
        second = self.start_pty()
        second.feed(b"new")
        res = self.open_stream(after=old_seq)
        data = self.next_event(res)[1]
        self.assertEqual(base64.b64decode(data["data"]), b"new")
        self.assertGreater(data["seq"], old_seq)

    def test_after_zero_replays_everything(self):
        pty = self.start_pty()
        pty.feed(b"alpha")
        pty.feed(b"beta")
        res = self.open_stream(after=0)
        seen = [base64.b64decode(self.next_event(res)[1]["data"]) for _ in range(2)]
        self.assertEqual(seen, [b"alpha", b"beta"])

    def test_live_output_and_exit(self):
        pty = self.start_pty()
        res = self.open_stream(after=0)
        pty.feed(b"live")
        self.assertEqual(base64.b64decode(self.next_event(res)[1]["data"]), b"live")
        pty.finish(7)
        self.assertEqual(self.next_event(res), ("exit", {"code": 7}))
        self.assertTrue(wait_until(lambda: not self.terminal.running))
        self.assertEqual(self.terminal.status()["exit_code"], 7)

    def test_state_event(self):
        res = self.open_stream(after=0)
        time.sleep(0.05)
        self.terminal.publish_state()
        self.assertEqual(self.next_event(res), ("state", {}))

    def test_heartbeat_comment(self):
        res = self.open_stream(after=0)
        line = res.readline()
        self.assertEqual(line, b": heartbeat\n")

    def test_new_cli_replaces_the_buffer_but_seq_keeps_growing(self):
        first = self.start_pty()
        first.feed(b"old")
        first.finish(0)
        self.assertTrue(wait_until(lambda: not self.terminal.running))
        second = self.start_pty()
        second.feed(b"new")
        res = self.open_stream(after=0)
        name, data = self.next_event(res)
        self.assertEqual(base64.b64decode(data["data"]), b"new")
        self.assertGreater(data["seq"], 2)


class Ring(unittest.TestCase):
    def test_ring_is_bounded(self):
        FakePty.created = []
        term = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: [c],
                               command_checker=lambda c, env=None: None, ring_bytes=100)
        term.start("cli", ".", "x")
        self.addCleanup(term.stop)
        pty = FakePty.created[-1]
        for i in range(30):
            pty.feed(b"0123456789")
        events, cursor, _ = term.wait_events(0, term.state_generation, 0)
        self.assertLessEqual(sum(len(e[2]) for e in events), 100)
        self.assertEqual(cursor, 30)
        self.assertEqual(events[-1][0], 30)

    def test_stale_cursor_replays_from_the_start(self):
        FakePty.created = []
        term = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: [c],
                               command_checker=lambda c, env=None: None)
        term.start("cli", ".", "x")
        self.addCleanup(term.stop)
        FakePty.created[-1].feed(b"data")
        events, _, _ = term.wait_events(9999, term.state_generation, 0)
        self.assertEqual(len(events), 1)


    def test_the_owner_stays_after_the_cli_exits_and_release_clears_everything(self):
        FakePty.created = []
        term = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: [c],
                               command_checker=lambda c, env=None: None)
        self.addCleanup(term.stop)
        term.start("cli", ".", "Run 1 of 3", owner="lesson:hook:hook-compare")
        pty = FakePty.created[-1]
        pty.feed(b"output")
        pty.finish(1)
        self.assertTrue(wait_until(lambda: not term.running))
        self.assertEqual(term.status(), {"running": False, "label": "Run 1 of 3", "exit_code": 1,
                                         "owner": "lesson:hook:hook-compare"})
        before = term.state_generation
        term.release()
        self.assertEqual(term.status(), {"running": False, "label": "", "exit_code": None, "owner": None})
        self.assertGreater(term.state_generation, before)
        events, _, _ = term.wait_events(0, term.state_generation, 0)
        self.assertEqual(events, [])

    def test_release_stops_a_running_cli(self):
        FakePty.created = []
        term = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: [c],
                               command_checker=lambda c, env=None: None)
        self.addCleanup(term.stop)
        term.start("cli", ".", "x", owner="generate")
        term.release()
        self.assertTrue(FakePty.created[-1].closed)
        self.assertFalse(term.running)
        self.assertIsNone(term.status()["owner"])


if __name__ == "__main__":
    unittest.main()
