# Repository Guidelines

## Scope
- These rules apply to the entire repository unless a deeper `AGENTS.md` overrides them.

## Core workflow
- Treat documentation as part of the feature, fix, refactor, installer change, test change, and release work.
- Update `README.md`, `CHANGELOG.md`, and `docs/context.md` in the same iteration as the code change when they are affected.
- Keep commits small and regular. Do not defer documentation alignment to a later pass.
- If a change truly needs no user-facing documentation update, record the rationale in `docs/context.md` and use the commit marker `[docs-skip: REASON]`.

## Documentation quality
- Optimize Markdown for GitHub rendering first while keeping raw Markdown readable.
- Put the most important information near the top: what the project is, why it exists, key features, install path, and quickstart.
- Use clear headings, fenced code blocks, short bullets, and compact tables when they improve scanability.
- Keep examples copy-pasteable and keep warnings or prerequisites visually prominent.
- Write docs for both humans and machine readers: explicit headings, stable terminology, and concise descriptions.

## Contribution guardrails
- Do not remove or weaken the doc-sync hooks or CI checks without replacing them with equivalent enforcement.
- Keep install paths relocatable and user-space by default.
- Keep generated user files under `~/.local` and `~/.config` by default.
