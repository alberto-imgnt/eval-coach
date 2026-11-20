"""Every lesson, review and kit route over a real server: token, Host and Origin checks, error contract, and no early answers."""
from __future__ import annotations

import http.client
import json
import shutil
import tempfile
import threading
import unittest
import urllib.parse
from pathlib import Path

import course_helpers as ch
import helpers
from helpers import FakePty
from test_http import ServerCase

from eval_coach.engine import Engine
from eval_coach.server import AppServer
from eval_coach.terminal import TerminalManager

POST_ROUTES = {
    "/api/lesson/answer": {"lesson": "several-runs", "activity": "generate-spot", "answer": {"option": "a"}},
    "/api/lesson/complete": {"lesson": "mission"},
    "/api/lesson/skip": {"lesson": "several-runs"},
    "/api/lesson/cli/start": {"lesson": "hook", "activity": "hook-compare"},
    "/api/lesson/cli/send": {"lesson": "hook", "activity": "hook-compare"},
    "/api/lesson/cli/stop": {"lesson": "hook", "activity": "hook-compare"},
    "/api/lesson/rule-run": {"lesson": "rules", "activity": "rules-lab", "rule": "r-length", "text": "x"},
    "/api/placement/answer": {"id": "p-hook", "option": "a"},
    "/api/review/answer": {"item": "hook:r-hook-1", "option": "a"},
    "/api/review/postpone": {},
    "/api/step/question": {"step": "generate", "option": "a"},
}
GET_ROUTES = ("/api/lesson?id=mission", "/api/kit?ref=kit:skills/build-eval-script/SKILL.md", "/api/review")
SECRET_KEYS = {"correct", "expected", "bucket", "feedback_right", "feedback_wrong"}


