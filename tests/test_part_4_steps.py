"""Part 4's step kinds through the engine (OpenSpec change part-4-course): the starting point, the known-good answer, and
each round's hypothesis, edit, measure and decide steps. Everything runs on the stand-in files and the fake terminal; no
AI is called and no answer is typed by the app."""
from __future__ import annotations

import json
from pathlib import Path

import course_helpers as ch
import helpers
import pf_helpers as pf
from eval_coach import attempts as A
from eval_coach import baseline, gates, project, resources, state as store
from eval_coach.engine import EngineError
from test_part_4_attempts import HYPOTHESIS, REFERENCE, SAMPLE, log_entry

PART = store.PART_4
BAD = (helpers.NORTHWIND / "fixture-bad.txt").read_text(encoding="utf-8")
ROUND_1_PROMPT = "Round one prompt with a stricter tone line.\n"


class P4(ch.CourseBase):
    """An engine with the bundled course, Part 4 open, and the Practice baseline as the usual starting point."""

    track = "script"

    def setUp(self):
        self.fake = pf.FakePromptfoo()
        super().setUp()
        self.setup_project()

    def new_engine(self, lessons=True, demo=True):
        helpers.write_passed_preflight(self.home, track=self.track)
        engine = helpers.make_engine(self.home, self.terminal, poll_interval=0.01, lessons=self.course,
                                     clock=self.clock, demo=demo, preflight_runner=self.fake)
        self.addCleanup(engine.shutdown)
        return engine

    # --- driving the steps ---------------------------------------------------

    def open_to(self, step):
        """Mark every lesson before `step` done and every required step before it done, as the participant's work."""
        block = self.engine._progress_of(PART)
        lessons = self.engine._lessons_block()["per_lesson"]
        done = []
        for kind, item in PART.course:
            if item == step:
                break
            if kind == "lesson":
                lessons[item] = {"status": "done", "activities": {}}
            else:
                done.append(item)
        block["done"][:] = done
        self.engine._save()

    def data(self, step):
        return self.engine.get_state(step=step)["step"]["data"]

    def view(self, step):
        return self.engine.get_state(step=step)["step"]

    def submit(self, step, **data):
        return self.engine.step_submit(step, data)

    def refused(self, code, fn, *args, **kwargs):
        with self.assertRaises(EngineError) as ctx:
            fn(*args, **kwargs)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception

    def status(self, step):
        return self.engine._status(step)

    def attempts(self):
        return A.Attempts.for_engine(self.engine)

    def ap(self, n, practice=None):
        if practice is None:
            practice = self.engine.progress["parts"].get("part-4", {}).get("start") == "practice"
        return self.paths.attempt(n, practice=practice)

    def choose_practice(self):
        self.open_to("starting-point")
        self.submit("starting-point", action="choose", choice="practice")

    def pass_known_good(self, text=SAMPLE[1]):
        self.open_to("known-good")
        self.submit("known-good", action="save", text=text)

    def to_hypothesis_1(self):
        self.choose_practice()
        self.pass_known_good()

    def save_hypothesis(self, n, text=HYPOTHESIS):
        self.open_to(f"hypothesis-{n}")
        self.submit(f"hypothesis-{n}", action="save", text=text)

    def edit(self, n, prompt=ROUND_1_PROMPT):
        self.open_to(f"edit-{n}")
        self.submit(f"edit-{n}", action="save", prompt=prompt)

    def collect(self, n, sources=(1, 1, 1, 1, 1)):
        """Five answers through the AI window flow: each is saved by the output watcher in a new chat."""
        step = f"measure-{n}"
        self.open_to(step)
        for k, source in enumerate(sources, start=1):
            self.engine.step_start(step)
            start = self.terminal.starts[-1]
            (Path(start["cwd"]) / "output.txt").write_text(SAMPLE[source], encoding="utf-8")
            self.assertTrue(helpers.wait_until(lambda: gates.has_text(self.ap(n).run_file(k))), f"answer {k}")
            self.assertTrue(helpers.wait_until(lambda: not self.terminal.running))

    def measure(self, n, sources=(1, 1, 1, 1, 1)):
        self.collect(n, sources)
        self.submit(f"measure-{n}", action="score")

    def round_1(self, sources=(1, 1, 1, 1, 1), decision=None):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.edit(1)
        self.measure(1, sources)
        if decision:
            self.open_to("decide-1")
            self.submit("decide-1", action="decide", choice=decision)

    def practice_log(self, *attempts, zero=True):
        """The Practice log with Iteration 0 and one entry for each (n, decision) that matches the saved results."""
        text = resources.read_text(project.PRACTICE_LOG)
        parts = [text] if zero else []
        for n, decision in attempts:
            hypothesis = gates.read_text(self.ap(n).hypothesis).strip()
            parts.append(log_entry(store.read_json(self.ap(n).results), n, decision, hypothesis))
        return "\n".join(parts)

    def write_practice_log(self, text):
        self.paths.part4_practice.iteration_log.write_text(text, encoding="utf-8")

    def finish_part_3(self):
        """Part 3's baseline as the participant left it: five answers, the reference checker and a fresh result."""
        paths = self.paths
        paths.check_py.write_text(REFERENCE, encoding="utf-8")
        for n in range(1, 6):
            paths.run_file(n).write_text(SAMPLE[n], encoding="utf-8")
        result = baseline.run_checks(paths.project, "script")
        self.engine.progress["done"] = list(store.STEP_IDS)
        self.engine._save_result("baseline", {"track": "script", "result": result, "summary": baseline.summarize(result)})
        record = self.engine._step("baseline")
        record["run_check_hash"] = gates.file_sha256(paths.check_py)
        record["run_runs_hash"] = baseline.runs_hash(paths)
        self.engine._save()


