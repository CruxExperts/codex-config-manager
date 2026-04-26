# codex-config-manager

A user-space utility for installing and managing Codex provider configuration with a safe, relocatable workflow built for GitHub distribution.

## Why This Exists

`codex-config-manager` exists to make provider setup repeatable, reviewable, and easy to operate on laptops, servers, and CI without requiring `pip`, root access, or hand-edited scattered config.

It supports two complementary ways of working:

- an interactive wizard for guided setup, editing, diagnostics, and removal
- scriptable subcommands for repeatable automation and repository-driven workflows

## Features

- ✨ User-space install under `~/.local` by default
- 🧭 Interactive no-arg configuration wizard for create, edit, remove, and diagnostics
- 🔒 Masked API-key entry with copy-ready shell export snippets and no raw secret persistence in managed config
- 🧩 Scriptable `apply`, `wizard`, `doctor`, and `uninstall` commands for repeatable automation
- 📋 Summary-first terminal UX with dashboard-style menu, review, remove, and diagnostics screens
- 🔁 Idempotent installer and uninstaller with managed shell PATH blocks
- 📦 GitHub-friendly install flows for clone, raw installer, and release tarballs
- 📝 Documentation-first workflow with hooks and CI that keep docs aligned with code

## Installation

### Option A: clone and install

Clone this repository, then run:

```sh
./install.sh
```

Then launch the wizard:

```sh
codex-config-manager
```

### Option B: one-line installer from GitHub raw URL

```sh
curl -fsSL https://raw.githubusercontent.com/CruxExperts/codex-config-manager/main/install.sh | sh
```

Security tradeoff: piping a remote script directly to `sh` is convenient but reduces review. For server or production use, review the installer first:

```sh
curl -fsSL https://raw.githubusercontent.com/CruxExperts/codex-config-manager/main/install.sh -o install.sh
less install.sh
sh install.sh
```

### Option C: run directly without installation

From the repository root:

```sh
python3 codex_config_manager.py
```

Or launch the interactive flow explicitly:

```sh
python3 codex_config_manager.py wizard
```

### Release tarball install

```sh
tar -xzf codex-config-manager_VERSION.tar.gz
cd codex-config-manager_VERSION
./install.sh
```

## Quickstart

### Interactive workflow

Run `codex-config-manager` with no parameters to open the wizard:

```sh
codex-config-manager
```

The current wizard supports:

- creating a provider from scratch with a provider-name-first flow
- auto-suggesting a slugified provider ID from the provider name
- editing existing providers with current values prefilled
- handling provider ID changes explicitly with keep, rename, or copy behavior
- guiding wire API selection with readable labels and defaults
- capturing API keys with masked terminal input when a real TTY is available
- storing only environment variable references in managed provider JSON, automatically uppercasing them during wizard entry
- generating a copy-ready `export` snippet without persisting the raw secret
- managing profiles in a guided list editor with numbered actions, pickers, and removal confirmation
- reviewing a ready-to-save dashboard before writing anything
- reviewing a ready-to-remove summary and impact list before deletion
- checking current managed state from a doctor screen with summary, paths, and provider list

### Scripted workflow

Apply the bundled example:

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

Inspect current managed state:

```sh
codex-config-manager doctor --scope user
```

Remove a provider by ID:

```sh
codex-config-manager uninstall --provider-id openrouter-demo --yes
```

## Commands

| Command | Purpose |
| --- | --- |
| `wizard` | Launch the interactive configuration wizard explicitly |
| `apply` | Create or update a managed provider record in user config space |
| `doctor` | Print user-scope diagnostics for managed state, paths, and provider list |
| `uninstall` | Remove a managed provider record by provider id |

## Wizard Walkthrough

The interactive wizard follows a provider-first sequence:

1. Provider identity
2. Connection details
3. Authentication references and optional masked key capture
4. Guided profile add, edit, and remove management
5. Default profile and managed-default selection
6. Ready-to-save review and save confirmation

