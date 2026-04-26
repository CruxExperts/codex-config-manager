# Changelog

## Unreleased

### Interactive wizard

- Added an interactive no-arg terminal wizard with explicit `wizard` subcommand support.
- Added a provider-name-first flow with slugified provider ID suggestions.
- Added explicit keep, rename, and copy handling when an edited provider ID changes.
- Added guided wire API selection with readable recommended labels.
- Added a short plain-English explanation before the wire API choice so users can understand the functional difference without leaving the wizard.
- Added a guided profile editor with numbered actions, pickers, profile counts, and delete confirmation while keeping legacy shortcuts working.

### Safety and secrets

- Added masked API-key entry when running on a real interactive terminal.
- Added copy-ready shell export snippets while keeping raw secrets out of managed provider JSON.
- Added stronger review, remove, and default-provider warnings so destructive or state-changing actions are more explicit.
- Normalized environment variable names to uppercase during wizard entry and shared provider normalization so users are not forced to retype lowercase or mixed-case input.

### Dashboard UX

- Added a dashboard-style main menu with managed provider count and current default provider.
- Added a ready-to-save review screen with grouped sections and checklist-style summary.
- Added a ready-to-remove summary with an explicit impact list before deletion.
- Added a richer doctor view with summary, paths, state, and managed-provider list.
- Unified wizard wording across menus, review, diagnostics, save, and remove flows so the terminal experience reads with one consistent voice.

### Shared validation and persistence

- Refactored provider persistence so scripted `apply` and interactive wizard flows share validation and state-writing behavior.
- Added validation for provider IDs, URLs, environment variable names, profile presence, and default-profile correctness.
- Kept scripted `apply`, `doctor`, and `uninstall` behavior intact for automation.

### Installer, packaging, and docs

- Bootstrapped the repository with a user-space installer, uninstaller, CLI entrypoint, Git hooks, CI checks, release packaging, tests, and public-facing documentation.
- Added raw-installer bootstrap support for downloading the main script and example files when project files are not present locally.
- Added managed shell PATH blocks for `bash`, `zsh`, `fish`, and `~/.profile` fallback with custom-prefix awareness and idempotent behavior.
- Added broader installer and hook behavior coverage, including custom prefixes, shell hook removal, raw bootstrap installs, and docs-sync validation.
- Configured public GitHub install documentation and raw bootstrap defaults for `CruxExperts/codex-config-manager`.
- Removed empty managed state files and directories after the last provider uninstall for cleaner production behavior.
- Replaced real-world example endpoint and provider identifiers with safe public OpenRouter demo values.
