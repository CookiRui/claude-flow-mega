#!/usr/bin/env python3
"""Tests for scoped-rules.py module-scoped rules loader."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib

scoped_rules = importlib.import_module("scoped-rules")


class TestDetectModules(unittest.TestCase):
    """Test module detection (directories with .claude/ subdirectory)."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Root has .claude/
        os.makedirs(os.path.join(self.tmpdir, ".claude", "rules"))
        # Module A has .claude/
        os.makedirs(os.path.join(self.tmpdir, "module-a", ".claude", "rules"))
        # Module B has .claude/
        os.makedirs(os.path.join(self.tmpdir, "module-b", ".claude", "rules"))
        # Module C does NOT have .claude/ (not a scoped module)
        os.makedirs(os.path.join(self.tmpdir, "module-c", "src"))

    def test_detect_modules_finds_scoped_dirs(self):
        modules = scoped_rules.detect_modules(self.tmpdir)
        names = [m["name"] for m in modules]
        self.assertIn("module-a", names)
        self.assertIn("module-b", names)
        self.assertNotIn("module-c", names)

    def test_detect_modules_includes_root(self):
        modules = scoped_rules.detect_modules(self.tmpdir)
        paths = [m["path"] for m in modules]
        self.assertIn(self.tmpdir, paths)

    def test_detect_modules_returns_relative_paths(self):
        modules = scoped_rules.detect_modules(self.tmpdir)
        for m in modules:
            if m["name"] != ".":
                self.assertFalse(os.path.isabs(m["rel_path"]))


class TestAffectedModules(unittest.TestCase):
    """Test determining which modules are affected by a set of changed files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, ".claude", "rules"))
        os.makedirs(os.path.join(self.tmpdir, "module-a", ".claude", "rules"))
        os.makedirs(os.path.join(self.tmpdir, "module-b", ".claude", "rules"))
        os.makedirs(os.path.join(self.tmpdir, "module-c", "src"))

    def test_files_in_module_a_affect_module_a(self):
        changed = ["module-a/src/app.py", "module-a/tests/test_app.py"]
        affected = scoped_rules.affected_modules(self.tmpdir, changed)
        names = [m["name"] for m in affected]
        self.assertIn("module-a", names)
        self.assertNotIn("module-b", names)

    def test_files_in_root_affect_root(self):
        changed = ["setup.py", "README.md"]
        affected = scoped_rules.affected_modules(self.tmpdir, changed)
        names = [m["name"] for m in affected]
        self.assertIn(".", names)

    def test_files_in_non_module_dir_affect_root(self):
        changed = ["module-c/src/something.py"]
        affected = scoped_rules.affected_modules(self.tmpdir, changed)
        names = [m["name"] for m in affected]
        # module-c has no .claude/, so changes there fall under root
        self.assertIn(".", names)

    def test_empty_changed_files_returns_empty(self):
        affected = scoped_rules.affected_modules(self.tmpdir, [])
        self.assertEqual(len(affected), 0)


class TestLoadModuleRules(unittest.TestCase):
    """Test loading rules from a module's .claude/ directory."""

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

    def test_load_root_rules(self):
        rules = scoped_rules.load_module_rules(self.tmpdir, ".")
        self.assertTrue(len(rules) > 0)
        rule_files = [r["file"] for r in rules]
        self.assertTrue(any("security.md" in f for f in rule_files))

    def test_load_module_rules(self):
        rules = scoped_rules.load_module_rules(self.tmpdir, "module-a")
        rule_files = [r["file"] for r in rules]
        self.assertTrue(any("perf.md" in f for f in rule_files))

    def test_load_module_constitution(self):
        constitution = scoped_rules.load_module_constitution(self.tmpdir, "module-a")
        self.assertIsNotNone(constitution)
        self.assertIn("Module-specific constraint", constitution["content"])

    def test_load_root_constitution(self):
        constitution = scoped_rules.load_module_constitution(self.tmpdir, ".")
        self.assertIsNotNone(constitution)
        self.assertIn("Global constraint", constitution["content"])


class TestRulePriority(unittest.TestCase):
    """Test rule priority resolution."""

    def test_module_rules_override_root_on_conflict(self):
        root_rules = [
            {"file": "security.md", "scope": "root", "content": "# Security\n\n## Rule 1: Use SHA256"},
        ]
        module_rules = [
            {"file": "security.md", "scope": "module-a", "content": "# Security\n\n## Rule 1: Use SHA512"},
        ]
        merged = scoped_rules.merge_rules(root_rules, module_rules)
        # Module-level security.md should take priority
        security = [r for r in merged if "security.md" in r["file"]]
        self.assertEqual(len(security), 1)
        self.assertIn("SHA512", security[0]["content"])

    def test_non_conflicting_rules_are_both_included(self):
        root_rules = [
            {"file": "security.md", "scope": "root", "content": "# Security"},
        ]
        module_rules = [
            {"file": "perf.md", "scope": "module-a", "content": "# Performance"},
        ]
        merged = scoped_rules.merge_rules(root_rules, module_rules)
        self.assertEqual(len(merged), 2)

    def test_empty_module_rules_returns_root(self):
        root_rules = [
            {"file": "security.md", "scope": "root", "content": "# Security"},
        ]
        merged = scoped_rules.merge_rules(root_rules, [])
        self.assertEqual(len(merged), 1)


class TestScopedRulesForDiff(unittest.TestCase):
    """Integration test: given changed files, get the scoped rules."""

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

    def test_get_scoped_rules_for_module_change(self):
        changed = ["module-a/src/app.py"]
        result = scoped_rules.get_scoped_rules(self.tmpdir, changed)
        self.assertIn("constitutions", result)
        self.assertIn("rules", result)
        # Should have root constitution + module constitution
        const_scopes = [c["scope"] for c in result["constitutions"]]
        self.assertIn("root", const_scopes)
        self.assertIn("module-a", const_scopes)

    def test_get_scoped_rules_for_root_change(self):
        changed = ["setup.py"]
        result = scoped_rules.get_scoped_rules(self.tmpdir, changed)
        const_scopes = [c["scope"] for c in result["constitutions"]]
        self.assertIn("root", const_scopes)
        # Should NOT include module-a constitution
        self.assertNotIn("module-a", const_scopes)

    def test_output_format_is_json_serializable(self):
        changed = ["module-a/src/app.py"]
        result = scoped_rules.get_scoped_rules(self.tmpdir, changed)
        # Should be JSON-serializable
        serialized = json.dumps(result)
        self.assertIsInstance(serialized, str)


if __name__ == "__main__":
    unittest.main()
