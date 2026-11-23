"""The project folder must be separate from the app's storage folder, however the path is spelled."""
from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

import helpers  # noqa: F401  (puts the app on the path)

from eval_coach import project


class SeparateFromStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="eval-coach-path-")).resolve()
        self.addCleanup(shutil.rmtree, str(self.tmp), True)
        self.home = self.tmp / ".eval-coach"
        self.home.mkdir()

    def test_a_folder_inside_or_around_the_storage_is_refused(self):
        for chosen in (self.home / "inner", self.tmp):
            with self.subTest(chosen=str(chosen)):
                with self.assertRaises(project.ProjectError):
                    project.validate_project_path(self.home, chosen)

    def test_a_separate_folder_is_accepted(self):
        project.validate_project_path(self.home, self.tmp / "eval-project")

    def test_the_same_folder_spelled_with_other_capitals_is_refused(self):
        other = self.tmp / ".EVAL-COACH"
        if not other.exists():
            self.skipTest("this file system tells .EVAL-COACH from .eval-coach")
        # What a Mac's usual file system does: the folder is found by either spelling, a new project below it too.
        self.assertTrue(project._inside_on_disk(str(other / "project"), str(self.home)))
        with self.assertRaises(project.ProjectError):
            project.validate_project_path(self.home, other / "project")

    def test_a_link_to_the_storage_is_refused(self):
        link = self.tmp / "shortcut"
        try:
            os.symlink(str(self.home), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("this computer does not allow links here")
        with self.assertRaises(project.ProjectError):
            project.validate_project_path(self.home, link / "project")

    def test_an_unrelated_existing_folder_is_not_inside(self):
        (self.tmp / "other").mkdir()
        self.assertFalse(project._inside_on_disk(str(self.tmp / "other" / "p"), str(self.home)))


if __name__ == "__main__":
    unittest.main()