class CourseServer(ServerCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-http-course-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        FakePty.created = []
        self.clock = ch.FakeClock()
        self.course = ch.bundled_course()
        self.terminal = TerminalManager(pty_factory=FakePty, argv_parser=lambda c, env=None: c.split(),
                                        command_checker=lambda c, env=None: None)
        helpers.write_passed_preflight(self.tmp / "home")
        self.engine = helpers.make_engine(self.tmp / "home", self.terminal, poll_interval=0.01, lessons=self.course,
                                          clock=self.clock)
        self.server = AppServer(self.engine, port=0, heartbeat=0.2)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.port = self.server.port
        self.token = self.server.token

    def get(self, path, **kw):
        status, _, raw = self.request("GET", path, **kw)
        return status, json.loads(raw)

    def answer(self, lesson, activity, body):
        return self.post("/api/lesson/answer", {"lesson": lesson, "activity": activity, "answer": body})

    def activity(self, activity_id):
        for lesson in self.course.data["lessons"]:
            for activity in lesson["activities"]:
                if activity["id"] == activity_id:
                    return activity

    def finish_mission(self):
        self.finish_lessons("mission")

    def finish_lessons(self, *lessons):
        """Pass every activity and complete each lesson through the routes. Hook runs are saved as files."""
        for lesson in lessons:
            for activity in self.course.get(lesson)["activities"]:
                if activity["type"] == "cli_compare":
                    paths = self.engine.paths
                    paths.hook_runs.mkdir(parents=True, exist_ok=True)
                    for n in range(1, activity["runs"] + 1):
                        paths.hook_run_file(n).write_text(f"run {n}", encoding="utf-8")
                elif activity["type"] == "cli_practice":
                    paths = self.engine.paths
                    paths.practice_runs.mkdir(parents=True, exist_ok=True)
                    paths.practice_output(activity["id"]).write_text("saved", encoding="utf-8")
                status, body = self.answer(lesson, activity["id"], ch.correct_answer(activity))
                self.assertEqual(status, 200, body)
            status, body = self.post("/api/lesson/complete", {"lesson": lesson})
            self.assertEqual(status, 200, body)


class Security(CourseServer):
    def test_every_new_route_needs_the_token(self):
        for path in GET_ROUTES:
            with self.subTest(path=path):
                status, _, raw = self.request("GET", path, token=False)
                self.assertEqual(status, 401)
                self.assertNotIn(b"mission", raw)
        for path, body in POST_ROUTES.items():
            with self.subTest(path=path):
                status, payload = self.post(path, body, token=False)
                self.assertEqual(status, 401)
                self.assertEqual(payload["error"]["code"], "bad_token")
                self.assertNotIn("state", payload)
        for path in GET_ROUTES:
            with self.subTest(path=path, token="wrong"):
                status, _, _ = self.request("GET", path, headers={"X-Eval-Token": "wrong"}, token=False)
                self.assertEqual(status, 401)

    def test_the_query_token_does_not_open_the_course_routes(self):
        status, _, _ = self.request("GET", f"/api/lesson?id=mission&t={self.token}", token=False)
        self.assertEqual(status, 401)

    def test_host_and_origin_are_checked_on_every_new_route(self):
        for path in GET_ROUTES:
            with self.subTest(path=path, check="host"):
                status, _, _ = self.request("GET", path, headers={"Host": "evil.example"})
                self.assertEqual(status, 403)
            with self.subTest(path=path, check="origin"):
                status, _, _ = self.request("GET", path, headers={"Origin": "http://evil.example"})
                self.assertEqual(status, 403)
        for path, body in POST_ROUTES.items():
            with self.subTest(path=path, check="host"):
                status, payload = self.post(path, body, headers={"Host": "evil.example"})
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"]["code"], "bad_host")
            with self.subTest(path=path, check="origin"):
                status, payload = self.post(path, body, headers={"Origin": "http://evil.example"})
                self.assertEqual(status, 403)
                self.assertEqual(payload["error"]["code"], "bad_origin")

    def test_the_same_origin_is_accepted(self):
        status, _, _ = self.request("GET", "/api/review", headers={"Origin": f"http://127.0.0.1:{self.port}"})
        self.assertEqual(status, 200)

    def test_posts_need_a_json_content_type_and_a_json_object(self):
        for path in POST_ROUTES:
            with self.subTest(path=path):
                conn = self.connection()
                self.addCleanup(conn.close)
                conn.request("POST", path, body=b"x=1", headers={"X-Eval-Token": self.token,
                                                                 "Content-Type": "text/plain"})
                self.assertEqual(conn.getresponse().status, 415)
        status, _, raw = self.request("POST", "/api/lesson/answer", None, headers={"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("POST", "/api/review/postpone", body=b"[1]", headers={"X-Eval-Token": self.token,
                                                                          "Content-Type": "application/json"})
        self.assertEqual(conn.getresponse().status, 400)

    def test_methods_do_not_mix(self):
        status, _, _ = self.request("POST", "/api/review", {})
        self.assertEqual(status, 404)
        status, _, _ = self.request("GET", "/api/lesson/answer")
        self.assertEqual(status, 404)

    def test_unknown_api_routes_are_404_with_the_token_and_401_without(self):
        self.assertEqual(self.request("GET", "/api/lesson/nope")[0], 404)
        self.assertEqual(self.request("GET", "/api/lesson/nope", token=False)[0], 401)


class LessonRoute(CourseServer):
    def test_returns_the_lesson_without_answers(self):
        status, body = self.get("/api/lesson?id=mission")
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        lesson = body["lesson"]
        self.assertEqual(lesson["id"], "mission")
        self.assertEqual(lesson["status"], "active")
        self.assertEqual(lesson["mission"], self.course.mission)
        self.assertFalse(set(ch.walk_keys(body)) & SECRET_KEYS)
        self.assertTrue(lesson["can_complete"])
        self.assertEqual(lesson["activities"], [])
        self.assertEqual(lesson["placement"], [])
        self.assertEqual(lesson["primary_source"]["ref"], "kit:northwind/northwind-test-cases-reference.md")
        self.assertTrue(lesson["sources"])

    def test_no_answer_text_appears_anywhere_in_the_response(self):
        self.setup_project()
        self.finish_lessons("mission", "hook")
        _, _, raw = self.request("GET", "/api/lesson?id=several-runs")
        text = raw.decode("utf-8")
        activities = self.course.get("several-runs")["activities"]
        self.assertTrue(activities)
        for activity in activities:
            if activity["type"] == "choice":
                for option in activity["options"]:
                    self.assertNotIn(option["feedback"], text)
            if activity["type"] == "sort":
                for item in activity["items"]:
                    self.assertNotIn(item["feedback"], text)
        for retrieval in self.course.get("several-runs")["retrieval"]:
            self.assertNotIn(retrieval["prompt"], text)

    def test_the_mission_carries_no_questions(self):
        self.assertEqual(self.course.get("mission")["retrieval"], [])
        self.assertEqual(self.course.data["placement"], [])
        _, body = self.get("/api/lesson?id=mission")
        self.assertEqual(body["lesson"]["activities"], [])
        self.assertEqual(body["lesson"]["placement"], [])

    def test_option_order_is_the_same_on_every_request(self):
        self.setup_project()
        self.finish_mission()
        first = self.get("/api/lesson?id=hook")[1]["lesson"]["activities"][1]["options"]
        self.assertEqual(self.course.get("hook")["activities"][1]["type"], "choice")
        for _ in range(3):
            self.assertEqual(first, self.get("/api/lesson?id=hook")[1]["lesson"]["activities"][1]["options"])

    def test_errors_use_the_error_contract(self):
        for path, code in (("/api/lesson?id=nope", "unknown_lesson"), ("/api/lesson", "unknown_lesson"),
                           ("/api/lesson?id=", "unknown_lesson"), ("/api/lesson?id=hook", "lesson_locked"),
                           ("/api/lesson?id=mission&id=several-runs", "active")):
            with self.subTest(path=path):
                status, body = self.get(path)
                if code == "active":
                    self.assertEqual(status, 200)
                    continue
                self.assertEqual(status, 400)
                self.assertEqual(set(body), {"ok", "error", "state"})
                self.assertFalse(body["ok"])
                self.assertEqual(body["error"]["code"], code)
                self.assertTrue(body["error"]["message"])
                self.assertIn("course", body["state"])

    def test_a_locked_lesson_after_setup(self):
        self.setup_project()
        status, body = self.get("/api/lesson?id=several-runs")
        self.assertEqual((status, body["error"]["code"]), (400, "lesson_locked"))
        self.assertNotIn("lesson", body)
        status, body = self.get("/api/lesson?id=mission")
        self.assertEqual(status, 200)

    def test_viewing_a_lesson_changes_nothing(self):
        self.setup_project()
        before = self.get("/api/state")[1]["course"]
        self.get("/api/lesson?id=mission")
        self.get("/api/review")
        self.assertEqual(self.get("/api/state")[1]["course"], before)
        self.assertEqual(self.engine.progress["lessons"]["records"], [])


class AnswerRoutes(CourseServer):
    def test_a_wrong_then_right_answer_over_http(self):
        self.setup_project()
        self.finish_lessons("mission", "hook")
        activity = self.activity("generate-spot")
        status, body = self.answer("several-runs", "generate-spot", ch.wrong_answer(activity))
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertFalse(body["result"]["passed"])
        shown = next(a for a in body["result"]["lesson"]["activities"] if a["id"] == "generate-spot")
        self.assertFalse(shown["passed"])
        self.assertNotIn("explanations", shown["result"])
        status, body = self.answer("several-runs", "generate-spot", ch.correct_answer(activity))
        self.assertTrue(body["result"]["passed"])
        self.assertEqual({i["id"]: i["status"] for i in body["state"]["course"]}["several-runs"], "active")

    def test_a_wrong_answer_never_reveals_the_right_one(self):
        self.setup_project()
        self.finish_lessons("mission", "hook", "several-runs")
        self.engine.progress["done"].append("generate")
        self.engine._save()
        activity = self.activity("build-sort")
        _, body = self.answer("rules", "build-sort", ch.wrong_answer(activity))
        text = json.dumps(body)
        for item in activity["items"]:
            self.assertNotIn(item["feedback"], text)
        self.assertFalse(set(ch.walk_keys(body)) & SECRET_KEYS)

    def test_complete_needs_no_answers_when_the_lesson_has_no_exercise(self):
        status, body = self.post("/api/lesson/complete", {"lesson": "mission"})
        self.assertEqual(status, 200, body)
        _, state = self.get("/api/state")
        self.assertEqual(state["course"][0]["status"], "done")

    def test_complete_with_every_activity_passed_moves_the_course_on(self):
        self.finish_mission()
        _, state = self.get("/api/state")
        self.assertEqual(state["course"][0]["status"], "done")

    def test_a_step_question_is_answered_over_http(self):
        self.finish_mission()
        status, _ = self.post("/api/setup", {"project_path": str(self.tmp / "project"), "cli_command": "mycli",
                                              "starter": "northwind"})
        self.assertEqual(status, 200)
        status, body = self.post("/api/step/question", {"step": "generate", "option": "a"})
        self.assertEqual((status, body["error"]["code"]), (400, "step_question_locked"))
        self.engine.progress["done"].append("generate")
        item = self.course.step_checks["generate"]
        status, body = self.post("/api/step/question", {"step": "generate", "option": ch.wrong_option(item)})
        self.assertEqual(status, 200, body)
        self.assertFalse(body["result"]["passed"])
        self.assertFalse(set(ch.walk_keys(body)) & SECRET_KEYS)
        status, body = self.post("/api/step/question", {"step": "generate", "option": ch.correct_option(item)})
        self.assertTrue(body["result"]["passed"])
        self.assertTrue(body["state"]["step"]["question"]["passed"])

    def test_error_codes_for_bad_bodies(self):
        cases = (({"lesson": "nope", "activity": "x", "answer": {}}, "unknown_lesson"),
                 ({"activity": "x", "answer": {}}, "unknown_lesson"),
                 ({"lesson": "mission", "activity": "nope", "answer": {}}, "unknown_activity"),
                 ({"lesson": ["mission"], "activity": "hook-explain", "answer": {}}, "unknown_lesson"),
                 ({"lesson": "several-runs", "activity": "generate-spot", "answer": {"option": "a"}},
                  "lesson_locked"))
        self.check_answer_errors(cases)
        self.setup_project()
        self.finish_mission()
        cases = (({"lesson": "hook", "activity": "hook-explain", "answer": {"option": "zzz"}}, "bad_answer"),
                 ({"lesson": "hook", "activity": "hook-explain", "answer": "a"}, "bad_answer"),
                 ({"lesson": "hook", "activity": "hook-explain"}, "bad_answer"))
        self.check_answer_errors(cases)

    def check_answer_errors(self, cases):
        for body, code in cases:
            with self.subTest(body=body):
                status, payload = self.post("/api/lesson/answer", body)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], code)
                self.assertEqual(set(payload), {"ok", "error", "state"})

    def test_skip_is_refused_for_lessons_that_cannot_be_skipped_yet(self):
        self.setup_project()
        self.finish_mission()
        status, body = self.post("/api/lesson/skip", {"lesson": "hook"})
        self.assertEqual((status, body["error"]["code"]), (400, "cannot_skip"))
        status, body = self.post("/api/lesson/skip", {"lesson": "nope"})
        self.assertEqual((status, body["error"]["code"]), (400, "unknown_lesson"))
        self.finish_lessons("hook")
        status, body = self.post("/api/lesson/skip", {"lesson": "several-runs"})
        self.assertEqual((status, body["error"]["code"]), (400, "cannot_skip"))

    def test_rule_run_over_http(self):
        self.setup_project()
        self.finish_lessons("mission", "hook", "several-runs")
        self.engine.progress["done"].append("generate")
        self.engine._save()
        status, body = self.post("/api/lesson/rule-run", {"lesson": "rules", "activity": "rules-lab",
                                                         "rule": "r-length", "text": "one two three"})
        self.assertEqual(status, 200)
        self.assertEqual(body["result"], {"verdict": "pass", "reason": "3 words (limit: under 20)"})
        again = self.post("/api/lesson/rule-run", {"lesson": "rules", "activity": "rules-lab",
                                                   "rule": "r-length", "text": "one two three"})[1]
        self.assertEqual(again["result"], body["result"])
        for bad, code in (({"rule": "nope", "text": "x"}, "unknown_rule"), ({"rule": "r-length", "text": ""}, "bad_answer"),
                          ({"rule": "r-length"}, "bad_answer")):
            with self.subTest(bad=bad):
                status, payload = self.post("/api/lesson/rule-run", dict({"lesson": "rules", "activity": "rules-lab"}, **bad))
                self.assertEqual((status, payload["error"]["code"]), (400, code))
        sample = self.activity("rules-lab")["samples"][0]["text"]
        status, payload = self.post("/api/lesson/rule-run", {"lesson": "rules", "activity": "rules-lab",
                                                            "rule": "r-length", "text": sample})
        self.assertEqual((status, payload["error"]["code"]), (400, "sample_before_answer"))

    def test_the_state_in_every_post_carries_the_course(self):
        status, body = self.post("/api/review/postpone", {})
        self.assertEqual(status, 200)
        for key in ("course", "current_item", "review", "course_text"):
            self.assertIn(key, body["state"])
        self.assertEqual(body["state"]["review"]["postponed"], True)


