import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from eval_coach import hostos  # noqa: E402

WIN, MAC = "win32", "darwin"


class PlatformTests(unittest.TestCase):
    def test_platform_keys(self):
        self.assertEqual(hostos.platform_key(WIN), "windows")
        self.assertEqual(hostos.platform_key(MAC), "mac")
        self.assertEqual(hostos.platform_key("linux"), "other")

    def test_windows_tools_are_the_system32_programs(self):
        for name, tail in (("curl", "curl.exe"), ("tar", "tar.exe"), ("taskkill", "taskkill.exe"),
                           ("cmd", "cmd.exe")):
            parts = hostos.tool_path(name, WIN).lower().split("\\")
            self.assertEqual(parts[-2:], ["system32", tail])
        self.assertTrue(hostos.tool_path("powershell", WIN).lower().endswith(
            "\\windowspowershell\\v1.0\\powershell.exe"))

    def test_mac_tools_are_fixed_system_paths(self):
        self.assertEqual(hostos.tool_path("curl", MAC), "/usr/bin/curl")
        self.assertEqual(hostos.tool_path("shasum", MAC), "/usr/bin/shasum")
        self.assertEqual(hostos.tool_path("zsh", MAC), "/bin/zsh")


class CommandTests(unittest.TestCase):
    def test_windows_download_argv_is_unchanged(self):
        argv = hostos.download_argv("n.zip", "https://x/n.zip", 900, WIN)
        self.assertEqual(argv[0], hostos.tool_path("curl", WIN))
        self.assertEqual(argv[1:5], ["--fail", "--location", "--ssl-no-revoke", "--connect-timeout"])
        self.assertEqual(argv[-3:], ["--output", "n.zip", "https://x/n.zip"])
        self.assertIn("--max-time", argv)

    def test_mac_download_argv_has_no_windows_only_option(self):
        argv = hostos.download_argv("n.tar.gz", "https://x/n.tar.gz", 900, MAC)
        self.assertEqual(argv[0], "/usr/bin/curl")
        self.assertNotIn("--ssl-no-revoke", argv)
        self.assertEqual(argv[-3:], ["--output", "n.tar.gz", "https://x/n.tar.gz"])

    def test_extract_argv(self):
        self.assertEqual(hostos.extract_argv("a.zip", "stage", WIN)[1:], ["-xf", "a.zip", "-C", "stage"])
        self.assertEqual(hostos.extract_argv("a.tar.gz", "stage", MAC),
                         ["/usr/bin/tar", "-xzf", "a.tar.gz", "-C", "stage"])

    def test_recipe_shell_argv(self):
        self.assertEqual(hostos.recipe_shell_argv("cmd", "winget x", WIN)[1:], ["/d", "/s", "/c", "winget x"])
        self.assertEqual(hostos.recipe_shell_argv("powershell", "irm x | iex", WIN)[1:],
                         ["-NoProfile", "-Command", "irm x | iex"])
        self.assertEqual(hostos.recipe_shell_argv("zsh", "echo hi", MAC), ["/bin/zsh", "-lc", "echo hi"])

    def test_recipe_shells(self):
        self.assertEqual(hostos.recipe_shells(WIN), ("cmd", "powershell", "none"))
        self.assertEqual(hostos.recipe_shells(MAC), ("zsh", "none"))

    def test_popen_flags(self):
        self.assertEqual(hostos.popen_flags(WIN), {"creationflags": 0x08000000})
        self.assertEqual(hostos.popen_flags(MAC), {"start_new_session": True})
        self.assertEqual(hostos.popen_flags(MAC, new_group=False), {})


class NodeTests(unittest.TestCase):
    def test_windows_pin(self):
        pin = hostos.node_pin(WIN)
        self.assertTrue(pin.url.endswith("node-v26.13.0-win-x64.zip"))
        self.assertEqual(pin.exe_relative, ("node.exe",))

    def test_mac_pins_by_chip(self):
        arm, intel = hostos.node_pin(MAC, "arm64"), hostos.node_pin(MAC, "x86_64")
        self.assertTrue(arm.url.endswith("darwin-arm64.tar.gz"))
        self.assertTrue(intel.url.endswith("darwin-x64.tar.gz"))
        self.assertNotEqual(arm.sha256, intel.sha256)
        self.assertEqual(arm.exe_relative, ("bin", "node"))
        self.assertEqual(arm.npx_cli_relative[0], "lib")

    def test_mac_version_floor(self):
        self.assertTrue(hostos.node_supported(MAC, "13.5"))
        self.assertTrue(hostos.node_supported(MAC, "15.1.1"))
        self.assertFalse(hostos.node_supported(MAC, "13.4.1"))
        self.assertFalse(hostos.node_supported(MAC, "12.7"))
        self.assertTrue(hostos.node_supported(WIN, "1.0"))
        self.assertTrue(hostos.node_supported(MAC, "unknown"), "an unreadable version is not blocked")

    def test_private_python_and_names(self):
        self.assertEqual(hostos.private_python_relative(WIN)[-1], "python.exe")
        self.assertEqual(hostos.private_python_relative(MAC)[-2:], ("bin", "python3"))
        self.assertEqual(hostos.python_command_names(MAC), ("python3", "python"))
        self.assertEqual(hostos.python_command_names(WIN), ("python",))


class PathTests(unittest.TestCase):
    def test_mac_dirs_only_those_that_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".local" / "bin").mkdir(parents=True)
            found = hostos.mac_tool_dirs(tmp)
            self.assertIn(os.path.join(tmp, ".local", "bin"), found)
            self.assertNotIn(os.path.join(tmp, ".claude", "local"), found)
            self.assertEqual(hostos.extra_path_dirs(MAC, tmp), found)

    def test_other_platform_adds_nothing(self):
        self.assertEqual(hostos.extra_path_dirs("linux"), [])


class MarkerTests(unittest.TestCase):
    HINTS = {"marker_variable": "WT_SESSION", "marker_variable_mac": "TERM_PROGRAM",
             "marker_value_mac": "Apple_Terminal"}

    def test_windows_marker_is_a_fresh_id(self):
        variable, value = hostos.terminal_marker(self.HINTS, WIN)
        self.assertEqual(variable, "WT_SESSION")
        self.assertEqual(len(value), 36)

    def test_mac_marker(self):
        self.assertEqual(hostos.terminal_marker(self.HINTS, MAC), ("TERM_PROGRAM", "Apple_Terminal"))
        self.assertEqual(hostos.terminal_marker({"marker_variable": "WT_SESSION"}, MAC), (None, None))


class HelpTextTests(unittest.TestCase):
    def test_home_label(self):
        self.assertEqual(hostos.default_home_label(WIN), "%USERPROFILE%\\.eval-coach")
        self.assertEqual(hostos.default_home_label(MAC), "~/.eval-coach")
        self.assertNotIn("USERPROFILE", hostos.default_home_label(MAC))


if __name__ == "__main__":
    unittest.main()
