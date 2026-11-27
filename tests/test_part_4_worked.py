"""The authored worked answers of Part 4's Practice task (OpenSpec change part-4-course).

Ten saved answers (five for each worked round) are scored by the reference checker, so no number in the worked example
is typed by hand. Iteration 0 is the Practice task's five sample answers.
"""
from __future__ import annotations

import importlib.util
import unittest

from helpers import GOLDEN, NORTHWIND

_spec = importlib.util.spec_from_file_location("reference_check_worked", str(GOLDEN / "reference-check.py"))
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)

WORKED = GOLDEN / "part4-worked"
RULES = [cid for cid, _name, _fn in reference.CRITERIA]


def read(path):
    return path.read_text(encoding="utf-8")


def counts(texts):
    """{rule id: passes} over the answers, scored by the reference checker."""
    return {cid: sum(1 for text in texts if fn(text)[0]) for cid, _name, fn in reference.CRITERIA}


def zero():
    return [read(NORTHWIND / f"sample-run-{n}.txt") for n in range(1, 6)]


def round_answers(n):
    return [read(WORKED / f"round-{n}" / f"run-{k}.txt") for k in range(1, 6)]


class WorkedAnswers(unittest.TestCase):
    def test_iteration_0_is_25_of_30_with_factual_tone_at_3_of_5(self):
        scored = counts(zero())
        self.assertEqual(scored, {"C1": 4, "C2": 4, "C3": 4, "C4": 5, "C5": 3, "C6": 5})
        self.assertEqual(sum(scored.values()), 25)

    def test_round_1_is_26_of_30_with_tone_up_and_the_notes_rule_down(self):
        scored = counts(round_answers(1))
        before = counts(zero())
        self.assertEqual(scored["C5"], 5)
        self.assertEqual(scored["C6"], 4)
        for cid in ("C1", "C2", "C3", "C4"):
            self.assertEqual(scored[cid], before[cid], cid)
        self.assertEqual(sum(scored.values()), 26)

    def test_round_2_is_26_of_30_with_the_same_count_for_every_rule(self):
        self.assertEqual(counts(round_answers(2)), counts(round_answers(1)))
        self.assertEqual(sum(counts(round_answers(2)).values()), 26)

    def test_the_one_lost_note_keyword_is_lunch_and_the_other_five_are_kept(self):
        for n in (1, 2):
            missing = [reference.check_c6_uses_the_notes(text)[1] for text in round_answers(n)
                       if not reference.check_c6_uses_the_notes(text)[0]]
            self.assertEqual(missing, ["missing keyword(s): lunch"], n)

    def test_each_round_has_five_distinct_non_empty_answers(self):
        for n in (1, 2):
            answers = round_answers(n)
            self.assertEqual(len(set(answers)), 5)
            self.assertTrue(all(a.strip() for a in answers))
        self.assertTrue(set(round_answers(1)).isdisjoint(round_answers(2)))

    def test_no_worked_answer_names_the_certification_or_a_session(self):
        for n in (1, 2):
            for text in round_answers(n):
                self.assertNotRegex(text.lower(), r"stage 3|certif|session|presenter")


if __name__ == "__main__":
    unittest.main()
