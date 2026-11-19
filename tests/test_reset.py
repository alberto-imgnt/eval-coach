"""The two resets: inventory, backup, all-or-nothing, and what each one keeps."""
from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from unittest import mock

import helpers
from course_helpers import CourseBase
from helpers import ROOT

from eval_coach import project, reset, state

STANDIN_PROJECTS = ("standin-project", "standin-project-pf")
STANDIN_HOMES = ("standin-home", "standin-home-pf")
E2E = ROOT / "e2e-work"


def tree(root):
    """Every file under root as {relative path: sha256}."""
    root = Path(root)
    if not root.exists():
        return {}
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class InventoryTests(unittest.TestCase):
    """The lists in reset.py cover everything a finished stand-in run leaves behind."""

    def test_every_path_the_app_names_is_on_a_list(self):
        paths = project.Paths("C:\\home", "C:\\proj")
        for name, value in vars(paths).items():
            if not isinstance(value, Path) or name in ("home", "project"):
                continue
            for root, classify in ((paths.project, reset.classify_project_path), (paths.home, reset.classify_home_path)):
                try:
                    rel = value.relative_to(root).as_posix()
                except ValueError:
                    continue
                if name in ("part1", "part2"):
                    continue  # a folder of named files: each file is checked in the next tests
                self.assertIsNotNone(classify(rel + "/x" if not Path(rel).suffix else rel),
                                     f"{name} ({rel}) is on no reset list")

    def test_every_file_part_one_writes_is_on_a_list(self):
        paths = project.Paths("C:\\home", "C:\\proj")
        written = [paths.part1_prompt(s) for s in project.PART1_FILES] + [paths.part1_output(s) for s in project.PART1_FILES]
        written += [paths.part1_own(which) for which in project.PART1_OWN_FILES]
        for path in written:
            rel = path.relative_to(paths.project).as_posix()
            self.assertIsNotNone(reset.classify_project_path(rel), rel)
        self.assertIsNone(reset.classify_project_path("part-1/my-notes.txt"))
        self.assertEqual(reset.classify_home_path("part1/cold/output.txt"), "move")

    def test_part_one_outputs_move_with_both_resets_and_its_prompts_only_with_the_configuration_reset(self):
        for name in ("output-cold.txt", "output-framework.txt"):
            for configuration in (False, True):
                self.assertEqual(reset.classify_project_path(f"part-1/{name}", configuration), "move")
        for name in ("prompt-cold.md", "prompt-framework.md", "own-before.md", "own-after.md"):
            self.assertEqual(reset.classify_project_path(f"part-1/{name}", False), "keep")
            self.assertEqual(reset.classify_project_path(f"part-1/{name}", True), "move")

    def test_every_file_part_two_writes_is_on_a_list_and_only_the_configuration_reset_moves_them(self):
        paths = project.Paths("C:\\home", "C:\\proj")
        for which in project.PART2_FILES:
            rel = paths.part2_file(which).relative_to(paths.project).as_posix()
            self.assertEqual(reset.classify_project_path(rel, False), "keep", rel)
            self.assertEqual(reset.classify_project_path(rel, True), "move", rel)
        self.assertIsNone(reset.classify_project_path("part-2/my-notes.txt"))
        self.assertIsNone(reset.classify_project_path("part-2/nested/test-cases.md"))

    def test_every_file_a_restart_can_move_is_on_a_reset_list(self):
        paths = project.Paths("C:\\home", "C:\\proj")
        for part in (state.PART_1, state.PART_2):
            for step, owns in part.restart.items():
                for rel in owns.files + owns.rewrite:
                    self.assertEqual(reset.classify_project_path(rel, True), "move", f"{part.id} {step}: {rel}")
                for name in owns.scratch:
                    self.assertEqual(reset.classify_home_path(name, True), "move", f"{part.id} {step}: {name}")
                self.assertTrue(set(owns.rewrite) <= set(state.PART_2.restart["draft"].files), step)
        with self.assertRaisesRegex(ValueError, "my-notes.txt is on no reset list"):
            odd = state.Part("part-8", 8, "m", (), "", "", restart={"x": state.StepOwns(files=("part-1/my-notes.txt",))})
            reset.build_restart_plan("C:\\home", paths, odd, ["x"])

    def test_finished_standin_projects_have_no_unlisted_file(self):
        found = False
        for name in STANDIN_PROJECTS:
            folder = E2E / name
            if not folder.is_dir():
                continue
            found = True
            for rel in tree(folder):
                self.assertIsNotNone(reset.classify_project_path(rel), f"{name}/{rel} is on no reset list")
        if not found:
            self.skipTest("no finished stand-in project on this machine")

    def test_finished_standin_homes_have_no_unlisted_folder(self):
        found = False
        for name in STANDIN_HOMES:
            folder = E2E / name
            if not folder.is_dir():
                continue
            found = True
            for child in folder.iterdir():
                self.assertIsNotNone(reset.classify_home_path(child.name), f"{name}/{child.name} is on no reset list")
        if not found:
            self.skipTest("no finished stand-in home on this machine")

    def test_progress_reset_keeps_the_starting_files_and_skills(self):
        for rel in ("prompt-v0.md", "test-cases.md", "skills/build-eval-script/SKILL.md"):
            self.assertEqual(reset.classify_project_path(rel, configuration=False), "keep")
            self.assertEqual(reset.classify_project_path(rel, configuration=True), "move")

    def test_unknown_files_are_on_no_list(self):
        self.assertIsNone(reset.classify_project_path("notes.txt"))
        self.assertIsNone(reset.classify_project_path("skills/my-own-skill.md"))
        self.assertIsNone(reset.classify_home_path("something-new"))


