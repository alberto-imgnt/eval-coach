"""Demo access: the hash, the tool that makes it, the engine switch and the routes (spec demo-access)."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import course_helpers as ch
import helpers
from helpers import DEMO_PASSWORD, ROOT
from test_http import ServerCase

from eval_coach import demo_access, state
from eval_coach.engine import Engine, EngineError


class HashTests(unittest.TestCase):
    def test_the_right_password_verifies_and_a_wrong_or_empty_one_does_not(self):
        record = helpers.demo_record()
        self.assertTrue(demo_access.verify(DEMO_PASSWORD, record))
        for wrong in ("", "nope", DEMO_PASSWORD + " ", None, 5):
            self.assertFalse(demo_access.verify(wrong, record), repr(wrong))

    def test_the_record_holds_a_salt_a_hash_and_a_count_and_never_the_password(self):
        record = helpers.demo_record()
        self.assertEqual(set(record), {"salt", "hash", "iterations"})
        self.assertNotIn(DEMO_PASSWORD, json.dumps(record))
        self.assertEqual(len(bytes.fromhex(record["salt"])), demo_access.SALT_BYTES)

    def test_each_record_has_its_own_salt(self):
        self.assertNotEqual(demo_access.make_record("same", iterations=10)["salt"],
                            demo_access.make_record("same", iterations=10)["salt"])

    def test_the_shipped_strength_is_slow_and_salted(self):
        self.assertGreaterEqual(demo_access.ITERATIONS, 200_000)

    def test_a_broken_record_never_verifies(self):
        for record in (None, {}, {"salt": "zz", "hash": "00", "iterations": 5}, {"salt": "00", "hash": "00", "iterations": 0},
                       {"salt": "", "hash": "", "iterations": 5}):
            self.assertFalse(demo_access.verify(DEMO_PASSWORD, record))

    def test_a_missing_or_unusable_file_means_unavailable(self):
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-demo-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        self.assertIsNone(demo_access.load_record(tmp / "absent.json"))
        (tmp / "bad.json").write_text("{not json", encoding="utf-8")
        self.assertIsNone(demo_access.load_record(tmp / "bad.json"))
        (tmp / "ok.json").write_text(json.dumps(helpers.demo_record()), encoding="utf-8")
        self.assertEqual(demo_access.load_record(tmp / "ok.json"), helpers.demo_record())

    def test_no_shipped_hash_in_a_clean_checkout_or_it_is_a_real_record(self):
        shipped = ROOT / "app" / "eval_coach" / demo_access.HASH_FILE
        if shipped.exists():
            self.assertIsNotNone(demo_access.load_record(), "the shipped hash file is unusable")
        else:
            self.assertIsNone(demo_access.load_record())


class MakeHashTool(unittest.TestCase):
    def test_the_tool_writes_a_salt_and_a_hash_and_never_the_password(self):
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import make_demo_hash
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-demo-tool-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        out = tmp / "demo_hash.json"
        with mock.patch("getpass.getpass", side_effect=[DEMO_PASSWORD, DEMO_PASSWORD]):
            self.assertEqual(make_demo_hash.main(["--out", str(out)]), 0)
        text = out.read_text(encoding="utf-8")
        self.assertNotIn(DEMO_PASSWORD, text)
        self.assertTrue(demo_access.verify(DEMO_PASSWORD, json.loads(text)))
        self.assertFalse(demo_access.verify("another", json.loads(text)))

    def test_the_tool_writes_nothing_for_an_empty_or_mismatched_password(self):
        sys.path.insert(0, str(ROOT / "tools"))
        self.addCleanup(sys.path.remove, str(ROOT / "tools"))
        import make_demo_hash
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-demo-tool-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        out = tmp / "demo_hash.json"
        for answers in ([""], ["one", "two"]):
            with mock.patch("getpass.getpass", side_effect=answers):
                self.assertEqual(make_demo_hash.main(["--out", str(out)]), 1)
            self.assertFalse(out.exists())


class EngineSwitch(ch.CourseBase):
    def setUp(self):
        super().setUp()
        self.engine.demo_lock()
        self.setup_project()

    def part_state(self, part):
        return next(p["state"] for p in self.engine.get_state()["series"]["parts"] if p["id"] == part)

    def test_a_wrong_password_leaves_it_off_with_one_plain_message(self):
        messages = set()
        for wrong in ("", "nope", None, 7):
            error = self.assert_code("demo_refused", self.engine.demo_unlock, wrong)
            messages.add(error.message)
        self.assertEqual(messages, {"That password was not accepted."})
        self.assertFalse(self.engine.get_state()["demo"]["on"])

    def test_the_right_password_opens_every_part_but_only_at_its_next_item(self):
        self.assertEqual(self.part_state("part-3"), "locked")
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.assertEqual(self.part_state("part-3"), "not_started")
        self.assertEqual(self.part_state("part-2"), "not_started")
        statuses = {i["id"]: i["status"] for i in self.engine.get_state(part="part-3")["course"]}
        self.assertEqual([k for k, v in statuses.items() if v == "active"], ["mission"])
        self.assertEqual(statuses["hook"], "locked")
        self.assert_code("lesson_locked", self.engine.lesson_view, "hook")  # no reading ahead inside a Part

    def test_it_marks_nothing_done_or_skipped_and_turning_it_off_locks_again(self):
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.engine.lesson_complete("mission")
        saved = self.paths.progress_file.read_bytes()
        self.engine.demo_lock()
        self.assertEqual(self.part_state("part-3"), "locked")
        self.assertEqual(self.engine._lessons_block()["skipped_parts"], [])
        self.assertEqual(self.engine.progress["lessons"]["per_lesson"]["mission"]["status"], "done")  # work is kept
        self.assertEqual(self.paths.progress_file.read_bytes(), saved)

    def test_setup_and_the_key_stay_as_for_anyone(self):
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.engine.lesson_complete("mission")
        self.assert_code("step_locked", self.engine.get_state, step="key")
        (self.home / "preflight.json").unlink()
        engine = self.new_engine(demo=False)
        engine.demo_unlock(DEMO_PASSWORD)
        self.assert_code("preflight_incomplete", engine.step_start, "generate")

    def test_it_is_held_in_memory_only(self):
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.assertTrue(self.engine.get_state()["demo"]["on"])
        self.engine.lesson_complete("mission")
        again = self.new_engine(demo=False)
        self.assertFalse(again.get_state()["demo"]["on"])
        for path in (self.home, self.project):
            for file in path.rglob("*"):
                if file.is_file():
                    self.assertNotIn(DEMO_PASSWORD.encode(), file.read_bytes(), file.name)
                    if file.suffix == ".json":
                        self.assertNotIn(b"demo", file.read_bytes().lower(), file.name)

    def test_the_resets_leave_it_alone(self):
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.engine.reset_progress(True)
        self.assertTrue(self.engine.get_state()["demo"]["on"])
        self.engine.reset_configuration(True)
        self.assertTrue(self.engine.get_state()["demo"]["on"])

    def test_without_a_hash_it_is_unavailable_and_nothing_unlocks(self):
        engine = Engine(self.home, self.terminal, poll_interval=0.01, lessons=self.course, clock=self.clock,
                        demo_hash={})
        self.addCleanup(engine.shutdown)
        with mock.patch.object(demo_access, "load_record", return_value=None):
            engine = Engine(self.home, self.terminal, poll_interval=0.01, lessons=self.course, clock=self.clock)
            self.addCleanup(engine.shutdown)
            self.assertFalse(engine.get_state()["demo"]["available"])
            self.assert_code("demo_refused", engine.demo_unlock, DEMO_PASSWORD)
            self.assertFalse(engine.get_state()["demo"]["on"])

    def test_the_state_says_whether_it_is_available_and_on(self):
        self.assertEqual(self.engine.get_state()["demo"], {"available": True, "on": False})
        self.engine.demo_unlock(DEMO_PASSWORD)
        self.assertEqual(self.engine.get_state()["demo"], {"available": True, "on": True})


class Routes(ServerCase):
    def setUp(self):
        super().setUp()
        self.engine._demo_record = helpers.demo_record()

    def test_unlock_and_lock_over_the_routes(self):
        status, body = self.post("/api/demo/unlock", {"password": "wrong"})
        self.assertEqual((status, body["error"]["code"]), (400, "demo_refused"))
        self.assertEqual(body["state"]["demo"], {"available": True, "on": False})
        status, body = self.post("/api/demo/unlock", {"password": DEMO_PASSWORD})
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["demo"], {"available": True, "on": True})
        status, _, raw = self.request("GET", "/api/state")  # a reload keeps it
        self.assertTrue(json.loads(raw)["demo"]["on"])
        status, body = self.post("/api/demo/lock", {})
        self.assertEqual(body["state"]["demo"], {"available": True, "on": False})

    def test_the_password_is_not_in_any_response(self):
        status, _, raw = self.request("POST", "/api/demo/unlock", {"password": DEMO_PASSWORD})
        self.assertNotIn(DEMO_PASSWORD.encode(), raw)


class TheHiddenFlag(unittest.TestCase):
    def test_the_flag_is_not_in_the_help_text(self):
        out = subprocess.run([sys.executable, "-m", "eval_coach", "--help"], cwd=ROOT / "app", capture_output=True,
                             text=True, timeout=60).stdout
        self.assertNotIn("demo", out.lower())


if __name__ == "__main__":
    unittest.main()
