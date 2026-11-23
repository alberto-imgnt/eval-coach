"""Platform words: every word that depends on the computer comes from content/platform.json."""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import helpers
from helpers import FakeTerminal

from eval_coach import hostos, import_checks, resources
from eval_coach.engine import Engine
from eval_coach.lessons import load_bundled

CONTENT = helpers.ROOT / "app" / "eval_coach" / "content"
TOKENS = json.loads((CONTENT / "platform.json").read_text(encoding="utf-8"))["tokens"]
# Content that is data for one platform, or that is the platform table itself.
RAW_EXEMPT = ("platform.json", "cli-recipes.json")
WINDOWS_ONLY_WORDS = ("Ctrl+", "File Explorer", "C:\\\\Users", "Copy as path", "py instead of python", "drive letter")
MAC_ONLY_WORDS = ("Finder", "⌘", "Command-V", "Option-Command-C")


def content_files():
    return sorted(p for p in CONTENT.glob("*.json") if p.name not in RAW_EXEMPT)


def rendered(name, key):
    with resources.platform_words(key):
        return resources.read_text(f"content/{name}")


class TokenTable(unittest.TestCase):
    def test_every_token_has_both_platforms_and_words(self):
        for name, values in TOKENS.items():
            self.assertEqual(set(values), {"windows", "mac"}, name)
            for key, text in values.items():
                self.assertTrue(text.strip(), f"{name} has no {key} text")

    def test_the_token_names_are_what_the_content_uses(self):
        used = set()
        for path in content_files():
            used |= set(re.findall(r"\{([a-z][a-z_]*)\}", path.read_text(encoding="utf-8"))) & set(TOKENS)
        self.assertEqual(used, set(TOKENS), "a token nobody uses, or content that uses a token the table lacks")

    def test_windows_values_are_the_words_the_course_always_had(self):
        windows = {name: values["windows"] for name, values in TOKENS.items()}
        self.assertEqual(windows["paste_key"], "Ctrl+V")
        self.assertEqual(windows["sep"], "\\")
        self.assertEqual(windows["python_swap"], "py instead of python")
        self.assertEqual(windows["path_example"], "C:\\Users\\you\\Documents")


class EveryContentFileRenders(unittest.TestCase):
    def test_both_platforms_render_valid_json_with_no_token_left(self):
        for path in content_files():
            for key in ("windows", "mac"):
                text = rendered(path.name, key)
                json.loads(text)
                left = set(re.findall(r"\{([a-z][a-z_]*)\}", text)) & set(TOKENS)
                self.assertEqual(left, set(), f"{path.name} on {key} still has tokens")

    def test_no_windows_word_is_written_into_the_course_text_twice(self):
        for path in content_files():
            raw = path.read_text(encoding="utf-8")
            if path.name == "preflight.json":
                raw = raw.split('"platform_overrides"')[0]
            for word in ("Ctrl+", "File Explorer", "C:\\\\", "Copy as path", "py instead of python"):
                self.assertNotIn(word, raw, f"{path.name} has the Windows word {word!r} outside platform.json")

    def test_mac_text_has_no_windows_word(self):
        for path in content_files():
            text = rendered(path.name, "mac")
            for word in WINDOWS_ONLY_WORDS:
                self.assertNotIn(word, text, f"{path.name} on a Mac says {word!r}")
            self.assertNotRegex(text, r"skills\\\\\w")
            self.assertNotRegex(text, r"part-2\\\\\w")

    def test_windows_text_has_no_mac_word(self):
        for path in content_files():
            text = rendered(path.name, "windows")
            for word in MAC_ONLY_WORDS:
                self.assertNotIn(word, text, f"{path.name} on Windows says {word!r}")

    def test_the_python_command_on_a_mac_is_python3(self):
        text = rendered("steps.json", "mac")
        self.assertIn("with python3 instead of python", text)
        self.assertNotIn("with py ", text)
        self.assertIn("run python3 --version", rendered("preflight.json", "mac"))
        self.assertIn("run python --version", rendered("preflight.json", "windows"))

    def test_folder_names_use_the_separator_of_the_computer(self):
        mac, windows = rendered("steps.json", "mac"), rendered("steps.json", "windows")
        self.assertIn("skills/build-eval-script/SKILL.md", mac)
        self.assertIn("skills\\\\build-eval-script\\\\SKILL.md", windows)
        self.assertIn("part-2/test-cases.md", rendered("part-2-lessons.json", "mac"))

    def test_the_paste_shortcut(self):
        self.assertIn("paste with ⌘V (Command-V) and press Enter", rendered("steps.json", "mac"))
        self.assertIn("paste with Ctrl+V and press Enter", rendered("steps.json", "windows"))
        self.assertIn("press ⌘C (Command-C)", rendered("part-1-steps.json", "mac"))

    def test_the_two_platforms_differ_only_where_the_table_says(self):
        for path in content_files():
            if path.name == "preflight.json":
                continue  # it also has Mac-only message overrides, covered in test_preflight
            windows, mac = rendered(path.name, "windows"), rendered(path.name, "mac")
            if not any("{" + name + "}" in path.read_text(encoding="utf-8") for name in TOKENS):
                self.assertEqual(windows, mac, path.name)


