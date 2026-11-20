"""The words participants read: "your AI" and "AI window" (never a bare "CLI"), "Practice task" (never "Northwind"
as an option name), "categories" for the five groups of what a prompt needs, and no recommended track."""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import helpers
from helpers import ROOT

PACKAGE = ROOT / "app" / "eval_coach"
CONTENT = PACKAGE / "content"
WEB = PACKAGE / "web"
KIT = PACKAGE / "kit"

BARE_CLI = re.compile(r"\bCLIs?\b")
# Allowed uses of "CLI", each with its reason. A string is checked after these exact phrases are removed.
ALLOWED_CLI = {
    "GitHub Copilot CLI": "vendor product name",
    "Copilot CLI": "vendor product name",
    "Devin CLI": "vendor product name",
}
# "Northwind" is the client name inside the example's own text. These content strings quote the example itself.
ALLOWED_NORTHWIND_PATHS = {
    ("part-1-steps.json", "steps/cold/scenario/requirements/2/label"): "client names in the scenario card",
    ("part-2-steps.json", "steps/draft/scenario/requirements/2/label"): "client names in the scenario card",
    ("part-2-steps.json", "steps/test-file/build/title"): "the title of the example's own test case file",
}
FORBIDDEN_FOR_TRACKS = re.compile(r"\b(default|recommended|best)\b", re.I)


def content_strings():
    """Every (file, path, text) string in the content files."""
    found = []

    def walk(name, value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                walk(name, item, f"{path}/{key}" if path else key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(name, item, f"{path}/{index}")
        elif isinstance(value, str):
            found.append((name, path, value))

    for file in sorted(CONTENT.glob("*.json")):
        walk(file.name, json.loads(file.read_text(encoding="utf-8")), "")
    return found


JS_TOKEN = re.compile(r"""//[^\n]*|/\*.*?\*/|'(?:\\.|[^'\\\n])*'|"(?:\\.|[^"\\\n])*"|`(?:\\.|[^`\\])*`""", re.S)


def web_strings():
    """Every string literal in the interface files (comments are not participant text)."""
    found = []
    for file in sorted(list(WEB.glob("*.html")) + list((WEB / "js").glob("*.js"))):
        text = file.read_text(encoding="utf-8")
        if file.suffix == ".html":
            found.append((file.name, text))
            continue
        for match in JS_TOKEN.finditer(text):
            token = match.group(0)
            if not token.startswith(("//", "/*")):
                found.append((file.name, token))
    return found


def kit_files():
    for path in sorted(KIT.rglob("*")):
        relative = path.relative_to(KIT).as_posix()
        if path.is_file() and path.suffix in {".md", ".txt"} and not relative.startswith("skills/"):
            yield relative, path.read_text(encoding="utf-8")


def without_allowed(text):
    for phrase in ALLOWED_CLI:
        text = text.replace(phrase, "")
    return text


class NoBareCli(unittest.TestCase):
    def test_no_content_string_says_cli_outside_a_product_name(self):
        offenders = [f"{name} {path}: {text[:90]}" for name, path, text in content_strings()
                     if BARE_CLI.search(without_allowed(text))]
        self.assertEqual(offenders, [])

    def test_no_interface_string_says_cli_outside_a_product_name(self):
        offenders = [f"{name}: {text[:90]}" for name, text in web_strings() if BARE_CLI.search(without_allowed(text))]
        self.assertEqual(offenders, [])

    def test_no_bundled_kit_file_says_cli(self):
        offenders = [relative for relative, text in kit_files() if BARE_CLI.search(without_allowed(text))]
        self.assertEqual(offenders, [])

    def test_the_scan_catches_a_new_bare_cli(self):
        self.assertTrue(BARE_CLI.search(without_allowed("Start your CLI first.")))
        self.assertFalse(BARE_CLI.search(without_allowed("Install GitHub Copilot CLI or Devin CLI.")))

    def test_every_allowed_use_has_a_reason(self):
        self.assertTrue(all(reason for reason in ALLOWED_CLI.values()))

    def test_the_glossary_explains_the_ai_window_and_has_no_cli_entry(self):
        terms = {t["term"]: t for t in json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))["terms"]}
        self.assertNotIn("CLI", terms)
        entry = terms["AI window"]
        self.assertEqual(entry["kind"], "course")
        self.assertTrue(entry["meaning"].startswith("In this course,"))
        self.assertFalse(BARE_CLI.search(without_allowed(entry["meaning"])))
        for needle in ("terminal inside this app", "new chat starts a new AI window", "control"):
            self.assertIn(needle, entry["meaning"])

    def test_the_vendor_names_stay_in_the_list_of_tools(self):
        recipes = json.loads((CONTENT / "cli-recipes.json").read_text(encoding="utf-8"))["recipes"]
        names = [r["name"] for r in recipes]
        self.assertIn("GitHub Copilot CLI", names)
        self.assertIn("Devin CLI", names)