class Order(P4):
    def test_the_course_list_is_the_documented_order(self):
        items = [(i["kind"], i["id"]) for i in self.engine.get_state(part="part-4")["course"]]
        self.assertEqual(items, list(PART.course))

    def test_the_known_good_check_comes_before_any_comparison(self):
        self.open_to("known-good")
        self.refused("step_locked", self.engine.get_state, step="hypothesis-1")
        self.assertEqual(self.status("hypothesis-1"), "locked")

    def test_a_step_is_locked_until_the_one_before_it_is_done(self):
        self.open_to("starting-point")
        self.assertEqual(self.status("starting-point"), "active")
        self.assertEqual(self.status("known-good"), "locked")
        self.refused("step_locked", self.engine.step_submit, "known-good", {"action": "save", "text": "x"})

    def test_the_series_row_shows_state_count_and_open_control_and_parts_5_and_6_are_unchanged(self):
        rows = {p["id"]: p for p in self.engine.get_state()["series"]["parts"]}
        part_4 = rows["part-4"]
        self.assertEqual((part_4["kind"], part_4["state"], part_4["done"], part_4["total"]),
                         ("course", "not_started", 0, len(PART.course)))
        self.assertTrue(part_4["can_skip"])
        self.assertEqual([x["id"] for x in part_4["lessons"]], list(PART.lesson_ids))
        for part_id, kind in (("part-5", "soon"), ("part-6", "live")):
            self.assertEqual(rows[part_id]["kind"], kind)
            self.assertNotIn("state", rows[part_id])
            self.assertNotIn("lessons", rows[part_id])

    def test_part_4_offers_no_restart_and_refuses_one(self):
        self.to_hypothesis_1()
        self.assertEqual(self.view("starting-point")["restart"], {"available": False})
        self.refused("restart_unavailable", self.engine.step_restart, "starting-point", True)
        self.assertIsNone(PART.restart)