class ImportMessages(unittest.TestCase):
    def messages(self, key):
        with resources.platform_words(key):
            return import_checks._messages()

    def test_a_mac_participant_is_asked_for_a_slash_path_and_shown_finder(self):
        mac = self.messages("mac")["blocking"]
        self.assertIn("/Users/you/Documents/my-prompt.md", mac["missing_prompt_path"])
        self.assertIn("starting with a slash (/)", mac["not_absolute"])
        self.assertIn("Finder", mac["not_absolute"])
        self.assertIn("Option-Command-C", mac["file_not_found"])
        self.assertNotIn("drive letter", mac["not_absolute"])

    def test_windows_messages_are_what_they_were(self):
        windows = self.messages("windows")["blocking"]
        self.assertEqual(
            windows["missing_prompt_path"],
            "Enter the full path of your prompt file, for example C:\\Users\\you\\Documents\\my-prompt.md. Then press Check my files.")
        self.assertIn("starting with a drive letter, for example C:\\Users\\you\\Documents\\my-file.md. "
                      "In File Explorer you can right-click the file and choose Copy as path. Then press Check my files.",
                      windows["not_absolute"])

    @unittest.skipIf(hostos.is_windows(), "a Windows path is absolute on Windows")
    def test_a_relative_or_drive_path_is_not_absolute_on_a_mac(self):
        for text in ("Documents/prompt-v0.md", "C:\\Users\\you\\prompt-v0.md"):
            data, finding = import_checks._read_source(text, "prompt", None)
            self.assertIsNone(data)
            self.assertEqual(finding["code"], "not_absolute")


class WholeApp(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-words-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def state_text(self, key):
        with resources.platform_words(key):
            engine = Engine(self.tmp / key, FakeTerminal(), lessons=load_bundled())
            state = json.dumps(engine.get_state(), ensure_ascii=False, default=str)
            state += json.dumps(engine.content, ensure_ascii=False, default=str)
            state += json.dumps(engine.preflight.content, ensure_ascii=False, default=str)
        return state

    def test_the_app_shows_each_platforms_words(self):
        mac, windows = self.state_text("mac"), self.state_text("windows")
        self.assertIn("⌘V (Command-V)", mac)
        self.assertNotIn("Ctrl+V", mac)
        self.assertIn("Ctrl+V", windows)
        self.assertNotIn("⌘", windows)


class ProjectPathMessage(unittest.TestCase):
    def test_the_example_path_follows_the_platform(self):
        with unittest.mock.patch.dict("os.environ", {"EVAL_COACH_TEST_PLATFORM": "mac"}):
            self.assertEqual(hostos.project_path_example(), "/Users/you/eval-project")
        with unittest.mock.patch.dict("os.environ", {"EVAL_COACH_TEST_PLATFORM": "windows"}):
            self.assertEqual(hostos.project_path_example(), "C:\\Users\\you\\eval-project")


if __name__ == "__main__":
    unittest.main()