### Navigation

- `Esc` then Enter backs up one step when backtracking is available.
- `Ctrl+C` exits safely before save.
- Selection screens accept numbered choices.
- When a default option exists, pressing Enter accepts it.

### Identity step

The wizard asks for provider name first, then suggests a compatible provider ID.

Example:

- provider name: `OpenRouter Demo`
- suggested provider ID: `openrouter-demo`

If you are editing an existing provider and change the provider ID, the wizard offers three explicit choices:

- keep the current provider ID
- rename the existing provider to the new ID
- create a copy with the new ID and keep the current provider

### Connection step

The wizard validates the base URL and explains the wire API choice in plain English before presenting user-facing labels:

- `Responses API` is the newer default and is usually the right choice for modern providers.
- `Chat Completions API` is mainly for providers that still expect the older chat-style request format.

The selection list then presents:

- `Responses API - recommended for most modern providers`
- `Chat Completions API - use when the provider expects chat-compatible payloads`

### Authentication step

The wizard stores references such as `OPENROUTER_API_KEY`, not raw API keys, in managed provider JSON. If the user types lowercase or mixed case variable names, the wizard normalizes them to uppercase automatically.

If you ask it to generate an export snippet, it can capture the real key during the wizard and print a copy-ready command such as:

```sh
export OPENROUTER_API_KEY='your-real-key'
```

Behavior details:

- secret typing is masked on an interactive terminal
- raw secrets are not written into the managed provider JSON file
- non-interactive test or pipe-based input cannot be masked by the terminal

### Profiles step

Profiles are managed through a guided editor with a persistent list and profile count.

Supported actions:

- add profile
- edit profile
- remove profile
- done

Legacy commands still work for compatibility:

- `add`
- `edit <number>`
- `remove <number>`
- `done`

### Defaults step

The wizard asks for:

- the default profile within the provider
- whether the provider should become the managed default provider

If you are editing the current managed default provider and choose not to keep it as default, the wizard warns that the managed default setting will be cleared.

### Review and save step

Before saving, the wizard shows:

- a ready-to-save summary
- risk checks when something deserves extra attention
- grouped identity, connection, authentication, defaults, and profiles sections
- the copy-ready export snippet, when requested

Nothing is written until you confirm save.

### Remove flow

The remove flow is intentionally more deliberate than a single yes/no prompt.

Before deletion it shows:

- a ready-to-remove summary
- the number of profiles affected
- whether the provider is currently the managed default provider
- a “What changes” section listing the removal impact

If the provider is the managed default, the wizard explicitly warns that the default setting will be cleared.

### Diagnostics flow

The doctor view presents:

- a summary block with provider count, default provider, and state presence
- managed config paths
- the current managed provider list
- raw state booleans for quick troubleshooting

## Managed Files

By default the project writes only to user-space locations:

| Path | Purpose |
| --- | --- |
| `~/.local/bin/codex-config-manager` | command shim |
| `~/.local/share/codex-config-manager/codex_config_manager.py` | installed script |
| `~/.local/share/codex-config-manager/examples` | bundled examples |
| `~/.config/codex-config-manager/providers/*.json` | managed provider records |
| `~/.config/codex-config-manager/state.json` | managed state index |

If you install with `--prefix`, the installer keeps the same relative layout under that prefix and writes the PATH hook for that prefix's `bin/` directory when needed.

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

## Documentation Workflow

This repository keeps code and docs aligned in the same iteration.

Enable the repository hooks:

```sh
git config core.hooksPath .githooks
```

Commits that change code, scripts, workflows, tests, or examples must also stage updates to at least one of:

- `README.md`
- `CHANGELOG.md`
- `docs/context.md`

If a change truly needs no user-facing documentation update, record the reason in `docs/context.md` and use the commit marker `[docs-skip: REASON]`.

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
- The standalone uninstaller does not remove managed provider config by default.
- The interactive wizard auto-launches only when a real TTY is available; otherwise use explicit subcommands.
