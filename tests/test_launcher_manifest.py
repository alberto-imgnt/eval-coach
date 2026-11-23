"""The pinned runtime values live in packaging/runtime-manifest.json; every place that repeats them must agree."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

import helpers

ROOT = helpers.ROOT
sys.path.insert(0, str(ROOT / "tools"))

import build_pyz  # noqa: E402
from eval_coach import hostos  # noqa: E402

MANIFEST = json.loads((ROOT / "packaging" / "runtime-manifest.json").read_text(encoding="utf-8"))


class LaunchersAgreeWithTheManifest(unittest.TestCase):
    def test_the_windows_launcher_is_already_stamped(self):
        source = (ROOT / "packaging" / "launcher.cmd").read_bytes()
        self.assertEqual(build_pyz.stamp_cmd(source, MANIFEST), source)

    def test_the_mac_launcher_is_already_stamped(self):
        source = (ROOT / "packaging" / "launcher.sh").read_bytes()
        self.assertEqual(build_pyz.stamp_sh(source, MANIFEST), source)

    def test_stamping_changes_exactly_the_pinned_values(self):
        source = (ROOT / "packaging" / "launcher.sh").read_bytes()
        changed = json.loads(json.dumps(MANIFEST))
        changed["mac"]["python"]["arm64"]["sha256"] = "f" * 64
        stamped = build_pyz.stamp_sh(source, changed)
        self.assertNotEqual(stamped, source)
        self.assertIn(b'EC_PY_ARM64_SHA256="' + b"f" * 64 + b'"', stamped)
        self.assertEqual(len(stamped.splitlines()), len(source.splitlines()))

    def test_stamping_keeps_the_windows_line_endings(self):
        source = (ROOT / "packaging" / "launcher.cmd").read_bytes()
        changed = json.loads(json.dumps(MANIFEST))
        changed["windows"]["python"]["sha256"] = "a" * 64
        stamped = build_pyz.stamp_cmd(source, changed)
        self.assertEqual(stamped.count(b"\r\n"), source.count(b"\r\n"))
        self.assertIn(b"a" * 64, stamped)

    def test_a_missing_variable_fails_the_build(self):
        with self.assertRaises(ValueError):
            build_pyz.stamp_sh(b"#!/bin/bash\nexit 0\n", MANIFEST)
        with self.assertRaises(ValueError):
            build_pyz.stamp_cmd(b"@echo off\r\n", MANIFEST)

    def test_the_built_mac_launcher_refuses_windows_line_endings(self):
        with self.assertRaises(ValueError):
            build_pyz.assemble_mac_launcher(b"#!/bin/bash\r\n" + build_pyz.MAC_LAUNCHER_MARKER, b"PK")
        with self.assertRaises(ValueError):
            build_pyz.assemble_mac_launcher(b"#!/bin/bash\nexit 0\n", b"PK")


class TheAppAgreesWithTheManifest(unittest.TestCase):
    def check(self, pin, entry, version):
        self.assertEqual(pin.url, entry["url"])
        self.assertEqual(pin.sha256, entry["sha256"])
        self.assertEqual(pin.folder, entry["folder"])
        self.assertEqual(pin.download_bytes, entry["download_bytes"])
        self.assertEqual(pin.version, version)

    def test_windows_node(self):
        node = MANIFEST["windows"]["node"]
        self.check(hostos.NODE_PINS["windows"], node, node["version"])

    def test_mac_node_for_both_chips(self):
        node = MANIFEST["mac"]["node"]
        self.check(hostos.NODE_PINS["mac-arm64"], node["arm64"], node["version"])
        self.check(hostos.NODE_PINS["mac-x64"], node["x64"], node["version"])

    def test_the_mac_node_floor(self):
        major, minor = MANIFEST["mac"]["node"]["min_macos"].split(".")
        self.assertEqual(hostos.MAC_NODE_MIN_VERSION, (int(major), int(minor)))


class ManifestShape(unittest.TestCase):
    def test_every_pin_has_a_url_and_a_sha256(self):
        found = []

        def walk(value):
            if isinstance(value, dict):
                if "sha256" in value:
                    found.append(value)
                for child in value.values():
                    walk(child)

        walk(MANIFEST)
        self.assertEqual(len(found), 6)
        for entry in found:
            self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(entry["url"].startswith("https://"))

    def test_each_download_comes_from_a_host_the_rules_allow(self):
        hosts = ("https://www.python.org/", "https://nodejs.org/", "https://github.com/astral-sh/python-build-standalone/")
        urls = re.findall(r'"url": "([^"]+)"', (ROOT / "packaging" / "runtime-manifest.json").read_text(encoding="utf-8"))
        self.assertTrue(urls)
        for url in urls:
            self.assertTrue(url.startswith(hosts), url)

    def test_the_mac_python_asset_names_match_the_release(self):
        python = MANIFEST["mac"]["python"]
        for chip, name in (("arm64", "aarch64"), ("x86_64", "x86_64")):
            url = python[chip]["url"]
            self.assertIn(f"/{python['release']}/", url)
            self.assertIn(f"cpython-{python['version']}%2B{python['release']}-{name}-apple-darwin-install_only.tar.gz", url)


if __name__ == "__main__":
    unittest.main()
