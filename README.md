# codex-config-manager

A user-space utility for installing and managing Codex provider configuration with a safe, relocatable workflow built for GitHub distribution.

## Why This Exists

`codex-config-manager` exists to make provider setup repeatable, reviewable, and easy to operate on laptops, servers, and CI without requiring `pip`, root access, or hand-edited scattered config.

## Features

- ✨ User-space install under `~/.local` by default
- 🔒 No `sudo`, no `pip`, and no root-owned files required
- 🧭 Managed provider `apply`, `doctor`, and `uninstall` commands
- 📦 GitHub-friendly install flows for clone, raw installer, and release tarballs
- 🔁 Idempotent installer and uninstaller with managed shell PATH blocks
- 📝 Documentation-first workflow with hooks and CI that keep docs aligned with code
- 🤖 Clear Markdown structure for both humans and search/agent readers

## Installation

### Option A: clone and install

Clone this GitHub repository, then run:

```sh
./install.sh
```

Then:

```sh
codex-config-manager --help
```

### Option B: one-line installer from GitHub raw URL

```sh
curl -fsSL https://raw.githubusercontent.com/CruxExperts/codex-config-manager/main/install.sh | sh
```

Security tradeoff: piping a remote script directly to `sh` is convenient but reduces review. For production or server use, review the installer first:

```sh
curl -fsSL https://raw.githubusercontent.com/CruxExperts/codex-config-manager/main/install.sh -o install.sh
less install.sh
sh install.sh
```

### Option C: direct Python usage without installation

```sh
python3 codex_config_manager.py --help
```

### Release tarball install

```sh
tar -xzf codex-config-manager_VERSION.tar.gz
cd codex-config-manager_VERSION
./install.sh
```

## Quickstart

Apply from the bundled example:

```sh
codex-config-manager apply --file examples/openrouter.codex-provider.yaml
```

Apply from explicit flags:

```sh
codex-config-manager apply \
  --provider-id openrouter-demo \
  --provider-name "OpenRouter Demo" \
  --base-url https://openrouter.ai/api/v1 \
  --wire-api responses \
  --env-key OPENROUTER_API_KEY \
  --profile openrouter-gpt4o-mini=openai/gpt-4o-mini \
  --profile openrouter-claude-sonnet=anthropic/claude-3.5-sonnet \
  --default-profile openrouter-gpt4o-mini \
  --prompt-api-key OPENROUTER_API_KEY \
  --yes
```

Check the managed user scope:

```sh
codex-config-manager doctor --scope user
```

## Commands

| Command | Purpose |
| --- | --- |
| `apply` | Create or update a managed provider record in user config space |
| `doctor` | Print user-scope diagnostics for managed state |
| `uninstall` | Remove a managed provider record by provider id |

## Install Layout

- Command shim: `~/.local/bin/codex-config-manager`
- Installed script: `~/.local/share/codex-config-manager/codex_config_manager.py`
- Bundled examples: `~/.local/share/codex-config-manager/examples`
- Managed config: `~/.config/codex-config-manager`

If you install with `--prefix`, the installer keeps the same relative layout under that prefix and writes the shell PATH hook for that prefix’s `bin/` directory.

## Shell Integration

When needed, the installer adds one managed PATH block to the current shell startup file and never duplicates it.

For `bash`, `zsh`, and `~/.profile` fallback:

```sh
# BEGIN managed by codex-config-manager installer
export PATH="$HOME/.local/bin:$PATH"
# END managed by codex-config-manager installer
```

For `fish`:

```fish
# BEGIN managed by codex-config-manager installer
fish_add_path "$HOME/.local/bin"
# END managed by codex-config-manager installer
```

If you use a custom `--prefix`, the block uses that prefix’s `bin` path instead.

## Documentation Workflow

This repo keeps code and docs aligned on every iteration.

```sh
git config core.hooksPath .githooks
```

Commits that change code, scripts, workflow, tests, or examples must also stage updates to `README.md`, `CHANGELOG.md`, or `docs/context.md`, unless the commit message includes `[docs-skip: REASON]` and the rationale is recorded in `docs/context.md`.

## Release Packaging

Build a release tarball containing the installable files:

```sh
./scripts/package_release.sh 0.1.0
```

The release archive contains:

- `codex_config_manager.py`
- `install.sh`
- `uninstall.sh`
- `README.md`
- `examples/`

## Notes

- The installer checks for `python3` and requires Python `3.10+`.
- The installer is idempotent and safe to rerun.
- The installer writes only under the selected prefix and your shell rc file when a PATH hook is needed.
- The CLI removes empty managed state files and directories after the last managed provider is uninstalled.
- The uninstaller does not remove managed Codex provider config by default.
