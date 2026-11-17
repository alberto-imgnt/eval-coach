"""Part 1 in the engine: the course order and locking, the three step kinds, their gates, files and resets.

Uses the fake terminal and the stand-in file writes; no real CLI is started.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import course_helpers as ch
import helpers
from helpers import FakeTerminal, wait_until
from test_http_course import CourseServer

from eval_coach import part_steps, project, reset, state
from eval_coach.engine import Engine, EngineError

LINE = "Read prompt.md, follow it, and save only your answer to output.txt. Do nothing else."
COLD_PROMPT = "Please turn my notes into a Friday update for my lead."
LABELLED = "Role: a consultant\nTask: write the Friday update\nContext: I work on two clients\nConstraints: under 150 words"
ANSWER = "Update for Friday. Northwind work went well. Blocker: test data access."
YES5 = {f"r{i}": "yes" for i in range(1, 6)}


def marks(yes):
    return {f"r{i}": "yes" if i <= yes else "no" for i in range(1, 6)}


class PartOneBase(ch.CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()

    # --- reading ---------------------------------------------------------

    def view(self, step=None):
        return self.engine.get_state(step=step, part=None if step else "part-1")

    def detail(self, step):
        return self.engine.get_state(step=step)["step"]

    def data(self, step):
        return self.detail(step)["data"]

    def done(self):
        return list(self.engine.progress["parts"].get("part-1", {}).get("done", []))

    def record(self, step):
        return self.engine.progress["parts"]["part-1"]["steps"][step]

    def status(self, item):
        return next(x["status"] for x in self.view()["course"] if x["id"] == item)

    def check(self, step):
        self.engine.step_check(step)
        return self.engine._step(step)["last_check"]

    # --- doing -----------------------------------------------------------

    def do_run(self, step, prompt, model="everyday-model", output=ANSWER, **extra):
        body = {"prompt": prompt}
        body.update(extra)
        self.engine.step_submit(step, body)
        self.engine.step_start(step)
        if model is not None:
            # The app records the model at the start. The typed route stands in for a toggle change, so a test can
            # compare two different recorded models; model=None keeps what the start recorded.
            self.engine.step_submit(step, {"model_name": model})
        self.engine.step_send(step)
        (self.paths.part1_work(step) / "output.txt").write_text(output, encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.paths.part1_output(step).is_file()), "the run was never saved")
        self.assertTrue(wait_until(lambda: not self.terminal.running))

    def do_cold(self, **kw):
        self.do_run("cold", COLD_PROMPT, **kw)
        self.assertTrue(self.check("cold")["ok"])

    def do_score(self, yes=2):
        self.engine.step_submit("score", {"answers": marks(yes), "gap": "No blocker ask", "in_prompt": "no"})
        self.assertTrue(self.check("score")["ok"])

    def do_rewrite(self, **kw):
        kw.setdefault("framework", "rtcc")
        self.do_run("rewrite", LABELLED, **kw)
        self.assertTrue(self.check("rewrite")["ok"])

    def do_rescore(self, yes=4):
        self.engine.step_submit("rescore", {"answers": marks(yes), "reflections": {"added": "Context.", "better": "More."}})
        self.assertTrue(self.check("rescore")["ok"])

    def reach(self, item):
        """Finish everything before `item`, in order."""
        for kind, name in state.PART_1.course:
            if name == item:
                return
            if kind == "lesson":
                self.finish(name)
            else:
                {"cold": self.do_cold, "score": self.do_score, "rewrite": self.do_rewrite,
                 "rescore": self.do_rescore, "own": lambda: None}[name]()


class CourseOrderAndLocking(PartOneBase):
    def test_the_course_lists_the_nine_items_in_order_with_lessons_and_steps_together(self):
        course = self.view()["course"]
        self.assertEqual([(x["kind"], x["id"]) for x in course], list(state.PART_1.course))
        self.assertEqual(self.view()["steps"][0]["id"], "cold")
        self.assertEqual([s["id"] for s in self.view()["steps"]], ["cold", "score", "rewrite", "rescore", "own"])

    def test_part_three_is_not_disturbed_by_part_one(self):
        self.assertEqual([x["id"] for x in self.engine.get_state()["course"]][0], "mission")
        self.reach("cold")
        self.assertEqual(self.status("p1-mission"), "done")
        self.assertEqual(self.engine.get_state()["course"][0]["status"], "active")

    def test_only_the_mission_is_active_at_first_and_ids_are_unique_across_parts(self):
        self.assertEqual([x["id"] for x in self.view()["course"] if x["status"] == "active"], ["p1-mission"])
        self.assertEqual(state.duplicate_ids(), [])

    def test_a_step_after_a_lesson_is_locked_until_that_lesson_is_done_and_names_it(self):
        self.reach("p1-gaps")
        self.assertEqual(self.status("p1-gaps"), "active")
        self.finish("p1-gaps")
        self.assertEqual(self.status("rewrite"), "locked")
        error = self.assert_code("step_locked", self.engine.step_start, "rewrite")
        self.assertIn(self.course.get("p1-frameworks")["title"], error.message)
        self.finish("p1-frameworks")
        self.assertEqual(self.status("rewrite"), "active")

    def test_a_locked_step_of_another_part_is_a_preview_and_changes_nothing(self):
        before = self.paths.progress_file.read_bytes()
        preview = self.detail("score")
        self.assertTrue(preview["preview"])
        self.assertEqual((preview["status"], preview["cli"], preview["data"]), ("locked", None, {}))
        self.assertEqual(preview["held_by"]["id"], "p1-mission")
        self.assertEqual(self.engine.lesson_view("p1-gaps")["lesson"]["status"], "preview")
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertFalse(self.paths.part1_root.exists())

    def test_the_first_step_waits_for_the_mission_and_each_step_for_the_one_before(self):
        error = self.assert_code("step_locked", self.engine.step_submit, "cold", {"model_name": "x"})
        self.assertIn(self.course.get("p1-mission")["title"], error.message)
        self.finish("p1-mission")
        self.assertEqual(self.status("cold"), "active")
        self.assertEqual(self.status("score"), "locked")
        self.assert_code("step_locked", self.engine.step_submit, "score", {"gap": "x"})

    def test_old_progress_with_no_part_one_loads_with_part_one_not_started(self):
        data = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        data.pop("parts", None)
        self.paths.progress_file.write_text(json.dumps(data), encoding="utf-8")
        loaded = state.load_progress(self.paths.progress_file)
        self.assertEqual(loaded["parts"], {})
        engine = self.new_engine()
        view = engine.get_state(part="part-1")
        self.assertEqual({x["status"] for x in view["course"]}, {"active", "locked"})
        row = next(p for p in view["series"]["parts"] if p["id"] == "part-1")
        self.assertEqual((row["state"], row["done"], row["total"]), ("not_started", 0, 9))

    def test_the_part_one_block_is_made_on_first_use_and_holds_the_default_records(self):
        self.assertNotIn("part-1", self.engine.progress["parts"])
        self.finish("p1-mission")
        self.engine.step_submit("cold", {"model_name": "m"})
        block = self.engine.progress["parts"]["part-1"]
        self.assertEqual(block["done"], [])
        self.assertEqual(set(block["steps"]), set(state.PART_1.step_ids))

    def test_step_questions_follow_the_usual_rules(self):
        self.reach("cold")
        self.assert_code("step_question_locked", self.engine.step_question_answer, "cold", "a")
        self.do_cold()
        question = self.detail("cold")["question"]
        self.assertIsNotNone(question)
        self.assertEqual(len(question["options"]), 4)
        self.assertTrue(self.engine.step_question_answer("cold", ch.correct_option(self.course.step_checks["cold"]))["passed"])
        self.assertEqual(self.status("score"), "active")  # an unanswered or answered question never gates


class BeforeSetup(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-p1-gate-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home, self.project = self.tmp / "home", self.tmp / "project"
        self.terminal = FakeTerminal()
        self.engine = Engine(self.home, self.terminal, poll_interval=0.01, lessons=ch.bundled_course())
        self.addCleanup(self.engine.shutdown)
        self.engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.paths = project.Paths(self.home, self.project)

    def code_of(self, fn, *args):
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        return ctx.exception.code

    def test_the_mission_opens_before_setup_and_the_steps_are_previews(self):
        view = self.engine.get_state(part="part-1")
        self.assertEqual(view["course"][0]["status"], "active")
        self.assertEqual(self.engine.lesson_view("p1-mission")["lesson"]["status"], "active")
        before = self.paths.progress_file.read_bytes()
        for step in state.PART_1.step_ids:
            preview = self.engine.get_state(step=step)["step"]
            with self.subTest(step=step):
                self.assertTrue(preview["preview"])
                self.assertEqual(preview["status"], "locked")
                self.assertIsNone(preview["cli"])
                self.assertTrue(preview["instructions"])
        self.assertEqual(self.paths.progress_file.read_bytes(), before)

    def test_save_start_send_check_and_the_question_are_refused_and_nothing_is_written(self):
        before = self.paths.progress_file.read_bytes()
        for step in ("cold", "score", "own"):
            for name in ("submit", "check"):
                args = ({"prompt": "x"},) if name == "submit" else ()
                with self.subTest(step=step, call=name):
                    self.assertEqual(self.code_of(getattr(self.engine, f"step_{name}"), step, *args),
                                     "preflight_incomplete")
        for name in ("start", "send"):
            with self.subTest(call=name):
                self.assertEqual(self.code_of(getattr(self.engine, f"step_{name}"), "cold"), "preflight_incomplete")
        self.assertEqual(self.code_of(self.engine.step_question_answer, "cold", "a"), "step_question_locked")
        self.assertEqual(self.terminal.starts, [])
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertFalse(self.paths.part1.exists())
        self.assertFalse(self.paths.part1_root.exists())


class WriteAndRunCold(PartOneBase):
    def setUp(self):
        super().setUp()
        self.finish("p1-mission")

    def test_the_view_shows_the_scenario_the_notes_and_no_preview_until_a_prompt_is_saved(self):
        detail = self.detail("cold")
        data = detail["data"]
        self.assertEqual(detail["kind"], "write_and_run")
        self.assertEqual(len(data["scenario"]["requirements"]), 5)
        self.assertEqual(data["notes"], part_steps.rough_notes())
        self.assertEqual((data["prompt"], data["prompt_saved"], data["preview"], data["output"]), ("", False, "", None))
        self.assertEqual(detail["cli"]["line"], LINE)
        self.assertIn("Save your prompt first", detail["cli"]["start_blocked"])
        self.assertNotIn("labels", data)

    def test_save_writes_only_the_participants_words_and_nothing_else_changes_it(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        self.assertEqual(self.paths.part1_prompt("cold").read_text(encoding="utf-8"), COLD_PROMPT)
        self.assertNotIn("Mon:", self.paths.part1_prompt("cold").read_text(encoding="utf-8"))
        self.engine.step_submit("cold", {"model_name": "a model"})
        self.assertEqual(self.paths.part1_prompt("cold").read_text(encoding="utf-8"), COLD_PROMPT)
        self.engine.step_submit("cold", {"prompt": "A new version."})
        self.assertEqual(self.paths.part1_prompt("cold").read_text(encoding="utf-8"), "A new version.")
        self.assertTrue(self.data("cold")["prompt_saved"])

    def test_bad_saves_are_refused(self):
        self.assert_code("bad_input", self.engine.step_submit, "cold", {"prompt": 5})
        self.assert_code("bad_input", self.engine.step_submit, "cold", {"prompt": "x" * 60000})
        self.assert_code("bad_input", self.engine.step_submit, "cold", {"nothing": 1})
        self.assert_code("bad_input", self.engine.step_submit, "cold", {"framework": "rtcc"})
        self.assert_code("bad_input", self.engine.step_submit, "cold", ["not", "an", "object"])

    def test_the_model_name_is_one_plain_line(self):
        self.engine.step_submit("cold", {"model_name": "  Some \n model\t name  "})
        self.assertEqual(self.record("cold")["model_name"], "Some model name")

    def test_start_needs_a_saved_prompt(self):
        self.assert_code("prompt_missing", self.engine.step_start, "cold")
        self.engine.step_submit("cold", {"prompt": "   \n"})
        self.assert_code("prompt_missing", self.engine.step_start, "cold")
        self.assertEqual(self.terminal.starts, [])

    def test_start_clears_the_folder_and_writes_only_prompt_md_with_the_notes_under_the_words(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        work = self.paths.part1_work("cold")
        work.mkdir(parents=True)
        (work / "leftover.txt").write_text("old", encoding="utf-8")
        self.engine.step_start("cold")
        self.assertEqual(sorted(p.name for p in work.iterdir()), ["prompt.md"])
        text = (work / "prompt.md").read_text(encoding="utf-8")
        divider = json.loads(ch.resources.read_text("content/part-1-steps.json"))["steps"]["cold"]["divider"]
        self.assertEqual(text, COLD_PROMPT + "\n\n" + divider + "\n\n" + part_steps.rough_notes() + "\n")
        self.assertEqual(self.terminal.starts[-1]["cwd"], str(work))
        self.assertEqual(self.data("cold")["preview"], text)
        self.assertEqual(self.terminal.starts[-1]["command"], "mycli")
        self.assertEqual(self.terminal.owner, "cold")

    def test_send_types_the_exact_line_and_needs_a_running_cli(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        self.assert_code("cli_not_running", self.engine.step_send, "cold")
        self.engine.step_start("cold")
        self.engine.step_send("cold")
        self.assertEqual(self.terminal.typed, [LINE])
        self.assertTrue(self.detail("cold")["cli"]["sent"])

    def test_the_output_is_saved_after_two_unchanged_polls_and_the_cli_stops(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        self.engine.step_start("cold")
        (self.paths.part1_work("cold") / "output.txt").write_text(ANSWER, encoding="utf-8")
        self.assertTrue(wait_until(lambda: self.paths.part1_output("cold").is_file()))
        self.assertEqual(self.paths.part1_output("cold").read_text(encoding="utf-8"), ANSWER)
        self.assertTrue(wait_until(lambda: not self.terminal.running))
        self.assertTrue(wait_until(lambda: self.terminal.state_events >= 1))
        self.assertEqual(self.data("cold")["output"], ANSWER)

    def test_a_cli_that_writes_nothing_leaves_the_step_unfinished(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT, "model_name": "m"})
        self.engine.step_start("cold")
        (self.paths.part1_work("cold") / "output.txt").write_text("   \n", encoding="utf-8")
        self.assertFalse(wait_until(lambda: self.paths.part1_output("cold").exists(), timeout=0.3))
        result = self.check("cold")
        self.assertFalse(result["ok"])
        self.assertEqual([i["ok"] for i in result["items"]], [True, False, True])
        self.assertEqual(self.status("cold"), "active")
        self.assertIsNone(self.data("cold")["output"])

    def test_the_gate_names_what_is_missing_and_passes_with_all_three(self):
        result = self.check("cold")
        self.assertEqual([i["ok"] for i in result["items"]], [False, False, False])
        self.assertTrue(all(i["detail"] for i in result["items"]))
        self.do_run("cold", COLD_PROMPT, model="")
        self.assertEqual([i["ok"] for i in self.check("cold")["items"]], [True, True, False])
        self.engine.step_submit("cold", {"model_name": "everyday"})
        self.assertTrue(self.check("cold")["ok"])
        self.assertEqual(self.done(), ["cold"])
        self.assertFalse(self.terminal.running)

    def test_the_start_records_the_model_so_the_gate_needs_no_typing(self):
        self.do_run("cold", COLD_PROMPT, model=None)
        self.assertEqual(self.record("cold")["model_name"], "the AI's own default model")
        self.assertNotIn("model_name", self.data("cold"))
        self.assertTrue(self.check("cold")["ok"])

    def test_a_done_step_shows_the_prompt_and_output_and_offers_no_second_run(self):
        self.do_cold()
        self.assert_code("step_done", self.engine.step_start, "cold")
        self.assert_code("step_done", self.engine.step_submit, "cold", {"prompt": "again"})
        detail = self.detail("cold")
        self.assertEqual((detail["status"], detail["data"]["prompt"], detail["data"]["output"]),
                         ("done", COLD_PROMPT, ANSWER))

    def test_a_second_start_replaces_an_unfinished_answer(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        self.do_run("cold", COLD_PROMPT, output="first")
        self.engine.step_start("cold")
        self.assertFalse(self.paths.part1_output("cold").exists())

    def test_a_changed_prompt_after_the_run_is_noted_but_does_not_block(self):
        self.do_run("cold", COLD_PROMPT)
        self.assertFalse(self.data("cold")["prompt_changed"])
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT + " Extra."})
        self.assertTrue(self.data("cold")["prompt_changed"])
        result = self.check("cold")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["nudges"]), 1)

    def test_the_step_cannot_run_before_the_one_before_it_is_done_and_score_steps_have_no_cli(self):
        self.assert_code("not_supported", self.engine.step_start, "score")

    def test_the_output_is_plain_text_in_the_view(self):
        html = "<b>bold</b> <script>alert(1)</script>"
        self.do_run("cold", COLD_PROMPT, output=html)
        self.assertEqual(self.data("cold")["output"], html)  # sent as text; the page puts it in a text node

    def test_a_running_cli_of_another_step_is_stopped_when_a_new_run_starts(self):
        self.engine.step_submit("cold", {"prompt": COLD_PROMPT})
        self.engine.step_start("cold")
        stops = self.terminal.stops
        self.engine.step_start("cold")
        self.assertGreater(self.terminal.stops, stops)
        self.assertEqual(len(self.terminal.starts), 2)


class ScoreSteps(PartOneBase):
    def setUp(self):
        super().setUp()
        self.reach("score")

    def test_the_view_has_the_output_the_five_rows_and_the_three_answers(self):
        data = self.data("score")
        self.assertEqual(data["output"], ANSWER)
        self.assertEqual([r["id"] for r in data["rows"]], ["r1", "r2", "r3", "r4", "r5"])
        self.assertEqual(data["fields"], ["gap", "in_prompt"])
        self.assertIsNone(data["score"])
        self.assertFalse(data["all_yes"])
        self.assertIsNone(self.detail("score")["cli"])

    def test_the_score_is_counted_from_the_answers_only_and_only_when_all_five_are_given(self):
        self.engine.step_submit("score", {"answers": {"r1": "yes", "r2": "no"}})
        self.assertIsNone(self.data("score")["score"])
        self.assertEqual(self.data("score")["answered"], 2)
        self.engine.step_submit("score", {"answers": {"r3": "yes", "r4": "no", "r5": "no"}})
        score = self.data("score")["score"]
        self.assertEqual((score["yes"], score["total"], score["text"]), (2, 5, "2 of 5"))

    def test_the_output_text_never_changes_the_score(self):
        for output in ("Teams message under 150 words grouped by client blocker factual", "x"):
            self.paths.part1_output("cold").write_text(output, encoding="utf-8")
            self.engine.step_submit("score", {"answers": marks(1)})
            self.assertEqual(self.data("score")["score"]["yes"], 1)

    def test_all_five_yes_is_flagged_so_the_page_can_change_the_question(self):
        self.engine.step_submit("score", {"answers": YES5})
        self.assertTrue(self.data("score")["all_yes"])
        self.assertEqual(self.data("score")["score"]["text"], "5 of 5")

    def test_the_gate_needs_every_row_the_gap_and_the_prompt_question(self):
        result = self.check("score")
        self.assertEqual([i["ok"] for i in result["items"]], [False, False, False])
        self.assertIn("0 of 5 are answered", result["items"][0]["detail"])
        self.engine.step_submit("score", {"answers": marks(3)})
        self.assertEqual([i["ok"] for i in self.check("score")["items"]], [True, False, False])
        self.engine.step_submit("score", {"gap": "  ", "in_prompt": "not_sure"})
        self.assertEqual([i["ok"] for i in self.check("score")["items"]], [True, False, True])
        self.engine.step_submit("score", {"gap": "Missed the ask"})
        self.assertTrue(self.check("score")["ok"])
        self.assertEqual(self.done(), ["cold", "score"])

    def test_no_answer_can_make_the_gate_fail_so_all_no_passes(self):
        self.engine.step_submit("score", {"answers": marks(0), "gap": "g", "in_prompt": "yes"})
        self.assertTrue(self.check("score")["ok"])
        self.assertEqual(self.data("score")["score"]["text"], "0 of 5")

    def test_no_answer_can_make_the_gate_fail_so_all_yes_passes(self):
        self.engine.step_submit("score", {"answers": YES5, "gap": "My prompt named the reader", "in_prompt": "yes"})
        self.assertTrue(self.check("score")["ok"])
        self.assertEqual(self.data("score")["score"]["text"], "5 of 5")
    def test_bad_answers_are_refused_with_the_steps_own_words(self):
        for body in ({"answers": {"r9": "yes"}}, {"answers": {"r1": "maybe"}}, {"answers": ["yes"]},
                     {"in_prompt": "perhaps"}, {"reflections": {"added": "x"}}, {"nothing": 1}):
            with self.subTest(body=body):
                self.assert_code("bad_input", self.engine.step_submit, "score", body)

    def test_answers_are_kept_per_step_and_hold_nothing_but_the_participants_marks(self):
        self.engine.step_submit("score", {"answers": marks(2), "gap": "g", "in_prompt": "no"})
        record = self.record("score")
        self.assertEqual(set(record), {"answers", "gap", "in_prompt", "last_check"})
        self.assertEqual(record["answers"], marks(2))
        text = json.dumps(self.engine.progress["parts"])
        self.assertNotIn(ANSWER, text)
        self.assertNotIn("Mon:", text)

    def test_a_done_score_step_is_a_record_and_refuses_changes(self):
        self.do_score()
        self.assert_code("step_done", self.engine.step_submit, "score", {"gap": "other"})
        self.assertEqual(self.data("score")["score"]["yes"], 2)


class RewriteAndCompare(PartOneBase):
    def setUp(self):
        super().setUp()
        self.reach("rewrite")

    def test_the_view_offers_three_equal_label_sets_none_chosen_and_the_first_prompt(self):
        data = self.data("rewrite")
        self.assertEqual([x["id"] for x in data["labels"]], ["rtcc", "rise", "own"])
        self.assertEqual(data["framework"], "")
        self.assertEqual(data["cold_prompt"], COLD_PROMPT)
        self.assertEqual(len({len(x["description"].split()) for x in data["labels"]}), 1)

    def test_a_label_set_must_be_one_of_the_three(self):
        self.engine.step_submit("rewrite", {"framework": "rise"})
        self.assertEqual(self.data("rewrite")["framework"], "rise")
        self.assert_code("bad_input", self.engine.step_submit, "rewrite", {"framework": "costar"})
        self.engine.step_submit("rewrite", {"framework": ""})
        self.assertEqual(self.data("rewrite")["framework"], "")

    def test_the_run_copy_ends_with_the_same_rough_notes_as_the_cold_run(self):
        self.do_run("rewrite", LABELLED, framework="rtcc")
        rewrite = (self.paths.part1_work("rewrite") / "prompt.md").read_text(encoding="utf-8")
        cold = (self.paths.part1_work("cold") / "prompt.md").read_text(encoding="utf-8")
        self.assertTrue(rewrite.startswith(LABELLED))
        self.assertTrue(rewrite.endswith(part_steps.rough_notes() + "\n"))
        self.assertEqual(rewrite.split("\n\n", 1)[1].split("\n\n", 1)[1], cold.split("\n\n", 1)[1].split("\n\n", 1)[1])

    def test_a_new_cli_process_starts_for_each_run(self):
        self.do_run("rewrite", LABELLED)
        self.assertEqual([s["cwd"] for s in self.terminal.starts],
                         [str(self.paths.part1_work("cold")), str(self.paths.part1_work("rewrite"))])

    def test_the_gate_needs_labels_a_changed_prompt_an_output_and_a_model(self):
        self.engine.step_submit("rewrite", {"prompt": COLD_PROMPT, "model_name": "everyday-model"})
        result = self.check("rewrite")
        self.assertEqual([i["ok"] for i in result["items"]], [False, True, False, False, True])
        self.assertIn("same as your first one", result["items"][2]["detail"])
        self.do_run("rewrite", LABELLED, framework="own")
        self.assertTrue(self.check("rewrite")["ok"])

    def test_an_unchanged_prompt_fails_even_with_other_spacing(self):
        self.do_run("rewrite", "  " + COLD_PROMPT.replace(" ", "  ") + "\n", framework="rtcc")
        self.assertFalse(self.check("rewrite")["items"][2]["ok"])

    def test_a_different_model_passes_with_a_plain_nudge(self):
        self.do_run("rewrite", LABELLED, framework="rtcc", model="another-model")
        self.assertIsNotNone(self.data("rewrite")["model_note"])
        result = self.check("rewrite")
        self.assertTrue(result["ok"])
        self.assertEqual(len(result["nudges"]), 1)
        self.assertIn("less fair", result["nudges"][0])

    def test_the_same_recorded_model_in_both_runs_gets_no_nudge(self):
        self.do_run("rewrite", LABELLED, framework="rtcc", model=None)
        self.assertEqual(self.record("rewrite")["model_name"], "the AI's own default model")
        self.engine._step("cold")["model_name"] = "the AI's own default model"
        self.assertIsNone(self.detail("rewrite")["data"]["model_note"])
        self.assertEqual(self.check("rewrite")["nudges"], [])

    def test_the_same_model_in_other_case_or_spacing_gets_no_nudge(self):
        self.do_run("rewrite", LABELLED, framework="rtcc", model="  Everyday-MODEL ")
        result = self.check("rewrite")
        self.assertTrue(result["ok"])
        self.assertEqual(result["nudges"], [])
        self.assertIsNone(self.detail("rewrite")["data"]["model_note"])

    def test_the_second_score_shows_both_runs_side_by_side_with_the_change(self):
        self.do_rewrite()
        compare = self.data("rescore")["compare"]
        self.assertEqual((compare["first"]["prompt"], compare["first"]["output"]), (COLD_PROMPT, ANSWER))
        self.assertEqual((compare["second"]["prompt"], compare["second"]["output"]), (LABELLED, ANSWER))
        self.assertEqual(compare["first"]["score"]["text"], "2 of 5")
        self.assertIsNone(compare["second"]["score"])
        self.assertIsNone(compare["change"])
        self.assertEqual(len(compare["notes"]), 1)
        self.assertIn("Part 3 measures that", compare["notes"][0])

    def test_a_higher_a_lower_and_an_equal_second_score_are_described(self):
        self.do_rewrite()
        for yes, expected in ((4, "went up by 2"), (1, "went down by 1"), (2, "stayed the same")):
            self.engine.step_submit("rescore", {"answers": marks(yes)})
            compare = self.data("rescore")["compare"]
            with self.subTest(yes=yes):
                self.assertIn(expected, compare["change_text"])
                self.assertEqual(compare["change"], yes - 2)
                self.assertEqual(len(compare["notes"]), 2 if yes < 2 else 1)

    def test_a_worse_score_points_to_the_missing_part_without_blaming_the_labels(self):
        self.do_rewrite()
        self.engine.step_submit("rescore", {"answers": marks(0)})
        notes = " ".join(self.data("rescore")["compare"]["notes"])
        self.assertIn("A lower second score can happen", notes)
        self.assertIn("still missing", notes)

    def test_the_rescore_gate_needs_five_answers_and_both_written_answers(self):
        self.do_rewrite()
        result = self.check("rescore")
        self.assertEqual([i["ok"] for i in result["items"]], [False, False, False])
        self.engine.step_submit("rescore", {"answers": marks(3), "reflections": {"added": "Context"}})
        self.assertEqual([i["ok"] for i in self.check("rescore")["items"]], [True, True, False])
        self.engine.step_submit("rescore", {"reflections": {"better": "It had more"}})
        self.assertTrue(self.check("rescore")["ok"])
        self.assertEqual(self.done(), ["cold", "score", "rewrite", "rescore"])

    def test_the_rescore_step_refuses_a_gap_field_it_does_not_have(self):
        self.do_rewrite()
        self.assert_code("bad_input", self.engine.step_submit, "rescore", {"gap": "x"})
        self.assert_code("bad_input", self.engine.step_submit, "rescore", {"reflections": {"nope": "x"}})


class OwnStep(PartOneBase):
    def setUp(self):
        super().setUp()
        self.reach("own")

    def test_the_view_has_no_cli_and_the_saved_texts(self):
        detail = self.detail("own")
        self.assertEqual(detail["kind"], "write_pair")
        self.assertIsNone(detail["cli"])
        self.assertEqual(detail["data"], {"before": "", "after": "", "labels": ""})
        self.assert_code("not_supported", self.engine.step_start, "own")
        self.assert_code("not_supported", self.engine.step_send, "own")

    def test_save_writes_the_two_files_and_the_label_note(self):
        self.engine.step_submit("own", {"before": "Write my report.", "after": "Role: writer\nTask: my report", "labels": "RTCC"})
        self.assertEqual(self.paths.part1_own("before").read_text(encoding="utf-8"), "Write my report.")
        self.assertEqual(self.paths.part1_own("after").read_text(encoding="utf-8"), "Role: writer\nTask: my report")
        self.assertEqual(self.record("own")["labels"], "RTCC")
        self.assertEqual(self.data("own")["after"], "Role: writer\nTask: my report")

    def test_the_gate_needs_three_texts_and_two_that_differ(self):
        self.assertEqual([i["ok"] for i in self.check("own")["items"]], [False, False, False, True])
        self.engine.step_submit("own", {"before": "Same text", "after": "Same  text", "labels": "mine"})
        result = self.check("own")
        self.assertEqual([i["ok"] for i in result["items"]], [True, True, True, False])
        self.engine.step_submit("own", {"after": "Role: x\nTask: Same text"})
        self.assertTrue(self.check("own")["ok"])
        self.assertEqual(self.done(), list(state.PART_1.step_ids))

    def test_finishing_the_last_step_finishes_the_part(self):
        self.engine.step_submit("own", {"before": "a", "after": "b", "labels": "c"})
        self.check("own")
        row = next(p for p in self.view()["series"]["parts"] if p["id"] == "part-1")
        self.assertEqual((row["done"], row["total"]), (9, 9))
        self.assertEqual(row["state"], "done")
        self.assertIsNone(self.view()["current_item"])
        self.assertIn("Part 2", self.view()["course_text"]["finished_body"])


class SamplePromptsStayClosedUntilRescoreIsDone(PartOneBase):
    def test_the_samples_open_only_after_the_rescore_step(self):
        for name in ("sample-rtcc.md", "sample-rise.md"):
            self.assert_code("bad_ref", self.engine.kit_file, f"kit:part1/{name}")
        self.reach("p1-benefits")
        for name in ("sample-rtcc.md", "sample-rise.md"):
            kit = self.engine.kit_file(f"kit:part1/{name}")["kit"]
            self.assertIn("Role:", kit["text"])

    def test_the_benefits_lesson_opens_only_after_the_rescore_step_and_its_sources_then_read(self):
        self.reach("p1-benefits")
        lesson = self.engine.lesson_view("p1-benefits")["lesson"]
        self.assertEqual(lesson["status"], "active")
        refs = [s["ref"] for s in lesson["sources"]]
        self.assertIn("kit:part1/sample-rise.md", refs)


class Resets(PartOneBase):
    def populate(self):
        self.reach("own")
        self.engine.step_submit("own", {"before": "a", "after": "b", "labels": "c"})
        self.unknown = self.paths.part1 / "my-notes.txt"
        self.unknown.write_text("mine", encoding="utf-8")

    def part_one_files(self):
        return {p.name for p in self.paths.part1.iterdir()} if self.paths.part1.exists() else set()

    def test_reset_lesson_progress_moves_outputs_and_scratch_and_keeps_prompts_and_own_work(self):
        self.populate()
        self.assertTrue(self.paths.part1_work("cold").exists())
        self.engine.reset_progress(True)
        self.assertEqual(self.part_one_files(),
                         {"prompt-cold.md", "prompt-framework.md", "own-before.md", "own-after.md", "my-notes.txt"})
        self.assertFalse(self.paths.part1_root.exists())
        backup = self.home / reset.BACKUP_NAME
        moved = {p.name for p in (backup / "project" / "part-1").iterdir()}
        self.assertEqual(moved, {"output-cold.txt", "output-framework.txt"})
        self.assertEqual(self.paths.part1_own("before").read_text(encoding="utf-8"), "a")
        self.assertEqual(self.engine.progress["parts"], {})
        self.assertEqual(self.view()["course"][0]["status"], "active")

    def test_reset_app_configuration_moves_the_prompts_too_and_leaves_only_unknown_files(self):
        self.populate()
        self.engine.reset_configuration(True)
        self.assertEqual(self.part_one_files(), {"my-notes.txt"})
        moved = {p.name for p in (self.home / reset.BACKUP_NAME / "project" / "part-1").iterdir()}
        self.assertEqual(moved, {"output-cold.txt", "output-framework.txt", "prompt-cold.md", "prompt-framework.md",
                                 "own-before.md", "own-after.md"})
        self.assertTrue(self.unknown.is_file())

    def test_the_configuration_reset_removes_the_empty_part_one_folder(self):
        self.reach("rewrite")
        self.engine.reset_configuration(True)
        self.assertFalse(self.paths.part1.exists())

    def test_no_file_part_one_writes_is_on_no_reset_list(self):
        self.populate()
        for path in self.paths.part1.iterdir():
            if path != self.unknown:
                self.assertIsNotNone(reset.classify_project_path(path.relative_to(self.paths.project).as_posix()), path.name)
        self.assertIsNone(reset.classify_project_path("part-1/my-notes.txt"))


class StateForThePage(PartOneBase):
    def test_a_request_names_the_part_and_a_step_names_its_own(self):
        self.assertEqual(self.engine.get_state(part="part-1")["course_text"]["brand_sub"], "Part 1 \u00b7 Structured prompting")
        self.assertEqual(self.engine.get_state()["course_text"]["brand_sub"], "Part 3 \u00b7 Running evals and baseline")
        self.assert_code("unknown_part", self.engine.get_state, None, "part-77")
        self.assertEqual(self.engine.get_state(step="cold")["steps"][0]["id"], "cold")


class OverHttp(CourseServer):
    """The routes pass the Part through, so a lesson answer or a step save returns the Part the page is in."""

    def setUp(self):
        super().setUp()
        status, body = self.post("/api/setup", {"project_path": str(self.tmp / "project"), "cli_command": "mycli",
                                                "starter": "northwind"})
        self.assertEqual(status, 200, body)

    def test_a_lesson_post_with_a_part_returns_that_parts_course(self):
        status, body = self.post("/api/lesson/complete", {"lesson": "p1-mission", "part": "part-1"})
        self.assertEqual(status, 200, body)
        self.assertEqual([x["id"] for x in body["state"]["course"]], [item for _, item in state.PART_1.course])
        self.assertEqual(body["state"]["course_text"]["brand_sub"], "Part 1 \u00b7 Structured prompting")
        status, body = self.post("/api/review/postpone", {})
        self.assertEqual(body["state"]["course"][0]["id"], "mission")

    def test_a_step_post_returns_the_steps_own_part_and_an_unknown_part_falls_back(self):
        self.finish_lessons_part_one()
        status, body = self.post("/api/step/submit", {"step": "cold", "data": {"model_name": "m"}})
        self.assertEqual(status, 200, body)
        self.assertEqual(body["state"]["step"]["id"], "cold")
        self.assertEqual(body["state"]["steps"][0]["id"], "cold")
        status, body = self.post("/api/review/postpone", {"part": "part-77"})
        self.assertEqual(status, 200)
        self.assertEqual(body["state"]["course"][0]["id"], "mission")

    def finish_lessons_part_one(self):
        status, body = self.post("/api/lesson/complete", {"lesson": "p1-mission", "part": "part-1"})
        self.assertEqual(status, 200, body)

    def test_the_state_route_takes_the_part(self):
        status, body = self.get("/api/state?part=part-1")
        self.assertEqual(status, 200)
        self.assertEqual(body["course"][0]["id"], "p1-mission")
        status, body = self.get("/api/state?part=part-77")
        self.assertEqual(status, 400)
        self.assertEqual(body["error"]["code"], "unknown_part")

    def test_the_new_step_routes_need_the_token_like_every_other(self):
        for path, body in (("/api/step/submit", {"step": "cold", "data": {"prompt": "x"}}),
                           ("/api/step/start", {"step": "cold"}), ("/api/step/check", {"step": "own"})):
            status, payload = self.post(path, body, token=False)
            self.assertEqual(status, 401, path)
            self.assertNotIn("state", payload)


if __name__ == "__main__":
    unittest.main()