class KitRoute(CourseServer):
    def kit(self, ref):
        return self.get("/api/kit?ref=" + urllib.parse.quote(ref, safe=":/"))

    def test_reads_a_bundled_file(self):
        status, body = self.kit("kit:skills/make-eval-fixtures/SKILL.md")
        self.assertEqual(status, 200)
        self.assertEqual(body["kit"]["name"], "SKILL.md")
        self.assertEqual(body["kit"]["ref"], "kit:skills/make-eval-fixtures/SKILL.md")
        self.assertEqual(body["kit"]["text"], (helpers.KIT / "skills" / "make-eval-fixtures" / "SKILL.md")
                         .read_bytes().decode("utf-8"))

    def test_the_text_comes_back_as_json_text_not_html(self):
        conn = self.connection()
        self.addCleanup(conn.close)
        conn.request("GET", "/api/kit?ref=kit:lessons/hook/requirements.md", headers={"X-Eval-Token": self.token})
        res = conn.getresponse()
        res.read()
        self.assertIn("application/json", res.getheader("Content-Type"))
        self.assertEqual(res.getheader("X-Content-Type-Options"), "nosniff")

    def test_traversal_absolute_paths_and_other_folders_are_refused(self):
        bad = ("kit:../server.py", "kit:../../tests/helpers.py", "kit:..%2Fserver.py", "kit:%2e%2e/server.py",
               "kit:skills/../../engine.py", "kit:/etc/passwd", "kit:C:\\Windows\\win.ini", "kit:C:/Windows/win.ini",
               "kit:\\Windows\\win.ini", "kit:..\\server.py", "kit:northwind/answer-key.md",
               "kit:NORTHWIND/Answer-Key.md", "kit:northwind/ANSWER~1.MD", "kit:northwind/answer-key.md::$DATA",
               "kit:", "kit:northwind", "kit:content/steps.json",
               "kit:web/index.html", "kit:northwind/NUL", "content/steps.json", "https://example.com/x",
               "file:///C:/Windows/win.ini", "../server.py", "C:\\Windows\\win.ini")
        for ref in bad:
            with self.subTest(ref=ref):
                status, body = self.kit(ref)
                self.assertEqual(status, 400)
                self.assertEqual(body["error"]["code"], "bad_ref")
                self.assertEqual(set(body), {"ok", "error", "state"})
                self.assertNotIn("def ", json.dumps(body))
                self.assertNotIn("Answer key", json.dumps(body))

    def test_raw_percent_encoded_traversal_in_the_query_is_refused(self):
        for raw in ("/api/kit?ref=kit:%2e%2e%2fserver.py", "/api/kit?ref=kit%3A..%2F..%2Fengine.py",
                    "/api/kit?ref=kit:..%5Cserver.py", "/api/kit?ref=kit:%2Fetc%2Fpasswd", "/api/kit",
                    "/api/kit?ref=", "/api/kit?ref=kit:northwind%2Fanswer-key.md"):
            with self.subTest(raw=raw):
                status, body = self.get(raw)
                self.assertEqual((status, body["error"]["code"]), (400, "bad_ref"))

    def test_a_path_traversal_in_the_url_path_never_reaches_the_kit(self):
        for raw in ("/api/kit/../../server.py", "/api/kit%2f..%2fserver.py"):
            with self.subTest(raw=raw):
                status, _, body = self.request("GET", raw)
                self.assertIn(status, (400, 404))
                self.assertNotIn(b"class Handler", body)

    def test_every_source_a_lesson_names_can_be_opened(self):
        for lesson in self.course.data["lessons"]:
            for source in lesson["sources"] + [lesson["primary_source"]]:
                if "sample-r" in source["ref"]:
                    continue  # the Part 1 sample prompts open only after the rescore step (test_part_1_steps)
                with self.subTest(ref=source["ref"]):
                    status, body = self.kit(source["ref"])
                    self.assertEqual(status, 200)
                    self.assertTrue(body["kit"]["text"])