class ResetBase(CourseBase):
    def setUp(self):
        super().setUp()
        self.setup_project()
        self.unknown = self.project / "notes.txt"
        self.unknown.write_text("mine", encoding="utf-8")
        self.populate()

    def populate(self):
        p = self.paths
        files = {
            p.check_py: "print('check')", p.config_yaml: "x: 1", p.live_config: "x: 2", p.agent_provider: "//",
            p.project / "results.json": "{}", p.iteration_log: "# log", p.run_file(1): "run one",
            p.fixtures / "fixture-bad.txt": "bad", p.examples / "c1-pass.txt": "pass",
            p.results_dir / "baseline.json": "{}", p.hook_run_file(1): "hook", p.practice_output("build-try"): "t",
            p.hook_output: "o", p.demo_check: "d", p.blind_prompt: "p", p.key_work_key: "SECRET KEY",
            p.practice_work("build-try") / "output.txt": "t", p.sealed_key: "SECRET KEY",
            self.home / "pending-lessons.json": "{}",
        }
        for path, text in files.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        self.engine.progress["done"].append("generate")
        self.engine.progress["track"] = "promptfoo"
        self.engine.progress["lessons"]["seed"] = "abc"
        self.engine._save()

    def reset_progress(self):
        return self.engine.reset_progress(True)

    def reset_config(self):
        return self.engine.reset_configuration(True)

    def backup(self):
        return self.home / reset.BACKUP_NAME

    def course_files(self):
        p = self.paths
        return [p.check_py, p.config_yaml, p.live_config, p.agent_provider, p.project / "results.json",
                p.iteration_log, p.run_file(1), p.fixtures / "fixture-bad.txt", p.examples / "c1-pass.txt"]

    def fresh_state(self, state):
        return {key: state[key] for key in ("configured", "course", "steps", "current_step", "current_item",
                                           "optional_steps", "review", "step")}


