# Changelog

## Unreleased

- Bootstrapped the repository with a user-space installer, uninstaller, CLI entrypoint, Git hooks, CI checks, release packaging, tests, and public-facing documentation.
- Added raw-installer bootstrap support for downloading the main script and example files when project files are not present locally.
- Added managed shell PATH blocks for `bash`, `zsh`, `fish`, and `~/.profile` fallback with custom-prefix awareness and idempotent behavior.
- Added broader installer and hook behavior coverage, including custom prefixes, shell hook removal, raw bootstrap installs, and docs-sync validation.
- Configured public GitHub install documentation and raw bootstrap defaults for `CruxExperts/codex-config-manager`.
- Removed empty managed state files and directories after the last provider uninstall for cleaner production behavior.
- Replaced real-world example endpoint and provider identifiers with safe public OpenRouter demo values.
