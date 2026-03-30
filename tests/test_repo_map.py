#!/usr/bin/env python3
"""Tests for repo-map.py layered code map."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add scripts/ to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import importlib

repo_map = importlib.import_module("repo-map")


class TestScanFiles(unittest.TestCase):
    """Test file scanning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "src", "auth"))
        os.makedirs(os.path.join(self.tmpdir, "src", "api"))
        os.makedirs(os.path.join(self.tmpdir, "tests"))
        Path(os.path.join(self.tmpdir, "src", "auth", "login.py")).write_text(
            "class LoginService:\n    def authenticate(self, user):\n        pass\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.tmpdir, "src", "api", "routes.py")).write_text(
            "def get_users():\n    pass\ndef create_user():\n    pass\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.tmpdir, "tests", "test_auth.py")).write_text(
            "def test_login():\n    pass\n",
            encoding="utf-8",
        )

    def test_scan_finds_python_files(self):
        files = repo_map.scan_files(self.tmpdir)
        basenames = [os.path.basename(f) for f in files]
        self.assertIn("login.py", basenames)
        self.assertIn("routes.py", basenames)
        self.assertIn("test_auth.py", basenames)

    def test_scan_with_subdir(self):
        files = repo_map.scan_files(self.tmpdir, "src/auth")
        basenames = [os.path.basename(f) for f in files]
        self.assertIn("login.py", basenames)
        self.assertNotIn("routes.py", basenames)

    def test_scan_nonexistent_subdir_returns_empty(self):
        files = repo_map.scan_files(self.tmpdir, "nonexistent")
        self.assertEqual(files, [])


class TestExtractSymbols(unittest.TestCase):
    """Test symbol extraction."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.pyfile = os.path.join(self.tmpdir, "example.py")
        Path(self.pyfile).write_text(
            "class MyClass:\n"
            "    def my_method(self):\n"
            "        pass\n"
            "\n"
            "def standalone_func():\n"
            "    pass\n",
            encoding="utf-8",
        )

    def test_extract_class_and_functions(self):
        symbols = repo_map.extract_symbols(self.pyfile, self.tmpdir)
        names = [s["name"] for s in symbols]
        self.assertIn("MyClass", names)
        self.assertIn("my_method", names)
        self.assertIn("standalone_func", names)

    def test_symbols_have_required_fields(self):
        symbols = repo_map.extract_symbols(self.pyfile, self.tmpdir)
        for s in symbols:
            self.assertIn("name", s)
            self.assertIn("type", s)
            self.assertIn("file", s)
            self.assertIn("line", s)

    def test_noise_names_are_skipped(self):
        noise_file = os.path.join(self.tmpdir, "noise.py")
        Path(noise_file).write_text(
            "def __init__(self):\n    pass\n"
            "def __str__(self):\n    pass\n",
            encoding="utf-8",
        )
        symbols = repo_map.extract_symbols(noise_file, self.tmpdir)
        names = [s["name"] for s in symbols]
        self.assertNotIn("__init__", names)
        self.assertNotIn("__str__", names)


class TestDetectModules(unittest.TestCase):
    """Test module detection from directory structure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Create module-like directories with source files
        for mod in ["auth", "api"]:
            mod_dir = os.path.join(self.tmpdir, mod)
            os.makedirs(mod_dir)
            Path(os.path.join(mod_dir, "app.py")).write_text(
                "class App:\n    pass\n", encoding="utf-8"
            )
        # Create a docs dir (should be excluded)
        os.makedirs(os.path.join(self.tmpdir, "docs"))
        Path(os.path.join(self.tmpdir, "docs", "notes.txt")).write_text(
            "just docs", encoding="utf-8"
        )
        # Root-level file
        Path(os.path.join(self.tmpdir, "setup.py")).write_text(
            "def setup():\n    pass\n", encoding="utf-8"
        )

    def test_detects_source_directories_as_modules(self):
        config = {"modules": {}, "exclude_dirs": [], "auto_detect": True}
        modules = repo_map.detect_modules(self.tmpdir, config)
        names = [m["name"] for m in modules]
        self.assertIn("auth", names)
        self.assertIn("api", names)

    def test_excludes_non_module_dirs(self):
        config = {"modules": {}, "exclude_dirs": [], "auto_detect": True}
        modules = repo_map.detect_modules(self.tmpdir, config)
        names = [m["name"] for m in modules]
        self.assertNotIn("docs", names)

    def test_includes_root_pseudo_module(self):
        config = {"modules": {}, "exclude_dirs": [], "auto_detect": True}
        modules = repo_map.detect_modules(self.tmpdir, config)
        names = [m["name"] for m in modules]
        self.assertIn("_root", names)

    def test_explicit_config_modules(self):
        config = {
            "modules": {
                "my-module": {"paths": ["auth/"], "description": "Auth module"}
            },
            "exclude_dirs": [],
            "auto_detect": False,
        }
        modules = repo_map.detect_modules(self.tmpdir, config)
        names = [m["name"] for m in modules]
        self.assertIn("my-module", names)
        # With auto_detect=False, only explicit modules + root
        self.assertNotIn("api", names)


