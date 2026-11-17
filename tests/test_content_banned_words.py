"""Task 3.29: banned words in everything a participant can read, and the files that must not change."""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

import helpers
from helpers import KIT, ROOT

from eval_coach import lessons as L
from eval_coach import resources

PACKAGE = ROOT / "app" / "eval_coach"
CONTENT = PACKAGE / "content"
WEB = PACKAGE / "web"

# Whole words only, so "clockwise" or "bedroom" are never flagged. "Copilot Chat" is matched as a phrase.
BANNED = re.compile(r"\b(presenters?|facilitators?|rooms?|breakouts?|waterfalls?|handouts?|neighbou?rs?|clocks?|"
                    r"copilot\s+chat)\b", re.I)
SESSION_LABELS = re.compile(r"\broom\s+[ab]\b", re.I)

# The bundled skills must stay byte-identical to the Session 3 source. The word "room" appears in their own
# sentence ("every place a threshold left room") and cannot change, so they are checked by hash instead.
SKILL_HASHES = {
    "skills/build-eval-script/SKILL.md": "3b7c9c29a4cc42e2d68cc5fd574afd09f4897a83c89dfd776d9d21534723f40b",
    "skills/build-promptfoo-config/SKILL.md": "c40187a241737bc7661ac9ede9f8c9c866e8f7fa00471fac441639b1c1415c13",
    "skills/build-promptfoo-config/agent-provider.js": "09e1ef76cd07458d59e3179c7aea8670ca73d8ca247f3523ecb1ab5f95da94ed",
    "skills/build-promptfoo-config/summarize_results.py": "d76751c600b7a3b4016662168236ec36a19f0c1644455f845d1a2701bbaaa9a8",
    "skills/make-eval-fixtures/SKILL.md": "c9d7700decc88712768473d7e24aefb6a7a87afb82b7e94230dae0d432adabec",
}
# The Northwind starter files are copies of the session's examples. They are scanned for words as well,
# and their hashes are recorded so a wording "fix" cannot slip in unnoticed.
NORTHWIND_HASHES = {
    "answer-key.md": "115a454a838e2a1a37813047f61fee13126daf9d4f322df42fa10f341eee59db",
    "fixture-bad.txt": "9279b47785f656e4285d947e7556b5bdc43438f742978e99c749df3cb8cf26e1",
    "fixture-polished-but-wrong.txt": "7000400e462170b8de35153e9911851e8f5d10f0e00fed899da33e8275abf4ca",
    "northwind-prompt-v0.md": "60755f7da1f9a58fe60983dbb263c94254448162dd576ce677a7a8b4265c46de",
    "northwind-test-cases-reference.md": "38e8a236fc20a3201971634ae716f611b6905b2295bed373426e1cfdd263f064",
    "sample-run-1.txt": "60584adb0bb83a3b460952d1f718687afcf35c4168d85774b0a2f0f2346c788b",
    "sample-run-2.txt": "c6ed92c73757819a8161a3a5a5a2bfbfb014db5c4c424f3468ca1d056ae6def2",
    "sample-run-3.txt": "c5afe8379cfa90e286ade8a32b8a98023d673cf9e36a0e7e759fed6b0fca20a0",
    "sample-run-4.txt": "42e045d7e96c69678ced1b35da32ab889ab032282285a897305ebf945a273ad3",
    "sample-run-5.txt": "aa2b565b54a7c8d7ccfc2529fddb9275c21c1da67b580fa76429b9f57e761f4d",
}
# The two catch-up copies open with one comment line that names the Part they stand in for. That line is course
# wording and may change; the hash covers everything else.
CATCH_UP_COMMENT = b"<!-- Catch-up copy"
TEXT_SUFFIXES = {".json", ".md", ".txt", ".html", ".js", ".css", ".svg"}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def body_sha256(path):
    """The hash of a file without its catch-up comment line."""
    lines = Path(path).read_bytes().splitlines(keepends=True)
    return hashlib.sha256(b"".join(x for x in lines if not x.startswith(CATCH_UP_COMMENT))).hexdigest()