class PracticeTask(unittest.TestCase):
    def test_northwind_is_never_an_option_name(self):
        offenders = []
        for name, path, text in content_strings():
            if "Northwind" in text and (name, path) not in ALLOWED_NORTHWIND_PATHS:
                offenders.append(f"{name} {path}: {text[:90]}")
        self.assertEqual(offenders, [])

    def test_every_allowed_northwind_use_exists_and_has_a_reason(self):
        strings = {(name, path): text for name, path, text in content_strings()}
        for key, reason in ALLOWED_NORTHWIND_PATHS.items():
            with self.subTest(key=key):
                self.assertTrue(reason)
                self.assertIn("Northwind", strings[key])

    def test_the_project_page_offers_a_practice_task_and_my_own_task(self):
        ui = json.loads((CONTENT / "preflight.json").read_text(encoding="utf-8"))["ui"]
        self.assertEqual(ui["starter_northwind_label"], "Practice task")
        self.assertEqual(ui["starter_own_label"], "My own task")
        hint = ui["starter_northwind_hint"]
        self.assertIn("ready-made example", hint)
        self.assertIn("nothing to bring", hint)
        self.assertIn("for practice only", hint)
        self.assertIn("provide", ui["starter_own_hint"])
        self.assertRegex(ui["northwind_note"], r"cannot be your submission")
        messages = json.loads((CONTENT / "preflight.json").read_text(encoding="utf-8"))["messages"]
        text = messages["project_files_missing"]["next"]
        self.assertIn("Practice task", text)
        self.assertIn("My own task", text)


class TracksAndSeriesWords(unittest.TestCase):
    def test_tracks_are_described_by_technical_level_with_no_recommendation(self):
        pf = json.loads((CONTENT / "preflight.json").read_text(encoding="utf-8"))
        options = pf["track_options"]
        self.assertEqual(options["script"]["label"], "Script track")
        self.assertEqual(options["promptfoo"]["label"], "promptfoo track")
        script = options["script"]["hint"]
        for needle in ("No technical experience needed", "Your AI builds the checker", "nothing extra to install"):
            self.assertIn(needle, script)
        promptfoo = options["promptfoo"]["hint"]
        for needle in ("technical users", "Node.js", "about 1 GB"):
            self.assertIn(needle, promptfoo)
        track_text = [options["script"]["hint"], options["promptfoo"]["hint"], pf["track_promptfoo_note"],
                      pf["messages"]["track_script"]["detail"], pf["messages"]["track_promptfoo"]["detail"],
                      pf["ui"]["track_legend"]]
        settings = json.loads((CONTENT / "settings.json").read_text(encoding="utf-8"))["settings"]
        track_text += [v for k, v in settings.items() if "track" in k and isinstance(v, str)]
        for text in track_text:
            with self.subTest(text=text[:50]):
                self.assertIsNone(FORBIDDEN_FOR_TRACKS.search(text))

    def test_the_series_map_intro_is_about_doing_the_work_yourself(self):
        intro = json.loads((CONTENT / "series.json").read_text(encoding="utf-8"))["ui"]["intro"]
        self.assertIn("Six Parts, one method.", intro)
        self.assertIn("Do each one yourself", intro)
        self.assertNotRegex(intro, r"(?i)look ahead|stage 3")


