#!/usr/bin/env python3
"""Tests for scope-loader.py module-scoped rules loader."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib

scope_loader = importlib.import_module("scope-loader")


class TestDetectModules(unittest.TestCase):
    """Test module detection (directories with source files)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Module A has source files
        mod_a = os.path.join(self.tmpdir, "module-a", "src")
        os.makedirs(mod_a)
        Path(os.path.join(mod_a, "app.py")).write_text("# code", encoding="utf-8")
        # Module B has source files
        mod_b = os.path.join(self.tmpdir, "module-b", "src")
        os.makedirs(mod_b)
        Path(os.path.join(mod_b, "main.py")).write_text("# code", encoding="utf-8")
        # Module C has no source files
        os.makedirs(os.path.join(self.tmpdir, "module-c"))
        Path(os.path.join(self.tmpdir, "module-c", "readme.txt")).write_text("no code", encoding="utf-8")

    def _detect(self):
        config = scope_loader.load_config(self.tmpdir)
        return scope_loader.detect_modules(self.tmpdir, config)

    def test_detect_modules_finds_source_dirs(self):
        modules = self._detect()
        names = [m["name"] for m in modules]
        self.assertIn("module-a", names)
        self.assertIn("module-b", names)

    def test_detect_modules_includes_root(self):
        modules = self._detect()
        names = [m["name"] for m in modules]
        self.assertIn("_root", names)

    def test_detect_modules_skips_no_source_dirs(self):
        modules = self._detect()
        names = [m["name"] for m in modules]
        self.assertNotIn("module-c", names)


class TestClassifyFileToModule(unittest.TestCase):
    """Test file-to-module classification."""

    def setUp(self):
        self.modules = [
            {"name": "module-a", "paths": ["module-a/"], "description": ""},
            {"name": "module-b", "paths": ["module-b/"], "description": ""},
            {"name": "_root", "paths": [""], "description": "Root"},
        ]

    def test_file_in_module_a(self):
        result = scope_loader.classify_file_to_module("module-a/src/app.py", self.modules)
        self.assertEqual(result, "module-a")

    def test_file_in_root(self):
        result = scope_loader.classify_file_to_module("setup.py", self.modules)
        self.assertEqual(result, "_root")

    def test_file_in_unknown_dir(self):
        result = scope_loader.classify_file_to_module("other/thing.py", self.modules)
        self.assertEqual(result, "_root")


class TestGetAffectedModules(unittest.TestCase):
    """Test determining which modules are affected by changed files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        mod_a = os.path.join(self.tmpdir, "module-a", "src")
        os.makedirs(mod_a)
        Path(os.path.join(mod_a, "app.py")).write_text("# code", encoding="utf-8")
        mod_b = os.path.join(self.tmpdir, "module-b", "src")
        os.makedirs(mod_b)
        Path(os.path.join(mod_b, "main.py")).write_text("# code", encoding="utf-8")

    def test_files_in_module_a_affect_module_a(self):
        changed = ["module-a/src/app.py"]
        affected = scope_loader.get_affected_modules(changed, self.tmpdir)
        self.assertIn("module-a", affected)
        self.assertNotIn("module-b", affected)

    def test_files_in_root_affect_root(self):
        changed = ["setup.py", "README.md"]
        affected = scope_loader.get_affected_modules(changed, self.tmpdir)
        self.assertIn("_root", affected)

    def test_empty_changed_files_returns_empty(self):
        affected = scope_loader.get_affected_modules([], self.tmpdir)
        self.assertEqual(len(affected), 0)


class TestFindRules(unittest.TestCase):
    """Test loading rules from .claude/ directories."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Root rules
        root_rules = os.path.join(self.tmpdir, ".claude", "rules")
        os.makedirs(root_rules)
        Path(os.path.join(root_rules, "security.md")).write_text(
            "# Security Rules\n\n## Rule 1: No secrets in code\n",
            encoding="utf-8",
        )
        # Root constitution
        Path(os.path.join(self.tmpdir, ".claude", "constitution.md")).write_text(
            "# Root Constitution\n\n## S1: Global constraint\n",
            encoding="utf-8",
        )
        # Module rules
        mod_rules = os.path.join(self.tmpdir, "module-a", ".claude", "rules")
        os.makedirs(mod_rules)
        Path(os.path.join(mod_rules, "perf.md")).write_text(
            "# Performance Rules\n\n## Rule 1: No allocations in hot path\n",
            encoding="utf-8",
        )
        # Module constitution
        Path(os.path.join(self.tmpdir, "module-a", ".claude", "constitution.md")).write_text(
            "# Module A Constitution\n\n## S1: Module-specific constraint\n",
            encoding="utf-8",
        )

    def test_find_root_rules(self):
        result = scope_loader.find_root_rules(self.tmpdir)
        self.assertTrue(len(result) > 0)
        paths = [r["path"] for r in result]
        self.assertTrue(any("security.md" in p for p in paths))

    def test_find_root_constitutions(self):
        result = scope_loader.find_root_constitutions(self.tmpdir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["scope"], "root")

    def test_find_module_rules(self):
        result = scope_loader.find_module_rules(["module-a"], self.tmpdir)
        paths = [r["path"] for r in result]
        self.assertTrue(any("perf.md" in p for p in paths))

    def test_find_module_constitutions(self):
        result = scope_loader.find_module_constitutions(["module-a"], self.tmpdir)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["scope"], "module-a")


class TestResolveAll(unittest.TestCase):
    """Integration test: full resolution for affected modules."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Root
        os.makedirs(os.path.join(self.tmpdir, ".claude", "rules"))
        Path(os.path.join(self.tmpdir, ".claude", "constitution.md")).write_text(
            "# Root Constitution\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.tmpdir, ".claude", "rules", "security.md")).write_text(
            "# Security Rules\n",
            encoding="utf-8",
        )
        # Module A
        os.makedirs(os.path.join(self.tmpdir, "module-a", ".claude", "rules"))
        Path(os.path.join(self.tmpdir, "module-a", ".claude", "constitution.md")).write_text(
            "# Module A Constitution\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.tmpdir, "module-a", ".claude", "rules", "perf.md")).write_text(
            "# Perf Rules\n",
            encoding="utf-8",
        )

    def test_resolve_for_module_change(self):
        result = scope_loader.resolve_all(self.tmpdir, ["module-a"])
        self.assertIn("constitutions", result)
        self.assertIn("rules", result)
        const_scopes = [c["scope"] for c in result["constitutions"]]
        self.assertIn("root", const_scopes)
        self.assertIn("module-a", const_scopes)

    def test_resolve_for_root_only(self):
        result = scope_loader.resolve_all(self.tmpdir, ["_root"])
        const_scopes = [c["scope"] for c in result["constitutions"]]
        self.assertIn("root", const_scopes)
        self.assertNotIn("module-a", const_scopes)

    def test_output_format_is_json_serializable(self):
        result = scope_loader.resolve_all(self.tmpdir, ["module-a"])
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)


if __name__ == "__main__":
    unittest.main()
