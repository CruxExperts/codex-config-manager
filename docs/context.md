# Context Log

## 2026-04-25

- Added an interactive no-arg wizard as the primary onboarding path while preserving explicit scripted subcommands for automation.
- Chose a stdlib-only terminal wizard instead of a dependency-backed full-screen TUI so install and release packaging remain simple.
- Kept provider-first editing with prefilled values, chunked profile management, review-before-save, and explicit destructive confirmations.
- Added masked API-key entry and copy-ready export snippets, but intentionally do not persist raw secrets in managed provider JSON.
- Refactored shared provider validation and persistence so interactive and non-interactive flows stay consistent.
- Expanded tests to cover no-arg behavior, wizard create/edit/delete/cancel flows, and secret-handling guarantees.
- Refined wizard control hints so navigation appears as a dedicated screen-level controls line instead of being mixed into field prompts, and fixed the warning shown when editing the current default provider and choosing not to keep it as default.
- Added more stateful wizard context by surfacing provider counts and current default status in the main menu and provider picker, and made wire API selection read like user-facing guidance instead of internal field names.
- Shifted the profile submenu from command-heavy text entry toward a guided numbered-action editor so the busiest part of the wizard feels more like a familiar terminal setup flow while retaining legacy shortcuts for compatibility.
- Improved the final review screen to summarize save readiness, defaults, and export-snippet status before commit so the wizard closes with a stronger sense of confirmation and outcome.
- Added a more deliberate destructive-action flow for provider removal so users see what will be deleted, whether the default setting is affected, and what changed after confirmation.
- Continued converging the main menu and diagnostics view toward the same summary-first layout so the wizard feels like one cohesive terminal application rather than a set of unrelated prompts.
- Standardized headings and action/result wording across the wizard so save, cancel, remove, and diagnostics states all communicate in the same concise style.

## 2026-04-24

- Initialized the repository as a Git project with documentation-first contribution rules.
- Added a user-space installation flow under `~/.local` with a shim command named `codex-config-manager`.
- Added `apply`, `doctor`, and `uninstall` CLI subcommands to provide a usable baseline workflow.
- Added hook and CI enforcement so code changes require synchronized documentation updates.
- Set the Markdown quality bar to GitHub-first, high-structure, and easy for both humans and agents to parse.
- Tightened the installer to support raw bootstrap downloads, custom prefix PATH hooks, and idempotent managed shell block handling.
- Expanded validation to cover installer edge cases, docs-sync checks, release packaging, and release-ready hygiene like ignored build artifacts.
- Configured public GitHub install documentation and raw bootstrap defaults for `CruxExperts/codex-config-manager`.
- Pruned empty managed config state after the last provider uninstall so production usage leaves no stale state.json or empty provider directories.
- Replaced the example provider configuration with a public-safe OpenRouter demo so published docs do not expose a real private endpoint or credential naming.
- Performed a full documentation refresh so the README now describes the current wizard flow end to end instead of only accumulating incremental notes from each UX pass.
- Adjusted environment variable entry to normalize user input to uppercase automatically because forcing a retry for lowercase or mixed-case names was unnecessary friction in the wizard.
- Added a plain-English explanation for the Responses-versus-Chat choice directly in the wizard because users should not have to know provider wire-format history to make the right selection.

