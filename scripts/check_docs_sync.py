#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

DOC_FILES = {"README.md", "CHANGELOG.md", "docs/context.md"}
CODE_EXTENSIONS = {".py", ".sh", ".yml", ".yaml", ".toml", ".json", ".md"}
REQUIRED_README_HEADINGS = [
    "# codex-config-manager",
    "## Why This Exists",
    "## Features",
    "## Installation",
    "## Quickstart",
]


def git(args: list[str]) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def collect_files(mode: str, base_ref: str) -> list[str]:
    if mode == "staged":
        output = git(["diff", "--cached", "--name-only"])
    else:
        output = git(["diff", "--name-only", base_ref, "HEAD"])
    return [line for line in output.splitlines() if line]


def commit_message_has_override() -> bool:
    commit_editmsg = Path(".git/COMMIT_EDITMSG")
    if not commit_editmsg.exists():
        return False
    text = commit_editmsg.read_text()
    return bool(re.search(r"\[docs-skip:\s*[^\]]+\]", text))


def context_contains_override_note() -> bool:
    context_file = Path("docs/context.md")
    if not context_file.exists():
        return False
    text = context_file.read_text()
    return "docs-skip" in text or "no-docs rationale" in text


def readme_quality_ok() -> tuple[bool, str]:
    readme = Path("README.md")
    if not readme.exists():
        return False, "README.md is missing"
    text = readme.read_text()
    for heading in REQUIRED_README_HEADINGS:
        if heading not in text:
            return False, f"README.md is missing required heading: {heading}"
    if text.count("```") % 2 != 0:
        return False, "README.md contains unbalanced fenced code blocks"
    for placeholder in ("TODO", "coming soon"):
        if placeholder in text:
            return False, f"README.md still contains placeholder text: {placeholder}"
    return True, "ok"


def requires_doc_sync(file_name: str) -> bool:
    path = Path(file_name)
    if file_name in DOC_FILES:
        return False
    if file_name.startswith(("docs/", ".github/", ".githooks/", "tests/", "scripts/", "examples/")):
        return True
    return path.suffix in CODE_EXTENSIONS


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate doc-sync policy.")
    parser.add_argument("--mode", choices=["staged", "range"], default="staged")
    parser.add_argument("--base-ref", default="HEAD~1")
    args = parser.parse_args()

    files = collect_files(args.mode, args.base_ref)

    ok, message = readme_quality_ok()
    if not ok:
        print(message, file=sys.stderr)
        return 1

    if not files:
        return 0

    changed_docs = set(files) & DOC_FILES
    changed_code = any(requires_doc_sync(file_name) for file_name in files)

    if changed_code and not changed_docs:
        if args.mode == "staged" and commit_message_has_override() and context_contains_override_note():
            return 0
        print(
            "Code or workflow changes require updates to README.md, CHANGELOG.md, or docs/context.md.\n"
            "Use [docs-skip: REASON] only with a matching rationale recorded in docs/context.md.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