class StartingPoint(P4):
    def test_nothing_is_chosen_and_nothing_is_created_until_a_choice_is_submitted(self):
        self.open_to("starting-point")
        data = self.data("starting-point")
        self.assertIsNone(data["chosen"])
        self.assertEqual([c["id"] for c in data["choices"]], ["own", "practice"])
        self.assertTrue(data["choices"][1]["available"])
        self.assertIn("practice only", data["practice_only"])
        self.assertFalse(self.paths.part4.exists())
        self.assertIsNone(self.progress_block()["start"])
        self.assertEqual(self.status("starting-point"), "active")

    def progress_block(self):
        return self.engine.progress["parts"].get("part-4") or store.new_part_progress(PART)

    def test_the_participants_baseline_is_unavailable_with_a_reason_when_part_3_was_skipped(self):
        self.engine.part_skip("part-3", True)
        self.open_to("starting-point")
        own = self.data("starting-point")["choices"][0]
        self.assertFalse(own["available"])
        self.assertIn("skipped Part 3", own["reason"])
        self.refused("start_unavailable", self.submit, "starting-point", action="choose", choice="own")
        self.assertTrue(self.data("starting-point")["choices"][1]["available"])

    def test_the_participants_baseline_is_unavailable_when_part_3_is_unfinished_or_its_files_changed(self):
        self.open_to("starting-point")
        self.assertIn("not finished", self.data("starting-point")["choices"][0]["reason"])
        self.finish_part_3()
        self.assertTrue(self.data("starting-point")["choices"][0]["available"])
        self.paths.run_file(2).write_text("changed after the count", encoding="utf-8")
        self.assertIn("changed after the baseline was counted", self.data("starting-point")["choices"][0]["reason"])

    def test_the_participants_baseline_can_be_chosen_and_nothing_of_part_3_changes(self):
        self.finish_part_3()
        self.open_to("starting-point")
        before = {p.name: p.read_bytes() for p in self.paths.project.glob("*") if p.is_file()}
        self.submit("starting-point", action="choose", choice="own")
        self.assertEqual(self.engine.progress["parts"]["part-4"]["start"], "own")
        self.assertEqual(self.status("starting-point"), "done")
        self.assertFalse(self.paths.part4_practice.project.exists())
        self.assertEqual({p.name: p.read_bytes() for p in self.paths.project.glob("*") if p.is_file()}, before)

    def test_a_note_says_there_is_little_to_improve_at_95_percent(self):
        self.finish_part_3()
        for n in range(1, 6):
            self.paths.run_file(n).write_text(SAMPLE[1], encoding="utf-8")
        result = baseline.run_checks(self.paths.project, "script")
        self.engine._save_result("baseline", {"track": "script", "result": result, "summary": baseline.summarize(result)})
        self.engine._step("baseline")["run_runs_hash"] = baseline.runs_hash(self.paths)
        self.open_to("starting-point")
        data = self.data("starting-point")
        self.assertIn("little to improve", data["little_gap"])
        self.assertTrue(data["choices"][1]["available"])

    def test_the_practice_baseline_is_copied_and_the_step_is_done(self):
        self.choose_practice()
        self.assertEqual(self.status("starting-point"), "done")
        self.assertEqual(self.engine.progress["parts"]["part-4"]["start"], "practice")
        self.assertTrue(self.paths.part4_practice.prompt.is_file())
        self.assertEqual(self.data("starting-point")["chosen"], "practice")

    def test_a_bad_choice_is_refused_and_changes_nothing(self):
        self.open_to("starting-point")
        for bad in ({"action": "choose", "choice": "both"}, {"action": "choose"}, {"action": "x", "choice": "own"}, []):
            self.refused("bad_input", self.engine.step_submit, "starting-point", bad)
        self.assertFalse(self.paths.part4.exists())

    def test_the_choice_is_fixed_once_attempt_1_exists(self):
        self.to_hypothesis_1()
        before = self.paths.part4_practice.prompt.read_bytes()
        error = self.refused("start_fixed", self.submit, "starting-point", action="choose", choice="own")
        self.assertIn("reset your lesson progress", error.message)
        self.assertEqual(self.engine.progress["parts"]["part-4"]["start"], "practice")
        self.assertEqual(self.paths.part4_practice.prompt.read_bytes(), before)
        self.assertTrue(self.data("starting-point")["fixed"])


class KnownGood(P4):
    def test_no_score_is_shown_before_an_answer_is_saved(self):
        self.choose_practice()
        self.open_to("known-good")
        data = self.data("known-good")
        self.assertIsNone(data["result"])
        self.assertFalse(data["saved"])
        self.assertIn("Blocker", data["rules"])
        self.assertEqual(self.engine.progress["parts"].get("part-4", {}).get("attempts", []), [])

    def test_an_answer_that_meets_95_percent_finishes_the_step(self):
        self.choose_practice()
        self.pass_known_good()
        data = self.data("known-good")
        self.assertEqual((data["result"]["passes"], data["result"]["checked"], data["result"]["meets"]), (6, 6, True))
        self.assertIn("95%", data["result"]["text"])
        self.assertEqual(self.status("known-good"), "done")
        self.assertTrue(self.ap(1).known_good.is_file())

    def test_an_answer_under_95_percent_does_not_finish_and_never_offers_to_loosen_a_rule(self):
        self.choose_practice()
        self.open_to("known-good")
        self.submit("known-good", action="save", text=BAD)
        view = self.view("known-good")
        self.assertFalse(view["data"]["result"]["meets"])
        self.assertIn("Do not loosen a rule", view["data"]["result"]["next_step"])
        self.assertEqual(view["status"], "active")
        self.assertFalse(view["gate"]["ok"])
        self.submit("known-good", action="save", text=SAMPLE[1])
        self.assertEqual(self.status("known-good"), "done")

    def test_a_blank_answer_is_refused(self):
        self.choose_practice()
        self.open_to("known-good")
        self.refused("known_good_blank", self.submit, "known-good", action="save", text="   ")

    def test_the_known_good_score_is_apart_from_the_five_answer_score(self):
        self.round_1()
        view = self.attempts().view(1)
        self.assertEqual(view["known_good"]["checked"], 6)
        self.assertEqual(view["five_answers"]["total"], 30)

    def test_a_finished_known_good_step_cannot_be_overwritten(self):
        self.choose_practice()
        self.pass_known_good()
        self.refused("step_done", self.submit, "known-good", action="save", text=BAD)

    def test_on_the_participants_own_baseline_attempt_1_starts_from_part_3(self):
        self.finish_part_3()
        self.open_to("starting-point")
        self.submit("starting-point", action="choose", choice="own")
        self.pass_known_good()
        self.assertEqual(self.paths.attempt(1).project, self.paths.project / "part-4" / "attempts" / "1")
        self.assertTrue(self.paths.attempt(1).known_good.is_file())
        self.assertFalse(self.paths.part4_practice.project.exists())


