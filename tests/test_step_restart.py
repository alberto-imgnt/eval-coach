"""Starting a finished step again (spec step-restart): what a restart clears, keeps and backs up, and when it refuses.

Parts 1 and 2 register a restart plan; Part 3 does not. The AI is the fake terminal, so nothing real runs.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from unittest import mock

import course_helpers as ch
from helpers import FakeTerminal
from test_part_1_steps import PartOneBase
from test_part_2_steps import CHOICES, ROWS, PartTwoBase

from eval_coach import criteria_steps, project, reset, state
from eval_coach.engine import Engine

PART_1_FILES = ["output-cold.txt", "output-framework.txt", "own-after.md", "own-before.md", "prompt-cold.md",
                "prompt-framework.md"]


def names(folder):
    folder = Path(folder)
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def backup_files(home):
    root = Path(home) / reset.BACKUP_NAME
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()) if root.is_dir() else []


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PartOneRestart(PartOneBase):
    def finish_part(self):
        self.reach("own")
        self.engine.step_submit("own", {"before": "Write my report.", "after": "Role: analyst\nTask: my report",
                                        "labels": "RTCC"})
        self.assertEqual(self.done(), list(state.PART_1.step_ids))

    def restart(self, step):
        return self.engine.step_restart(step, True)

    def part_folder(self):
        return names(self.paths.part1)

    def test_every_finished_step_offers_a_restart_that_names_the_steps_it_clears(self):
        self.finish_part()
        for step, count in (("cold", 5), ("score", 4), ("rewrite", 3), ("rescore", 2), ("own", 1)):
            view = self.detail(step)["restart"]
            with self.subTest(step=step):
                self.assertTrue(view["available"])
                self.assertEqual(len(view["steps"]), count)
                self.assertEqual(view["backup_folder"], str(self.home / reset.BACKUP_NAME))
        self.assertEqual(self.detail("score")["restart"]["steps_text"],
                         "Score what you got, Try a framework, Score it again and Use it on your own work")

    def test_an_unfinished_a_locked_and_a_part_three_step_offer_no_restart_and_refuse_it(self):
        self.reach("rewrite")
        self.assertEqual(self.detail("rewrite")["restart"], {"available": False})
        self.assertEqual(self.detail("own")["restart"], {"available": False})  # a locked preview
        before = self.paths.progress_file.read_bytes()
        self.assert_code("restart_not_done", self.engine.step_restart, "rewrite", True)
        self.assert_code("restart_not_done", self.engine.step_restart, "own", True)
        self.assert_code("restart_unavailable", self.engine.step_restart, "generate", True)
        self.assert_code("unknown_step", self.engine.step_restart, "no-such-step", True)
        self.assert_code("confirm_required", self.engine.step_restart, "cold", None)
        self.assert_code("confirm_required", self.engine.step_restart, "cold", "yes")
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertFalse((self.home / reset.BACKUP_NAME).exists())

    def test_restarting_cold_clears_the_whole_part_and_moves_every_file_to_the_backup(self):
        self.finish_part()
        result = self.restart("cold")
        self.assertEqual(result["steps"], list(state.PART_1.step_ids))
        self.assertEqual(result["backup_folder"], str(self.home / reset.BACKUP_NAME))
        self.assertIn("start again", result["message"])
        self.assertEqual(self.done(), [])
        self.assertEqual(self.engine.progress["parts"]["part-1"]["steps"], state.new_part_1_steps())
        self.assertEqual(self.part_folder(), [])
        self.assertFalse(self.paths.part1_root.exists() and any(self.paths.part1_root.iterdir()))
        moved = backup_files(self.home)
        for name in PART_1_FILES:
            self.assertIn(f"project/part-1/{name}", moved)
        self.assertEqual(self.status("cold"), "active")
        self.assertEqual(self.status("score"), "locked")

    def test_restarting_rewrite_keeps_cold_and_moves_the_framework_and_own_files(self):
        self.finish_part()
        self.restart("rewrite")
        self.assertEqual(self.done(), ["cold", "score"])
        self.assertEqual(self.part_folder(), ["output-cold.txt", "prompt-cold.md"])
        moved = [n for n in backup_files(self.home) if n.startswith("project/")]
        self.assertEqual(moved, [f"project/part-1/{n}" for n in
                                 ("output-framework.txt", "own-after.md", "own-before.md", "prompt-framework.md")])
        self.assertTrue(self.paths.part1_work("cold").exists())
        self.assertFalse(self.paths.part1_work("rewrite").exists())
        self.assertTrue(self.record("cold")["model_name"])
        self.assertEqual(self.status("rewrite"), "active")

    def test_restarting_score_clears_the_marks_and_what_followed_but_keeps_cold(self):
        self.finish_part()
        self.restart("score")
        self.assertEqual(self.done(), ["cold"])
        self.assertEqual(self.part_folder(), ["output-cold.txt", "prompt-cold.md"])
        self.assertEqual(self.record("score"), state.new_part_1_steps()["score"])
        self.assertEqual(self.data("score")["answered"], 0)
        self.assertEqual(self.data("score")["gap"], "")
        self.assertEqual(self.status("score"), "active")
        preview = self.detail("rewrite")
        self.assertTrue(preview["preview"])  # later steps lock again, and the preview names where the participant is
        self.assertEqual(preview["held_by"]["id"], "score")

    def test_restarting_rescore_and_own_move_only_what_they_made(self):
        self.finish_part()
        self.restart("own")
        self.assertEqual(self.part_folder(), ["output-cold.txt", "output-framework.txt", "prompt-cold.md",
                                              "prompt-framework.md"])
        self.assertEqual(self.done(), ["cold", "score", "rewrite", "rescore"])
        self.assertEqual(self.record("own"), state.new_part_1_steps()["own"])
        before = backup_files(self.home)
        self.restart("rescore")  # nothing left to move: the earlier backup stays as it is
        self.assertEqual(backup_files(self.home), before)
        self.assertEqual(self.done(), ["cold", "score", "rewrite"])
        self.assertEqual(self.record("rescore")["answers"], {})

    def test_a_step_can_be_done_again_and_the_ai_window_opens_by_itself_again(self):
        self.finish_part()
        starts = len(self.terminal.starts)
        self.restart("cold")
        self.assertFalse(self.record("cold")["auto_started"])
        self.do_cold()
        self.assertEqual(len(self.terminal.starts), starts + 1)
        self.assertEqual(self.done(), ["cold"])

    def test_a_running_ai_window_is_stopped_before_anything_is_cleared(self):
        self.finish_part()
        self.terminal.running = True
        stops = self.terminal.stops
        self.restart("score")
        self.assertGreater(self.terminal.stops, stops)
        self.assertFalse(self.terminal.running)

    def test_quick_check_answers_of_the_cleared_steps_are_cleared_and_earlier_ones_stay(self):
        self.finish_part()
        for step in ("cold", "score", "rewrite"):
            self.engine.step_question_answer(step, ch.correct_option(self.course.step_checks[step]))
        checks = self.engine._lessons_block()["step_checks"]
        self.assertTrue(all(checks[s]["passed"] for s in ("cold", "score", "rewrite")))
        self.restart("score")
        checks = self.engine._lessons_block()["step_checks"]
        self.assertEqual(sorted(checks), ["cold"])
        self.assertIsNone(self.detail("score")["question"])  # not finished again yet

    def test_other_parts_lessons_setup_and_the_answer_key_are_untouched(self):
        self.finish_part()
        block = state.new_part_progress(state.PART_2)
        block["done"] = ["draft"]
        block["steps"]["draft"]["checks"] = {"traces": True, "distinct": False}
        self.engine.progress["parts"]["part-2"] = block
        part_two_files = self.paths.part2
        part_two_files.mkdir(parents=True, exist_ok=True)
        worksheet = part_two_files / "worksheet.json"
        worksheet.write_text('{"rows": []}', encoding="utf-8")
        self.paths.sealed_key.parent.mkdir(parents=True, exist_ok=True)
        self.paths.sealed_key.write_text("THE KEY", encoding="utf-8")
        self.engine.progress["done"] = ["generate"]
        self.engine._save()
        part_two_before = copy.deepcopy(block)
        lessons_before = copy.deepcopy(self.engine.progress["lessons"]["per_lesson"])
        self.restart("cold")
        self.assertEqual(self.engine.progress["parts"]["part-2"], part_two_before)
        self.assertEqual(self.engine.progress["done"], ["generate"])
        self.assertEqual(self.engine.progress["lessons"]["per_lesson"], lessons_before)
        self.assertEqual(worksheet.read_text(encoding="utf-8"), '{"rows": []}')
        self.assertEqual(self.paths.sealed_key.read_text(encoding="utf-8"), "THE KEY")
        self.assertTrue((self.home / "preflight.json").is_file())
        self.assertEqual(self.engine.progress["cli_command"], "mycli")

    def test_the_backup_replaces_an_earlier_one_and_keeps_only_the_newest(self):
        self.finish_part()
        old = self.home / reset.BACKUP_NAME / "project" / "old-reset.txt"
        old.parent.mkdir(parents=True)
        old.write_text("from an earlier reset", encoding="utf-8")
        self.restart("rewrite")
        moved = backup_files(self.home)
        self.assertNotIn("project/old-reset.txt", moved)
        self.assertIn("project/part-1/prompt-framework.md", moved)
        self.assertFalse((self.home / reset.STAGING_NAME).exists())
        self.assertFalse((self.home / reset.OLD_NAME).exists())

    def test_a_move_that_fails_changes_nothing_and_says_so_in_plain_words(self):
        self.finish_part()
        before = copy.deepcopy(self.engine.progress)
        files = {p.name: digest(p) for p in self.paths.part1.iterdir()}
        real = reset.move

        def flaky(source, dest):
            if Path(dest).name == "output-framework.txt" and reset.STAGING_NAME in str(dest):
                raise OSError("the disk is full")
            return real(source, dest)

        with mock.patch.object(reset, "move", flaky):
            error = self.assert_code("reset_backup_failed", self.engine.step_restart, "cold", True)
        self.assertIn("Nothing was changed", error.message)
        self.assertEqual(self.engine.progress, before)
        self.assertEqual({p.name: digest(p) for p in self.paths.part1.iterdir()}, files)
        self.assertTrue(self.paths.part1_work("cold").exists())
        self.assertFalse((self.home / reset.STAGING_NAME).exists())
        self.assertFalse((self.home / reset.BACKUP_NAME).exists())

    def test_a_restart_before_setup_is_refused(self):
        engine = Engine(self.tmp / "other-home", FakeTerminal(), lessons=self.course)
        self.addCleanup(engine.shutdown)
        self.assert_code("not_configured", engine.step_restart, "cold", True)


class PartTwoRestart(PartTwoBase):
    def finish_part(self):
        self.reach("reference")
        self.assertEqual(self.done(), ["draft", "thresholds", "test-file"])

    def restart(self, step):
        return self.engine.step_restart(step, True)

    def part_folder(self):
        return names(self.paths.part2)

    def test_restarting_draft_moves_the_worksheet_and_the_test_file_and_clears_all_four(self):
        self.finish_part()
        worksheet, file_text = self.paths.part2_file("worksheet").read_bytes(), self.file_text()
        result = self.restart("draft")
        self.assertEqual(result["steps"], list(state.PART_2.step_ids))
        self.assertEqual(self.part_folder(), [])
        self.assertEqual(self.done(), [])
        self.assertEqual(self.engine.progress["parts"]["part-2"]["steps"], state.new_part_2_steps())
        root = self.home / reset.BACKUP_NAME / "project" / "part-2"
        self.assertEqual((root / "worksheet.json").read_bytes(), worksheet)
        self.assertEqual((root / "test-cases.md").read_text(encoding="utf-8"), file_text)
        self.assertEqual(self.status("draft"), "active")

    def test_restarting_thresholds_keeps_the_criteria_with_empty_thresholds_and_backs_up_the_original(self):
        self.finish_part()
        original = self.paths.part2_file("worksheet").read_bytes()
        draft_record = copy.deepcopy(self.record("draft"))
        self.restart("thresholds")
        rows = json.loads(self.paths.part2_file("worksheet").read_text(encoding="utf-8"))["rows"]
        self.assertEqual([(r["requirement"], r["criterion"], r["type"]) for r in rows],
                         [(r["requirement"], r["criterion"], r["type"]) for r in ROWS])
        self.assertTrue(all(r["threshold"] == "" for r in rows))
        self.assertEqual(self.part_folder(), ["worksheet.json"])
        root = self.home / reset.BACKUP_NAME / "project" / "part-2"
        self.assertEqual((root / "worksheet.json").read_bytes(), original)
        self.assertTrue((root / "test-cases.md").is_file())
        self.assertEqual(self.done(), ["draft"])
        self.assertEqual(self.record("draft"), draft_record)
        self.assertEqual(self.record("thresholds"), state.new_part_2_steps()["thresholds"])
        self.assertEqual(self.status("thresholds"), "active")
        self.assertEqual([r["threshold"] for r in self.data("thresholds")["rows"]], ["", "", ""])

    def test_restarting_test_file_moves_only_the_test_file_and_reference_only_clears_choices(self):
        self.finish_part()
        self.restart("test-file")
        self.assertEqual(self.part_folder(), ["worksheet.json"])
        self.assertEqual(self.done(), ["draft", "thresholds"])
        self.assertEqual(backup_files(self.home), ["project/part-2/test-cases.md"])
        self.do_test_file()
        self.engine.step_submit("reference", {"choices": CHOICES})
        self.engine.step_check("reference")
        self.assertEqual(self.done(), list(state.PART_2.step_ids))
        before = backup_files(self.home)
        result = self.restart("reference")
        self.assertIsNone(result["backup_folder"])
        self.assertIn("no files to back up", result["message"])
        self.assertEqual(backup_files(self.home), before)  # nothing moved, so the earlier backup stays
        self.assertEqual(self.record("reference")["choices"], {})
        self.assertTrue(self.paths.part2_file("test_cases").is_file())

    def test_part_threes_own_test_file_is_never_touched(self):
        self.finish_part()
        root_file = self.paths.project / "test-cases.md"
        root_file.write_text("Part 3's own file", encoding="utf-8")
        for step in ("draft", "thresholds", "test-file"):
            self.restart(step)
            self.assertEqual(root_file.read_text(encoding="utf-8"), "Part 3's own file")
            self.finish_part_again()

    def finish_part_again(self):
        self.engine.progress["parts"]["part-2"]["done"][:] = []
        self.engine.progress["parts"]["part-2"]["steps"].update(state.new_part_2_steps())
        self.do_draft()
        self.do_thresholds()
        self.do_test_file()

    def test_a_rewrite_that_fails_puts_every_file_back_and_changes_nothing(self):
        self.finish_part()
        before = copy.deepcopy(self.engine.progress)
        files = {p.name: digest(p) for p in self.paths.part2.iterdir()}

        def broken(raw):
            raise OSError("the worksheet could not be written")

        with mock.patch.dict(criteria_steps.REWRITES, {"part-2/worksheet.json": broken}):
            error = self.assert_code("restart_failed", self.engine.step_restart, "thresholds", True)
        self.assertIn("Nothing was changed", error.message)
        self.assertEqual(self.engine.progress, before)
        self.assertEqual({p.name: digest(p) for p in self.paths.part2.iterdir()}, files)
        self.assertFalse((self.home / reset.STAGING_NAME).exists())
        self.assertFalse((self.home / reset.BACKUP_NAME).exists())

    def test_later_steps_lock_again_and_the_view_of_a_cleared_step_is_a_fresh_record(self):
        self.finish_part()
        self.restart("thresholds")
        self.assertTrue(self.detail("test-file")["preview"])
        self.assertEqual(self.detail("test-file")["held_by"]["id"], "thresholds")
        self.assertEqual(self.detail("draft")["restart"]["steps"][0], "Draft your criteria")
        self.assertEqual(self.detail("thresholds")["restart"], {"available": False})
        self.assertFalse(project.Paths(self.home, self.project).part2_file("test_cases").exists())