class TestClassifyFileToModule(unittest.TestCase):
    """Test file-to-module classification."""

    def setUp(self):
        self.modules = [
            {"name": "auth", "paths": ["auth/"]},
            {"name": "api", "paths": ["api/"]},
            {"name": "_root", "paths": [""]},
        ]

    def test_classify_file_in_module(self):
        self.assertEqual(
            repo_map.classify_file_to_module("auth/login.py", self.modules),
            "auth"
        )

    def test_classify_root_file(self):
        self.assertEqual(
            repo_map.classify_file_to_module("setup.py", self.modules),
            "_root"
        )

    def test_classify_unknown_path_falls_back_to_root(self):
        # _root is a catch-all for files not in named modules
        self.assertEqual(
            repo_map.classify_file_to_module("unknown/deep/file.py", self.modules),
            "_root"
        )

    def test_classify_without_root_returns_unclassified(self):
        modules_no_root = [
            {"name": "auth", "paths": ["auth/"]},
            {"name": "api", "paths": ["api/"]},
        ]
        self.assertEqual(
            repo_map.classify_file_to_module("unknown/deep/file.py", modules_no_root),
            "_unclassified"
        )


class TestBuildFlatMap(unittest.TestCase):
    """Test legacy flat map building."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "src"))
        Path(os.path.join(self.tmpdir, "src", "app.py")).write_text(
            "class App:\n    def run(self):\n        pass\n",
            encoding="utf-8",
        )

    def test_build_returns_expected_structure(self):
        result = repo_map.build_flat_map(self.tmpdir, count_refs=False)
        self.assertIn("total_files", result)
        self.assertIn("total_symbols", result)
        self.assertIn("symbols", result)
        self.assertEqual(result["total_files"], 1)


class TestBuildModuleData(unittest.TestCase):
    """Test module data building."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmpdir, "auth"))
        os.makedirs(os.path.join(self.tmpdir, "api"))
        Path(os.path.join(self.tmpdir, "auth", "login.py")).write_text(
            "class LoginService:\n    def authenticate(self):\n        pass\n",
            encoding="utf-8",
        )
        Path(os.path.join(self.tmpdir, "api", "routes.py")).write_text(
            "def get_users():\n    pass\n",
            encoding="utf-8",
        )
        self.modules = [
            {"name": "auth", "paths": ["auth/"], "description": ""},
            {"name": "api", "paths": ["api/"], "description": ""},
        ]

    def test_builds_data_for_all_modules(self):
        syms, counts, files = repo_map.build_module_data(
            self.tmpdir, self.modules, count_refs=False
        )
        self.assertIn("auth", syms)
        self.assertIn("api", syms)
        auth_names = [s["name"] for s in syms["auth"]]
        self.assertIn("LoginService", auth_names)

    def test_only_modules_filter(self):
        syms, counts, files = repo_map.build_module_data(
            self.tmpdir, self.modules, count_refs=False, only_modules={"auth"}
        )
        self.assertIn("auth", syms)
        self.assertNotIn("api", syms)


class TestGenerateL0(unittest.TestCase):
    """Test L0 generation."""

    def test_l0_contains_module_table(self):
        modules = [
            {"name": "auth", "paths": ["auth/"], "description": "Authentication"},
            {"name": "api", "paths": ["api/"], "description": "REST API"},
        ]
        module_symbols = {
            "auth": [{"name": "LoginService", "type": "class", "file": "auth/login.py", "line": 1, "references": 5}],
            "api": [{"name": "get_users", "type": "function", "file": "api/routes.py", "line": 1, "references": 0}],
        }
        file_counts = {"auth": 1, "api": 1}
        output = repo_map.generate_l0(".", modules, module_symbols, file_counts, [], "abc123")
        self.assertIn("auth", output)
        self.assertIn("api", output)
        self.assertIn("Authentication", output)
        self.assertIn("L0", output)

    def test_l0_shows_cross_refs(self):
        modules = [
            {"name": "auth", "paths": ["auth/"], "description": ""},
            {"name": "api", "paths": ["api/"], "description": ""},
        ]
        module_symbols = {"auth": [], "api": []}
        file_counts = {"auth": 1, "api": 1}
        cross_refs = [("api", "auth", 10)]
        output = repo_map.generate_l0(".", modules, module_symbols, file_counts, cross_refs, "abc123")
        self.assertIn("api -> auth", output)
        self.assertIn("10 refs", output)