class Categories(unittest.TestCase):
    # Other senses of "kind" that stay: what kind of thing to produce, a different kind of problem.
    OTHER_SENSES = ("kind of thing to produce", "kind of problem")
    FILES = ("content/part-1-lessons.json", "content/part-1-steps.json", "kit/part1/frameworks-map.md",
             "kit/part1/typical-gaps.md")

    def test_the_five_groups_are_never_called_kinds(self):
        for relative in self.FILES:
            text = (PACKAGE / relative).read_text(encoding="utf-8")
            text = re.sub(r'"kind":', "", text)
            for phrase in self.OTHER_SENSES:
                text = text.replace(phrase, "")
            with self.subTest(file=relative):
                self.assertEqual(re.findall(r".{20}\bkinds?\b.{20}", text, re.I), [])

    def test_the_glossary_names_categories_not_kinds_for_frameworks(self):
        terms = {t["term"]: t["meaning"] for t in json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))["terms"]}
        self.assertIn("categories of information", terms["Prompting framework"])

    def test_crisp_stays_out_of_part_one(self):
        texts = [(relative, (PACKAGE / relative).read_text(encoding="utf-8")) for relative in self.FILES]
        texts += [(f"kit/{r}", t) for r, t in kit_files() if r.startswith("part1/")]
        glossary = json.loads((CONTENT / "glossary.json").read_text(encoding="utf-8"))["terms"]
        texts += [(f"glossary {t['term']}", t["term"] + " " + t["meaning"]) for t in glossary if t.get("lesson", "").startswith("p1-")]
        for relative, text in texts:
            with self.subTest(file=relative):
                self.assertNotRegex(text, r"\bCRISP\b")