class ProgressResetTests(ResetBase):
    def test_refused_without_confirmation(self):
        before = tree(self.project)
        for value in (None, False, "yes", 1):
            self.assert_code("confirm_required", self.engine.reset_progress, value)
        self.assertEqual(tree(self.project), before)
        self.assertEqual(self.engine.progress["done"], ["generate"])
        self.assertFalse(self.backup().exists())

    def test_clears_progress_and_course_files_and_keeps_the_rest(self):
        starting = {name: tree(self.project).get(name) for name in ("prompt-v0.md", "test-cases.md")}
        skills = {k: v for k, v in tree(self.project).items() if k.startswith("skills/")}
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.course_files()}
        result = self.reset_progress()
        self.assertEqual(self.engine.progress["done"], [])
        self.assertIsNone(self.engine.progress["track"])
        self.assertIsNone(self.engine.progress["lessons"]["seed"])
        self.assertEqual(self.engine.progress["cli_command"], "mycli")
        after = tree(self.project)
        for name, digest in starting.items():
            self.assertEqual(after[name], digest)
        self.assertEqual({k: v for k, v in after.items() if k.startswith("skills/")}, skills)
        self.assertEqual(self.unknown.read_text(encoding="utf-8"), "mine")
        for path in self.course_files():
            self.assertFalse(path.exists(), path)
        self.assertEqual(sorted(after), sorted(["notes.txt", "prompt-v0.md", "test-cases.md", ".learning/progress.json"]
                                               + list(skills)))
        for path in self.course_files():
            moved = self.backup() / "project" / path.relative_to(self.project)
            self.assertEqual(hashlib.sha256(moved.read_bytes()).hexdigest(), before[str(path)])
        self.assertEqual(result["backup_folder"], str(self.backup()))
        self.assertIn(str(self.backup()), result["message"])
        for folder in (self.paths.runs, self.paths.fixtures, self.paths.examples, self.paths.learning):
            self.assertTrue(folder.is_dir())

    def test_scratch_folders_and_pending_progress_are_cleared(self):
        self.reset_progress()
        for name in ("hook", "demo", "blind", "key-work", "practice"):
            self.assertFalse((self.home / name).exists(), name)
        self.assertFalse((self.home / "pending-lessons.json").exists())

    def test_the_answer_key_is_gone_everywhere_including_the_backup(self):
        self.reset_progress()
        keys = [p for root in (self.home, self.project) for p in root.rglob("answer-key.md")]
        self.assertEqual(keys, [])
        self.assertFalse(self.paths.sealed_key.exists())

    def test_setup_and_downloads_are_kept(self):
        (self.home / "runtime").mkdir()
        (self.home / "runtime" / "node.exe").write_text("node", encoding="utf-8")
        preflight_before = (self.home / "preflight.json").read_bytes()
        app_before = (self.home / "app.json").read_bytes()
        self.reset_progress()
        self.assertEqual((self.home / "preflight.json").read_bytes(), preflight_before)
        self.assertEqual((self.home / "app.json").read_bytes(), app_before)
        self.assertTrue((self.home / "runtime" / "node.exe").exists())
        self.assertTrue(self.engine.get_state()["preflight"]["passed"])

    def test_only_the_newest_backup_remains(self):
        self.reset_progress()
        (self.paths.check_py).write_text("second", encoding="utf-8")
        self.reset_progress()
        self.assertEqual(sorted(p.name for p in self.home.iterdir() if p.name.startswith("reset-backup")),
                         ["reset-backup"])
        self.assertEqual((self.backup() / "project" / "check.py").read_text(encoding="utf-8"), "second")

    def test_the_track_can_be_chosen_again(self):
        self.assert_code("track_locked", self.engine.preflight_track, "script")
        self.reset_progress()
        self.engine.preflight_track("script")
        self.assertEqual(self.engine.get_state()["preflight"]["track"], "script")

    def test_state_equals_a_fresh_start(self):
        self.engine.progress["lessons"]["per_lesson"]["mission"] = {"status": "done", "activities": {}}
        self.engine._save()
        self.reset_progress()
        other = CourseBase()
        other.setUp()
        self.addCleanup(shutil.rmtree, other.tmp, True)
        other.setup_project()
        self.assertEqual(self.fresh_state(self.engine.get_state()), self.fresh_state(other.engine.get_state()))

    def test_a_running_cli_is_stopped_first(self):
        self.terminal.running = True
        self.engine._cli_step = "generate"
        stops = self.terminal.stops
        self.reset_progress()
        self.assertGreater(self.terminal.stops, stops)
        self.assertFalse(self.terminal.running)

    def test_no_project_clears_only_earlier_progress_and_makes_no_backup(self):
        home = self.tmp / "home2"
        helpers.write_passed_preflight(home)
        (home / "pending-lessons.json").write_text(json.dumps({"seed": "s"}), encoding="utf-8")
        from helpers import FakeTerminal
        from eval_coach.engine import Engine
        engine = Engine(home, FakeTerminal(), poll_interval=0.01, lessons=self.course)
        self.addCleanup(engine.shutdown)
        result = engine.reset_progress(True)
        self.assertIsNone(result["backup_folder"])
        self.assertFalse((home / "pending-lessons.json").exists())
        self.assertFalse((home / reset.BACKUP_NAME).exists())
        self.assertTrue((home / "preflight.json").exists())

    def test_a_failed_backup_changes_nothing(self):
        before_project, before_home = tree(self.project), tree(self.home)
        with mock.patch.object(reset, "move", side_effect=OSError("disk full")):
            err = self.assert_code("reset_backup_failed", self.engine.reset_progress, True)
        self.assertIn("Nothing was changed", err.message)
        self.assertEqual(tree(self.project), before_project)
        self.assertEqual(tree(self.home), before_home)
        self.assertEqual(self.engine.progress["done"], ["generate"])
        self.assertFalse((self.home / reset.STAGING_NAME).exists())

    def test_a_failure_part_way_puts_everything_back(self):
        before_project, before_home = tree(self.project), tree(self.home)
        real = reset.move
        calls = []

        def flaky(source, dest):
            calls.append(source)
            if len(calls) == 5:
                raise OSError("locked")
            real(source, dest)

        with mock.patch.object(reset, "move", side_effect=flaky):
            self.assert_code("reset_backup_failed", self.engine.reset_progress, True)
        self.assertGreater(len(calls), 5)
        self.assertEqual(tree(self.project), before_project)
        self.assertEqual(tree(self.home), before_home)
        self.assertEqual(self.engine.progress["done"], ["generate"])

    def test_a_failed_swap_puts_everything_back_and_keeps_the_key(self):
        before_project, before_home = tree(self.project), tree(self.home)
        with mock.patch.object(reset, "swap_backup", side_effect=OSError("busy")):
            self.assert_code("reset_failed", self.engine.reset_progress, True)
        self.assertEqual(tree(self.project), before_project)
        self.assertEqual(tree(self.home), before_home)
        self.assertTrue(self.paths.sealed_key.exists())


