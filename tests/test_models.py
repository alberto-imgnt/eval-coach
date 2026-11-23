"""The Sonnet or Haiku choice: launch options from data, the hidden model-list read, the saved results, reset."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

import helpers
import test_engine_gates as base
from eval_coach import models, resources
from eval_coach.models import Models
from eval_coach.terminal import TerminalManager
from helpers import ALIAS_MODELS, FakePty

DEFAULT = "the AI's own default model"
LISTING = ("\nSelect a model\n  1. gpt-5.4-mini\n  2. claude-haiku-5.5\n  3. claude-sonnet-4.5\n"
           "  4. claude-sonnet-5.5 (default)\n  5. claude-opus-5\n")
DISCOVER = {"command": "/model", "ready_quiet_seconds": 0.05, "read_quiet_seconds": 0.05, "max_seconds": 1.5,
            "stop_words": ["sign in", "log in", "trust", "allow", "approve"],
            "id_pattern": "[A-Za-z0-9][A-Za-z0-9._-]*"}
KEYWORD_MODELS = {
    "discover": DISCOVER,
    "sonnet": {"label": "Sonnet", "keyword": "sonnet", "launch": ["--model={id}"], "fallback_id": "fallback-sonnet-1"},
    "haiku": {"label": "Haiku", "keyword": "haiku", "launch": ["--model={id}"], "fallback_id": "fallback-haiku-1"},
}


def recipe(command, data):
    return {"id": command, "name": command, "cli_command": command, "shell": "none", "command": "", "models": data}


class ScriptedPty(FakePty):
    """Prints `banner` once started and `listing` after a line is typed, like a tool with a /model picker.

    A real pseudo console hands the app bytes, so `as_bytes` makes this one do the same.
    """

    as_bytes = False

    def __init__(self, argv, banner="ready >", listing=LISTING, **kw):
        super().__init__(argv, **kw)
        if banner:
            threading.Timer(0.01, lambda: self._emit(banner)).start()
        self._listing = listing

    def _emit(self, text):
        self.on_output(text.encode("utf-8") if self.as_bytes else text)

    def type_line(self, text):
        super().type_line(text)
        if self._listing:
            threading.Timer(0.01, lambda: self._emit(self._listing)).start()


class ModelsCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-models-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(self.tmp), True))
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.program = self.bin / ("copilot.exe" if sys.platform == "win32" else "copilot")
        self.program.write_bytes(b"version one")
        self.program.chmod(0o755)
        self.env = {"PATH": str(self.bin)}
        self.ptys = []

    def factory(self, **scripted):
        def make_pty(argv, **kw):
            pty = ScriptedPty(argv, **scripted, **kw)
            self.ptys.append(pty)
            return pty
        return lambda: TerminalManager(pty_factory=make_pty, argv_parser=lambda command, env=None: command.split())

    def models(self, data=None, **scripted):
        data = KEYWORD_MODELS if data is None else data
        return Models(self.home, lambda: [recipe("copilot", data)], DEFAULT, terminal_factory=self.factory(**scripted))

    def cache(self):
        return json.loads((self.home / models.CACHE_NAME).read_text(encoding="utf-8"))


class Resolve(ModelsCase):
    def test_a_fixed_alias_is_the_launch_option_and_never_triggers_discovery(self):
        m = self.models(ALIAS_MODELS)
        self.assertEqual(m.resolve("copilot", "sonnet", self.env), (["--model", "sonnet"], "sonnet"))
        self.assertEqual(m.resolve("copilot", "haiku", self.env), (["--model", "haiku"], "haiku"))
        self.assertEqual(self.ptys, [])

    def test_no_data_means_no_option_and_the_default_label(self):
        m = Models(self.home, lambda: [{"id": "x", "cli_command": "other", "shell": "none"}], DEFAULT)
        self.assertEqual(m.resolve("other", "sonnet", self.env), ([], DEFAULT))
        self.assertEqual(m.resolve("unknown-tool", "haiku", self.env), ([], DEFAULT))
        self.assertEqual(m.options("other"), [])

    def test_a_model_the_participant_already_named_is_left_alone(self):
        m = self.models(ALIAS_MODELS)
        self.assertEqual(m.resolve("copilot --model gpt-x", "haiku", self.env), ([], "gpt-x"))
        self.assertEqual(m.resolve("copilot --model=gpt-y", "haiku", self.env), ([], "gpt-y"))
        self.assertEqual(m.options("copilot --model gpt-x"), [])

    def test_the_command_is_matched_by_program_name_not_by_path_or_extension(self):
        m = self.models(ALIAS_MODELS)
        for command in ('C:\\Tools\\Copilot.EXE', '"C:\\Program Files\\x\\copilot.cmd" --flag', "copilot"):
            with self.subTest(command=command):
                self.assertEqual(m.resolve(command, "sonnet", self.env)[0][:2], ["--model", "sonnet"])

    def test_an_unquoted_program_path_with_spaces_is_recognised(self):
        m = self.models(ALIAS_MODELS)
        command = "C:\\Program Files\\Tools\\copilot.exe --some-flag"
        self.assertEqual(m.resolve(command, "haiku", self.env)[0], ["--model", "haiku"])
        self.assertEqual([o["id"] for o in m.options(command)], ["sonnet", "haiku"])

    def test_a_keyword_entry_uses_the_saved_id_for_this_program(self):
        m = self.models()
        marker = m.program_marker("copilot", self.env)
        (self.home / models.CACHE_NAME).write_text(json.dumps(
            {"copilot": {"program": marker, "ids": {"sonnet": "claude-sonnet-9.9"}}}), encoding="utf-8")
        self.assertEqual(m.resolve("copilot", "sonnet", self.env), (["--model=claude-sonnet-9.9"], "claude-sonnet-9.9"))
        self.assertEqual(self.ptys, [])

    def test_a_keyword_entry_falls_back_when_discovery_cannot_run(self):
        m = self.models()
        self.assertEqual(m.resolve("copilot", "haiku", self.env, can_discover=lambda: False),
                         (["--model=fallback-haiku-1"], "fallback-haiku-1"))
        self.assertEqual(self.ptys, [])
        no_discover = {k: v for k, v in KEYWORD_MODELS.items() if k != "discover"}
        self.assertEqual(self.models(no_discover).resolve("copilot", "sonnet", self.env)[1], "fallback-sonnet-1")
        self.assertEqual(self.ptys, [])

    def test_the_shipped_data_adds_no_permission_or_approval_option(self):
        shipped = json.loads(resources.read_text("content/cli-recipes.json"))["recipes"]
        launches = [arg for r in shipped for c in models.CHOICES for arg in r.get("models", {}).get(c, {}).get("launch", [])]
        self.assertTrue(launches)
        for arg in launches:
            self.assertRegex(arg, r"^--model(=\{id\})?$|^(sonnet|haiku)$")

    def test_every_supported_tool_offers_exactly_sonnet_and_haiku(self):
        shipped = json.loads(resources.read_text("content/cli-recipes.json"))["recipes"]
        m = Models(self.home, lambda: shipped, DEFAULT)
        for command in ("copilot", "claude", "devin"):
            with self.subTest(command=command):
                self.assertEqual([o["id"] for o in m.options(command)], ["sonnet", "haiku"])
        self.assertEqual(m.options("my-own-ai"), [])


class Discovery(ModelsCase):
    def test_the_newest_match_wins_and_only_the_list_command_is_typed(self):
        m = self.models()
        self.assertEqual(m.resolve("copilot", "sonnet", self.env), (["--model=claude-sonnet-5.5"], "claude-sonnet-5.5"))
        pty = self.ptys[0]
        self.assertEqual(pty.lines, ["/model"])
        self.assertEqual(pty.written, [])  # nothing selected, no other key
        self.assertTrue(pty.closed)
        self.assertEqual(pty.cwd, str(self.home / models.SCRATCH_NAME))
        self.assertEqual(list((self.home / models.SCRATCH_NAME).iterdir()), [])

    def test_output_arriving_as_bytes_is_read_the_same_way(self):
        ScriptedPty.as_bytes = True
        self.addCleanup(setattr, ScriptedPty, "as_bytes", False)
        m = self.models()
        self.assertEqual(m.resolve("copilot", "sonnet", self.env)[1], "claude-sonnet-5.5")

    def test_the_real_copilot_picker_shows_names_not_ids_so_the_fallback_is_used(self):
        # Recorded from GitHub Copilot CLI 1.0.113 on 2026-11-17 (only the model lines, no account text): the picker
        # lists display names such as "Claude Sonnet 5.5", which hold no model ID, so nothing is found and nothing is saved.
        listing = (Path(__file__).parent / "golden" / "copilot-model-picker.txt").read_text(encoding="utf-8")
        self.assertIsNone(models.newest_id(listing, "sonnet", DISCOVER["id_pattern"]))
        m = self.models(listing=listing)
        self.assertEqual(m.resolve("copilot", "sonnet", self.env), (["--model=fallback-sonnet-1"], "fallback-sonnet-1"))
        self.assertFalse((self.home / models.CACHE_NAME).exists())

    def test_one_read_finds_both_models(self):
        m = self.models()
        m.resolve("copilot", "sonnet", self.env)
        self.assertEqual(m.resolve("copilot", "haiku", self.env)[1], "claude-haiku-5.5")
        self.assertEqual(len(self.ptys), 1)

    def test_a_list_with_no_match_falls_back_and_saves_nothing(self):
        m = self.models(listing="\nSelect a model\n  1. gpt-5.4-mini\n  2. some-other-model\n")
        self.assertEqual(m.resolve("copilot", "sonnet", self.env)[1], "fallback-sonnet-1")
        self.assertFalse((self.home / models.CACHE_NAME).exists())
        self.assertTrue(self.ptys[0].closed)

    def test_a_question_on_screen_means_nothing_is_typed(self):
        for banner in ("Do you trust the files in this folder? (y/n)", "Please sign in to continue"):
            with self.subTest(banner=banner):
                self.ptys.clear()
                m = self.models(banner=banner)
                self.assertEqual(m.resolve("copilot", "sonnet", self.env)[1], "fallback-sonnet-1")
                self.assertEqual(self.ptys[0].lines, [])
                self.assertEqual(self.ptys[0].written, [])
                self.assertTrue(self.ptys[0].closed)

    def test_a_tool_that_prints_nothing_times_out_and_falls_back(self):
        data = {**KEYWORD_MODELS, "discover": {**DISCOVER, "max_seconds": 0.3}}
        m = self.models(data, banner="")
        self.assertEqual(m.resolve("copilot", "sonnet", self.env)[1], "fallback-sonnet-1")
        self.assertEqual(self.ptys[0].lines, [])
        self.assertTrue(self.ptys[0].closed)

    def test_a_tool_that_will_not_start_falls_back(self):
        def broken(argv, **kw):
            raise OSError("no such program")
        m = Models(self.home, lambda: [recipe("copilot", KEYWORD_MODELS)], DEFAULT,
                   terminal_factory=lambda: TerminalManager(pty_factory=broken, argv_parser=lambda c, env=None: c.split()))
        self.assertEqual(m.resolve("copilot", "sonnet", self.env)[1], "fallback-sonnet-1")

    def test_a_failed_read_is_not_tried_again_in_the_same_run(self):
        m = self.models(listing="nothing useful")
        m.resolve("copilot", "sonnet", self.env)
        m.resolve("copilot", "sonnet", self.env)
        self.assertEqual(len(self.ptys), 1)

    def test_it_does_not_run_while_an_ai_window_runs(self):
        m = self.models()
        self.assertEqual(m.resolve("copilot", "sonnet", self.env, can_discover=lambda: False)[1], "fallback-sonnet-1")
        self.assertEqual(self.ptys, [])
        # Skipped is not failed: the next start, with no AI running, reads the list.
        self.assertEqual(m.resolve("copilot", "sonnet", self.env, can_discover=lambda: True)[1], "claude-sonnet-5.5")

    def test_a_tool_that_is_not_installed_is_not_read(self):
        m = self.models()
        self.assertEqual(m.resolve("copilot", "sonnet", {"PATH": str(self.tmp / "empty")})[1], "fallback-sonnet-1")
        self.assertEqual(self.ptys, [])


class SavedResults(ModelsCase):
    def test_a_saved_id_is_reused_until_the_program_changes(self):
        m = self.models()
        m.resolve("copilot", "sonnet", self.env)
        self.assertEqual(len(self.ptys), 1)
        self.assertEqual(self.models().resolve("copilot", "sonnet", self.env)[1], "claude-sonnet-5.5")  # a new run
        self.assertEqual(len(self.ptys), 1)
        self.program.write_bytes(b"version two, a different size")
        fresh = self.models(listing=LISTING.replace("5.5 (default)", "6.0 (default)"))
        self.assertEqual(fresh.resolve("copilot", "sonnet", self.env)[1], "claude-sonnet-6.0")
        self.assertEqual(len(self.ptys), 2)

    def test_only_ids_and_a_version_marker_are_kept(self):
        self.models().resolve("copilot", "sonnet", self.env)
        saved = self.cache()
        self.assertEqual(set(saved), {"copilot"})
        self.assertEqual(set(saved["copilot"]), {"program", "ids"})
        self.assertEqual(saved["copilot"]["ids"], {"sonnet": "claude-sonnet-5.5", "haiku": "claude-haiku-5.5"})
        text = (self.home / models.CACHE_NAME).read_text(encoding="utf-8")
        for screen_text in ("Select a model", "gpt-5.4-mini", "opus", "default"):
            self.assertNotIn(screen_text, text)


class ParsingHelpers(unittest.TestCase):
    def test_control_sequences_are_stripped_before_matching(self):
        raw = "\x1b[2J\x1b[H\x1b[1;32mclaude-sonnet-4.5\x1b[0m \x1b]0;title\x07 and \x1b[90mclaude-sonnet-5.5\x1b[0m"
        self.assertEqual(models.newest_id(raw, "sonnet", r"[A-Za-z0-9][A-Za-z0-9._-]*"), "claude-sonnet-5.5")

    def test_a_word_without_a_digit_is_not_an_id(self):
        self.assertIsNone(models.newest_id("Sonnet is the default. sonnet-latest", "sonnet", r"[A-Za-z0-9][A-Za-z0-9._-]*"))

    def test_versions_compare_as_numbers_not_text(self):
        self.assertEqual(models.newest_id("claude-sonnet-4.10 claude-sonnet-4.9", "sonnet", r"[A-Za-z0-9][A-Za-z0-9._-]*"),
                         "claude-sonnet-4.10")


class EngineModelChoice(base.EngineCase):
    """The preference, the toggle's state, and what each AI start passes and records."""

    def new_engine(self):
        helpers.write_recipes(self.home, "mycli", ALIAS_MODELS)
        return super().new_engine()

    def start_generate(self):
        self.engine.step_start("generate")
        return self.terminal.starts[-1]

    def test_the_state_says_sonnet_by_default_and_offers_both(self):
        self.setup_project(cli_command="mycli")
        block = self.state()["ai_model"]
        self.assertEqual((block["preference"], block["available"], block["applies_next_start"]), ("sonnet", True, False))
        self.assertEqual(block["options"], [{"id": "sonnet", "label": "Sonnet"}, {"id": "haiku", "label": "Haiku"}])
        self.assertIn("next time", block["text"]["applies_next"])

    def test_the_toggle_is_not_available_for_a_command_with_no_model_data(self):
        self.setup_project(cli_command="another-ai")
        block = self.state()["ai_model"]
        self.assertEqual((block["available"], block["options"]), (False, []))
        self.assertEqual(self.start_generate()["command"], "another-ai")

    def test_the_toggle_is_not_available_when_the_command_names_its_own_model(self):
        self.setup_project(cli_command="mycli --model something")
        self.assertFalse(self.state()["ai_model"]["available"])
        self.assertEqual(self.start_generate()["command"], "mycli --model something")

    def test_the_choice_is_kept_across_a_new_engine_and_must_be_one_of_the_options(self):
        self.setup_project(cli_command="mycli")
        self.engine.set_model_preference("haiku")
        self.assertEqual(self.state()["ai_model"]["preference"], "haiku")
        self.assertEqual(json.loads((self.home / "preflight.json").read_text(encoding="utf-8"))["model_preference"], "haiku")
        self.engine = self.new_engine()
        self.assertEqual(self.state()["ai_model"]["preference"], "haiku")
        for bad in ("opus", "", None, 3, "SONNET"):
            with self.subTest(bad=bad):
                self.assert_code("bad_model", self.engine.set_model_preference, bad)
        self.assertEqual(self.state()["ai_model"]["preference"], "haiku")

    def test_a_start_passes_the_model_and_records_it(self):
        self.setup_project(cli_command="mycli")
        start = self.start_generate()
        self.assertEqual(start["command"], ["mycli", "--model", "sonnet"])
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet"])

    def test_a_change_applies_at_the_next_start_and_never_touches_a_running_window(self):
        self.setup_project(cli_command="mycli")
        self.start_generate()
        starts, stops = len(self.terminal.starts), self.terminal.stops
        self.engine.set_model_preference("haiku")
        self.assertTrue(self.state()["ai_model"]["applies_next_start"])
        self.assertEqual((len(self.terminal.starts), self.terminal.stops, self.terminal.typed), (starts, stops, []))
        self.assertEqual(self.start_generate()["command"], ["mycli", "--model", "haiku"])
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet", "haiku"])

    def test_no_model_data_records_the_default_label(self):
        self.setup_project(cli_command="another-ai")
        self.start_generate()
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], [DEFAULT])

    def test_the_setup_test_window_also_starts_on_the_chosen_model(self):
        self.setup_project(cli_command="mycli")
        self.engine.set_model_preference("haiku")
        self.engine._start_preflight_session("mycli", self.tmp, "Test", "preflight:test", ai=True)
        self.assertEqual(self.terminal.starts[-1]["command"], ["mycli", "--model", "haiku"])
        self.engine._start_preflight_session("mycli", self.tmp, "Sign in", "preflight:signin")
        self.assertEqual(self.terminal.starts[-1]["command"], "mycli")

    def test_a_configuration_reset_returns_to_sonnet_and_moves_the_saved_results(self):
        self.setup_project(cli_command="mycli")
        self.engine.set_model_preference("haiku")
        (self.home / models.CACHE_NAME).write_text("{}", encoding="utf-8")
        self.engine.reset_configuration(True)
        self.assertFalse((self.home / models.CACHE_NAME).exists())
        self.assertTrue((self.home / "reset-backup" / "app" / models.CACHE_NAME).is_file())
        self.assertEqual(self.state()["ai_model"]["preference"], "sonnet")

    def test_a_progress_reset_keeps_the_choice_and_the_saved_results(self):
        self.setup_project(cli_command="mycli")
        self.engine.set_model_preference("haiku")
        (self.home / models.CACHE_NAME).write_text("{}", encoding="utf-8")
        self.engine.reset_progress(True)
        self.assertTrue((self.home / models.CACHE_NAME).is_file())
        self.assertEqual(self.state()["ai_model"]["preference"], "haiku")


if __name__ == "__main__":
    unittest.main()