class ReviewRoutes(CourseServer):
    def due(self):
        self.setup_project()
        self.finish_lessons("mission", "hook")
        self.clock.advance(days=1)
        return self.get("/api/review")[1]["review"]["items"]

    def retrieval(self, key):
        return next(r for r in self.course.get("hook")["retrieval"] if "hook:" + r["id"] == key)

    def test_nothing_is_due_at_first(self):
        status, body = self.get("/api/review")
        self.assertEqual(status, 200)
        self.assertEqual(body["review"], {"items": [], "postponed": False})

    def test_finishing_the_mission_schedules_nothing(self):
        self.setup_project()
        self.finish_mission()
        self.clock.advance(days=1)
        self.assertEqual(self.get("/api/review")[1]["review"], {"items": [], "postponed": False})

    def test_due_items_have_no_answers(self):
        items = self.due()
        self.assertEqual(len(items), len(self.course.get("hook")["retrieval"]))
        for item in items:
            self.assertEqual(set(item), {"item", "lesson", "lesson_title", "prompt", "options"})
        self.assertFalse(set(ch.walk_keys(items)) & SECRET_KEYS)
        self.assertNotIn("feedback", json.dumps(items))

    def test_the_state_reports_how_many_are_due(self):
        self.setup_project()
        self.finish_lessons("mission", "hook")
        self.assertEqual(self.get("/api/state")[1]["review"]["due"], 0)
        self.clock.advance(days=1)
        self.assertEqual(self.get("/api/state")[1]["review"], {"due": 2, "postponed": False})

    def test_answering_right_and_wrong(self):
        items = self.due()
        first = items[0]
        retrieval = self.retrieval(first["item"])
        status, body = self.post("/api/review/answer", {"item": first["item"], "option": ch.correct_option(retrieval)})
        self.assertEqual(status, 200)
        self.assertTrue(body["result"]["passed"])
        self.assertEqual(body["state"]["review"]["due"], 1)
        second = items[1]
        retrieval = self.retrieval(second["item"])
        status, body = self.post("/api/review/answer", {"item": second["item"], "option": ch.wrong_option(retrieval)})
        self.assertFalse(body["result"]["passed"])
        self.assertTrue(body["result"]["feedback"])

    def test_errors(self):
        self.due()
        for body, code in (({"item": "nope", "option": "a"}, "review_unknown"), ({"option": "a"}, "review_unknown"),
                           ({"item": "hook:r-hook-1", "option": "zzz"}, "bad_answer"),
                           ({"item": "hook:r-hook-1"}, "bad_answer")):
            with self.subTest(body=body):
                status, payload = self.post("/api/review/answer", body)
                self.assertEqual((status, payload["error"]["code"]), (400, code))
                self.assertEqual(set(payload), {"ok", "error", "state"})

    def test_postpone(self):
        self.due()
        status, body = self.post("/api/review/postpone", {})
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["review"], {"due": 0, "postponed": True})
        self.assertEqual(self.get("/api/review")[1]["review"], {"items": [], "postponed": True})