class LockWords(unittest.TestCase):
    """The lock, the skip and the demo group: plain words, one tooltip, and no early mention of demo access."""

    SERIES = json.loads((CONTENT / "series.json").read_text(encoding="utf-8"))
    NOT_ALLOWED = re.compile(r"(?i)stage 3|office hours|AIR discussion|\b(presenters?|facilitators?|rooms?|handouts?)\b|contact |reach out")

    def test_the_lock_words_are_plain_and_the_tooltip_is_one_text(self):
        ui = json.loads((CONTENT / "lesson-ui.json").read_text(encoding="utf-8"))["ui"]
        self.assertEqual(ui["status_locked"], "Not started")
        self.assertEqual(ui["locked_tip"], "Opens when the previous ones are done")
        self.assertEqual(ui["locked_icon_label"], "Not open yet")
        copies = [(name, path) for name, path, text in content_strings() if "previous ones are done" in text.lower()]
        self.assertEqual(copies, [("lesson-ui.json", "ui/locked_tip")])
        for key in ("locked_tip", "locked_icon_label", "part_skipped_note"):
            self.assertFalse(BARE_CLI.search(without_allowed(ui[key])), key)

    def test_every_course_part_has_skip_words_that_say_what_it_teaches_and_why(self):
        courses = [p for p in self.SERIES["parts"] if p["kind"] == "course"]
        self.assertEqual(len(courses), 3)
        for part in courses:
            with self.subTest(part=part["id"]):
                for key in ("teaches", "matters"):
                    self.assertGreater(len(part["skip"][key].split()), 8)
                    self.assertIsNone(self.NOT_ALLOWED.search(part["skip"][key]))
                    self.assertFalse(BARE_CLI.search(without_allowed(part["skip"][key])))
        for part in self.SERIES["parts"]:
            if part["kind"] != "course":
                self.assertNotIn("skip", part)

    def test_the_skip_confirm_says_there_is_no_artifact_and_no_evaluator(self):
        ui = self.SERIES["ui"]
        self.assertIn("no artifact and no evaluator", ui["skip_cost"])
        for key in ("skip_button", "skip_title", "skip_cancel", "skip_confirm", "state_skipped", "state_locked", "skipped_note"):
            with self.subTest(key=key):
                self.assertTrue(ui[key].strip())
                self.assertIsNone(self.NOT_ALLOWED.search(ui[key]))
        self.assertEqual(ui["state_locked"], "Not started")
        self.assertEqual(ui["state_skipped"], "Skipped")

    def test_the_word_locked_is_not_used_for_a_lock_in_participant_text(self):
        # The lock is shown as "Not started" with a lock icon and the tooltip. (Locking predictions is a different thing.)
        offenders = []
        for name, path, text in content_strings():
            if re.search(r"(?i)\blocked\b", text) and not re.search(r"(?i)prediction|OneDrive|lock (it|in)|grid", text):
                offenders.append(f"{name} {path}: {text[:80]}")
        self.assertEqual(offenders, [])
        for name, text in web_strings():
            self.assertNotRegex(text, r"\bLocked\b", name)

    def test_demo_access_is_named_only_in_its_own_group(self):
        offenders = []
        for name, path, text in content_strings():
            if "demo access" in text.lower() and not (name == "settings.json" and path.startswith("demo/")):
                offenders.append(f"{name} {path}")
        self.assertEqual(offenders, [])
        for name, text in web_strings():
            self.assertNotIn("demo access", text.lower(), name)

    def test_the_demo_group_and_its_refusal_are_plain(self):
        settings = json.loads((CONTENT / "settings.json").read_text(encoding="utf-8"))
        for key in ("heading", "intro", "password_label", "unlock", "turn_off", "notice"):
            self.assertTrue(settings["demo"][key].strip(), key)
        self.assertEqual(settings["errors"]["demo_refused"], "That password was not accepted.")
        for key in ("notice",):
            self.assertIn("saved", settings["demo"][key])
        self.assertNotRegex(settings["errors"]["demo_refused"].lower(), r"hash|exist|wrong|hint")


class ModelChoiceWords(unittest.TestCase):
    """The app picks and records the model, so no step text sends the participant to /model or asks for a name."""

    ASKS_FOR_A_NAME = re.compile(r"(?i)\b(write|type|enter|record|note)\b[^.]{0,50}\bmodel('s)? name\b|model name[^.]{0,30}\bin the box")

    def participant_text(self):
        return [(name, path, text) for name, path, text in content_strings()
                if name != "cli-recipes.json"]  # its /model is the app's own discovery data, not shown to anyone

    def test_no_participant_text_mentions_the_model_command(self):
        offenders = [f"{name} {path}" for name, path, text in self.participant_text() if "/model" in text]
        self.assertEqual(offenders, [])

    def test_no_participant_text_asks_for_a_model_name_to_be_written(self):
        offenders = [f"{name} {path}: {text[:80]}" for name, path, text in self.participant_text()
                     if self.ASKS_FOR_A_NAME.search(text)]
        self.assertEqual(offenders, [])

    def test_the_toggle_words_are_plain_and_recommend_nothing(self):
        words = json.loads((CONTENT / "lesson-ui.json").read_text(encoding="utf-8"))["ai_model"]
        for key, text in words.items():
            with self.subTest(key=key):
                self.assertFalse(BARE_CLI.search(without_allowed(text)), text)
                self.assertNotRegex(text, r"(?i)\b(recommend|best|presenter|facilitator|room|handout)\b")
        self.assertIn("next time your AI starts", words["applies_next"])


if __name__ == "__main__":
    unittest.main()
