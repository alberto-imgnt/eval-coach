"""Optional live mode on the promptfoo track (built on purpose, with an explicit warning)."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import unittest
from pathlib import Path

import helpers
import test_engine_gates as base
from helpers import FakePty, KIT, ROOT
from pf_helpers import FIXTURE_TESTS, RUN_TESTS
from test_http import ServerCase
from test_promptfoo_track import PF_STEPS, PfCase

from eval_coach import gates, project, promptfoo, resources, scan
from eval_coach import state as store
from eval_coach.engine import EngineError
from eval_coach.parsers import parse_live_config

PROVIDER_JS = KIT / "skills" / "build-promptfoo-config" / "agent-provider.js"
LIVE_LINE = ("Read skills/build-promptfoo-config/SKILL.md and follow it in live mode. "
             "I use {cli} with the model {model}.")
CLIS = ("copilot", "claude", "devin")


def live_config(cli="copilot", model="mid-tier-model", provider="'exec: node ./agent-provider.js'",
                assertion="javascript", extra_provider="", extra=""):
    lines = ["description: Northwind live runs", "prompts:", "  - file://prompt-v0.md", "providers:",
             f"  - id: {provider}", "    label: my-agent", "    config:"]
    if cli:
        lines.append(f"      cli: {cli}")
    if model:
        lines.append(f"      model: {model}")
    if extra_provider:
        lines.append(extra_provider)
    lines += ["defaultTest:", "  assert:", "    # C1: under 150 words", f"    - type: {assertion}",
              "      metric: C1_length", "      value: output.length > 0"]
    if extra:
        lines.append(extra)
    lines.append("tests:")
    for n in range(1, 6):
        lines.append(f"  - description: run-{n}")
    return "\n".join(lines) + "\n"


class LiveCase(PfCase):
    def to_live(self):
        """Baseline done on the promptfoo track, so live mode is open."""
        self.to_pf("baseline")
        self.engine.step_run_checker("baseline", "baseline")
        from test_baseline_step import log_text
        self.write_log(log_text(self.data("baseline")["summary"]))
        self.engine.step_start("baseline")
        self.assertTrue(self.check("baseline")["ok"])
        self.assertEqual(self.status_of_live(), "active")

    def status_of_live(self):
        return self.engine._status("live")

    def live(self):
        return self.state("live")["step"]

    def ready(self, cli="copilot", ack=True):
        self.engine.step_submit("live", {"cli": cli, "acknowledged": ack})

    def write_live_files(self, config=None, provider=True):
        self.paths.live_config.write_text(config if config is not None else live_config(), encoding="utf-8")
        if provider:
            shutil.copy(str(PROVIDER_JS), str(self.paths.agent_provider))

    def started(self, cli="copilot"):
        self.ready(cli)
        self.engine.step_start("live")

    def refused(self, code, fn, *args):
        with self.assertRaises(EngineError) as ctx:
            fn(*args)
        self.assertEqual(ctx.exception.code, code)
        return ctx.exception.message


class Availability(LiveCase):
    def test_it_exists_on_the_promptfoo_track_only(self):
        script = base.EngineCase()
        script.setUp()
        self.addCleanup(script.tearDown)
        script.setup_project()
        with self.assertRaises(EngineError) as ctx:
            script.engine.step_start("live")
        self.assertEqual(ctx.exception.code, "unknown_step")
        with self.assertRaises(EngineError) as ctx:
            script.engine.get_state("live")
        self.assertEqual(ctx.exception.code, "unknown_step")
        self.assertNotIn("live", [s["id"] for s in script.state()["steps"]])
        self.assertEqual(script.state()["optional_steps"], [])

    def test_it_is_locked_until_the_baseline_is_done(self):
        self.setup_project()
        self.assertEqual(self.state()["steps"][-1]["id"], "baseline")
        self.assertEqual(self.state()["optional_steps"], [])
        self.refused("step_locked", self.engine.step_start, "live")
        self.to_pf("baseline")
        self.refused("step_locked", self.engine.step_start, "live")
        self.assertNotIn("live", [i["id"] for i in self.state()["course"]])
        self.assertEqual(self.state()["optional_steps"], [])

    def test_it_never_changes_the_step_order_or_what_is_current(self):
        self.to_live()
        state = self.state()
        self.assertEqual(store.step_ids("promptfoo"), tuple(PF_STEPS))
        self.assertIsNone(state["current_step"])
        self.assertIsNone(state["current_item"])
        self.assertIsNone(state["step"])
        self.assertEqual(self.engine.progress["done"], PF_STEPS)
        self.assertNotIn("live", self.engine.progress["done"])
        self.assertEqual([s["id"] for s in state["steps"]], PF_STEPS)
        self.assertNotIn("live", [i["id"] for i in state["course"]])
        self.assertEqual(state["optional_steps"], [{"id": "live", "title": "Optional: live mode", "status": "optional"}])
        for entry in state["steps"]:
            self.assertEqual(entry["status"], "done")
        self.assertTrue(all(i["status"] in ("done", "skipped") for i in state["course"]))

    def test_the_course_is_complete_without_it(self):
        self.to_live()
        self.assertEqual({s["status"] for s in self.state()["steps"]}, {"done"})
        self.assertIsNone(self.state()["current_item"])
        self.assertEqual(self.status_of_live(), "active")  # reachable, but not the current item
        self.assertEqual(self.engine.progress["done"], PF_STEPS)

    def test_the_detail_says_it_is_optional(self):
        self.to_live()
        detail = self.live()
        self.assertTrue(detail["optional"])
        self.assertEqual(detail["status"], "active")
        self.assertEqual(detail["title"], "Optional: live mode")
        self.assertEqual(detail["track"], "promptfoo")

    def test_other_steps_are_unchanged_and_never_carry_the_optional_flag(self):
        self.to_live()
        for step in PF_STEPS:
            self.assertNotIn("optional", self.state(step)["step"])
        self.assertEqual(set(self.state("baseline")["step"]["cli"]),
                         {"line", "folder_label", "mode", "started", "sent", "blocked", "can_auto_start",
                          "has_result", "paste_ready"})

    def test_live_cannot_be_skipped_or_run_by_the_app(self):
        self.to_live()
        self.refused("cannot_skip", self.engine.step_skip, "live")
        for which in ("first_look", "fixtures", "baseline", "live"):
            self.refused("bad_input", self.engine.step_run_checker, "live", which)
        self.assertEqual(self.fake.calls[-1]["argv"][1:], list(promptfoo.EVAL_ARGS))

    def test_older_progress_without_a_live_record_loads_and_offers_it(self):
        self.to_live()
        saved = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        saved["steps"].pop("live", None)
        self.paths.progress_file.write_text(json.dumps(saved), encoding="utf-8")
        engine = self.new_engine()
        self.assertEqual(engine.progress["done"], PF_STEPS)
        self.assertEqual(engine.get_state()["optional_steps"][0]["status"], "optional")
        again = engine.get_state("live")["step"]
        self.assertFalse(again["data"]["acknowledged"])
        self.assertEqual(again["data"]["cli"], "")

    def test_older_progress_from_before_the_baseline_step_still_loads(self):
        self.to_pf("baseline")
        saved = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))
        self.assertNotIn("live", saved["steps"])
        engine = self.new_engine()
        self.assertNotIn("live", [s["id"] for s in engine.get_state()["steps"]])
        self.assertEqual(engine.get_state()["optional_steps"], [])

    def test_the_record_survives_a_restart(self):
        self.to_live()
        self.started("devin")
        engine = self.new_engine()
        data = engine.get_state("live")["step"]["data"]
        self.assertEqual((data["cli"], data["acknowledged"], data["started"]), ("devin", True, True))


class WarningText(LiveCase):
    def test_nothing_can_start_or_be_copied_before_the_box_is_ticked_and_a_cli_chosen(self):
        self.to_live()
        message = self.refused("warning_not_acknowledged", self.engine.step_start, "live")
        self.assertIn("tick the box", message)
        self.assertFalse(self.live()["cli"]["paste_ready"])
        self.assertEqual(self.terminal.starts[-1]["label"], "Log your baseline")  # no CLI started for live
        self.assertEqual(self.live()["cli"]["start_blocked"], message)
        self.engine.step_submit("live", {"acknowledged": True})
        message = self.refused("cli_not_chosen", self.engine.step_start, "live")
        self.assertIn("Choose the AI tool", message)
        self.assertFalse(self.live()["cli"]["paste_ready"])
        self.engine.step_submit("live", {"cli": "claude"})
        self.assertIsNone(self.live()["cli"]["start_blocked"])
        self.assertTrue(self.live()["cli"]["paste_ready"])
        self.engine.step_start("live")
        self.assertEqual(self.terminal.starts[-1]["label"], "Optional: live mode")

    def test_unticking_turns_the_text_to_paste_off_again(self):
        self.to_live()
        self.started()
        self.assertTrue(self.live()["cli"]["paste_ready"])
        self.engine.step_submit("live", {"acknowledged": False})
        self.assertFalse(self.live()["cli"]["paste_ready"])
        self.refused("not_supported", self.engine.step_send, "live")
        self.assertEqual(self.terminal.typed, [])

    def test_live_mode_is_never_started_by_itself(self):
        self.to_live()
        self.ready()
        cli = self.live()["cli"]
        self.assertEqual((cli["mode"], cli["can_auto_start"]), ("paste", False))
        starts = len(self.terminal.starts)
        self.engine.step_auto_start("live")
        self.assertEqual(len(self.terminal.starts), starts)

    def test_the_acknowledgement_and_cli_are_validated(self):
        self.to_live()
        for bad in ("yes", 1, None, [True]):
            self.refused("bad_input", self.engine.step_submit, "live", {"acknowledged": bad})
        for bad in ("gemini", "COPILOT", 3, "copilot --yolo"):
            self.refused("bad_input", self.engine.step_submit, "live", {"cli": bad})
        self.engine.step_submit("live", {"cli": "devin"})
        self.engine.step_submit("live", {"cli": ""})
        self.assertEqual(self.live()["data"]["cli"], "")

    def test_the_warning_is_in_the_step_text_and_says_exactly_what_the_helper_does(self):
        self.to_live()
        ui = self.live()["ui"]
        text = " ".join(ui["warning_points"])
        self.assertIn("call your own signed-in AI tool to write fresh outputs", text)
        self.assertIn("No API key is involved", text)
        self.assertIn("Devin CLI the helper adds --permission-mode auto", text)
        self.assertIn("turns on Devin's auto mode for that run", text)
        self.assertIn("may act without asking you", text)
        self.assertIn("For GitHub Copilot CLI and Claude Code the helper adds no permission flag", text)
        self.assertIn("empty temporary folder, so it cannot see test-cases.md", text)
        self.assertIn("Results change from run to run", text)
        self.assertIn("does not use your saved runs and never changes your baseline", text)
        self.assertIn("The app does not run live mode", text)
        self.assertIn("you can skip this step", ui["warning_intro"])
        self.assertIn("complete without it", ui["warning_intro"])
        self.assertIn("auto mode", ui["ack_label"])


class TypedLine(LiveCase):
    def test_the_exact_line_with_the_chosen_cli_and_the_saved_model(self):
        self.to_live()
        for cli in CLIS:
            self.started(cli)
            self.engine.step_submit("live", {"model_name": "  my\nmodel\t\x07 v2 "})
            self.assertEqual(self.live()["cli"]["line"], LIVE_LINE.format(cli=cli, model="my model v2"))
            self.assertEqual(self.paste("live"), LIVE_LINE.format(cli=cli, model="my model v2"))
            self.engine.step_stop("live")

    def test_only_that_line_is_pasted_and_the_cli_command_gets_no_flag(self):
        self.to_live()
        self.started("devin")
        start = self.terminal.starts[-1]
        self.assertEqual(start["command"], self.engine.progress["cli_command"])
        self.assertEqual(start["cwd"], str(self.project))
        before = len(self.terminal.keystrokes)
        self.assertEqual(self.paste("live"), LIVE_LINE.format(cli="devin", model="sonnet"))
        self.assertEqual(len(self.terminal.keystrokes), before + 1)  # only the participant's paste reached the AI
        self.assertEqual(self.terminal.typed, [])
        self.assertNotIn("--permission-mode", json.dumps(start))
        self.assertNotIn("auto", self.engine.progress["cli_command"])

    def test_the_line_shows_every_option_until_one_is_chosen(self):
        self.to_live()
        self.assertEqual(self.live()["cli"]["line"],
                         LIVE_LINE.format(cli="<copilot | claude | devin>", model="sonnet"))

    def test_a_start_records_a_model_so_the_line_is_never_blocked_for_a_missing_one(self):
        self.to_live()
        self.ready()
        self.engine.step_submit("live", {"model_name": "   "})
        self.engine.step_start("live")
        self.assertIsNone(self.live()["cli"]["blocked"])
        self.assertEqual(self.engine.progress["steps"]["generate"]["models_used"], ["sonnet"])
        self.assertEqual(self.paste("live"), LIVE_LINE.format(cli="copilot", model="sonnet"))

    def test_the_model_has_one_home_shared_with_the_baseline(self):
        self.to_live()
        self.engine.step_submit("live", {"model_name": "shared-name"})
        self.assertEqual(self.engine.progress["steps"]["generate"]["model_name"], "shared-name")


class Hashes(LiveCase):
    def test_hashes_are_noted_once_at_the_first_start(self):
        self.to_live()
        self.ready()
        self.assertFalse(self.live()["data"]["started"])
        main = hashlib.sha256(self.paths.config_yaml.read_bytes()).hexdigest()
        log = hashlib.sha256(self.paths.iteration_log.read_bytes()).hexdigest()
        self.engine.step_start("live")
        saved = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))["steps"]["live"]
        self.assertEqual(saved["start_hashes"], {"config": main, "log": log})
        self.paths.config_yaml.write_text(self.paths.config_yaml.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")
        self.engine.step_stop("live")
        self.engine.step_start("live")  # a second Start does not absorb the change
        saved = json.loads(self.paths.progress_file.read_text(encoding="utf-8"))["steps"]["live"]
        self.assertEqual(saved["start_hashes"]["config"], main)

    def test_a_missing_log_is_recorded_as_missing(self):
        self.to_live()
        self.paths.iteration_log.unlink()
        self.started()
        self.assertIsNone(self.engine.progress["steps"]["live"]["start_hashes"]["log"])
        self.write_live_files()
        self.assertTrue(self.check("live")["ok"])


class Gate(LiveCase):
    def result(self):
        return self.check("live")

    def failing(self, result):
        return [i["label"] for i in result["items"] if not i["ok"]]

    def test_a_complete_live_step_passes_and_stops_the_cli(self):
        self.to_live()
        self.started()
        self.write_live_files()
        result = self.result()
        self.assertTrue(result["ok"], result)
        self.assertFalse(self.terminal.running)
        self.assertEqual(self.status_of_live(), "done")
        self.assertEqual(self.state()["optional_steps"][0]["status"], "done")
        self.assertEqual(self.engine.progress["done"], PF_STEPS)
        self.assertIsNone(self.state()["current_item"])
        self.refused("step_done", self.engine.step_start, "live")

    def test_the_app_runs_nothing_for_this_gate(self):
        self.to_live()
        self.started()
        self.write_live_files()
        calls = len(self.fake.calls)
        self.assertTrue(self.result()["ok"])
        self.assertEqual(len(self.fake.calls), calls)
        self.assertFalse((self.project / "results-live.json").exists())

    def test_each_missing_piece_is_named_with_a_next_action(self):
        self.to_live()
        result = self.check("live")
        self.assertEqual(self.failing(result), ["Warning read", "promptfooconfig.live.yaml exists", "Only the helper, rules only",
                                                "agent-provider.js is unchanged", "Live mode was started here",
                                                "promptfooconfig.yaml is unchanged", "iteration-log.md is unchanged"])
        for item in result["items"]:
            self.assertRegex(item["detail"], r"(Press|Read|Ask|Check)", item)
            self.assertTrue(item["detail"].rstrip().endswith("."), item)

    def test_the_main_config_must_be_unchanged(self):
        self.to_live()
        self.started()
        self.write_live_files()
        self.paths.config_yaml.write_text(self.paths.config_yaml.read_text(encoding="utf-8") + "# edit\n", encoding="utf-8")
        result = self.result()
        self.assertEqual(self.failing(result), ["promptfooconfig.yaml is unchanged"])
        self.assertIn("Ask your AI to undo that change", result["items"][-2]["detail"])
        self.assertEqual(self.status_of_live(), "active")

    def test_the_log_must_be_unchanged_even_by_a_new_entry(self):
        self.to_live()
        self.started()
        self.write_live_files()
        self.paths.iteration_log.write_text(self.paths.iteration_log.read_text(encoding="utf-8") + "\n## Iteration 1\n",
                                           encoding="utf-8")
        result = self.result()
        self.assertEqual(self.failing(result), ["iteration-log.md is unchanged"])
        self.assertIn("never changes your baseline", result["items"][-1]["detail"])

    def test_a_deleted_main_config_or_log_fails(self):
        self.to_live()
        self.started()
        self.write_live_files()
        self.paths.iteration_log.unlink()
        self.assertEqual(self.failing(self.result()), ["iteration-log.md is unchanged"])

    def test_the_provider_file_must_be_the_bundled_copy(self):
        self.to_live()
        self.started()
        self.write_live_files(provider=False)
        self.assertEqual(self.failing(self.result()), ["agent-provider.js is unchanged"])
        self.paths.agent_provider.write_text(PROVIDER_JS.read_text(encoding="utf-8") + "\n// edited\n", encoding="utf-8")
        self.assertEqual(self.failing(self.result()), ["agent-provider.js is unchanged"])
        shutil.copy(str(PROVIDER_JS), str(self.paths.agent_provider))
        self.assertTrue(self.result()["ok"])

    def test_the_scan_stops_model_graded_checks_other_providers_and_keys(self):
        self.to_live()
        self.started()
        cases = {
            "an llm-rubric check": live_config(assertion="llm-rubric"),
            "another provider": live_config(provider="openai:gpt-4o"),
            "the echo provider": live_config(provider="echo"),
            "an api key": live_config(extra_provider="      apiKey: sk-123"),
            "a different path": live_config(provider="'exec: node ./evil.js'"),
            "an unsupported CLI": live_config(cli="gemini"),
        }
        for name, config in cases.items():
            with self.subTest(name):
                self.write_live_files(config)
                result = self.result()
                self.assertEqual(self.failing(result), ["Only the helper, rules only"], name)
                self.assertTrue(result["items"][2]["detail"].rstrip().endswith("."))
                self.assertEqual(self.status_of_live(), "active")

    def test_a_pass_after_a_fail_needs_no_restart(self):
        self.to_live()
        self.started()
        self.write_live_files(live_config(assertion="llm-rubric"))
        self.assertFalse(self.result()["ok"])
        self.write_live_files()
        self.assertTrue(self.result()["ok"])

    def test_the_data_shows_what_the_panel_needs(self):
        self.to_live()
        self.started("copilot")
        data = self.live()["data"]
        self.assertEqual([c["id"] for c in data["clis"]], list(CLIS))
        self.assertEqual((data["config_exists"], data["provider_exists"], data["scan"]), (False, False, []))
        self.write_live_files(live_config(assertion="llm-rubric"))
        data = self.live()["data"]
        self.assertEqual((data["config_exists"], data["provider_exists"], data["provider_ok"]), (True, True, True))
        self.assertIn("llm-rubric", data["scan"][0]["message"])

    def test_nothing_else_is_changed_by_the_step(self):
        self.to_live()
        before = {n: (self.project / n).read_bytes() for n in ("promptfooconfig.yaml", "iteration-log.md", "test-cases.md",
                                                              "prompt-v0.md")}
        self.started()
        self.write_live_files()
        self.assertTrue(self.result()["ok"])
        for name, data in before.items():
            self.assertEqual((self.project / name).read_bytes(), data, name)
        self.assertFalse(self.paths.project_key.exists())


class Scan(unittest.TestCase):
    def messages(self, text, clis=CLIS):
        return [m["message"] for m in scan.scan_live_config_source(text, clis)]

    def test_the_skills_own_shape_passes(self):
        for cli in CLIS + (None,):
            with self.subTest(cli=cli):
                self.assertEqual(self.messages(live_config(cli=cli)), [])

    def test_the_provider_must_be_the_helper_written_the_way_the_skill_writes_it(self):
        for ok in ("'exec: node ./agent-provider.js'", '"exec: node ./agent-provider.js"', "exec:node ./agent-provider.js",
                   "'exec: node .\\agent-provider.js'"):
            with self.subTest(ok=ok):
                self.assertEqual(self.messages(live_config(provider=ok)), [])
        for bad in ("echo", "openai:gpt-4o", "'exec: node ./agent-provider.js --x'", "'exec: python ./agent-provider.js'",
                    "'exec: node ./other/agent-provider.js'", "'exec: node ./agent-provider.js && calc'",
                    "file://provider.js", "'exec: node agent-provider.js'"):
            with self.subTest(bad=bad):
                found = self.messages(live_config(provider=bad))
                self.assertEqual(len(found), 1, found)
                self.assertIn("Ask your AI", found[0])

    def test_every_model_graded_type_the_main_scan_knows_is_stopped(self):
        for kind in scan.MODEL_GRADED + ("model-graded-closedqa", "context-faithfulness", "llm-whatever", "not-llm-rubric"):
            with self.subTest(kind=kind):
                found = self.messages(live_config(assertion=kind))
                self.assertEqual(len(found), 1)
                self.assertIn(kind, found[0])

    def test_rule_assertions_pass(self):
        for kind in ("javascript", "regex", "contains", "word-count", "not-contains", "icontains-any"):
            self.assertEqual(self.messages(live_config(assertion=kind)), [], kind)

    def test_keys_and_addresses_are_stopped(self):
        for line in ("      apiKey: x", "      api_key: x", "      apiKeyEnvar: OPENAI_API_KEY", "      apiBaseUrl: http://x"):
            with self.subTest(line=line):
                found = self.messages(live_config(extra_provider=line))
                self.assertEqual(len(found), 1)
                self.assertIn("needs no API key", found[0])

    def test_a_provider_key_inside_a_check_is_stopped(self):
        found = self.messages(live_config(extra="      provider: openai:gpt-4o"))
        self.assertEqual(len(found), 1)
        self.assertIn("a model would grade", found[0])

    def test_no_provider_at_all(self):
        found = self.messages("description: x\ntests:\n  - description: run-1\n")
        self.assertEqual(len(found), 1)
        self.assertIn("does not name a provider", found[0])

    def test_the_cli_must_be_one_of_the_options_when_options_are_given(self):
        self.assertEqual(len(self.messages(live_config(cli="gemini"))), 1)
        self.assertIn("gemini", self.messages(live_config(cli="gemini"))[0])
        self.assertEqual(self.messages(live_config(cli="gemini"), clis=()), [])

    def test_bytes_with_a_byte_order_mark_and_windows_line_endings(self):
        text = live_config().replace("\n", "\r\n")
        self.assertEqual(scan.scan_live_config_source(("\ufeff" + text).encode("utf-8-sig"), CLIS), [])

    def test_every_message_ends_with_a_next_action_and_uses_no_banned_word(self):
        samples = [live_config(assertion="llm-rubric"), live_config(provider="echo"), live_config(extra_provider="      apiKey: x"),
                   live_config(cli="gemini"), live_config(extra="      provider: x"), "tests:\n"]
        for sample in samples:
            for message in self.messages(sample):
                with self.subTest(message=message[:60]):
                    self.assertRegex(message, r"(Ask your AI|Choose one)")
                    self.assertTrue(message.rstrip().endswith("."))

    def test_the_main_scan_is_unchanged(self):
        self.assertEqual(scan.scan_config_source("providers:\n  - id: 'exec: node ./agent-provider.js'\n"
                                                 "tests:\n  - description: run-1\n")[0]["message"].count("Only the"), 1)

    def test_the_parser_reads_the_cli_and_keys(self):
        parsed = parse_live_config(live_config(cli="devin", extra_provider="      apiKey: x"))
        self.assertEqual(parsed["clis"], ["devin"])
        self.assertEqual(parsed["secret_keys"], ["apiKey"])
        self.assertEqual(parsed["providers"], ["exec: node ./agent-provider.js"])
        self.assertEqual(parsed["test_names"], [f"run-{n}" for n in range(1, 6)])


class Http(ServerCase):
    def to_live(self):
        self.post("/api/preflight/track", {"track": "promptfoo"})
        self.setup_project()
        self.engine.progress["track"] = "promptfoo"
        self.engine.progress["done"] = list(PF_STEPS)
        self.engine._save()

    def test_the_state_lists_it_and_the_detail_is_served(self):
        self.to_live()
        status, _, raw = self.request("GET", "/api/state")
        state = json.loads(raw)
        self.assertIsNone(state["step"])
        self.assertEqual(state["optional_steps"][0]["status"], "optional")
        status, _, raw = self.request("GET", "/api/state?step=live")
        detail = json.loads(raw)["step"]
        self.assertEqual(status, 200)
        self.assertEqual(detail["id"], "live")
        self.assertTrue(detail["optional"])
        self.assertIsNotNone(detail["cli"]["start_blocked"])

    def test_the_whole_flow_over_http_with_only_the_one_line_typed(self):
        self.to_live()
        status, body = self.post("/api/step/start", {"step": "live"})
        self.assertEqual((status, body["error"]["code"]), (400, "warning_not_acknowledged"))
        self.assertEqual(FakePty.created, [])
        status, body = self.post("/api/step/submit", {"step": "live", "data": {"acknowledged": True}})
        self.assertEqual(status, 200, body)
        status, body = self.post("/api/step/start", {"step": "live"})
        self.assertEqual((status, body["error"]["code"]), (400, "cli_not_chosen"))
        status, body = self.post("/api/step/submit", {"step": "live", "data": {"cli": "claude"}})
        self.assertEqual(status, 200, body)
        status, body = self.post("/api/step/start", {"step": "live"})
        self.assertEqual(status, 200, body)
        pty = FakePty.created[-1]
        self.assertEqual(pty.argv, ["cli"])
        status, body = self.post("/api/step/send", {"step": "live"})
        self.assertEqual((status, body["error"]["code"]), (400, "not_supported"))
        line = body["state"]["step"]["cli"]["line"]
        self.assertEqual(line, LIVE_LINE.format(cli="claude", model="the AI's own default model"))
        status, body = self.post("/api/terminal/input", {"data": base64.b64encode((line + "\r").encode()).decode()})
        self.assertEqual(status, 200, body)
        self.assertEqual(pty.written, [(line + "\r").encode()])
        self.assertEqual(pty.lines, [])
        status, body = self.post("/api/step/check", {"step": "live"})
        self.assertEqual(status, 200)
        self.assertFalse(body["state"]["step"]["last_check"]["ok"])
        paths = project.Paths(self.tmp / "home", self.tmp / "project")
        paths.live_config.write_text(live_config(cli="claude"), encoding="utf-8")
        shutil.copy(str(PROVIDER_JS), str(paths.agent_provider))
        status, body = self.post("/api/step/check", {"step": "live"})
        self.assertTrue(body["state"]["step"]["last_check"]["ok"], body["state"]["step"]["last_check"])
        self.assertEqual(body["state"]["optional_steps"][0]["status"], "done")

    def test_run_checker_and_skip_are_refused_for_live(self):
        self.to_live()
        status, body = self.post("/api/step/run-checker", {"step": "live", "which": "baseline"})
        self.assertEqual((status, body["error"]["code"]), (400, "bad_input"))
        status, body = self.post("/api/step/skip", {"step": "live"})
        self.assertEqual((status, body["error"]["code"]), (400, "cannot_skip"))

    def test_the_script_track_has_no_such_step_over_http(self):
        self.setup_project()
        status, _, _ = self.request("GET", "/api/state?step=live")
        self.assertEqual(status, 400)
        status, body = self.post("/api/step/start", {"step": "live"})
        self.assertEqual((status, body["error"]["code"]), (400, "unknown_step"))


class Content(unittest.TestCase):
    def setUp(self):
        self.steps = json.loads(resources.read_text("content/steps.json"))["steps"]
        self.live = self.steps["live"]
        self.provider = PROVIDER_JS.read_text(encoding="utf-8")

    def strings(self, value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, list):
            for item in value:
                yield from self.strings(item)
        elif isinstance(value, dict):
            for item in value.values():
                yield from self.strings(item)

    def test_the_options_are_data_and_match_what_the_helper_supports(self):
        ids = [c["id"] for c in self.live["clis"]]
        self.assertEqual(ids, list(CLIS))
        for cli in ids:
            self.assertIn(f"  {cli}: () =>", self.provider)
        self.assertIn(f"['copilot', 'claude', 'devin']", self.provider)

    def test_the_notes_say_which_helper_builders_pass_a_permission_flag_and_only_those(self):
        blocks = dict(re.findall(r"^  (copilot|claude|devin): \(\) => \(\{(.*?)\}\),$", self.provider, re.S | re.M))
        self.assertEqual(sorted(blocks), sorted(CLIS))
        auto = {cli for cli, source in blocks.items() if "permission" in source}
        self.assertEqual(auto, {"devin"})
        self.assertIn("'--permission-mode', 'auto'", blocks["devin"])
        notes = {c["id"]: c["note"] for c in self.live["clis"]}
        for cli in CLIS:
            with self.subTest(cli=cli):
                if cli in auto:
                    self.assertIn("--permission-mode auto", notes[cli])
                    self.assertIn("may act without asking you", notes[cli])
                else:
                    self.assertIn("adds no permission flag", notes[cli])
                    self.assertNotIn("auto", notes[cli])
        warning = " ".join(self.live["ui"]["warning_points"])
        self.assertIn("--permission-mode auto", warning)
        self.assertEqual(warning.count("--permission-mode"), 1)

    def test_the_warning_points_cover_everything_the_user_required(self):
        points = self.live["ui"]["warning_points"]
        joined = " ".join(points)
        for needle in ("fresh outputs", "No API key", "auto mode", "empty temporary folder", "run to run", "saved runs",
                       "never changes your baseline"):
            self.assertIn(needle, joined)
        self.assertIn("skip", self.live["ui"]["warning_intro"])
        self.assertIn("complete without it", self.live["ui"]["warning_intro"])
        self.assertIn("complete without it", self.live["goal"])
        self.assertEqual(len(points), 6)

    def test_live_wording_is_allowed_only_in_the_live_step(self):
        pattern = re.compile(r"(?i)\blive mode\b|agent-provider|exec:|promptfooconfig\.live")
        content = helpers.ROOT / "app" / "eval_coach" / "content"
        lesson_ui = json.loads((content / "lesson-ui.json").read_text(encoding="utf-8"))["ui"]
        pointers = {k: v for k, v in lesson_ui.items() if k.startswith("optional_live_")}
        self.assertEqual(sorted(pointers), ["optional_live_button", "optional_live_note"])
        self.assertIn("complete without it", pointers["optional_live_note"])
        self.assertIn("never changes your baseline", pointers["optional_live_note"])
        for name, data in (("steps.json", {k: v for k, v in self.steps.items() if k != "live"}),
                           ("lesson-ui.json", {k: v for k, v in lesson_ui.items() if k not in pointers}),
                           ("preflight.json", json.loads((content / "preflight.json").read_text(encoding="utf-8"))),
                           ("lessons.json", json.loads((content / "lessons.json").read_text(encoding="utf-8"))),
                           ("glossary.json", json.loads((content / "glossary.json").read_text(encoding="utf-8")))):
            for string in self.strings(data):
                with self.subTest(file=name, text=string[:50]):
                    self.assertIsNone(pattern.search(string), string)

    def test_the_other_steps_never_mention_live_mode_even_in_their_promptfoo_text(self):
        pattern = re.compile(r"(?i)\blive\b|agent-provider|exec:")
        for step, text in self.steps.items():
            if step == "live":
                continue
            for string in self.strings(text):
                with self.subTest(step=step, text=string[:50]):
                    self.assertIsNone(pattern.search(string), string)

    def test_the_step_is_complete_and_every_fix_ends_like_a_sentence(self):
        for field in ("title", "goal", "why", "instructions", "troubleshooting", "gate", "line_template", "clis", "ui"):
            self.assertTrue(self.live.get(field), field)
        for item in self.live["troubleshooting"]:
            with self.subTest(problem=item["problem"]):
                self.assertEqual(set(item), {"problem", "fix"})
                self.assertTrue(item["fix"].rstrip().endswith((".", '"')))
        for key, entry in self.live["gate"].items():
            self.assertTrue(entry["label"], key)
            self.assertTrue(entry["fail"] == "{messages}" or entry["fail"].rstrip().endswith("."), key)

    def test_the_line_template_is_exactly_the_skills_live_request(self):
        self.assertEqual(self.live["line_template"], LIVE_LINE)

    def test_the_instructions_tell_people_not_to_log_the_live_runs_and_that_the_app_does_not_run_it(self):
        text = " ".join(self.live["instructions"])
        self.assertIn("Do not ask your AI to log these runs", text)
        self.assertIn("does not run the live config", text)
        self.assertIn("you answer them there", text)
        self.assertIn("The app never answers for you", text)

    def test_no_code_names_a_cli(self):
        pattern = re.compile(r"(?i)copilot|claude|devin")
        root = helpers.ROOT / "app" / "eval_coach"
        files = list(root.glob("*.py")) + [p for p in (root / "web" / "js").glob("*.js")]
        self.assertGreater(len(files), 10)
        for path in files:
            with self.subTest(file=path.name):
                self.assertIsNone(pattern.search(path.read_text(encoding="utf-8")))

    def test_the_bundled_helper_is_still_byte_identical(self):
        self.assertEqual(hashlib.sha256(PROVIDER_JS.read_bytes()).hexdigest(),
                         "09e1ef76cd07458d59e3179c7aea8670ca73d8ca247f3523ecb1ab5f95da94ed")
        self.assertEqual(resources.read_bytes(project.AGENT_PROVIDER), PROVIDER_JS.read_bytes())


if __name__ == "__main__":
    unittest.main()