class ConfigurationResetTests(ResetBase):
    def test_refused_without_confirmation(self):
        self.assert_code("confirm_required", self.engine.reset_configuration, None)
        self.assertIsNotNone(self.engine.progress)

    def test_does_everything_the_progress_reset_does(self):
        self.reset_config()
        for path in self.course_files():
            self.assertFalse(path.exists(), path)
        for name in ("hook", "demo", "blind", "key-work", "practice"):
            self.assertFalse((self.home / name).exists(), name)
        self.assertEqual([p for root in (self.home, self.project) for p in root.rglob("answer-key.md")], [])

    def test_only_unknown_files_are_left_in_the_project_folder(self):
        self.reset_config()
        self.assertEqual(sorted(tree(self.project)), ["notes.txt"])
        self.assertEqual(self.unknown.read_text(encoding="utf-8"), "mine")
        self.assertTrue(self.backup().is_dir())
        for name in ("prompt-v0.md", "test-cases.md", "skills/build-eval-script/SKILL.md", "check.py"):
            self.assertTrue((self.backup() / "project" / name).is_file(), name)

    def test_setup_is_forgotten_and_the_app_is_as_on_first_run(self):
        self.reset_config()
        state = self.engine.get_state()
        self.assertFalse(state["configured"])
        self.assertEqual(state["setup"]["project_path"], "")
        self.assertEqual(state["setup"]["cli_command"], "")
        self.assertFalse(state["preflight"]["passed"])
        self.assertTrue(all(s["status"] == "locked" for s in state["steps"]))
        self.assertIsNone(self.engine.paths)
        self.assertFalse((self.home / "preflight.json").exists())
        self.assertFalse((self.home / "app.json").exists())

    def test_a_new_engine_also_starts_as_on_first_run(self):
        self.reset_config()
        state = self.new_engine().get_state()
        self.assertFalse(state["configured"])
        self.assertFalse(state["preflight"]["passed"])

    def test_downloads_are_kept(self):
        for name in ("runtime", "npm-cache", "promptfoo"):
            (self.home / name).mkdir()
            (self.home / name / "f.txt").write_text(name, encoding="utf-8")
        (self.home / "cli-recipes.json").write_text("{}", encoding="utf-8")
        self.reset_config()
        for name in ("runtime", "npm-cache", "promptfoo"):
            self.assertEqual((self.home / name / "f.txt").read_text(encoding="utf-8"), name)
        self.assertTrue((self.home / "cli-recipes.json").exists())

    def test_the_same_folder_can_be_set_up_again_without_touching_an_unknown_file(self):
        self.reset_config()
        helpers.write_passed_preflight(self.home)
        engine = self.new_engine()
        engine.setup({"project_path": str(self.project), "cli_command": "mycli", "starter": "northwind"})
        self.assertEqual(self.unknown.read_text(encoding="utf-8"), "mine")
        self.assertEqual(engine.progress["done"], [])
        self.assertIsNone(engine.progress["lessons"]["seed"])
        self.assertEqual(engine.get_state()["current_item"]["id"], "mission")

    def test_a_failed_backup_changes_nothing(self):
        before_project, before_home = tree(self.project), tree(self.home)
        with mock.patch.object(reset, "move", side_effect=OSError("disk full")):
            self.assert_code("reset_backup_failed", self.engine.reset_configuration, True)
        self.assertEqual(tree(self.project), before_project)
        self.assertEqual(tree(self.home), before_home)
        self.assertIsNotNone(self.engine.progress)
        self.assertTrue(self.engine.get_state()["preflight"]["passed"])

    def test_without_a_project_only_the_saved_setup_is_cleared(self):
        home = self.tmp / "home3"
        helpers.write_passed_preflight(home)
        from helpers import FakeTerminal
        from eval_coach.engine import Engine
        engine = Engine(home, FakeTerminal(), poll_interval=0.01, lessons=self.course)
        self.addCleanup(engine.shutdown)
        engine.reset_configuration(True)
        self.assertFalse((home / "preflight.json").exists())
        self.assertFalse(engine.get_state()["preflight"]["passed"])


