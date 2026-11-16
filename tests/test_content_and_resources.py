from __future__ import annotations

import ast
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipapp
from pathlib import Path

import helpers
from helpers import ROOT

from eval_coach import resources
from eval_coach.project import strip_catch_up_comment

APP = ROOT / "app"
PACKAGE = APP / "eval_coach"
FORBIDDEN = re.compile(r"\b(facilitator|presenter|room|rooms|breakout|chat waterfall|waterfall|handout|handouts|"
                       r"neighbor|neighbour|clock)\b", re.I)


def strings_in(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from strings_in(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings_in(item)


class SettingsContent(unittest.TestCase):
    """content/settings.json holds every word the Settings panel and its dialogs show."""

    def setUp(self):
        self.data = json.loads(resources.read_text("content/settings.json"))

    def test_both_reset_dialogs_have_every_part(self):
        for kind in ("progress", "configuration"):
            words = self.data["reset"][kind]
            for key in ("button", "summary", "title", "lead", "clears_title", "clears", "keeps_title", "keeps",
                        "backup", "no_project", "keep_button", "confirm_button", "done", "done_no_backup"):
                self.assertTrue(words.get(key), f"{kind}.{key}")
            self.assertIn("{folder}", words["backup"])
            self.assertIn("{folder}", words["done"])
            self.assertTrue(all(isinstance(item, str) and item for item in words["clears"] + words["keeps"]))

    def test_the_configuration_dialog_says_progress_is_cleared_too_and_differs_from_the_other(self):
        words = self.data["reset"]
        self.assertIn("lesson progress", words["configuration"]["lead"].lower())
        self.assertNotEqual(words["configuration"]["title"], words["progress"]["title"])
        self.assertNotEqual(words["configuration"]["confirm_button"], words["progress"]["confirm_button"])

    def test_the_dialogs_name_the_backup_and_that_it_replaces_the_last_one(self):
        for kind in ("progress", "configuration"):
            self.assertIn("replaces the previous backup", self.data["reset"][kind]["backup"])

    def test_every_error_the_engine_raises_has_words(self):
        for key in ("confirm_required", "job_busy", "backup_failed", "key_failed", "reset_failed", "scaffold_failed"):
            self.assertTrue(self.data["errors"][key], key)

    def test_the_panel_the_banner_and_the_gate_have_every_word_the_page_shows(self):
        for key in ("tool", "heading", "lede", "close", "text_size_heading", "text_size_intro", "text_size_label",
                    "text_size_value", "text_size_default", "text_size_range", "setup_heading", "setup_intro",
                    "reset_heading", "reset_intro"):
            self.assertTrue(self.data["settings"].get(key), f"settings.{key}")
        for key in ("label", "text", "button"):
            self.assertTrue(self.data["banner"].get(key), f"banner.{key}")
        for key in ("cli_exercise", "step", "button", "preview_lesson", "preview_step", "preview_lesson_after",
                    "preview_step_after", "preview_back"):
            self.assertTrue(self.data["setup_gate"].get(key), f"setup_gate.{key}")
        self.assertIn("{value}", self.data["settings"]["text_size_value"])
        self.assertIn("{min}", self.data["settings"]["text_size_range"])

    def test_the_banner_says_hands_on_work_needs_setup_and_names_the_choice(self):
        self.assertIn("exercises that use your CLI", self.data["banner"]["text"])
        self.assertIn("setup", self.data["banner"]["button"].lower())

    def test_the_setup_screen_has_skip_words(self):
        ui = json.loads(resources.read_text("content/preflight.json"))["ui"]
        self.assertTrue(ui["skip_button"])
        self.assertIn("Settings", ui["skip_hint"])

    def test_the_setup_wizard_has_its_words_and_no_course_words(self):
        ui = json.loads(resources.read_text("content/preflight.json"))["ui"]
        keys = ("wizard_nav_label", "wizard_progress", "wizard_back", "wizard_next", "wizard_close", "wizard_needed")
        for key in keys:
            self.assertTrue(ui.get(key), f"ui.{key}")
            self.assertNotRegex(ui[key].lower(), r"\b(part|step|steps)\b", key)
        self.assertIn("{n}", ui["wizard_progress"])
        self.assertIn("{total}", ui["wizard_progress"])
        for key in ("setup_open", "setup_summary_label"):
            self.assertTrue(self.data["settings"].get(key), f"settings.{key}")

    def test_no_text_still_points_to_a_before_you_begin_screen_as_a_course_item(self):
        for name in ("lesson-ui.json", "preflight.json", "glossary.json", "settings.json", "steps.json"):
            data = json.loads(resources.read_text(f"content/{name}"))
            for text in strings_in(data):
                if name == "preflight.json" and text == "Before you begin":
                    continue  # the setup screen's own heading
                self.assertNotRegex(text, r"(?i)before you begin (screen|page)", f"{name}: {text}")

    def test_no_forbidden_words(self):
        for text in strings_in(self.data):
            self.assertIsNone(FORBIDDEN.search(text), text)
            self.assertNotRegex(text.lower(), r"\bsessions?\b")


class Content(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(resources.read_text("content/steps.json"))
        self.steps = self.data["steps"]

    def test_every_step_is_complete(self):
        self.assertEqual(list(self.steps),
                         ["generate", "build", "fixtures", "fixtures-config", "readback", "predict", "key", "run", "fix",
                          "baseline", "live"])
        for step_id, step in self.steps.items():
            for field in ("title", "goal", "why", "instructions", "troubleshooting", "gate"):
                with self.subTest(step=step_id, field=field):
                    self.assertTrue(step.get(field))
            for item in step["troubleshooting"]:
                self.assertEqual(set(item), {"problem", "fix"})

    def test_non_negotiable_wording(self):
        for text in strings_in(self.data):
            with self.subTest(text=text[:60]):
                self.assertIsNone(FORBIDDEN.search(text), text)
                self.assertNotIn("Copilot Chat", text)
                self.assertNotIn("Room A", text)
                self.assertNotIn("Room B", text)

    def test_generate_step_says_how_to_pick_and_record_a_model(self):
        text = " ".join(self.steps["generate"]["instructions"])
        for phrase in ("type /model", "Which model are you using", "Sonnet", "Opus", "exact model name"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertEqual(self.steps["generate"]["gate"]["model"]["fail"], "Write the model name in the box.")

    def test_required_teaching_lines(self):
        text = " ".join(strings_in(self.data))
        for phrase in ("Prompt, then answer, then file, then checker, then verdict.",
                       "You decide what good means. The agent writes the code. "
                       "Your job is to check that the code means what you meant.",
                       "Exit code 1 is normal", "approvals", "temporary error",
                       "Fix the spec, not the checker."):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_app_code_has_no_forbidden_words(self):
        for path in PACKAGE.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for literal in (n.value for n in ast.walk(ast.parse(text))
                            if isinstance(n, ast.Constant) and isinstance(n.value, str)):
                with self.subTest(path=path.name, text=literal[:50]):
                    self.assertIsNone(FORBIDDEN.search(literal), literal)


class PreflightContent(unittest.TestCase):
    def setUp(self):
        self.preflight = json.loads(resources.read_text("content/preflight.json"))
        self.recipes = json.loads(resources.read_text("content/cli-recipes.json"))

    def test_preflight_wording_rules(self):
        for text in strings_in(self.preflight) :
            with self.subTest(text=text[:60]):
                self.assertIsNone(FORBIDDEN.search(text), text)
                self.assertNotIn("Copilot Chat", text)
                self.assertNotIn("Room A", text)
                self.assertNotRegex(text, r"(?i)\bcontact\b")

    def test_recipe_wording_rules(self):
        for text in strings_in(self.recipes):
            with self.subTest(text=text[:60]):
                self.assertNotIn("Copilot Chat", text)
                self.assertNotIn("Teams", text)
                self.assertNotRegex(text, r"(?i)\bcontact\b")

    def test_every_message_ends_with_a_next_action(self):
        required = ("no_network", "download_timeout", "hash_mismatch", "not_enough_disk", "antivirus_removed",
                    "cli_not_found", "cli_not_found_after_install", "cli_not_signed_in",
                    "test_missing_output", "test_wrong_output", "test_missing_version", "npm_error")
        messages = self.preflight["messages"]
        for key in required:
            with self.subTest(key=key):
                self.assertTrue(messages[key]["detail"])
                self.assertTrue(messages[key]["next"].strip())
                self.assertTrue(messages[key]["next"].rstrip().endswith("."))

    def test_blocked_downloads_name_the_software_portal(self):
        for key in ("no_network", "download_timeout", "hash_mismatch", "antivirus_removed"):
            with self.subTest(key=key):
                text = self.preflight["messages"][key]["next"]
                self.assertIn("Company Portal or Software Center", text)
                self.assertIn("Check everything again", text)

    def test_recipes_match_phase_two(self):
        by_id = {r["id"]: r for r in self.recipes["recipes"]}
        self.assertEqual(by_id["copilot"]["command"], "winget install GitHub.Copilot")
        self.assertEqual(by_id["claude-installer"]["command"],
                         "curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd")
        self.assertEqual(by_id["claude-winget"]["command"], "winget install Anthropic.ClaudeCode")
        self.assertEqual(by_id["devin"]["command"], "irm https://static.devin.ai/cli/setup.ps1 | iex")
        self.assertEqual(by_id["devin"]["shell"], "powershell")
        self.assertEqual(by_id["other"]["shell"], "none")
        self.assertEqual(by_id["copilot"]["requires"]["recipe"], "powershell")
        self.assertEqual(by_id["powershell"]["command"], "winget install Microsoft.PowerShell")

    def test_working_test_line_is_exact(self):
        self.assertEqual(self.preflight["working_test"]["line"],
                         "Read input.txt, write its contents in uppercase to output.txt, then run python "
                         "--version and write what it prints to version.txt. Do nothing else.")

    def test_pinned_values_match_the_manifest(self):
        from eval_coach import preflight
        manifest = json.loads((ROOT / "spikes" / "phase0-preflight" / "runtime-manifest.json").read_text(encoding="utf-8"))
        node = manifest["node"]
        self.assertEqual(preflight.NODE_URL, node["url"])
        self.assertEqual(preflight.NODE_SHA256, node["sha256"])
        self.assertEqual(preflight.NODE_DOWNLOAD_BYTES, node["download_bytes"])
        self.assertEqual(preflight.NODE_VERSION, node["version"])
        self.assertEqual(preflight.PROMPTFOO_VERSION, manifest["promptfoo"]["version"])


class Resources(unittest.TestCase):
    def test_reads_from_disk(self):
        self.assertIn("build-eval-script", resources.read_text("kit/skills/build-eval-script/SKILL.md"))

    def test_lists_files(self):
        names = resources.list_files("kit/skills")
        self.assertIn("kit/skills/make-eval-fixtures/SKILL.md", names)
        self.assertEqual(len(names), 5)

    def test_unsafe_paths_are_refused(self):
        for bad in ("../server.py", "web/../server.py", "web\\index.html", "C:/x", "/abs", "a\0b",
                    "web//index.html", "web/.", "index.html.", "index.html "):
            with self.subTest(bad=bad), self.assertRaises(resources.ResourceNotFound):
                resources.read_bytes(bad)

    def test_read_web_cannot_escape(self):
        with self.assertRaises(resources.ResourceNotFound):
            resources.read_web("../server.py")

    def test_catch_up_comment_stripping(self):
        data = b"# Title\r\n\r\n<!-- Catch-up copy. Use it. -->\r\n\r\nBody\r\n"
        self.assertEqual(strip_catch_up_comment(data), b"# Title\r\n\r\nBody\r\n")
        self.assertEqual(strip_catch_up_comment(b"<!-- another -->\n"), b"<!-- another -->\n")

    def test_kit_matches_the_read_only_source(self):
        if not helpers.SOURCE.is_dir():
            self.skipTest("source folder absent")
        for name in ("build-eval-script", "build-promptfoo-config", "make-eval-fixtures"):
            source = helpers.SOURCE / "skills" / name
            for item in source.rglob("*"):
                if item.is_file():
                    copy = helpers.KIT / "skills" / name / item.relative_to(source)
                    self.assertEqual(item.read_bytes(), copy.read_bytes(), str(item))

    def test_loads_from_inside_a_zipapp(self):
        tmp = Path(tempfile.mkdtemp(prefix="eval-coach-zip-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        target = tmp / "app.pyz"
        zipapp.create_archive(str(APP), str(target), main="eval_coach.__main__:main",
                              filter=lambda p: "__pycache__" not in p.parts)
        script = (
            "import sys, json; sys.path.insert(0, sys.argv[1])\n"
            "from eval_coach import resources as r\n"
            "print(json.dumps({'archive': bool(r._ARCHIVE),\n"
            "  'skill': len(r.read_bytes('kit/skills/build-eval-script/SKILL.md')),\n"
            "  'skills': r.list_files('kit/skills'),\n"
            "  'web': len(r.read_web('index.html')),\n"
            "  'steps': json.loads(r.read_text('content/steps.json'))['steps']['fix']['title']}))\n"
        )
        out = subprocess.run([sys.executable, "-c", script, str(target)], capture_output=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr.decode())
        data = json.loads(out.stdout)
        self.assertTrue(data["archive"])
        self.assertEqual(len(data["skills"]), 5)
        self.assertGreater(data["web"], 0)
        self.assertEqual(data["steps"], "Fix the spec")


class Python39(unittest.TestCase):
    def test_syntax_is_valid_for_39(self):
        for folder in (APP, ROOT / "tests", ROOT / "tools"):
            for path in folder.rglob("*.py"):
                if "golden" in path.parts or "frontend" in path.parts:
                    continue
                with self.subTest(path=str(path)):
                    ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_future_annotations_everywhere_in_the_app(self):
        for path in PACKAGE.glob("*.py"):
            with self.subTest(path=path.name):
                self.assertIn("from __future__ import annotations", path.read_text(encoding="utf-8"))

    @unittest.skipUnless(hasattr(sys, "stdlib_module_names"), "needs Python 3.10 or newer")
    def test_stdlib_only(self):
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and not node.level:
                    names = [node.module]
                for name in names:
                    with self.subTest(path=path.name, name=name):
                        self.assertIn(name.split(".")[0], sys.stdlib_module_names | {"eval_coach"})


if __name__ == "__main__":
    unittest.main()