class KnownGoodOnThePromptfooTrack(KnownGood):
    track = "promptfoo"

    def test_on_the_participants_own_baseline_attempt_1_starts_from_part_3(self):
        self.skipTest("the participant's own Part 3 baseline is built on the Script track in these tests")


class Hypothesis(P4):
    def test_the_hypothesis_step_lists_every_rule_of_the_starting_version_and_marks_the_failing_ones(self):
        self.to_hypothesis_1()
        self.open_to("hypothesis-1")
        data = self.data("hypothesis-1")
        self.assertEqual([(r["id"], r["passes"], r["failing"]) for r in data["start_rules"]],
                         [("C1", 4, True), ("C2", 4, True), ("C3", 4, True), ("C4", 5, False), ("C5", 3, True),
                          ("C6", 5, False)])
        self.assertEqual(data["start_overall"], {"passes": 25, "total": 30})
        self.assertEqual(data["start"], 0)

    def test_saving_finishes_the_step_and_it_stays_editable_until_there_is_an_answer(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1, "First guess.")
        self.assertEqual(self.status("hypothesis-1"), "done")
        self.submit("hypothesis-1", action="save", text="A better guess.")
        self.assertEqual(self.data("hypothesis-1")["hypothesis"], "A better guess.")
        self.assertFalse(self.data("hypothesis-1")["locked"])

    def test_the_edit_step_stays_locked_without_a_saved_hypothesis(self):
        self.to_hypothesis_1()
        self.open_to("hypothesis-1")
        self.assertEqual(self.status("edit-1"), "locked")
        self.refused("step_locked", self.engine.step_submit, "edit-1", {"action": "save", "prompt": "x"})
        self.refused("step_locked", self.engine.get_state, step="edit-1")

    def test_a_blank_hypothesis_is_refused(self):
        self.to_hypothesis_1()
        self.open_to("hypothesis-1")
        self.refused("hypothesis_blank", self.submit, "hypothesis-1", action="save", text="  ")
        self.assertEqual(self.status("hypothesis-1"), "active")

    def test_a_hypothesis_cannot_change_once_the_round_has_a_saved_answer(self):
        self.round_1()
        error = self.refused("hypothesis_locked", self.submit, "hypothesis-1", action="save", text="Written afterwards.")
        self.assertIn("not a prediction", error.message)
        self.assertTrue(self.data("hypothesis-1")["locked"])
        self.assertEqual(self.ap(1).hypothesis.read_text(encoding="utf-8").strip(), HYPOTHESIS)

    def test_only_the_hypothesis_text_is_saved_in_the_round_folder(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.assertNotIn(HYPOTHESIS, json.dumps(self.engine.progress))


class Edit(P4):
    def test_an_unchanged_prompt_cannot_finish_the_step(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.open_to("edit-1")
        start = self.data("edit-1")["start_prompt"]
        self.submit("edit-1", action="save", prompt=start)
        view = self.view("edit-1")
        self.assertEqual(view["status"], "active")
        self.assertFalse(view["data"]["changed"])
        self.assertFalse(view["gate"]["ok"])
        self.submit("edit-1", action="save", prompt=start.replace(" ", "  ") + "\n\n")  # spacing is not a change
        self.assertEqual(self.status("edit-1"), "active")

    def test_a_changed_prompt_finishes_the_step_and_saves_only_the_rounds_own_copy(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        before = {p: p.read_bytes() for p in self.paths.part4_practice.project.rglob("*")
                  if p.is_file() and "attempts" not in p.relative_to(self.paths.part4_practice.project).parts}
        own = {p.name: p.read_bytes() for p in self.paths.project.glob("*.md")}
        self.edit(1)
        self.assertEqual(self.status("edit-1"), "done")
        self.assertEqual(self.ap(1).prompt.read_text(encoding="utf-8"), ROUND_1_PROMPT)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertEqual({p.name: p.read_bytes() for p in self.paths.project.glob("*.md")}, own)

    def test_a_blank_prompt_is_refused(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.open_to("edit-1")
        self.refused("bad_input", self.submit, "edit-1", action="save", prompt="  ")

    def test_the_prompt_cannot_change_once_an_answer_is_saved(self):
        self.round_1()
        error = self.refused("edit_locked", self.submit, "edit-1", action="save", prompt="Too late.\n")
        self.assertIn("exact prompt", error.message)
        self.assertEqual(self.ap(1).prompt.read_text(encoding="utf-8"), ROUND_1_PROMPT)

    def test_round_2_starts_from_the_kept_round_1_prompt(self):
        self.round_1(decision="keep")
        self.save_hypothesis(2, "Second guess.")
        self.open_to("edit-2")
        data = self.data("edit-2")
        self.assertEqual(data["start_prompt"], ROUND_1_PROMPT)
        self.assertEqual(data["prompt"], ROUND_1_PROMPT)


class Measure(P4):
    def test_a_run_without_a_saved_hypothesis_is_refused_by_name(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.edit(1)
        self.open_to("measure-1")
        self.ap(1).hypothesis.unlink()
        error = self.refused("hypothesis_needed", self.engine.step_start, "measure-1")
        self.assertIn("hypothesis", error.message)
        self.refused("hypothesis_needed", self.submit, "measure-1", action="score")
        self.assertEqual(self.terminal.starts, [])

    def test_the_ai_window_opens_by_itself_once_and_holds_only_the_rounds_prompt(self):
        self.round_1_to_measure()
        view = self.view("measure-1")
        self.assertTrue(view["cli"]["can_auto_start"])
        self.assertEqual(view["cli"]["mode"], "paste")
        self.assertIn("output.txt", view["cli"]["line"])
        self.engine.step_auto_start("measure-1")
        self.assertEqual(len(self.terminal.starts), 1)
        cwd = Path(self.terminal.starts[0]["cwd"])
        self.assertEqual(cwd, self.paths.part4_blind)
        self.assertEqual([p.name for p in cwd.iterdir()], ["prompt.md"])
        self.assertEqual((cwd / "prompt.md").read_text(encoding="utf-8"), ROUND_1_PROMPT)
        self.assertEqual(self.terminal.starts[0]["command"], "mycli")
        self.engine.step_auto_start("measure-1")  # asked again: nothing more starts
        self.assertEqual(len(self.terminal.starts), 1)
        self.assertFalse(self.view("measure-1")["cli"]["can_auto_start"])
        self.assertEqual(self.terminal.typed, [])  # the app never types into the AI window

    def round_1_to_measure(self):
        self.to_hypothesis_1()
        self.save_hypothesis(1)
        self.edit(1)
        self.open_to("measure-1")

    def test_each_answer_is_saved_as_the_next_run_in_a_new_chat_and_the_window_closes(self):
        self.round_1_to_measure()
        self.collect(1, (1, 2, 3, 4, 5))
        self.assertEqual([self.ap(1).run_file(k).read_text(encoding="utf-8") for k in range(1, 6)],
                         [SAMPLE[k] for k in range(1, 6)])
        self.assertEqual(len(self.terminal.starts), 5)
        self.assertFalse(self.terminal.running)
        data = self.data("measure-1")
        self.assertTrue(data["all_saved"])
        self.assertTrue(data["can_score"])
        self.assertEqual(data["current_run"], 5)
        self.refused("runs_complete", self.engine.step_start, "measure-1")

    def test_the_model_is_recorded_in_the_steps_own_record(self):
        self.round_1_to_measure()
        self.engine.step_start("measure-1")
        record = self.engine.progress["parts"]["part-4"]["steps"]["measure-1"]
        self.assertTrue(record["auto_started"])
        self.assertEqual(record["model"], " and ".join(record["models"]))
        self.assertTrue(record["model"])

    def test_scoring_shows_every_rule_before_and_after_and_finishes_the_step(self):
        self.round_1(sources=(1, 1, 1, 1, 1))
        self.assertEqual(self.status("measure-1"), "done")
        compare = self.data("measure-1")["attempt"]["compare"]
        self.assertEqual([r["id"] for r in compare["rules"]], ["C1", "C2", "C3", "C4", "C5", "C6"])
        c5 = next(r for r in compare["rules"] if r["id"] == "C5")
        self.assertEqual((c5["before"]["passes"], c5["after"]["passes"], c5["change"]), (3, 5, "up"))
        self.assertEqual((compare["before"], compare["after"]), ({"passes": 25, "total": 30}, {"passes": 30, "total": 30}))
        self.assertIsNone(self.data("measure-1")["attempt"]["evidence"])  # no "measured gain" before the decision
        self.assertTrue(self.view("measure-1")["gate"]["ok"])

    def test_a_score_below_the_target_gives_a_next_step_and_never_blocks(self):
        self.round_1(sources=(2, 2, 2, 2, 2))
        five = self.data("measure-1")["attempt"]["five_answers"]
        self.assertFalse(five["meets_target"])
        self.assertTrue(five["next_step"])
        self.assertEqual(self.status("measure-1"), "done")

    def test_a_model_note_appears_when_the_model_differs_from_the_attempt_before(self):
        self.round_1(decision="keep")
        self.save_hypothesis(2, "Second guess.")
        self.edit(2, "Round two prompt.\n")
        self.attempts().manifest()[0]["model"] = "Another model"
        self.engine._save()
        self.open_to("measure-2")
        self.engine.step_start("measure-2")
        self.assertIn("different model", self.data("measure-2")["model_note"] or "")

    def test_the_first_practice_round_has_no_model_note(self):
        self.round_1_to_measure()
        self.engine.step_start("measure-1")
        self.assertIsNone(self.data("measure-1")["model_note"])

    def test_a_file_that_changes_after_scoring_makes_it_stale_and_it_can_be_scored_again(self):
        self.round_1()
        self.ap(1).run_file(1).write_text(SAMPLE[3], encoding="utf-8")
        view = self.view("measure-1")
        self.assertEqual(view["data"]["attempt"]["stale"], ["runs"])
        self.assertFalse(view["gate"]["ok"])
        self.submit("measure-1", action="score")
        self.assertEqual(self.data("measure-1")["attempt"]["stale"], [])

    def test_the_original_config_and_part_3_files_never_change(self):
        self.finish_part_3()
        self.open_to("starting-point")
        self.submit("starting-point", action="choose", choice="own")
        before = {p.name: p.read_bytes() for p in self.paths.project.glob("*") if p.is_file()}
        self.pass_known_good()
        self.save_hypothesis(1)
        self.edit(1)
        self.measure(1)
        self.assertEqual({p.name: p.read_bytes() for p in self.paths.project.glob("*") if p.is_file()}, before)

    def test_a_scoring_request_with_missing_answers_is_refused_plainly(self):
        self.round_1_to_measure()
        error = self.refused("answers_missing", self.submit, "measure-1", action="score")
        self.assertIn("five saved answers", error.message)

    def test_a_failed_start_shows_why_and_never_raises_from_the_automatic_start(self):
        self.round_1_to_measure()
        def refuse(*args, **kwargs):
            raise OSError("the program did not start")

        self.terminal.start = refuse
        self.engine.step_auto_start("measure-1")
        self.assertIn("could not be started", self.view("measure-1")["cli"]["blocked"])


class MeasureOnThePromptfooTrack(Measure):
    track = "promptfoo"

    def test_the_original_config_and_part_3_files_never_change(self):
        self.choose_practice()
        config = self.paths.part4_practice.config_yaml
        original = config.read_bytes()
        self.pass_known_good()
        self.save_hypothesis(1)
        self.edit(1)
        self.measure(1)
        self.assertEqual(config.read_bytes(), original)
        attempt_config = self.ap(1).config_yaml
        self.assertTrue(attempt_config.is_file())
        self.assertNotEqual(attempt_config.read_bytes(), b"")


class Decide(P4):
    def test_no_line_to_paste_is_shown_before_the_decision(self):
        self.round_1()
        self.open_to("decide-1")
        view = self.view("decide-1")
        self.assertFalse(view["data"]["decided"])
        self.assertIsNone(view["cli"])
        self.assertTrue(view["data"]["can_decide"])
        self.refused("not_decided", self.engine.step_start, "decide-1")

    def test_a_decision_is_explicit_and_shows_the_line_naming_the_practice_log(self):
        self.round_1()
        self.open_to("decide-1")
        self.submit("decide-1", action="decide", choice="keep")
        view = self.view("decide-1")
        self.assertEqual(view["data"]["decision"], "kept")
        line = view["cli"]["line"]
        self.assertIn("run + log mode", line)
        if self.track == "script":
            self.assertIn("part-4/practice/attempts/1/runs/run-1.txt", line)
        self.assertIn("Append the entry to part-4/practice/iteration-log.md as Iteration 1", line)
        self.assertIn("leave Change, Result and Reasoning empty", line)
        self.assertEqual(view["data"]["log_file"], "part-4/practice/iteration-log.md")
        self.assertIn("measured gain on these rules", view["data"]["attempt"]["evidence"]["text"])
        self.assertEqual(self.attempts().kept(), 1)

    def test_a_bad_decision_is_refused(self):
        self.round_1()
        self.open_to("decide-1")
        self.refused("bad_input", self.submit, "decide-1", action="decide", choice="maybe")
        self.assertEqual(self.attempts().kept(), 0)

    def test_a_round_with_stale_results_cannot_be_decided(self):
        self.round_1()
        self.ap(1).run_file(1).write_text("changed", encoding="utf-8")
        self.open_to("decide-1")
        self.assertFalse(self.data("decide-1")["can_decide"])
        error = self.refused("stale", self.submit, "decide-1", action="decide", choice="keep")
        self.assertIn("answers", error.message)
        self.assertEqual(self.attempts().kept(), 0)

    def test_undo_leaves_the_kept_version_as_it_was(self):
        self.round_1(decision="undo")
        self.assertEqual(self.attempts().kept(), 0)
        view = self.attempts().view(1)
        self.assertEqual((view["decision"], view["evidence"]["verdict"]), ("undone", "no measured gain on these rules"))

    def test_check_my_work_needs_a_decision_first(self):
        self.round_1()
        self.open_to("decide-1")
        self.engine.step_check("decide-1")
        view = self.view("decide-1")
        self.assertEqual(view["status"], "active")
        self.assertEqual(view["last_check"]["items"][0]["detail"], "Keep or undo this round first.")

    def test_a_matching_log_finishes_the_step_closes_the_window_and_the_log_is_never_edited(self):
        self.round_1(decision="keep")
        self.open_to("decide-1")
        self.engine.step_auto_start("decide-1")
        self.assertTrue(self.terminal.running)
        self.assertEqual(Path(self.terminal.starts[-1]["cwd"]), self.paths.project)
        self.write_practice_log(self.practice_log((1, "kept")))
        before = self.paths.part4_practice.iteration_log.read_bytes()
        self.engine.step_check("decide-1")
        self.assertEqual(self.status("decide-1"), "done")
        self.assertFalse(self.terminal.running)
        self.assertEqual(self.paths.part4_practice.iteration_log.read_bytes(), before)

    def test_each_failure_is_a_plain_sentence_naming_the_difference(self):
        self.round_1(decision="keep")
        self.open_to("decide-1")
        text = self.practice_log((1, "kept"))
        cases = [
            (text.replace("- Decision: kept", "- Decision: undone"), "says attempt 1 was undone"),
            (text.replace("- Reasoning: because", "- Reasoning:"), "no text for: Reasoning"),
            (text.replace("| C2 Grouped by client | 5/5", "| C2 Grouped by client | 1/5"), "C2"),
            (text.replace("- Hypothesis: " + HYPOTHESIS, "- Hypothesis: something else"), "not the one you saved"),
            (self.practice_log(zero=True), "no entry for attempt 1"),
        ]
        for log, expected in cases:
            with self.subTest(expected=expected):
                self.write_practice_log(log)
                self.engine.step_check("decide-1")
                detail = " ".join(i["detail"] for i in self.view("decide-1")["last_check"]["items"] if not i["ok"])
                self.assertIn(expected, detail)
                self.assertEqual(self.status("decide-1"), "active")

    def test_the_participants_own_log_is_not_read_for_practice(self):
        self.round_1(decision="keep")
        self.open_to("decide-1")
        (self.paths.project / "iteration-log.md").write_text(self.practice_log((1, "kept")), encoding="utf-8")
        self.engine.step_check("decide-1")
        self.assertEqual(self.status("decide-1"), "active")

    def test_an_undone_second_edit_leaves_round_1_kept_and_round_3_starts_from_it(self):
        self.round_1(decision="keep")
        self.save_hypothesis(2, "Second guess.")
        self.edit(2, "Round two prompt that will be undone.\n")
        self.measure(2, (2, 2, 2, 2, 2))
        self.open_to("decide-2")
        self.submit("decide-2", action="decide", choice="undo")
        self.assertEqual(self.attempts().kept(), 1)
        self.assertEqual(self.attempts().view(2)["evidence"]["verdict"], "no measured gain on these rules")
        text = self.practice_log((1, "kept"))
        self.write_practice_log(text + "\n" + log_entry(store.read_json(self.ap(2).results), 2, "undone", "Second guess."))
        self.engine.step_check("decide-2")
        self.assertEqual(self.status("decide-2"), "done")
        nxt = self.attempts().start()
        self.assertEqual((nxt["n"], nxt["parent"]), (3, 1))
        self.assertEqual(self.ap(3).prompt.read_text(encoding="utf-8"), ROUND_1_PROMPT)

    def test_the_closing_reflection_is_saved_after_the_step_is_done_and_never_blocks(self):
        self.round_1(decision="keep")
        self.save_hypothesis(2, "Second guess.")
        self.edit(2, "Round two prompt.\n")
        self.measure(2)
        self.open_to("decide-2")
        self.assertIsNone(self.data("decide-2")["reflection"])
        self.refused("bad_input", self.submit, "decide-2", action="reflect", text="too early")
        self.submit("decide-2", action="decide", choice="keep")
        self.write_practice_log(self.practice_log((1, "kept"), (2, "kept")))
        self.engine.step_check("decide-2")
        self.assertEqual(self.status("decide-2"), "done")
        reflection = self.data("decide-2")["reflection"]
        self.assertIn("what can the score not tell you", reflection["prompt"])
        self.submit("decide-2", action="reflect", text="I kept it because every rule held. The score cannot tell tone.")
        self.assertIn("every rule held", self.data("decide-2")["reflection"]["text"])
        self.assertIsNone(self.data("decide-1")["reflection"])  # only decide-2 asks


class DecideOnThePromptfooTrack(Decide):
    track = "promptfoo"

    def test_the_line_for_the_promptfoo_track_names_the_config_and_its_skill(self):
        self.round_1()
        self.open_to("decide-1")
        self.submit("decide-1", action="decide", choice="keep")
        line = self.view("decide-1")["cli"]["line"]
        self.assertIn("skills/build-promptfoo-config/SKILL.md", line)
        self.assertIn("part-4/practice/attempts/1/promptfooconfig.yaml", line)


class RoundsAndFinishing(P4):
    def test_two_documented_rounds_finish_part_4_whatever_the_decisions_and_scores(self):
        self.round_1(sources=(2, 2, 2, 2, 2), decision="undo")
        self.write_practice_log(self.practice_log((1, "undone")))
        self.engine.step_check("decide-1")
        self.save_hypothesis(2, "Second guess.")
        self.edit(2, "Round two prompt.\n")
        self.measure(2, (2, 2, 2, 2, 2))
        self.open_to("decide-2")
        self.assertEqual(self.engine.get_state(part="part-4")["series"]["parts"][3]["state"], "in_progress")
        self.submit("decide-2", action="decide", choice="undo")
        self.write_practice_log(self.practice_log((1, "undone"), (2, "undone")))
        self.engine.step_check("decide-2")
        self.assertEqual(self.engine.progress["parts"]["part-4"]["done"][-1], "decide-2")
        self.lesson_all_done()
        row = next(p for p in self.engine.get_state()["series"]["parts"] if p["id"] == "part-4")
        self.assertEqual(row["state"], "done")
        completion = self.attempts().completion()
        self.assertTrue(completion["ok"])
        self.assertTrue(completion["next_step"])  # below the target: a next step and no block

    def lesson_all_done(self):
        lessons = self.engine._lessons_block()["per_lesson"]
        for lesson in PART.lesson_ids:
            lessons[lesson] = {"status": "done", "activities": {}}
        self.engine._save()

    def test_one_documented_round_is_not_enough(self):
        self.round_1(decision="keep")
        self.write_practice_log(self.practice_log((1, "kept")))
        self.engine.step_check("decide-1")
        self.assertEqual(self.attempts().completion()["rounds"], 1)
        self.assertFalse(self.attempts().completion()["ok"])
        row = next(p for p in self.engine.get_state()["series"]["parts"] if p["id"] == "part-4")
        self.assertNotEqual(row["state"], "done")

    def test_round_3_is_optional_listed_after_the_course_and_never_counts(self):
        self.lesson_all_done()
        block = self.engine._progress_of(PART)
        block["done"][:] = list(PART.step_ids)
        self.engine._save()
        state = self.engine.get_state(part="part-4")
        row = next(p for p in state["series"]["parts"] if p["id"] == "part-4")
        self.assertEqual(row["state"], "done")
        self.assertEqual((row["done"], row["total"]), (len(PART.course), len(PART.course)))
        self.assertEqual([(s["id"], s["status"]) for s in state["optional_steps"]],
                         [("hypothesis-3", "optional"), ("edit-3", "locked"), ("measure-3", "locked"),
                          ("decide-3", "locked")])
        self.assertEqual(len(state["course"]), len(PART.course))
        self.assertTrue(self.engine.get_state(step="hypothesis-3")["step"]["optional"])

    def test_round_3_stays_shut_until_the_required_items_are_done(self):
        self.open_to("decide-2")
        self.assertEqual(self.status("hypothesis-3"), "locked")
        self.refused("step_locked", self.engine.get_state, step="hypothesis-3")

    def test_round_3_starts_from_the_kept_version(self):
        self.round_1(decision="keep")
        self.write_practice_log(self.practice_log((1, "kept")))
        self.engine.step_check("decide-1")
        self.save_hypothesis(2, "Second guess.")
        self.edit(2, "Round two prompt.\n")
        self.measure(2, (2, 2, 2, 2, 2))
        self.open_to("decide-2")
        self.submit("decide-2", action="decide", choice="undo")
        self.write_practice_log(self.practice_log((1, "kept"), (2, "undone")))
        self.engine.step_check("decide-2")
        self.lesson_all_done()
        self.assertEqual(self.status("hypothesis-3"), "active")
        self.submit("hypothesis-3", action="save", text="Third guess.")
        self.assertEqual(self.ap(3).prompt.read_text(encoding="utf-8"), ROUND_1_PROMPT)
        self.assertEqual(self.attempts().view(3)["parent"], 1)
        self.assertEqual(self.status("edit-3"), "active")


if __name__ == "__main__":
    import unittest
    unittest.main()
