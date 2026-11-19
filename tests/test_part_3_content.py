"""Part 3's AI steps use the paste flow: their words, the shared paste words and the opt-in flag."""
from __future__ import annotations

import json
import re
import unittest

import helpers  # noqa: F401  puts app/ on sys.path

from eval_coach import lessons as L
from eval_coach import resources

PASTE_STEPS = ("generate", "build", "fixtures", "fixtures-config", "readback", "key", "fix", "baseline", "live")
OLD_WORDS = ("Start my AI", "Send to AI", "Start again", "Press Send", "Press Start", "press Send", "press Start",
             "then Send", "Start and Send")
SHARED_UI = ("ai_note", "paste_heading", "paste_note", "copy", "copied", "copy_failed", "new_chat",
             "new_chat_confirm_title", "new_chat_confirm_body", "new_chat_confirm_body_result", "new_chat_confirm",
             "ready_hint")
ALLOWED_CLI = ("GitHub Copilot CLI", "Copilot CLI", "Devin CLI")


def strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from strings(value)


def raw_steps():
    return json.loads(resources.read_text("content/steps.json"))["steps"]


class PasteSteps(unittest.TestCase):
    def test_the_nine_ai_steps_opt_in_and_the_two_without_an_ai_do_not(self):
        steps = raw_steps()
        for step in PASTE_STEPS:
            self.assertEqual(steps[step]["cli_mode"], "paste", step)
        for step in ("predict", "run"):
            self.assertNotIn("cli_mode", steps[step])

    def test_the_shared_paste_words_are_merged_under_each_steps_own_ui(self):
        content, _ = L.load_step_content()
        for step in PASTE_STEPS:
            ui = content["steps"][step]["ui"]
            for key in SHARED_UI:
                self.assertTrue(ui[key].strip(), (step, key))
        self.assertEqual(content["steps"]["generate"]["ui"]["new_chat"], "Open a new AI chat")
        self.assertIn("first_look_blurb", content["steps"]["build"]["ui"])  # a step's own words stay
        self.assertNotIn("new_chat", content["steps"]["predict"].get("ui", {}))

    def test_no_paste_step_names_the_old_buttons_or_a_bare_cli(self):
        steps = raw_steps()
        for step in PASTE_STEPS:
            text = "\n".join(strings(steps[step]))
            for old in OLD_WORDS:
                self.assertNotIn(old, text, step)
            for allowed in ALLOWED_CLI:
                text = text.replace(allowed, "")
            self.assertIsNone(re.search(r"\bCLIs?\b", text), step)

    def test_the_steps_that_start_no_ai_do_not_name_the_old_buttons_either(self):
        steps = raw_steps()
        for step in ("predict", "run"):
            text = "\n".join(strings(steps[step]))
            for old in OLD_WORDS:
                self.assertNotIn(old, text, step)

    def test_the_paste_steps_say_the_window_opens_by_itself_and_name_copy(self):
        steps = raw_steps()
        for step in PASTE_STEPS:
            text = "\n".join(strings(steps[step]["instructions"]))
            self.assertIn("Open a new AI chat", text, step)
            self.assertIn("Copy", text, step)
        self.assertIn("never opens your AI window by itself", "\n".join(strings(steps["live"]["instructions"])))


if __name__ == "__main__":
    unittest.main()