class PartTwoFilesTests(ResetBase):
    """The worksheet and test cases are the participant's own work: kept by the progress reset, moved by the other."""

    def populate(self):
        super().populate()
        self.worksheet, self.cases = self.paths.part2_file("worksheet"), self.paths.part2_file("test_cases")
        self.other = self.paths.part2 / "my-notes.txt"
        for path, text in ((self.worksheet, '{"rows": []}'), (self.cases, "# mine"), (self.other, "not on a list")):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def test_the_progress_reset_keeps_both_files_unchanged(self):
        self.reset_progress()
        self.assertEqual(self.worksheet.read_text(encoding="utf-8"), '{"rows": []}')
        self.assertEqual(self.cases.read_text(encoding="utf-8"), "# mine")
        self.assertEqual(self.other.read_text(encoding="utf-8"), "not on a list")
        self.assertFalse((self.backup() / "project" / "part-2").exists())

    def test_the_configuration_reset_moves_both_files_and_leaves_an_unrelated_one(self):
        self.reset_config()
        self.assertFalse(self.worksheet.exists() or self.cases.exists())
        self.assertEqual((self.backup() / "project" / "part-2" / "test-cases.md").read_text(encoding="utf-8"), "# mine")
        self.assertTrue((self.backup() / "project" / "part-2" / "worksheet.json").is_file())
        self.assertEqual(self.other.read_text(encoding="utf-8"), "not on a list")


class ReportingTests(ResetBase):
    def test_the_state_names_the_backup_folder_and_the_words(self):
        settings = self.engine.get_state()["settings"]
        self.assertEqual(settings["backup_folder"], str(self.backup()))
        self.assertTrue(settings["has_project"])
        self.assertIn("progress", settings["text"]["reset"])
        self.assertNotIn("errors", settings["text"])

    def test_a_running_setup_job_blocks_a_reset(self):
        with mock.patch.object(self.engine.preflight, "job_running", return_value=True):
            self.assert_code("job_busy", self.engine.reset_progress, True)
        self.assertEqual(self.engine.progress["done"], ["generate"])
