from __future__ import annotations

import json
import os
import pty
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


class WizardTests(unittest.TestCase):
    def run_cli(self, *args: str, env: dict[str, str], input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(REPO_ROOT / "codex_config_manager.py"), *args],
            env=env,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_cli_pty(self, *args: str, env: dict[str, str], input_text: str) -> tuple[int, str]:
        master_fd, slave_fd = pty.openpty()
        process = None
        try:
            process = subprocess.Popen(
                ["python3", str(REPO_ROOT / "codex_config_manager.py"), *args],
                env=env,
                stdin=slave_fd,
                stdout=slave_fd,
                stderr=slave_fd,
                close_fds=True,
            )
            os.close(slave_fd)
            slave_fd = -1
            os.write(master_fd, input_text.encode())
            try:
                os.write(master_fd, b"")
            except OSError:
                pass
            output_chunks: list[bytes] = []
            returncode = process.wait(timeout=10)
            return returncode, ""
        finally:
            if process is not None and process.poll() is None:
                process.kill()
            if master_fd != -1:
                os.close(master_fd)
            if slave_fd != -1:
                os.close(slave_fd)

    def test_no_arg_non_tty_prints_help(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            result = self.run_cli(env=env)
            self.assertEqual(result.returncode, 2)
            self.assertIn("usage:", result.stderr)
            self.assertIn("no subcommand provided", result.stderr)

    def test_wizard_creates_provider_and_keeps_raw_key_out_of_file(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            user_input = "".join(
                [
                    "1\n",
                    "Demo Provider\n",
                    "\n",
                    "https://example.invalid/v1\n",
                    "\n",
                    "DEMO_API_KEY\n",
                    "DEMO_API_KEY\n",
                    "y\n",
                    "super-secret-token\n",
                    "a\n",
                    "fast\n",
                    "openai/gpt-4o-mini\n",
                    "a\n",
                    "smart\n",
                    "anthropic/claude-3.5-sonnet\n",
                    "d\n",
                    "1\n",
                    "y\n",
                    "y\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            code, output = result.returncode, result.stdout
            self.assertEqual(code, 0)
            self.assertIn("Identity", output)
            self.assertIn("Confirmation: Nothing is written until you confirm save.", output)
            self.assertIn("Profiles", output)
            self.assertIn("Copy-ready shell export", output)
            self.assertIn("Ready to save", output)
            self.assertIn("Secret export: Ready", output)
            self.assertIn("Saved", output)
            self.assertIn("export DEMO_API_KEY='super-secret-token'", output)
            self.assertIn("Saved provider 'demo-provider'", output)
            provider_file = Path(home) / ".config/codex-config-manager/providers/demo-provider.json"
            state_file = Path(home) / ".config/codex-config-manager/state.json"
            provider = json.loads(provider_file.read_text())
            state = json.loads(state_file.read_text())
            self.assertEqual(provider["provider_id"], "demo-provider")
            self.assertEqual(provider["default_profile"], "fast")
            self.assertEqual(state["default_provider"], "demo-provider")
            self.assertNotIn("super-secret-token", provider_file.read_text())
            self.assertNotIn("Enter API key: super-secret-token", output)
            self.assertIn("Enter a human-friendly provider name first.", output)
            self.assertIn("Controls: [Esc] Back one step  [Ctrl+C] Exit without saving", output)
            self.assertIn("Enter API key:", output)
            self.assertIn("Dashboard", output)
            self.assertIn("managed_providers: 0", output)
            self.assertIn("default_provider: None", output)
            self.assertIn("Responses API is the newer default for most providers.", output)
            self.assertIn("Chat Completions API is mainly for providers that expect the older chat-style request format.", output)
            self.assertIn("Responses API - recommended for most modern providers", output)
            self.assertIn("Profile count: 0", output)
            self.assertIn("1. Add profile", output)

    def test_wizard_edits_existing_provider(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            seed = self.run_cli(
                "apply",
                "--provider-id",
                "seed-provider",
                "--provider-name",
                "Seed Provider",
                "--base-url",
                "https://seed.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "SEED_API_KEY",
                "--profile",
                "seed-fast=openai/gpt-4o-mini",
                "--default-profile",
                "seed-fast",
                "--prompt-api-key",
                "SEED_API_KEY",
                env=env,
            )
            self.assertEqual(seed.returncode, 0, seed.stderr)
            user_input = "".join(
                [
                    "2\n",
                    "1\n",
                    "Renamed Provider\n",
                    "\n",
                    "2\n",
                    "\n",
                    "2\n",
                    "\n",
                    "\n",
                    "n\n",
                    "e\n",
                    "1\n",
                    "seed-fast\n",
                    "openai/gpt-4.1-mini\n",
                    "a\n",
                    "seed-smart\n",
                    "anthropic/claude-3.5-sonnet\n",
                    "d\n",
                    "2\n",
                    "n\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            code, output = result.returncode, result.stdout
            self.assertEqual(code, 0, result.stderr)
            self.assertIn("Provider ID change detected", output)
            self.assertIn("Saved provider 'renamed-provider'", output)
            provider_file = Path(home) / ".config/codex-config-manager/providers/renamed-provider.json"
            provider = json.loads(provider_file.read_text())
            self.assertEqual(provider["provider_name"], "Renamed Provider")
            self.assertEqual(provider["wire_api"], "chat")
            self.assertEqual(provider["default_profile"], "seed-smart")
            self.assertEqual(provider["profiles"]["seed-fast"], "openai/gpt-4.1-mini")
            self.assertEqual(provider["profiles"]["seed-smart"], "anthropic/claude-3.5-sonnet")
            self.assertFalse((Path(home) / ".config/codex-config-manager/providers/seed-provider.json").exists())
            state = json.loads((Path(home) / ".config/codex-config-manager/state.json").read_text())
            self.assertIsNone(state["default_provider"])


    def test_wizard_keeps_current_provider_id_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            seed = self.run_cli(
                "apply",
                "--provider-id",
                "seed-provider",
                "--provider-name",
                "Seed Provider",
                "--base-url",
                "https://seed.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "SEED_API_KEY",
                "--profile",
                "seed-fast=openai/gpt-4o-mini",
                "--default-profile",
                "seed-fast",
                "--prompt-api-key",
                "SEED_API_KEY",
                env=env,
            )
            self.assertEqual(seed.returncode, 0, seed.stderr)
            user_input = "".join(
                [
                    "2\n",
                    "1\n",
                    "Renamed Provider\n",
                    "\n",
                    "\n",
                    "\n",
                    "\n",
                    "\n",
                    "\n",
                    "n\n",
                    "d\n",
                    "1\n",
                    "n\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Provider ID change detected", result.stdout)
            self.assertIn("Saved provider 'seed-provider'", result.stdout)
            provider_file = Path(home) / ".config/codex-config-manager/providers/seed-provider.json"
            provider = json.loads(provider_file.read_text())
            self.assertEqual(provider["provider_name"], "Renamed Provider")

    def test_wizard_can_copy_provider_when_id_changes(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            seed = self.run_cli(
                "apply",
                "--provider-id",
                "seed-provider",
                "--provider-name",
                "Seed Provider",
                "--base-url",
                "https://seed.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "SEED_API_KEY",
                "--profile",
                "seed-fast=openai/gpt-4o-mini",
                "--default-profile",
                "seed-fast",
                "--prompt-api-key",
                "SEED_API_KEY",
                env=env,
            )
            self.assertEqual(seed.returncode, 0, seed.stderr)
            user_input = "".join(
                [
                    "2\n",
                    "1\n",
                    "Copy Provider\n",
                    "\n",
                    "3\n",
                    "\n",
                    "\n",
                    "\n",
                    "\n",
                    "n\n",
                    "d\n",
                    "1\n",
                    "n\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Provider ID change detected", result.stdout)
            self.assertTrue((Path(home) / ".config/codex-config-manager/providers/seed-provider.json").exists())
            copy_file = Path(home) / ".config/codex-config-manager/providers/copy-provider.json"
            self.assertTrue(copy_file.exists())
            copied = json.loads(copy_file.read_text())
            self.assertEqual(copied["provider_name"], "Copy Provider")


    def test_wizard_doctor_view_groups_output(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            user_input = "".join(["4\n", "\n", "5\n"])
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Summary", result.stdout)
            self.assertIn("Managed providers", result.stdout)
            self.assertIn("Paths", result.stdout)
            self.assertIn("State", result.stdout)

    def test_wizard_delete_provider_prunes_state(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            seed = self.run_cli(
                "apply",
                "--provider-id",
                "delete-me",
                "--provider-name",
                "Delete Me",
                "--base-url",
                "https://delete.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "DELETE_API_KEY",
                "--profile",
                "delete-fast=openai/gpt-4o-mini",
                "--default-profile",
                "delete-fast",
                "--prompt-api-key",
                "DELETE_API_KEY",
                env=env,
            )
            self.assertEqual(seed.returncode, 0, seed.stderr)
            user_input = "".join(["3\n", "1\n", "y\n", "\n", "5\n"])
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            code, output = result.returncode, result.stdout
            self.assertEqual(code, 0)
            self.assertIn("Ready to remove", output)
            self.assertIn("What changes", output)
            self.assertIn("Removed", output)
            self.assertIn("Removed provider 'delete-me' from managed state", output)
            config_home = Path(home) / ".config/codex-config-manager"
            self.assertFalse(config_home.exists())

    def test_wizard_cancel_review_makes_no_changes(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            user_input = "".join(
                [
                    "1\n",
                    "Cancel Provider\n",
                    "\n",
                    "https://cancel.invalid/v1\n",
                    "\n",
                    "CANCEL_API_KEY\n",
                    "CANCEL_API_KEY\n",
                    "n\n",
                    "a\n",
                    "draft\n",
                    "openai/gpt-4o-mini\n",
                    "d\n",
                    "1\n",
                    "y\n",
                    "n\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Cancelled without saving.", result.stdout + result.stderr)
            config_home = Path(home) / ".config/codex-config-manager"
            self.assertFalse(config_home.exists())


    def test_wizard_back_out_of_profiles_submenu(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            user_input = "".join(
                [
                    "1\n",
                    "Back Provider\n",
                    "\n",
                    "https://back.invalid/v1\n",
                    "\n",
                    "BACK_API_KEY\n",
                    "BACK_API_KEY\n",
                    "n\n",
                    "\x1b\n",
                    "BACK_API_KEY\n",
                    "BACK_API_KEY\n",
                    "n\n",
                    "a\n",
                    "draft\n",
                    "openai/gpt-4o-mini\n",
                    "d\n",
                    "1\n",
                    "y\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertGreaterEqual(result.stdout.count("Step 3 of 5: Authentication"), 2)
            self.assertGreaterEqual(result.stdout.count("Step 4 of 5: Profiles"), 2)
            provider_file = Path(home) / ".config/codex-config-manager/providers/back-provider.json"
            provider = json.loads(provider_file.read_text())
            self.assertEqual(provider["env_key"], "BACK_API_KEY")
            self.assertEqual(provider["profiles"]["draft"], "openai/gpt-4o-mini")


    def test_apply_rejects_invalid_provider_id(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            result = self.run_cli(
                "apply",
                "--provider-id",
                "Bad Id",
                "--provider-name",
                "Bad Id",
                "--base-url",
                "https://example.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "BAD_KEY",
                "--profile",
                "fast=openai/gpt-4o-mini",
                "--default-profile",
                "fast",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("provider_id must use lowercase letters", result.stderr)

    def test_apply_rejects_invalid_base_url(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            result = self.run_cli(
                "apply",
                "--provider-id",
                "bad-url",
                "--provider-name",
                "Bad Url",
                "--base-url",
                "not-a-url",
                "--wire-api",
                "responses",
                "--env-key",
                "BAD_URL_KEY",
                "--profile",
                "fast=openai/gpt-4o-mini",
                "--default-profile",
                "fast",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("base_url must be a full http:// or https:// URL", result.stderr)

    def test_apply_rejects_invalid_env_var_name(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            result = self.run_cli(
                "apply",
                "--provider-id",
                "bad-env",
                "--provider-name",
                "Bad Env",
                "--base-url",
                "https://example.invalid/v1",
                "--wire-api",
                "responses",
                "--env-key",
                "bad-key",
                "--profile",
                "fast=openai/gpt-4o-mini",
                "--default-profile",
                "fast",
                env=env,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("env_key must be a shell-style uppercase variable name", result.stderr)

    def test_wizard_uppercases_env_var_names_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env.update({"HOME": home, "PATH": os.environ["PATH"]})
            user_input = "".join(
                [
                    "1\n",
                    "Case Provider\n",
                    "\n",
                    "https://case.invalid/v1\n",
                    "\n",
                    "mixed_case_key\n",
                    "promptKeyValue\n",
                    "n\n",
                    "1\n",
                    "fast\n",
                    "openai/gpt-4o-mini\n",
                    "4\n",
                    "1\n",
                    "y\n",
                    "y\n",
                    "\n",
                    "5\n",
                ]
            )
            result = self.run_cli("wizard", "--allow-non-tty", env=env, input_text=user_input)
            self.assertEqual(result.returncode, 0, result.stderr)
            provider_file = Path(home) / ".config/codex-config-manager/providers/case-provider.json"
            provider = json.loads(provider_file.read_text())
            self.assertEqual(provider["env_key"], "MIXED_CASE_KEY")
            self.assertEqual(provider["prompt_api_key"], "PROMPTKEYVALUE")



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
