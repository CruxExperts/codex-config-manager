from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class InstallTests(unittest.TestCase):
    def run_cmd(self, *args: str, cwd: Path | None = None, env: dict[str, str] | None = None, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            list(args),
            cwd=cwd or REPO_ROOT,
            env=merged_env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_install_creates_shim_and_runs_help(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": os.environ["PATH"]}
            result = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            shim = Path(home) / ".local/bin/codex-config-manager"
            script = Path(home) / ".local/share/codex-config-manager/codex_config_manager.py"
            self.assertTrue(shim.exists())
            self.assertTrue(os.access(shim, os.X_OK))
            self.assertTrue(script.exists())
            help_result = subprocess.run([str(shim), "doctor", "--scope", "user"], text=True, capture_output=True, check=False)
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("scope=user", help_result.stdout)

    def test_apply_from_example_file_needs_only_python(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": os.environ["PATH"]}
            install = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(install.returncode, 0, install.stderr)
            shim = Path(home) / ".local/bin/codex-config-manager"
            example = Path(home) / ".local/share/codex-config-manager/examples/openrouter.codex-provider.yaml"
            apply_result = subprocess.run([str(shim), "apply", "--file", str(example)], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            self.assertIn("Applied provider 'openrouter-demo'", apply_result.stdout)

    def test_install_is_idempotent_and_hook_not_duplicated(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": os.environ["PATH"]}
            first = self.run_cmd("sh", "install.sh", "--yes", env=env)
            second = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(second.returncode, 0, second.stderr)
            bashrc = Path(home) / ".bashrc"
            text = bashrc.read_text()
            self.assertEqual(text.count("# BEGIN managed by codex-config-manager installer"), 1)
            self.assertEqual(text.count(f'export PATH="{home}/.local/bin:$PATH"'), 1)

    def test_install_skips_shell_hook_when_bin_already_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            path = f"{home}/.local/bin:{os.environ['PATH']}"
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": path}
            result = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            bashrc = Path(home) / ".bashrc"
            self.assertFalse(bashrc.exists())
            self.assertIn("already on PATH; skipping shell hook", result.stdout)

    def test_install_supports_custom_prefix_and_command_name(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            prefix = Path(home) / "custom-prefix"
            env = {"HOME": home, "SHELL": "/bin/zsh", "PATH": os.environ["PATH"]}
            result = self.run_cmd("sh", "install.sh", "--yes", "--prefix", str(prefix), "--command-name", "ccm", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            shim = prefix / "bin/ccm"
            self.assertTrue(shim.exists())
            zshrc = Path(home) / ".zshrc"
            self.assertIn(f'export PATH="{prefix}/bin:$PATH"', zshrc.read_text())

    def test_install_supports_fish_hook(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/usr/bin/fish", "PATH": os.environ["PATH"]}
            result = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            config = Path(home) / ".config/fish/config.fish"
            self.assertIn('fish_add_path "' + str(Path(home) / '.local/bin') + '"', config.read_text())

    def test_uninstall_removes_shim_and_hook(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": os.environ["PATH"]}
            install = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(install.returncode, 0, install.stderr)
            uninstall = self.run_cmd("sh", "uninstall.sh", "--yes", env=env)
            self.assertEqual(uninstall.returncode, 0, uninstall.stderr)
            shim = Path(home) / ".local/bin/codex-config-manager"
            bashrc = Path(home) / ".bashrc"
            self.assertFalse(shim.exists())
            self.assertNotIn("# BEGIN managed by codex-config-manager installer", bashrc.read_text())

    def test_provider_uninstall_prunes_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/bash", "PATH": os.environ["PATH"]}
            install = self.run_cmd("sh", "install.sh", "--yes", env=env)
            self.assertEqual(install.returncode, 0, install.stderr)
            shim = Path(home) / ".local/bin/codex-config-manager"
            example = Path(home) / ".local/share/codex-config-manager/examples/openrouter.codex-provider.yaml"
            apply_result = subprocess.run([str(shim), "apply", "--file", str(example)], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(apply_result.returncode, 0, apply_result.stderr)
            uninstall_result = subprocess.run([str(shim), "uninstall", "--provider-id", "openrouter-demo", "--yes"], env=env, text=True, capture_output=True, check=False)
            self.assertEqual(uninstall_result.returncode, 0, uninstall_result.stderr)
            config_home = Path(home) / ".config/codex-config-manager"
            self.assertFalse((config_home / "state.json").exists())
            self.assertFalse((config_home / "providers").exists())
            self.assertFalse(config_home.exists())

    def test_install_does_not_require_sudo(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = {"HOME": home, "SHELL": "/bin/sh", "PATH": os.environ["PATH"]}
            result = self.run_cmd("sh", "install.sh", "--yes", "--no-shell-hook", env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("sudo", result.stdout + result.stderr)

    def test_raw_bootstrap_downloads_files(self) -> None:
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as workspace:
            bootstrap_dir = Path(workspace)
            shutil.copy(REPO_ROOT / "install.sh", bootstrap_dir / "install.sh")
            env = {
                "HOME": home,
                "SHELL": "/bin/sh",
                "PATH": os.environ["PATH"],
                "CODEX_CONFIG_MANAGER_RAW_BASE": (REPO_ROOT.resolve()).as_uri(),
            }
            result = self.run_cmd("sh", "install.sh", "--yes", "--no-shell-hook", cwd=bootstrap_dir, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            script = Path(home) / ".local/share/codex-config-manager/codex_config_manager.py"
            example = Path(home) / ".local/share/codex-config-manager/examples/openrouter.codex-provider.yaml"
            self.assertTrue(script.exists())
            self.assertTrue(example.exists())


class DocsSyncTests(unittest.TestCase):
    def run_cmd(self, *args: str, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(list(args), cwd=cwd, env=merged_env, text=True, capture_output=True, check=False)

    def make_repo(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp())
        subprocess.run(["git", "init"], cwd=temp_dir, check=True, capture_output=True, text=True)
        (temp_dir / "scripts").mkdir()
        (temp_dir / "docs").mkdir()
        shutil.copy(REPO_ROOT / "scripts/check_docs_sync.py", temp_dir / "scripts/check_docs_sync.py")
        (temp_dir / "README.md").write_text((REPO_ROOT / "README.md").read_text())
        (temp_dir / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- Seed entry.\n")
        (temp_dir / "docs/context.md").write_text("# Context Log\n\n## 2026-04-24\n\n- Seed context.\n")
        return temp_dir

    def test_docs_sync_passes_when_docs_are_staged(self) -> None:
        repo = self.make_repo()
        try:
            (repo / "tool.py").write_text("print('ok')\n")
            (repo / "CHANGELOG.md").write_text("# Changelog\n\n## Unreleased\n\n- Updated tool.\n")
            subprocess.run(["git", "add", "tool.py", "CHANGELOG.md", "README.md", "docs/context.md", "scripts/check_docs_sync.py"], cwd=repo, check=True)
            result = self.run_cmd("python3", "scripts/check_docs_sync.py", cwd=repo)
            self.assertEqual(result.returncode, 0, result.stderr)
        finally:
            shutil.rmtree(repo)

    def test_docs_sync_fails_when_code_changes_without_docs(self) -> None:
        repo = self.make_repo()
        try:
            (repo / "tool.py").write_text("print('missing docs')\n")
            subprocess.run(["git", "add", "tool.py"], cwd=repo, check=True)
            result = self.run_cmd("python3", "scripts/check_docs_sync.py", cwd=repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("require updates", result.stderr)
        finally:
            shutil.rmtree(repo)


if __name__ == "__main__":
    unittest.main()
