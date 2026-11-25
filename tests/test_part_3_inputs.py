from __future__ import annotations

import hashlib
import unittest

from helpers import write_passed_preflight
from pf_helpers import FakePromptfoo
from test_engine_gates import EngineCase
from eval_coach.engine import Engine
from eval_coach import import_checks, part_steps, project, state


class ChooseInputs(EngineCase):
    def setUp(self):
        super().setUp()
        self.setup_project(choose_inputs=False)

    def choices(self, key):
        return self.data("inputs")["files"][key]

    def earlier_files(self):
        prompt = self.paths.part1_prompt("rewrite")
        prompt.parent.mkdir(exist_ok=True)
        rewrite = "Write a clear weekly update."
        prompt.write_bytes(rewrite.encode("utf-8"))
        record = self.engine._progress_of(state.PART_1)
        record["done"] = ["cold", "score", "rewrite"]
        record["steps"]["rewrite"]["prompt_hash"] = hashlib.sha256(prompt.read_bytes()).hexdigest()
        cases = self.paths.part2_file("test_cases")
        cases.parent.mkdir(exist_ok=True)
        cases.write_bytes(self.paths.test_cases.read_bytes() + b"\n<!-- My cases -->\n")
        self.engine._progress_of(state.PART_2)["done"] = ["draft", "thresholds", "test-file"]
        return prompt, cases

    def test_active_labels_fallback_and_read_only_detail(self):
        before = self.paths.progress_file.read_bytes()
        for key in ("prompt", "test_cases"):
            file = self.choices(key)
            self.assertEqual(file["source"], "practice")
            self.assertEqual(file["text"], import_checks.decode(getattr(self.paths, key).read_bytes())[0])
            self.assertIn("Finish", file["choices"][1]["reason"])
            self.assertTrue(file["choices"][2]["available"])
        self.assertEqual(self.data("inputs")["notes"], [])
        self.assertEqual(self.paths.progress_file.read_bytes(), before)
        self.assertEqual(self.terminal.starts, [])
        self.assertIsNone(self.state("inputs")["step"]["cli"])
        for action in (self.engine.step_start, self.engine.step_send, self.engine.step_skip):
            self.assert_code("not_supported", action, "inputs")
        self.paths.prompt.write_bytes(b"Only in this project")
        self.assertEqual(self.choices("prompt")["source"], "project")
        self.engine.progress["starter"] = "own"
        self.assertEqual(self.choices("prompt")["source"], "own")

    def test_offers_label_skipped_missing_blank_large_and_two_criteria(self):
        prompt, cases = self.earlier_files()
        self.engine._lessons_block()["skipped_parts"].append("part-2")
        self.assertIn("skipped Part 2", self.choices("test_cases")["choices"][1]["reason"])
        self.engine._lessons_block()["skipped_parts"].clear()
        prompt.unlink()
        self.assertIn("could not be found", self.choices("prompt")["choices"][1]["reason"])
        prompt.write_bytes(b" \r\n")
        self.assertIn("no text", self.choices("prompt")["choices"][1]["reason"])
        prompt.write_bytes(b"x" * (import_checks.MAX_BYTES + 1))
        self.assertIn("larger than", self.choices("prompt")["choices"][1]["reason"])
        cases.write_bytes(cases.read_bytes().split(b"### C3:")[0])
        self.assertIn("1 more", self.choices("test_cases")["choices"][1]["reason"])

    def test_changed_rewrite_is_not_active_until_chosen(self):
        prompt, _ = self.earlier_files()
        prompt.write_bytes(b"New rewrite")
        active = self.choices("prompt")
        self.assertEqual(active["source"], "practice")
        self.assertTrue(active["choices"][1]["available"])
        self.assertIn("changed after its answer", active["choices"][1]["warning"])
        self.engine.step_submit("inputs", {"use": {"prompt": "part1"}})
        carried = self.paths.prompt.read_text(encoding="utf-8")
        self.assertEqual(carried, "New rewrite\n\n--- Rough notes (added by the app) ---\n\n"
                         + part_steps.rough_notes() + "\n")
        self.assertEqual(self.choices("prompt")["source"], "part1")
        self.assertEqual(self.data("inputs")["notes"], [])

    def test_choices_preserve_evidence_and_lock_after_continue(self):
        prompt, cases = self.earlier_files()
        source_bytes = (prompt.read_bytes(), cases.read_bytes())
        original = self.paths.prompt.read_bytes()
        self.paths.test_cases.write_bytes(b"My hand-edited copy")
        self.engine.step_submit("inputs", {"both": "mine"})
        self.assertEqual(self.choices("test_cases")["source"], "part2")
        backup = self.paths.project / project.REPLACED_INPUTS
        self.assertCountEqual([path.read_bytes() for path in backup.iterdir()],
                              [original, b"My hand-edited copy"])
        self.engine.step_submit("inputs", {"use": {"prompt": "practice"}})
        self.assertEqual(self.paths.prompt.read_bytes(), original)
        self.assertEqual((prompt.read_bytes(), cases.read_bytes()), source_bytes)
        self.assertTrue(self.check("inputs")["ok"])
        saved = state.read_json(self.paths.progress_file)["steps"]["inputs"]["choice"]
        self.assertEqual(set(saved), {"prompt", "test_cases"})
        self.assertEqual(saved["prompt"], {"source": "practice", "sha256": hashlib.sha256(original).hexdigest()})
        self.assertEqual(set(saved["test_cases"]), {"source", "sha256"})
        self.assertNotIn(b"My cases", self.paths.progress_file.read_bytes())
        self.assert_code("step_done", self.engine.step_submit, "inputs", {"both": "mine"})
        cases.write_bytes(cases.read_bytes() + b"\nEdited later\n")
        self.assertIn("changed since", self.choices("test_cases")["state"])
        self.assertEqual(self.paths.test_cases.read_bytes(), source_bytes[1])
        cases.unlink()
        self.assertIn("no longer available", self.choices("test_cases")["state"])

    def test_carrying_both_earlier_files_forward_opens_generate(self):
        prompt, cases = self.earlier_files()
        self.engine.step_submit("inputs", {"both": "mine"})
        self.assertTrue(self.check("inputs")["ok"])
        self.assertEqual(self.state()["current_step"], "generate")
        self.assertEqual(self.paths.test_cases.read_bytes(), cases.read_bytes())
        self.assertIn(part_steps.rough_notes(), self.paths.prompt.read_text(encoding="utf-8"))
        self.assertNotIn("output.txt", self.paths.prompt.read_text(encoding="utf-8"))

    def test_unusable_earlier_files_leave_the_practice_task_as_the_labelled_fallback(self):
        prompt, cases = self.earlier_files()
        self.engine._lessons_block()["skipped_parts"].extend(["part-1", "part-2"])
        for key in ("prompt", "test_cases"):
            offer, practice = self.choices(key)["choices"][1:]
            self.assertFalse(offer["available"])
            self.assertIn("skipped", offer["reason"])
            self.assertTrue(practice["available"])
        self.assert_code("input_unavailable", self.engine.step_submit, "inputs", {"both": "mine"})
        self.assertEqual(self.choices("prompt")["source"], "practice")
        self.engine.step_submit("inputs", {"use": {"prompt": "practice", "test_cases": "practice"}})
        self.assertTrue(self.check("inputs")["ok"])
        self.assertEqual(self.state()["current_step"], "generate")

    def test_continue_blocks_invalid_pair_but_not_task_mismatch(self):
        original_cases = self.paths.test_cases.read_bytes()
        self.paths.prompt.write_bytes(b" \n")
        self.paths.test_cases.write_bytes(original_cases.split(b"### C3:")[0])
        self.assertFalse(self.check("inputs")["ok"])
        self.assert_code("step_locked", self.engine.step_start, "generate")
        self.paths.prompt.write_bytes(b"Different task")
        self.assertFalse(self.check("inputs")["ok"])
        self.paths.test_cases.write_bytes(original_cases)
        self.assertIn("different tasks", self.data("inputs")["notes"][0])
        self.assertTrue(self.check("inputs")["ok"])
        self.assertEqual(self.paths.prompt.read_bytes(), b"Different task")
        self.assertEqual(self.paths.test_cases.read_bytes(), original_cases)


class PromptfooInputs(ChooseInputs):
    def new_engine(self):
        write_passed_preflight(self.home, "promptfoo")
        return Engine(self.home, self.terminal, poll_interval=0.01, preflight_runner=FakePromptfoo())

    def test_confirming_inputs_preserves_promptfoo_track(self):
        self.assertTrue(self.check("inputs")["ok"])
        self.assertEqual(self.state()["step"]["track"], "promptfoo")
        self.assertEqual(self.state()["current_step"], "generate")


if __name__ == "__main__":
    unittest.main()
