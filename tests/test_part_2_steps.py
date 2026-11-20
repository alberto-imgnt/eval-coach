"""Part 2 in the engine: the course order and locking, the three step kinds, their gates, files and the reveal.

No CLI is started anywhere in Part 2, so the fake terminal must record no start.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import course_helpers as ch
import helpers
from helpers import FakeTerminal
from test_http_course import CourseServer

from eval_coach import criteria_steps, import_checks, parsers, project, resources, state
from eval_coach.engine import Engine, EngineError

ROWS = [
    {"requirement": "It is under 150 words", "criterion": "The update is short", "type": "format",
     "threshold": "Word count under 100 passes"},
    {"requirement": "The work is grouped by client", "criterion": "Work is grouped by client", "type": "format",
     "threshold": "Passes if the labels Alpha and Beta both appear"},
    {"requirement": "It calls out the blocker", "criterion": "The blocker is named", "type": "content",
     "threshold": 'Passes if the word "stuck" appears'},
]
TICKS = {"traces": True, "distinct": True}
CHOICES = {"C1": "had", "C2": "missed", "C3": "different", "C4": "vague", "C5": "had", "C6": "had"}
REFERENCE_THRESHOLD = "Word count under 150 passes"


def rows_with(**changes):
    return [dict(row, **changes) for row in ROWS]


class PartTwoBase(ch.CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()

    def view(self, step=None):
        return self.engine.get_state(step=step, part=None if step else "part-2")

    def detail(self, step):
        return self.engine.get_state(step=step)["step"]

    def data(self, step):
        return self.detail(step)["data"]

    def done(self):
        return list(self.engine.progress["parts"].get("part-2", {}).get("done", []))

    def record(self, step):
        return self.engine.progress["parts"]["part-2"]["steps"][step]

    def status(self, item):
        return next(x["status"] for x in self.view()["course"] if x["id"] == item)

    def check(self, step):
        self.engine.step_check(step)
        return self.engine._step(step)["last_check"]

    def file_text(self):
        return self.paths.part2_file("test_cases").read_text(encoding="utf-8")

    def do_draft(self, rows=None, ticks=TICKS):
        self.engine.step_submit("draft", {"rows": ROWS if rows is None else rows, "checks": dict(ticks)})
        return self.check("draft")

    def do_thresholds(self):
        self.engine.step_submit("thresholds", {"rows": ROWS, "checks": {"script_test": True}})
        return self.check("thresholds")

    def do_test_file(self):
        self.engine.step_submit("test-file", {"build": True})
        return self.check("test-file")

    def reach(self, item):
        """Finish everything before `item`, in order."""
        for kind, name in state.PART_2.course:
            if name == item:
                return
            if kind == "lesson":
                self.finish(name)
            else:
                {"draft": self.do_draft, "thresholds": self.do_thresholds, "test-file": self.do_test_file,
                 "reference": lambda: None}[name]()
                self.assertEqual(self.done()[-1], name)


class CourseOrderAndLocking(PartTwoBase):
    def test_the_course_lists_the_eight_items_in_order(self):
        course = self.view()["course"]
        self.assertEqual([(x["kind"], x["id"]) for x in course], list(state.PART_2.course))
        self.assertEqual([item for _, item in state.PART_2.course],
                         ["p2-mission", "p2-criteria", "draft", "p2-thresholds", "thresholds", "p2-testfile",
                          "test-file", "reference"])
        self.assertEqual([s["id"] for s in self.view()["steps"]], ["draft", "thresholds", "test-file", "reference"])

    def test_ids_are_unique_across_parts_and_no_retired_id_is_used(self):
        self.assertEqual(state.duplicate_ids(), [])
        self.assertNotIn("compare", state.PART_2.step_ids)

    def test_only_the_mission_is_active_at_first_and_parts_are_independent(self):
        self.assertEqual([x["id"] for x in self.view()["course"] if x["status"] == "active"], ["p2-mission"])
        self.assertEqual(self.engine.get_state()["course"][0]["status"], "active")  # Part 3 is untouched

    def test_a_step_after_a_lesson_is_locked_until_the_lesson_is_done_and_names_it(self):
        self.reach("p2-thresholds")
        self.assertEqual(self.status("thresholds"), "locked")
        error = self.assert_code("step_locked", self.engine.step_submit, "thresholds", {"checks": {"script_test": True}})
        self.assertEqual(error.message, self.engine.lesson_text["ui"]["locked_tip"])
        self.finish("p2-thresholds")
        self.assertEqual(self.status("thresholds"), "active")

    def test_a_locked_step_is_refused_and_changes_nothing(self):
        before = self.paths.progress_file.read_bytes()
        for step in state.PART_2.step_ids:
            with self.subTest(step=step):
                self.assert_code("step_locked", self.engine.get_state, step=step)
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertFalse(self.paths.part2.exists())

    def test_old_progress_loads_with_part_two_not_started_and_a_stored_block_is_completed(self):
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        data["parts"] = {"part-2": {"done": [], "steps": {"draft": {"checks": {"traces": True}}}}}
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        loaded = state.load_progress(self.paths.progress_file)
        draft = loaded["parts"]["part-2"]["steps"]["draft"]
        self.assertEqual(draft["checks"], {"traces": True, "distinct": False})
        self.assertIn("reference", loaded["parts"]["part-2"]["steps"])
        data.pop("parts")
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        view = self.new_engine().get_state(part="part-2")
        row = next(p for p in view["series"]["parts"] if p["id"] == "part-2")
        self.assertEqual((row["state"], row["done"], row["total"]), ("not_started", 0, 8))

    def test_the_part_block_is_made_on_first_use_with_the_default_records(self):
        self.assertNotIn("part-2", self.engine.progress["parts"])
        self.reach("draft")
        self.engine.step_submit("draft", {"checks": {"traces": True}})
        block = self.engine.progress["parts"]["part-2"]
        self.assertEqual((block["done"], set(block["steps"])), ([], set(state.PART_2.step_ids)))

    def test_step_questions_follow_the_usual_rules_and_never_gate(self):
        self.reach("draft")
        self.assert_code("step_question_locked", self.engine.step_question_answer, "draft", "a")
        self.assertTrue(self.do_draft()["ok"])
        question = self.detail("draft")["question"]
        self.assertIsNotNone(question)
        self.assertEqual(self.status("p2-thresholds"), "active")


class Worksheet(PartTwoBase):
    def setUp(self):
        super().setUp()
        self.reach("draft")

    def test_the_view_has_the_scenario_the_five_requirements_and_no_cli(self):
        detail = self.detail("draft")
        self.assertEqual((detail["kind"], detail["cli"]), ("criteria_table", None))
        data = detail["data"]
        self.assertEqual(len(data["requirements"]), 5)
        self.assertEqual(len(data["scenario"]["requirements"]), 5)
        self.assertEqual((data["rows"], data["saved"], data["show_threshold"]), ([], False, False))
        self.assertTrue(data["rough_notes"])
        self.assertEqual([t["checked"] for t in data["ticks"]], [False, False])

    def test_the_requirements_are_the_same_five_as_part_ones_scenario(self):
        part_one = json.loads(resources.read_text("content/part-1-steps.json"))["steps"]["cold"]["scenario"]
        self.assertEqual(self.data("draft")["requirements"], part_one["requirements"])

    def test_save_writes_the_worksheet_and_reopening_shows_the_rows(self):
        self.engine.step_submit("draft", {"rows": ROWS})
        saved = json.loads(self.paths.part2_file("worksheet").read_text(encoding="utf-8"))
        self.assertEqual(saved["rows"], ROWS)
        self.assertEqual(self.data("draft")["rows"], ROWS)
        self.assertTrue(self.data("draft")["saved"])

    def test_the_ticks_are_saved_as_the_participant_works_without_touching_the_rows(self):
        self.engine.step_submit("draft", {"rows": ROWS})
        self.engine.step_submit("draft", {"checks": {"traces": True}})
        self.assertEqual(self.record("draft")["checks"], {"traces": True, "distinct": False})
        self.assertEqual(self.data("draft")["rows"], ROWS)
        self.engine.step_submit("draft", {"checks": {"traces": False}})
        self.assertFalse(self.record("draft")["checks"]["traces"])

    def test_fields_are_one_plain_line_and_limits_are_enforced(self):
        self.engine.step_submit("draft", {"rows": [{"requirement": "  a \n b\t", "criterion": "x" * 900, "type": "",
                                                   "threshold": ""}]})
        row = self.data("draft")["rows"][0]
        self.assertEqual(row["requirement"], "a b")
        self.assertEqual(len(row["criterion"]), criteria_steps.MAX_CELL)
        self.engine.step_submit("draft", {"rows": [dict(ROWS[0])] * criteria_steps.MAX_ROWS})
        self.assertEqual(len(self.data("draft")["rows"]), criteria_steps.MAX_ROWS)

    def test_bad_input_is_refused_with_the_steps_words_and_nothing_is_written(self):
        words = json.loads(resources.read_text("content/part-2-steps.json"))["steps"]["draft"]["messages"]["bad_rows"]
        bad = [{"rows": "x"}, {"rows": [1]}, {"rows": [dict(ROWS[0], type="other")]},
               {"rows": [dict(ROWS[0], criterion=5)]}, {"rows": [dict(ROWS[0])] * (criteria_steps.MAX_ROWS + 1)},
               {"checks": {"nope": True}}, {"checks": {"traces": "yes"}}, {"checks": []}]
        for body in bad:
            with self.subTest(body=str(body)[:50]):
                self.assertEqual(self.assert_code("bad_input", self.engine.step_submit, "draft", body).message, words)
        self.assert_code("bad_input", self.engine.step_submit, "draft", {})
        self.assert_code("bad_input", self.engine.step_submit, "draft", ["rows"])
        self.assertFalse(self.paths.part2_file("worksheet").exists())

    def test_the_gate_names_each_missing_piece(self):
        self.engine.step_submit("draft", {"rows": ROWS[:2]})
        result = self.check("draft")
        self.assertEqual([i["ok"] for i in result["items"]], [False, True, False, True, False, False])
        self.assertIn("1 more", result["items"][0]["detail"])
        self.assertIn("2 saved", result["items"][0]["detail"])
        self.assertIn("answer says", result["items"][2]["detail"])
        self.assertIn("first self-check", result["items"][4]["detail"])

    def test_a_row_with_a_missing_piece_is_named(self):
        rows = [dict(ROWS[0]), dict(ROWS[1], requirement=""), dict(ROWS[2], criterion="")]
        result = self.do_draft(rows)
        self.assertFalse(result["ok"])
        detail = next(i["detail"] for i in result["items"] if i["label"] == "Every row complete")
        self.assertIn("rows 2 and 3", detail)

    def test_a_missing_type_counts_as_incomplete(self):
        result = self.do_draft(rows_with(type=""))
        self.assertIn("rows 1, 2 and 3", next(i["detail"] for i in result["items"] if i["label"] == "Every row complete"))

    def test_a_repeated_criterion_is_named_ignoring_spacing_and_capitals(self):
        rows = [dict(ROWS[0]), dict(ROWS[1], criterion="  THE   update is   short "), dict(ROWS[2])]
        result = self.do_draft(rows)
        self.assertFalse(result["ok"])
        detail = next(i["detail"] for i in result["items"] if i["label"] == "No repeated criterion")
        self.assertIn("rows 1 and 2", detail)

    def test_every_row_of_type_format_has_no_content_criterion(self):
        result = self.do_draft(rows_with(type="format"))
        self.assertFalse(result["ok"])
        self.assertFalse(next(i["ok"] for i in result["items"] if i["label"] == "One about content"))

    def test_a_missing_tick_fails_and_names_which(self):
        result = self.do_draft(ticks={"traces": True, "distinct": False})
        self.assertFalse(result["ok"])
        self.assertEqual([i["ok"] for i in result["items"]], [True, True, True, True, True, False])
        self.assertIn("second", result["items"][5]["detail"])

    def test_a_complete_worksheet_passes_and_the_step_is_done_and_refuses_more(self):
        self.assertTrue(self.do_draft()["ok"])
        self.assertEqual(self.done(), ["draft"])
        self.assert_code("step_done", self.engine.step_submit, "draft", {"rows": ROWS})
        self.assert_code("step_done", self.engine.step_check, "draft")
        self.assertEqual(self.detail("draft")["status"], "done")
        self.assertEqual(self.data("draft")["rows"], ROWS)

    def test_part_one_marks_are_shown_when_they_exist_and_read_only(self):
        self.assertIsNone(self.data("draft")["part1"])
        part_one = state.PART_1
        block = self.engine._progress_of(part_one)
        block["steps"]["score"].update(answers={"r1": "yes", "r2": "no"}, gap="No blocker ask")
        self.engine._save()
        before = self.paths.progress_file.read_text(encoding="utf-8")
        mine = self.data("draft")["part1"]
        self.assertEqual(mine["gap"], "No blocker ask")
        self.assertEqual([(m["id"], m["answer"]) for m in mine["marks"]],
                         [("r1", "yes"), ("r2", "no"), ("r3", ""), ("r4", ""), ("r5", "")])
        self.assertEqual(self.paths.progress_file.read_text(encoding="utf-8"), before)
        self.assertFalse(self.paths.part1.exists())

    def test_nothing_in_part_two_starts_a_cli_or_a_checker(self):
        self.do_draft()
        self.assert_code("not_supported", self.engine.step_start, "draft")
        self.assert_code("not_supported", self.engine.step_send, "draft")
        self.assertEqual(self.terminal.starts, [])


class Thresholds(PartTwoBase):
    def setUp(self):
        super().setUp()
        self.reach("thresholds")
        self.rows = rows_with(threshold="")
        self.engine.step_submit("thresholds", {"rows": self.rows})  # only the threshold column is written

    def test_the_same_rows_are_shown_with_an_empty_threshold_for_each(self):
        self.engine.step_submit("thresholds", {"rows": [dict(r, threshold="") for r in ROWS]})
        data = self.data("thresholds")
        self.assertTrue(data["show_threshold"])
        self.assertEqual([r["criterion"] for r in data["rows"]], [r["criterion"] for r in ROWS])
        self.assertEqual([r["threshold"] for r in data["rows"]], ["", "", ""])

    def test_only_the_threshold_column_changes_here(self):
        changed = [dict(r, criterion="Changed", requirement="Changed", type="content", threshold=f"T{i}")
                   for i, r in enumerate(ROWS)]
        self.engine.step_submit("thresholds", {"rows": changed})
        saved = self.data("thresholds")["rows"]
        self.assertEqual([r["threshold"] for r in saved], ["T0", "T1", "T2"])
        self.assertEqual([(r["criterion"], r["requirement"], r["type"]) for r in saved],
                         [(r["criterion"], r["requirement"], r["type"]) for r in ROWS])
        self.assert_code("bad_input", self.engine.step_submit, "thresholds", {"rows": changed[:2]})
        self.assert_code("bad_input", self.engine.step_submit, "thresholds", {"rows": changed + changed[:1]})

    def test_a_missing_threshold_is_named_and_the_tick_is_required(self):
        rows = [dict(ROWS[0]), dict(ROWS[1], threshold=""), dict(ROWS[2])]
        self.engine.step_submit("thresholds", {"rows": rows})
        result = self.check("thresholds")
        self.assertEqual([i["ok"] for i in result["items"]], [False, False])
        self.assertIn("row 2", result["items"][0]["detail"])
        self.engine.step_submit("thresholds", {"rows": ROWS, "checks": {"script_test": False}})
        result = self.check("thresholds")
        self.assertEqual([i["ok"] for i in result["items"]], [True, False])
        self.assertIn("script test", result["items"][1]["detail"])

    def test_not_checked_with_a_reason_counts_as_written(self):
        rows = [dict(ROWS[0]), dict(ROWS[1]), dict(ROWS[2], threshold="Not checked: it needs a person to judge")]
        self.engine.step_submit("thresholds", {"rows": rows, "checks": {"script_test": True}})
        self.assertTrue(self.check("thresholds")["ok"])
        self.assertEqual(self.data("thresholds")["notes"], [])

    def test_a_vague_word_gets_a_note_that_never_blocks_and_quoted_words_are_not_flagged(self):
        rows = [dict(ROWS[0], threshold="The update is clear"), dict(ROWS[1], threshold='Contains the phrase "clear"'),
                dict(ROWS[2], threshold="Not checked: tone is good")]
        self.engine.step_submit("thresholds", {"rows": rows, "checks": {"script_test": True}})
        notes = self.data("thresholds")["notes"]
        self.assertEqual([n["row"] for n in notes], [1])
        self.assertIn("clear", notes[0]["text"])
        self.assertIn("a number", notes[0]["text"])
        self.assertIn("Not checked:", notes[0]["text"])
        self.assertTrue(self.check("thresholds")["ok"])

    def test_the_thresholds_step_passes_and_is_done(self):
        self.assertTrue(self.do_thresholds()["ok"])
        self.assertEqual(self.done(), ["draft", "thresholds"])
        self.assert_code("step_done", self.engine.step_submit, "thresholds", {"rows": ROWS})


class TestCaseFile(PartTwoBase):
    def setUp(self):
        super().setUp()
        self.reach("test-file")

    def test_build_writes_the_layout_part_three_reads_with_the_participants_own_words(self):
        self.engine.step_submit("test-file", {"build": True})
        text = self.file_text()
        self.assertTrue(text.startswith("# Test cases: "))
        self.assertNotIn("\r", text)
        criteria = parsers.parse_test_cases(text)
        self.assertEqual([c["id"] for c in criteria], ["C1", "C2", "C3"])
        self.assertEqual([c["name"] for c in criteria], [r["criterion"] for r in ROWS])
        self.assertEqual([c["requirement"] for c in criteria], [r["requirement"] for r in ROWS])
        self.assertEqual([c["threshold"] for c in criteria], [r["threshold"] for r in ROWS])
        self.assertEqual(list(import_checks.criterion_types(text).values()), ["Format", "Format", "Content"])
        self.assertIn(part_notes_line(), text)

    def test_the_built_file_passes_part_threes_own_file_checks(self):
        self.engine.step_submit("test-file", {"build": True})
        result = import_checks.analyze(None, self.file_text())
        self.assertTrue(result["ready"], result["blocking"])
        self.assertEqual([c["id"] for c in result["criteria"]], ["C1", "C2", "C3"])

    def test_the_supporting_list_section_is_an_example_line_with_no_reference_word(self):
        self.engine.step_submit("test-file", {"build": True})
        lists = self.file_text().split("## Supporting lists", 1)[1]
        reference_lists = resources.read_text(project.NORTHWIND_TEST_CASES).split("## Supporting lists", 1)[1]
        for word in ("excited", "thrilled", "proud", "amazing", "Blocker:", "Need:", "Contoso"):
            self.assertIn(word, reference_lists)
            self.assertNotIn(word, lists)

    def test_building_asks_before_replacing_saved_text_and_keeps_it_if_declined(self):
        self.engine.step_submit("test-file", {"text": "My own file."})
        error = self.assert_code("confirm_replace", self.engine.step_submit, "test-file", {"build": True})
        self.assertTrue(error.message)
        self.assertEqual(self.file_text(), "My own file.")
        self.engine.step_submit("test-file", {"build": True, "replace": True})
        self.assertIn("### C1", self.file_text())

    def test_a_blank_saved_file_is_replaced_without_asking(self):
        self.engine.step_submit("test-file", {"text": "  \n"})
        self.engine.step_submit("test-file", {"build": True})
        self.assertIn("### C1", self.file_text())

    def test_build_needs_a_worksheet(self):
        self.paths.part2_file("worksheet").unlink()
        self.assert_code("no_worksheet", self.engine.step_submit, "test-file", {"build": True})
        self.assertFalse(self.paths.part2_file("test_cases").exists())

    def test_save_writes_exactly_the_text(self):
        self.engine.step_submit("test-file", {"text": "# Mine\n\nLine"})
        self.assertEqual(self.file_text(), "# Mine\n\nLine")
        self.assertEqual(self.data("test-file")["text"], "# Mine\n\nLine")

    def test_bad_input_is_refused(self):
        for body in ({}, {"text": 5}, {"text": "x" * 60000}, {"text": "a", "build": True}, {"build": "yes"},
                     {"build": False}, {"replace": True}, {"other": 1}):
            with self.subTest(body=str(body)[:40]):
                self.assert_code("bad_input", self.engine.step_submit, "test-file", body)
        self.assertFalse(self.paths.part2_file("test_cases").exists())

    def test_an_unsaved_file_fails_the_gate_and_the_other_checks_pass_for_the_built_file(self):
        self.assertFalse(self.check("test-file")["ok"])
        self.assertEqual(self.done()[-1], "thresholds")
        self.assertTrue(self.do_test_file()["ok"])
        self.assertEqual(self.done()[-1], "test-file")

    def test_the_blocking_findings(self):
        cases = {
            "no_input": FILE.replace("## Test input\n- notes\n\n", ""),
            "few_criteria": FILE.replace(C3, "").replace(C2, ""),
            "no_criteria": "# Title\n\n## Test input\n- notes\n",
            "no_content_criterion": FILE.replace('Passes if the word "stuck" appears', "Word count under 90 passes").replace(
                "Passes if the labels Alpha and Beta both appear", "Word count over 10 passes"),
        }
        for code, text in cases.items():
            with self.subTest(code=code):
                self.engine.step_submit("test-file", {"text": text})
                blocking = [f["code"] for f in self.data("test-file")["findings"]["blocking"]]
                self.assertIn(code, blocking)
                result = self.check("test-file")
                self.assertFalse(result["ok"])
                self.assertTrue(all(i["detail"] for i in result["items"] if not i["ok"]))

    def test_the_two_criteria_message_says_how_many_are_missing_and_shows_the_heading_layout(self):
        self.engine.step_submit("test-file", {"text": FILE.replace(C3, "")})
        message = next(f["message"] for f in self.data("test-file")["findings"]["blocking"]
                       if f["code"] == "few_criteria")
        self.assertIn("2 of the 3", message)
        self.assertIn("Add 1 more", message)
        self.assertIn("### C3:", message)
        self.assertNotIn("press Check my files", message.lower())

    def test_notes_never_block(self):
        text = FILE.replace("Word count under 100 passes", "The update is clear").replace(
            "- Requirement: Short\n", "")
        self.engine.step_submit("test-file", {"text": text})
        findings = self.data("test-file")["findings"]
        self.assertEqual(findings["blocking"], [])
        self.assertEqual({n["code"] for n in findings["notes"]}, {"vague", "no_requirement"})
        self.assertTrue(self.check("test-file")["ok"])
        self.assertIn("“clear”", next(n["message"] for n in findings["notes"] if n["code"] == "vague"))

    def test_a_missing_threshold_is_a_note_and_not_checked_is_not(self):
        text = FILE.replace("Word count under 100 passes", "").replace("Passes if the labels Alpha and Beta both appear",
                                                                       "Not checked: needs a person")
        self.engine.step_submit("test-file", {"text": text})
        notes = self.data("test-file")["findings"]["notes"]
        self.assertEqual([(n["code"], n["criterion"]) for n in notes], [("missing_threshold", "C1")])

    def test_a_threshold_that_names_a_list_with_no_entry_is_a_note_and_an_entry_clears_it(self):
        text = FILE.replace("Word count under 100 passes", "Passes if no word from the banned list appears")
        self.engine.step_submit("test-file", {"text": text})
        notes = self.data("test-file")["findings"]["notes"]
        self.assertEqual([(n["code"], n["criterion"]) for n in notes], [("list_missing", "C1")])
        self.assertIn("Supporting lists", notes[0]["message"])
        self.engine.step_submit("test-file", {"text": text + "- Banned words: aaa, bbb\n"})
        self.assertEqual(self.data("test-file")["findings"]["notes"], [])

    def test_a_file_written_with_crlf_still_checks(self):
        self.engine.step_submit("test-file", {"text": FILE.replace("\n", "\r\n")})
        self.assertEqual(self.data("test-file")["findings"], {"blocking": [], "notes": []})
        self.assertTrue(self.check("test-file")["ok"])

    def test_an_existing_file_is_never_replaced_by_checking_or_viewing(self):
        self.engine.step_submit("test-file", {"text": FILE})
        self.check("test-file")
        self.detail("test-file")
        self.assertEqual(self.file_text(), FILE)

    def test_part_threes_own_test_cases_file_is_untouched(self):
        own = self.paths.test_cases.read_bytes()
        self.do_test_file()
        self.assertEqual(self.paths.test_cases.read_bytes(), own)
        self.assertNotEqual(self.paths.part2_file("test_cases"), self.paths.test_cases)


def part_notes_line():
    return resources.read_text(project.PART1_NOTES).splitlines()[0]


C1 = "### C1: Short\n- Requirement: Short\n- Type: Format\n- Threshold: Word count under 100 passes\n\n"
C2 = ("### C2: Grouped\n- Requirement: Grouped\n- Type: Format\n"
      "- Threshold: Passes if the labels Alpha and Beta both appear\n\n")
C3 = '### C3: Blocker\n- Requirement: Blocker\n- Type: Content\n- Threshold: Passes if the word "stuck" appears\n\n'
FILE = "# Test cases: Example\n\n## Test input\n- notes\n\n## Criteria\n\n" + C1 + C2 + C3 + \
       "## Supporting lists\n- Example: Terms to avoid: aaa\n"


class Reference(PartTwoBase):
    def setUp(self):
        super().setUp()
        self.reach("reference")

    def test_the_reference_rows_appear_only_once_test_file_is_done(self):
        data = self.data("reference")
        self.assertTrue(data["revealed"])
        self.assertEqual([r["id"] for r in data["reference"]], ["C1", "C2", "C3", "C4", "C5", "C6"])
        self.assertEqual(data["reference"][2]["type"], "Content")
        self.assertTrue(any("Banned words" in line for line in data["lists"]))
        self.assertEqual([o["id"] for o in data["options"]], ["had", "missed", "different", "vague"])
        self.assertEqual([m["id"] for m in data["mine"]], ["C1", "C2", "C3"])

    def test_detail_returns_nothing_of_the_reference_before_the_reveal(self):
        handler = state.STEP_KINDS["reveal_compare"]
        self.engine.progress["parts"]["part-2"]["done"].remove("test-file")
        data = handler.detail(self.engine, "reference")["data"]
        self.assertEqual((data["revealed"], data["reference"], data["lists"], data["choices"]), (False, [], [], {}))

    def test_the_gate_names_what_is_missing_and_passes_with_every_choice(self):
        self.engine.step_submit("reference", {"choices": {"C1": "had"}})
        result = self.check("reference")
        self.assertFalse(result["ok"])
        self.assertIn("Grouped by client", result["items"][0]["detail"])
        self.engine.step_submit("reference", {"choices": CHOICES})
        self.assertTrue(self.check("reference")["ok"])
        self.assertEqual(self.done()[-1], "reference")
        self.assertEqual(self.record("reference")["choices"], CHOICES)

    def test_bad_choices_are_refused(self):
        for body in ({"choices": {"C9": "had"}}, {"choices": {"C1": "great"}}, {"choices": ["had"]}, {},
                     {"choices": {}, "build": True}):
            with self.subTest(body=str(body)):
                self.assert_code("bad_input", self.engine.step_submit, "reference", body)

    def test_the_file_can_still_be_edited_here_and_the_gate_does_not_change(self):
        self.engine.step_submit("reference", {"choices": CHOICES})
        self.engine.step_submit("reference", {"text": FILE})
        self.assertEqual(self.file_text(), FILE)
        self.assertEqual(self.data("reference")["findings"], {"blocking": [], "notes": []})
        self.engine.step_submit("reference", {"text": "Broken"})
        self.assertTrue(self.data("reference")["findings"]["blocking"])
        self.assertTrue(self.check("reference")["ok"])

    def test_progress_never_holds_reference_text_or_worksheet_text(self):
        self.engine.step_submit("reference", {"choices": CHOICES})
        self.check("reference")
        saved = self.paths.progress_file.read_text(encoding="utf-8")
        reference = parsers.parse_test_cases(resources.read_text(project.NORTHWIND_TEST_CASES))
        for row in reference:
            for text in (row["name"], row["threshold"]):
                self.assertNotIn(text, saved)
        for row in ROWS:
            for text in (row["criterion"], row["threshold"]):
                self.assertNotIn(text, saved)
        self.assertNotIn("excited", saved)


class BeforeSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-p2-gate-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home, self.project = self.tmp / "home", self.tmp / "project"
        self.terminal = FakeTerminal()
        self.engine = helpers.make_engine(self.home, self.terminal, poll_interval=0.01, lessons=ch.bundled_course())
        self.addCleanup(self.engine.shutdown)
        self.engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.paths = project.Paths(self.home, self.project)

    def code_of(self, fn, *args):
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        return ctx.exception.code

    def test_the_mission_opens_and_the_steps_are_refused(self):
        view = self.engine.get_state(part="part-2")
        self.assertEqual(view["course"][0]["status"], "active")
        self.assertEqual(self.engine.lesson_view("p2-mission")["lesson"]["status"], "active")
        before = self.paths.progress_file.read_bytes()
        for step in state.PART_2.step_ids:
            with self.subTest(step=step):
                self.assertEqual(self.code_of(self.engine.get_state, step), "step_locked")
        self.assertEqual(self.paths.progress_file.read_bytes(), before)

    def test_save_and_check_are_refused_before_setup_and_nothing_is_written(self):
        before = self.paths.progress_file.read_bytes()
        bodies = {"draft": {"rows": ROWS}, "thresholds": {"rows": ROWS}, "test-file": {"text": "x"},
                  "reference": {"choices": {}}}
        for step, body in bodies.items():
            for name, args in (("submit", (body,)), ("check", ())):
                with self.subTest(step=step, call=name):
                    self.assertEqual(self.code_of(getattr(self.engine, f"step_{name}"), step, *args),
                                     "preflight_incomplete")
        self.assertEqual(self.code_of(self.engine.step_question_answer, "draft", "a"), "step_question_locked")
        self.assertEqual(self.terminal.starts, [])
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertFalse(self.paths.part2.exists())


class NoLeakBeforeTheReveal(PartTwoBase):
    """Nothing before `test-file` is done holds a reference criterion beyond the two worked examples."""

    def reference_phrases(self):
        text = resources.read_text(project.NORTHWIND_TEST_CASES)
        rows = parsers.parse_test_cases(text)
        phrases = [row["threshold"] for row in rows[1:]] + ["Teams, not email", "Factual tone", "Uses the rough notes"]
        return phrases + ["excited", "thrilled", "delighted", "happy to report", "Sincerely"]

    def test_no_response_before_the_gate_holds_a_reference_criterion_threshold_or_list_word(self):
        self.reach("test-file")
        bodies = []
        for step in state.PART_2.step_ids:
            try:
                bodies.append(json.dumps(self.engine.get_state(step=step)))
            except EngineError as exc:  # `reference` is locked, so nothing of it is returned at all
                self.assertEqual(exc.code, "step_locked")
        bodies += [json.dumps(self.engine.lesson_view(lesson)) for lesson in
                   ("p2-mission", "p2-criteria", "p2-thresholds", "p2-testfile")]
        bodies += [json.dumps(self.engine.get_state(part="part-2")), json.dumps(self.engine.get_state())]
        body = "\n".join(bodies).lower()
        for phrase in self.reference_phrases():
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase.lower(), body)


class OverHttp(CourseServer):
    def setUp(self):
        super().setUp()
        status, body = self.post("/api/setup", {"project_path": str(self.tmp / "project"), "cli_command": "mycli",
                                                "starter": "northwind"})
        self.assertEqual(status, 200, body)

    def finish_lessons(self, upto):
        for kind, item in state.PART_2.course:
            if item == upto:
                return
            if kind == "lesson":
                for activity in self.course.get(item)["activities"]:
                    answer = ch.correct_answer(activity)
                    if answer is not None:
                        self.answer(item, activity["id"], answer)
                status, body = self.post("/api/lesson/complete", {"lesson": item, "part": "part-2"})
                self.assertEqual(status, 200, body)

    def test_a_step_post_returns_the_steps_own_part_and_saving_works_over_the_routes(self):
        self.finish_lessons("draft")
        status, body = self.post("/api/step/submit", {"step": "draft", "data": {"rows": ROWS, "checks": TICKS}})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["state"]["step"]["id"], "draft")
        self.assertEqual([s["id"] for s in body["state"]["steps"]], ["draft", "thresholds", "test-file", "reference"])
        status, body = self.post("/api/step/check", {"step": "draft"})
        self.assertEqual(status, 200, body)
        self.assertTrue(body["state"]["step"]["last_check"]["ok"])

    def test_before_the_gate_no_route_returns_a_reference_threshold(self):
        self.finish_lessons("draft")
        phrase = REFERENCE_THRESHOLD.lower()
        for path in ("/api/state?step=reference", "/api/state?step=draft", "/api/state?part=part-2"):
            status, raw = self.get(path)
            self.assertEqual(status, 400 if path.endswith("reference") else 200)
            self.assertNotIn(phrase, json.dumps(raw).lower())