class CliRoutes(CourseServer):
    def test_start_send_stop_the_hook_run_over_http(self):
        self.setup_project()
        self.finish_mission()
        body = {"lesson": "hook", "activity": "hook-compare"}
        status, payload = self.post("/api/lesson/cli/start", body)
        self.assertEqual(status, 200, payload)
        self.assertTrue(payload["state"]["terminal"]["running"])
        self.assertEqual(FakePty.created[-1].cwd, str(self.engine.paths.hook_work))
        status, payload = self.post("/api/lesson/cli/send", body)
        self.assertEqual(status, 200)
        self.assertEqual(FakePty.created[-1].lines, [self.course.get("hook")["activities"][0]["line"]])
        status, payload = self.post("/api/lesson/cli/stop", body)
        self.assertEqual(status, 200)
        self.assertFalse(payload["state"]["terminal"]["running"])

    def test_refusals(self):
        status, payload = self.post("/api/lesson/cli/start", {"lesson": "hook", "activity": "hook-compare"})
        self.assertEqual((status, payload["error"]["code"]), (400, "lesson_locked"))
        self.setup_project()
        status, payload = self.post("/api/lesson/cli/start", {"lesson": "hook", "activity": "hook-compare"})
        self.assertEqual((status, payload["error"]["code"]), (400, "lesson_locked"))
        self.finish_mission()
        status, payload = self.post("/api/lesson/cli/send", {"lesson": "hook", "activity": "hook-explain"})
        self.assertEqual((status, payload["error"]["code"]), (400, "not_cli"))
        status, payload = self.post("/api/lesson/cli/send", {"lesson": "hook", "activity": "hook-compare"})
        self.assertEqual((status, payload["error"]["code"]), (400, "cli_not_running"))
        status, payload = self.post("/api/lesson/cli/start", {"lesson": "hook", "activity": "nope"})
        self.assertEqual((status, payload["error"]["code"]), (400, "unknown_activity"))
        status, payload = self.post("/api/lesson/cli/stop", {"lesson": "nope", "activity": "x"})
        self.assertEqual((status, payload["error"]["code"]), (400, "unknown_lesson"))