class TestGenerateL1(unittest.TestCase):
    """Test L1 generation."""

    def test_l1_shows_symbols_with_lines(self):
        module = {"name": "auth", "paths": ["auth/"], "description": ""}
        symbols = [
            {"name": "LoginService", "type": "class", "file": "auth/login.py", "line": 1, "references": 3},
            {"name": "authenticate", "type": "method", "file": "auth/login.py", "line": 2, "references": 0},
        ]
        output = repo_map.generate_l1(".", module, symbols, 1, "abc123")
        self.assertIn("LoginService", output)
        self.assertIn("authenticate", output)
        self.assertIn("L1", output)
        self.assertIn("auth/login.py", output)

    def test_l1_groups_by_file(self):
        module = {"name": "auth", "paths": ["auth/"], "description": ""}
        symbols = [
            {"name": "LoginService", "type": "class", "file": "auth/login.py", "line": 1, "references": 0},
            {"name": "SessionManager", "type": "class", "file": "auth/session.py", "line": 1, "references": 0},
        ]
        output = repo_map.generate_l1(".", module, symbols, 2, "abc123")
        self.assertIn("auth/login.py", output)
        self.assertIn("auth/session.py", output)


class TestGetChangedFiles(unittest.TestCase):
    """Test git diff integration for changed files."""

    @patch("subprocess.run")
    def test_returns_none_without_last_commit(self, mock_run):
        result = repo_map.get_changed_files(".", "")
        self.assertIsNone(result)
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_collects_from_multiple_git_commands(self, mock_run):
        # Simulate different git commands returning different files
        def side_effect(cmd, **kwargs):
            stdout_map = {
                "diff": "src/app.py\n",
                "ls-files": "src/new.py\n",
            }
            # Match based on first distinctive arg
            for key, val in stdout_map.items():
                if key in cmd:
                    return type("R", (), {"returncode": 0, "stdout": val})()
            return type("R", (), {"returncode": 0, "stdout": ""})()

        mock_run.side_effect = side_effect
        files = repo_map.get_changed_files(".", "abc123")
        self.assertIsNotNone(files)
        # Should contain files from different commands
        self.assertTrue(len(files) > 0)

    @patch("subprocess.run")
    def test_returns_none_on_git_failure(self, mock_run):
        mock_run.side_effect = FileNotFoundError("git not found")
        result = repo_map.get_changed_files(".", "abc123")
        self.assertIsNone(result)


class TestStateManagement(unittest.TestCase):
    """Test state save/load."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_load_state_returns_empty_when_no_file(self):
        state = repo_map.load_state(self.tmpdir)
        self.assertEqual(state, {})

    def test_save_and_load_roundtrip(self):
        state = {"last_commit": "abc123", "module_symbols": {"auth": []}}
        repo_map.save_state(self.tmpdir, state)
        loaded = repo_map.load_state(self.tmpdir)
        self.assertEqual(loaded["last_commit"], "abc123")

    def test_load_config_returns_defaults(self):
        config = repo_map.load_config(self.tmpdir)
        self.assertTrue(config["auto_detect"])
        self.assertEqual(config["modules"], {})


class TestFlatMarkdownFormat(unittest.TestCase):
    """Test legacy flat markdown output."""

    def test_format_includes_header(self):
        data = {
            "total_files": 2,
            "total_symbols": 3,
            "symbols": [
                {"name": "App", "type": "class", "file": "app.py", "line": 1, "references": 5},
                {"name": "run", "type": "method", "file": "app.py", "line": 2, "references": 0},
            ],
        }
        output = repo_map.format_flat_markdown(data)
        self.assertIn("# Repo Map", output)
        self.assertIn("Files: 2", output)
        self.assertIn("App", output)


class TestDetectPrimaryLanguage(unittest.TestCase):
    """Test language detection from symbols."""

    def test_python_detected(self):
        symbols = [
            {"name": "App", "file": "app.py"},
            {"name": "run", "file": "utils.py"},
        ]
        lang = repo_map.detect_primary_language(symbols)
        self.assertEqual(lang, "Python")

    def test_empty_symbols_returns_dash(self):
        self.assertEqual(repo_map.detect_primary_language([]), "-")


if __name__ == "__main__":
    unittest.main()