def scannable_files():
    """Every file a participant can read, other than vendor code and the byte-identical skills."""
    found = []
    for path in sorted(PACKAGE.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(PACKAGE).as_posix()
        if relative.startswith("web/vendor/") or relative.startswith("kit/skills/"):
            continue
        found.append(path)
    return found


def banned_in(text):
    return [m.group(0) for m in BANNED.finditer(text)] + [m.group(0) for m in SESSION_LABELS.finditer(text)]


class BannedWords(unittest.TestCase):
    def test_the_scan_covers_every_content_file_and_the_web_files(self):
        names = {p.relative_to(PACKAGE).as_posix() for p in scannable_files()}
        for expected in ("content/steps.json", "content/preflight.json", "content/lessons.json",
                         "content/import-checks.json", "content/part-1-lessons.json", "content/part-1-steps.json",
                         "kit/part1/rough-notes.txt", "kit/part1/typical-gaps.md", "kit/part1/frameworks-map.md",
                         "kit/part1/sample-rtcc.md", "kit/part1/sample-rise.md", "web/js/part-steps.js",
                         "content/part-2-lessons.json", "kit/part2/worked-examples.md",
                         "kit/part2/test-case-template.md",
                         "content/glossary.json", "content/lesson-ui.json", "content/cli-recipes.json",
                         "content/series.json", "web/js/series.js",
                         "kit/lessons/hook/requirements.md", "kit/lessons/demo/test-cases.md",
                         "kit/lessons/demo/output.txt", "web/index.html", "web/js/app.js", "web/js/panels.js",
                         "web/js/views.js", "web/styles.css", "kit/northwind/northwind-prompt-v0.md"):
            with self.subTest(file=expected):
                self.assertIn(expected, names)
        self.assertFalse([n for n in names if n.startswith("web/vendor/")])
        self.assertFalse([n for n in names if n.startswith("kit/skills/")])
        # Files another part of the Part 2 change adds: scanned as soon as they exist.
        for later in ("content/part-2-steps.json", "web/js/criteria-steps.js"):
            if (PACKAGE / later).is_file():
                self.assertIn(later, names)

    def test_no_file_a_participant_reads_uses_a_banned_word(self):
        for path in scannable_files():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.relative_to(PACKAGE).as_posix()):
                self.assertEqual(banned_in(text), [])

    def test_no_string_in_the_app_code_uses_a_banned_word(self):
        import ast
        for path in sorted(PACKAGE.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    with self.subTest(file=path.name, text=node.value[:40]):
                        self.assertEqual(banned_in(node.value), [])

    def test_every_string_in_every_content_file_is_clean_one_by_one(self):
        def strings(value):
            if isinstance(value, str):
                yield value
            elif isinstance(value, list):
                for item in value:
                    yield from strings(item)
            elif isinstance(value, dict):
                for key, item in value.items():
                    yield key
                    yield from strings(item)

        for path in sorted(CONTENT.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            for text in strings(data):
                with self.subTest(file=path.name, text=text[:50]):
                    self.assertEqual(banned_in(text), [])

    def test_the_banned_pattern_catches_what_it_should_and_leaves_ordinary_words_alone(self):
        for bad in ("The presenter said", "Ask the Facilitator", "in the room", "Room A", "room b", "breakout rooms",
                    "chat waterfall", "the handout", "your neighbor", "your neighbour", "the clock", "clocks",
                    "Copilot Chat", "copilot  chat", "Rooms"):
            with self.subTest(text=bad):
                self.assertTrue(banned_in(bad), bad)
        for fine in ("There is no clockwise order", "bedroom", "roomy", "a bathroom", "mushroom", "overclocked",
                     "neighborhood", "presentation", "Copilot CLI", "copilot-cli", "Claude Code", "clockwork"):
            with self.subTest(text=fine):
                self.assertEqual(banned_in(fine), [], fine)

    def test_the_word_clock_is_never_needed_in_the_content(self):
        # The injected time source in Python code is `_clock` (an identifier, never a string), so no allow-list
        # is needed for it. Content has no reason to say clock either.
        for path in scannable_files():
            self.assertNotRegex(path.read_text(encoding="utf-8"), r"(?i)\bclocks?\b", path.name)

    def test_the_skill_files_hold_their_one_allowed_use_of_room_and_nothing_else_banned(self):
        for name in SKILL_HASHES:
            text = resources.read_text("kit/" + name)
            hits = [m.group(0).lower() for m in BANNED.finditer(text)]
            with self.subTest(file=name):
                self.assertTrue(set(hits) <= {"room"}, hits)
        text = resources.read_text("kit/skills/build-eval-script/SKILL.md")
        self.assertEqual(len(re.findall(r"\bleft room\b", text)), 1)
        self.assertEqual(len(BANNED.findall(text)), 1)


class FilesThatMustNotChange(unittest.TestCase):
    def test_the_bundled_skills_are_byte_identical_to_the_recorded_hashes(self):
        for name, expected in SKILL_HASHES.items():
            with self.subTest(file=name):
                self.assertEqual(sha256(KIT / name), expected)

    def test_no_skill_file_was_added_or_removed(self):
        found = {p.relative_to(KIT).as_posix() for p in (KIT / "skills").rglob("*") if p.is_file()}
        self.assertEqual(found, set(SKILL_HASHES))

    def test_the_northwind_examples_are_unchanged(self):
        for name, expected in NORTHWIND_HASHES.items():
            with self.subTest(file=name):
                self.assertEqual(body_sha256(KIT / "northwind" / name), expected)
        found = {p.name for p in (KIT / "northwind").iterdir()}
        self.assertEqual(found, set(NORTHWIND_HASHES))

    def test_the_skills_match_the_session_source_when_it_is_available(self):
        if not helpers.SOURCE.is_dir():
            self.skipTest("source folder absent")
        for name in SKILL_HASHES:
            source = helpers.SOURCE / name
            with self.subTest(file=name):
                self.assertEqual(sha256(source), SKILL_HASHES[name])


class Approvals(unittest.TestCase):
    """Copilot Chat in Teams is never suggested, and Northwind is never a submission option."""

    def test_copilot_chat_in_teams_is_never_suggested_anywhere(self):
        for path in scannable_files():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertNotRegex(text, r"(?i)copilot\s+chat")
                self.assertNotRegex(text, r"(?i)teams\s+copilot")
                self.assertNotRegex(text, r"(?i)copilot\s+in\s+teams")

    def test_teams_appears_only_as_the_northwind_message_channel(self):
        for path in scannable_files():
            if path.suffix != ".json" or path.parent.name != "content":
                continue
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"(?i)\bteams\b", text):
                around = text[max(0, match.start() - 80):match.end() + 80]
                with self.subTest(file=path.name, text=around):
                    self.assertNotRegex(around, r"(?i)copilot|ai tool|recommend|use teams")

    def test_northwind_is_always_called_a_learning_example_where_the_course_introduces_it(self):
        data = json.loads(resources.read_text("content/lessons.json"))
        mission = next(x for x in data["lessons"] if x["id"] == "mission")
        self.assertIn("It is for practice only and is never something to submit", mission["body"])
        self.assertNotIn("Northwind", mission["body"])
        for lesson in data["lessons"]:
            for source in lesson["sources"] + [lesson["primary_source"]]:
                if "northwind" in source["ref"]:
                    with self.subTest(lesson=lesson["id"], ref=source["ref"]):
                        self.assertIn("learning example", source["label"].lower())

    def test_nothing_offers_northwind_as_a_submission(self):
        pattern = re.compile(r"(?i)(submit|hand in|turn in|deliver|send in)[^.\n]{0,60}northwind|"
                             r"northwind[^.\n]{0,60}(to submit|for submission|as your submission|you submit|"
                             r"you can submit|can be submitted)")
        for path in scannable_files():
            if path.suffix not in (".json", ".md", ".html", ".js"):
                continue
            text = path.read_text(encoding="utf-8")
            for match in pattern.finditer(text):
                around = text[max(0, match.start() - 60):match.end() + 60]
                with self.subTest(file=path.name, text=around):
                    self.assertRegex(around, r"(?i)never|not |cannot|can't|isn't|only for practice")

    def test_the_lessons_never_tell_participants_to_use_northwind_in_place_of_their_own_work(self):
        text = resources.read_text("content/lessons.json").lower()
        for needle in ("use northwind instead", "submit northwind", "submit the northwind", "northwind as your",
                       "northwind is your submission"):
            self.assertNotIn(needle, text)

    def test_no_lesson_gives_a_contact_instruction(self):
        data = json.loads(resources.read_text("content/lessons.json"))
        text = json.dumps(data) + resources.read_text("content/lesson-ui.json")
        for needle in ("contact ", "reach out", "ask the team", "ask your instructor", "ask your trainer",
                       "email us", "message us"):
            with self.subTest(needle=needle):
                self.assertNotIn(needle, text.lower())

    def test_lesson_content_is_valid_after_these_checks(self):
        L.load_bundled()


if __name__ == "__main__":
    unittest.main()