class StateShape(CourseServer):
    def test_the_new_state_fields(self):
        _, state = self.get("/api/state")
        self.assertEqual(state["current_item"], {"kind": "lesson", "id": "mission"})
        self.assertEqual(state["course"][0]["kind"], "lesson")
        self.assertEqual(state["course"][0]["status"], "active")
        self.assertEqual(state["review"], {"due": 0, "postponed": False})
        self.assertEqual(state["current_step"], None)
        self.assertIn("continue", state["course_text"])
        self.assertEqual({k for item in state["course"] for k in item}, {"kind", "id", "title", "status"})

    def test_the_state_never_holds_answers(self):
        _, _, raw = self.request("GET", "/api/state")
        self.assertFalse(set(ch.walk_keys(json.loads(raw))) & SECRET_KEYS)

    def test_steps_and_current_step_still_work_after_the_course_reaches_them(self):
        self.setup_project()
        self.finish_lessons("mission", "hook", "several-runs")
        _, state = self.get("/api/state")
        self.assertEqual(state["current_step"], "generate")
        self.assertEqual(state["current_item"], {"kind": "step", "id": "generate"})
        self.assertEqual(state["step"]["id"], "generate")
        self.assertEqual([s["id"] for s in state["steps"]][:2], ["generate", "build"])
        self.assertEqual(state["steps"][0]["status"], "active")

    def test_the_part_selector_defaults_to_part_three_and_refuses_an_unknown_part(self):
        _, plain = self.get("/api/state")
        status, named = self.get("/api/state?part=part-3")
        self.assertEqual(status, 200)
        for key in ("course", "steps", "current_step", "current_item", "course_text", "series"):
            self.assertEqual(named[key], plain[key])
        status, body = self.get("/api/state?part=part-99")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unknown_part")
        self.assertEqual(body["state"]["course"], plain["course"])


class ReferenceData(CourseServer):
    def test_the_reference_page_data_is_static_and_holds_no_answers(self):
        status, _, raw = self.request("GET", "/reference-data.json", token=False)
        self.assertEqual(status, 200)
        data = json.loads(raw)
        self.assertEqual(set(data), {"glossary", "reference"})
        names = {t["term"] for t in data["glossary"]}
        self.assertTrue({"Checker", "Deterministic", "Baseline (Iteration 0)"} <= names)
        self.assertFalse(set(ch.walk_keys(data)) & SECRET_KEYS)
        self.assertIn("In this course your prompt gives an answer, the answer is saved to a file, your checker reads "
                      "the file, and the checker gives a result.", data["reference"]["loop_lines"])


if __name__ == "__main__":
    unittest.main()
