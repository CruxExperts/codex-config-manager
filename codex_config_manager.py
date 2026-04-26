#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

APP_NAME = "codex-config-manager"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
PROVIDERS_DIR = CONFIG_HOME / "providers"
STATE_FILE = CONFIG_HOME / "state.json"
DEFAULT_STATE = {"default_provider": None, "providers": {}}
REQUIRED_PROVIDER_FIELDS = ("provider_id", "provider_name", "base_url", "wire_api", "env_key")
BACK = "__back__"
ESCAPE = "\x1b"


def ensure_dirs() -> None:
    PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return deepcopy(DEFAULT_STATE)
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_STATE)


def save_state(state: dict[str, Any]) -> None:
    ensure_dirs()
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def prune_empty_managed_dirs() -> None:
    if PROVIDERS_DIR.exists() and not any(PROVIDERS_DIR.iterdir()):
        PROVIDERS_DIR.rmdir()
    if STATE_FILE.exists():
        return
    if CONFIG_HOME.exists() and not any(CONFIG_HOME.iterdir()):
        CONFIG_HOME.rmdir()


def parse_simple_yaml(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_map: dict[str, str] | None = None
    current_key: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  "):
            if current_map is None or current_key is None:
                raise SystemExit(f"unsupported YAML structure: {raw_line!r}")
            stripped = line.strip()
            if ":" not in stripped:
                raise SystemExit(f"invalid YAML line: {raw_line!r}")
            key, value = stripped.split(":", 1)
            current_map[key.strip()] = value.strip()
            continue
        if ":" not in line:
            raise SystemExit(f"invalid YAML line: {raw_line!r}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "":
            current_map = {}
            current_key = key
            result[key] = current_map
        else:
            result[key] = value
            current_map = None
            current_key = None

    return result


def build_provider_record(args: argparse.Namespace) -> dict[str, Any]:
    profiles = {}
    for item in args.profile or []:
        if "=" not in item:
            raise SystemExit(f"invalid --profile value: {item!r}; expected NAME=MODEL")
        name, model = item.split("=", 1)
        profiles[name] = model

    record = {
        "provider_id": args.provider_id,
        "provider_name": args.provider_name,
        "base_url": args.base_url,
        "wire_api": args.wire_api,
        "env_key": args.env_key,
        "profiles": profiles,
        "default_profile": args.default_profile,
        "prompt_api_key": args.prompt_api_key,
    }
    return {key: value for key, value in record.items() if value not in (None, {}, [])}


def provider_path(provider_id: str) -> Path:
    return PROVIDERS_DIR / f"{provider_id}.json"


def slugify_provider_name(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = slug.strip("-")
    return slug or "provider"


def make_unique_provider_id(base_slug: str, used_ids: set[str], current_id: str | None = None) -> str:
    candidate = base_slug
    counter = 2
    while candidate in used_ids and candidate != current_id:
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


def is_valid_provider_id(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value))


def is_valid_env_var_name(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", value))


def is_valid_base_url(value: str) -> bool:
    return bool(re.fullmatch(r"https?://[^\s/$.?#].[^\s]*", value))


def normalize_env_var_name(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().upper()


def prompt_validated_text(
    label: str,
    *,
    default: str | None = None,
    allow_back: bool = False,
    example: str | None = None,
    validator: callable | None = None,
    error_message: str | None = None,
) -> str:
    while True:
        value = prompt_text(label, default=default, allow_back=allow_back, example=example)
        if value == BACK:
            return BACK
        if validator is None or validator(value):
            return value
        print(error_message or "Invalid value.")


def choose_rename_behavior(original_id: str, new_id: str) -> str | None:
    print()
    print("Provider ID change detected")
    print(f"  Current ID: {original_id}")
    print(f"  Proposed ID: {new_id}")
    print("  Changing the ID updates this provider to a new managed identifier.")
    print("  Keep the current ID to avoid renaming the existing provider.")
    print("  Or choose rename to replace it, or copy to keep both providers.")
    choice = prompt_choice(
        "How should this ID change be handled?",
        [
            "Keep the current provider ID",
            "Rename existing provider to the new ID",
            "Create a copy with the new ID and keep the current provider",
        ],
        default_index=1,
        allow_back=True,
    )
    if choice == BACK:
        return None
    if choice == "Keep the current provider ID":
        return "keep"
    if choice == "Rename existing provider to the new ID":
        return "rename"
    return "copy"


def normalize_provider(provider: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in provider.items() if value not in (None, "", [], {})}
    normalized["env_key"] = normalize_env_var_name(normalized.get("env_key"))
    if "prompt_api_key" in normalized:
        normalized["prompt_api_key"] = normalize_env_var_name(normalized.get("prompt_api_key"))
    profiles = normalized.get("profiles") or {}
    normalized["profiles"] = dict(profiles)
    return normalized


def validate_provider(provider: dict[str, Any]) -> None:
    for field in REQUIRED_PROVIDER_FIELDS:
        if not provider.get(field):
            raise SystemExit(f"provider field '{field}' is required")
    if not is_valid_provider_id(str(provider.get("provider_id", ""))):
        raise SystemExit("provider_id must use lowercase letters, numbers, and dashes only")
    if not is_valid_base_url(str(provider.get("base_url", ""))):
        raise SystemExit("base_url must be a full http:// or https:// URL")
    if not is_valid_env_var_name(str(provider.get("env_key", ""))):
        raise SystemExit("env_key must be a shell-style uppercase variable name")
    prompt_api_key = provider.get("prompt_api_key")
    if prompt_api_key and not is_valid_env_var_name(str(prompt_api_key)):
        raise SystemExit("prompt_api_key must be a shell-style uppercase variable name")
    profiles = provider.get("profiles") or {}
    if not profiles:
        raise SystemExit("provider must include at least one profile")
    default_profile = provider.get("default_profile")
    if default_profile and default_profile not in profiles:
        raise SystemExit("default_profile must match one of the configured profiles")


def apply_provider(provider: dict[str, Any], set_default_provider: bool | None = None) -> tuple[str, Path]:
    ensure_dirs()
    state = load_state()
    normalized = normalize_provider(provider)
    validate_provider(normalized)
    provider_id = normalized["provider_id"]
    path = provider_path(provider_id)
    path.write_text(json.dumps(normalized, indent=2, sort_keys=True) + "\n")
    state.setdefault("providers", {})[provider_id] = str(path)
    if set_default_provider is True:
        state["default_provider"] = provider_id
    elif set_default_provider is False and state.get("default_provider") == provider_id:
        state["default_provider"] = None
    save_state(state)
    return provider_id, path


def remove_provider(provider_id: str) -> None:
    state = load_state()
    path = provider_path(provider_id)
    if path.exists():
        path.unlink()
        print(f"Removed provider file {path}")
    providers = state.get("providers", {})
    providers.pop(provider_id, None)
    if state.get("default_provider") == provider_id:
        state["default_provider"] = None
    if providers:
        save_state(state)
    else:
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        prune_empty_managed_dirs()


def load_provider(provider_id: str) -> dict[str, Any]:
    path = provider_path(provider_id)
    if path.exists():
        return json.loads(path.read_text())
    state = load_state()
    state_path = state.get("providers", {}).get(provider_id)
    if state_path and Path(state_path).exists():
        return json.loads(Path(state_path).read_text())
    raise SystemExit(f"provider '{provider_id}' was not found")


def list_provider_ids() -> list[str]:
    state = load_state()
    return sorted(state.get("providers", {}).keys())


def is_interactive_terminal() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def clear_screen() -> None:
    if is_interactive_terminal():
        print("\033[2J\033[H", end="")


def print_header(title: str) -> None:
    clear_screen()
    print(f"== {title} ==")
    print(f"Config home: {CONFIG_HOME}")
    print()


def print_screen_controls(primary: str | None = None, allow_back: bool = False) -> None:
    if primary:
        print(primary)
    controls: list[str] = []
    if allow_back:
        controls.append("[Esc] Back one step")
    controls.append("[Ctrl+C] Exit without saving")
    if controls:
        print("Controls: " + "  ".join(controls))
    print()


def is_back_value(value: str, allow_back: bool) -> bool:
    return allow_back and value == ESCAPE


def print_prompt_hint(message: str | None = None, allow_back: bool = False) -> None:
    hints: list[str] = []
    if message:
        hints.append(message)
    if allow_back:
        hints.append("[Esc] Back one step")
    if hints:
        print("Hint: " + "  ".join(hints))


def prompt_text(
    label: str,
    default: str | None = None,
    allow_blank: bool = False,
    allow_back: bool = False,
    example: str | None = None,
) -> str:
    while True:
        placeholder = default if default not in (None, "") else example
        suffix = f" [{placeholder}]" if placeholder else ""
        value = input(f"{label}{suffix}: ").strip()
        if is_back_value(value, allow_back):
            return BACK
        if value:
            return value
        if default is not None:
            return default
        if allow_blank:
            return ""
        print("Value required.")


def prompt_choice(
    label: str,
    options: list[str],
    allow_blank: bool = False,
    default_index: int | None = None,
    allow_back: bool = False,
) -> str:
    while True:
        print(label)
        for index, option in enumerate(options, start=1):
            marker = " (default)" if default_index == index else ""
            print(f"  {index}. {option}{marker}")
        if default_index is not None:
            print("Press Enter to accept the default choice.")
        raw = input("Choice: ").strip()
        if is_back_value(raw, allow_back):
            return BACK
        if not raw and default_index is not None:
            return options[default_index - 1]
        if allow_blank and not raw:
            return ""
        if raw.isdigit():
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1]
        print("Invalid selection.")


def prompt_yes_no(label: str, default: bool = True, allow_back: bool = False) -> bool | str:
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        value = input(f"{label} {suffix}: ").strip().lower()
        if is_back_value(value, allow_back):
            return BACK
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer y or n.")


def prompt_secret(label: str, allow_back: bool = False) -> str:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print_prompt_hint("Input stays masked only in an interactive terminal.", allow_back=allow_back)
        value = input(f"{label}: ").strip()
        if is_back_value(value, allow_back):
            return BACK
        return value
    try:
        import termios
        import tty
    except ImportError:
        print_prompt_hint(allow_back=allow_back)
        value = input(f"{label}: ").strip()
        if is_back_value(value, allow_back):
            return BACK
        return value

    print_prompt_hint(allow_back=allow_back)
    print(f"{label}: ", end="", flush=True)
    chars: list[str] = []
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        while True:
            char = sys.stdin.read(1)
            if char in {"\r", "\n"}:
                print()
                break
            if char == "\x03":
                raise KeyboardInterrupt
            if allow_back and char == ESCAPE and not chars:
                print()
                return BACK
            if char in {"\x7f", "\b"}:
                if chars:
                    chars.pop()
                    print("\b \b", end="", flush=True)
                continue
            chars.append(char)
            print("*", end="", flush=True)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return "".join(chars).strip()


def prompt_to_continue() -> None:
    input("Press Enter to continue...")


def choose_profile_action(has_profiles: bool) -> str:
    print("Actions")
    print("  1. Add profile")
    if has_profiles:
        print("  2. Edit profile")
        print("  3. Remove profile")
    else:
        print("  2. Edit profile (unavailable until one exists)")
        print("  3. Remove profile (unavailable until one exists)")
    print("  4. Done")
    print()
    print("Legacy commands still work: add, edit <number>, remove <number>, done")
    return input("Action: ").strip().lower()


def choose_profile_by_number(profiles: dict[str, str], purpose: str) -> str | None:
    ordered_names = [name for name, _model in sorted(profiles.items())]
    choice = prompt_choice(f"Choose a profile to {purpose}", ordered_names, allow_back=True)
    if choice == BACK:
        return None
    return choice


def edit_single_profile(profiles: dict[str, str], name: str) -> bool:
    current_model = profiles[name]
    new_name = prompt_text("Profile name", default=name, allow_back=True, example="fast")
    if new_name == BACK:
        return False
    model = prompt_text("Model name", default=current_model, allow_back=True, example="openai/gpt-4o-mini")
    if model == BACK:
        return False
    if new_name != name and new_name in profiles:
        print("Profile name already exists.")
        return False
    profiles.pop(name)
    profiles[new_name] = model
    return True


def remove_single_profile(profiles: dict[str, str], name: str) -> bool:
    model = profiles[name]
    print_confirmation_note(f"Remove profile '{name}' mapped to '{model}'?")
    confirmed = prompt_yes_no("Remove this profile?", default=False, allow_back=True)
    if confirmed in {False, BACK}:
        return False
    profiles.pop(name)
    return True


def edit_profiles(existing: dict[str, str] | None = None) -> dict[str, str] | str:
    profiles = dict(existing or {})
    while True:
        print()
        print("Profiles")
        print_screen_controls("Manage profiles with a guided menu or legacy commands.", allow_back=True)
        print(f"Profile count: {len(profiles)}")
        if profiles:
            for index, (name, model) in enumerate(sorted(profiles.items()), start=1):
                print(f"  {index}. {name} -> {model}")
        else:
            print("  No profiles configured yet.")
        print()
        action = choose_profile_action(bool(profiles))
        if is_back_value(action, True):
            return BACK
        if action in {"1", "a", "add"}:
            name = prompt_text("Profile name", allow_back=True, example="fast")
            if name == BACK:
                continue
            if name in profiles:
                print("Profile name already exists.")
                continue
            model = prompt_text("Model name", allow_back=True, example="openai/gpt-4o-mini")
            if model == BACK:
                continue
            profiles[name] = model
            continue
        if action in {"4", "d", "done"}:
            if profiles:
                return profiles
            print("At least one profile is required.")
            continue
        if action in {"2", "e"}:
            if not profiles:
                print("No profiles to edit.")
                continue
            name = choose_profile_by_number(profiles, "edit")
            if name is None:
                continue
            edit_single_profile(profiles, name)
            continue
        if action.startswith("edit "):
            if not profiles:
                print("No profiles to edit.")
                continue
            raw_index = action.split(None, 1)[1]
            if not raw_index.isdigit():
                print("Use `edit <number>`.")
                continue
            ordered = sorted(profiles.items())
            index = int(raw_index)
            if not 1 <= index <= len(ordered):
                print("Profile number out of range.")
                continue
            name, _current_model = ordered[index - 1]
            edit_single_profile(profiles, name)
            continue
        if action in {"3", "r"}:
            if not profiles:
                print("No profiles to remove.")
                continue
            name = choose_profile_by_number(profiles, "remove")
            if name is None:
                continue
            remove_single_profile(profiles, name)
            continue
        if action.startswith("remove "):
            if not profiles:
                print("No profiles to remove.")
                continue
            raw_index = action.split(None, 1)[1]
            if not raw_index.isdigit():
                print("Use `remove <number>`.")
                continue
            ordered = sorted(profiles.items())
            index = int(raw_index)
            if not 1 <= index <= len(ordered):
                print("Profile number out of range.")
                continue
            name, _current_model = ordered[index - 1]
            remove_single_profile(profiles, name)
            continue
        print("Invalid action.")


def choose_default_profile(profiles: dict[str, str], current: str | None = None) -> str:
    options = sorted(profiles)
    default_index = options.index(current) + 1 if current in profiles else 1
    return prompt_choice("Choose the default profile", options, default_index=default_index, allow_back=True)


def print_review_section(title: str, rows: list[tuple[str, str]]) -> None:
    print(title)
    for label, value in rows:
        print(f"  {label}: {value}")
    print()


def build_review_warnings(provider: dict[str, Any], set_default_provider: bool) -> list[str]:
    warnings: list[str] = []
    if provider.get("provider_id") != slugify_provider_name(provider.get("provider_name", "")):
        warnings.append("Provider ID differs from the auto-generated slug.")
    if not set_default_provider:
        warnings.append("This provider will not become the managed default provider.")
    if len(provider.get("profiles", {})) == 1:
        warnings.append("Only one profile is configured.")
    return warnings


def print_confirmation_note(message: str) -> None:
    print()
    print(f"Confirmation: {message}")
    print()


def build_review_status(provider: dict[str, Any], set_default_provider: bool, export_snippet: str | None) -> list[tuple[str, str]]:
    return [
        ("Profiles", str(len(provider.get("profiles", {})))),
        ("Default profile", provider.get("default_profile", "")),
        ("Managed default", "Yes" if set_default_provider else "No"),
        ("Secret export", "Ready" if export_snippet else "Not requested"),
    ]


def print_review_checklist(provider: dict[str, Any], set_default_provider: bool, export_snippet: str | None) -> None:
    print("Ready to save")
    for label, value in build_review_status(provider, set_default_provider, export_snippet):
        print(f"  - {label}: {value}")
    print()


def print_post_save_summary(provider_id: str, path: Path, set_default_provider: bool, export_snippet: str | None) -> None:
    print()
    print("Saved")
    print(f"  provider_id: {provider_id}")
    print(f"  path: {path}")
    print(f"  managed_default: {'yes' if set_default_provider else 'no'}")
    if export_snippet:
        print("  export_snippet: available")
    print()


def print_remove_summary(provider: dict[str, Any], is_default: bool) -> None:
    print()
    print("Ready to remove")
    print(f"  provider_name: {provider.get('provider_name', provider.get('provider_id', ''))}")
    print(f"  provider_id: {provider.get('provider_id', '')}")
    print(f"  profiles: {len(provider.get('profiles', {}))}")
    print(f"  managed_default: {'yes' if is_default else 'no'}")
    print()


def print_remove_impact(is_default: bool) -> None:
    print("What changes")
    print("  - Deletes the managed provider JSON file.")
    print("  - Removes the provider from managed state.")
    if is_default:
        print("  - Clears the current managed default provider setting.")
    print()


def print_doctor_summary(state: dict[str, Any]) -> None:
    managed_providers = sorted(state.get("providers", {}).keys())
    print("Summary")
    print(f"  provider_count: {len(managed_providers)}")
    print(f"  default_provider: {state.get('default_provider') or 'None'}")
    print(f"  providers_dir: {'present' if PROVIDERS_DIR.exists() else 'missing'}")
    print(f"  state_file: {'present' if STATE_FILE.exists() else 'missing'}")
    print()


def print_doctor_provider_list(state: dict[str, Any]) -> None:
    managed_providers = sorted(state.get("providers", {}).keys())
    print("Managed providers")
    if not managed_providers:
        print("  - None")
    else:
        for provider_id in managed_providers:
            marker = " (default)" if provider_id == state.get("default_provider") else ""
            print(f"  - {provider_id}{marker}")
    print()


def print_provider_summary(provider: dict[str, Any], set_default_provider: bool, export_snippet: str | None) -> None:
    print()
    print("Review")
    print_screen_controls("Review the provider details before saving.")

    print_review_checklist(provider, set_default_provider, export_snippet)

    warnings = build_review_warnings(provider, set_default_provider)
    if warnings:
        print("Risk checks")
        for warning in warnings:
            print(f"  ! {warning}")
        print()

    print_review_section(
        "Identity",
        [
            ("provider_name", provider["provider_name"]),
            ("provider_id", provider["provider_id"]),
        ],
    )
    print_review_section(
        "Connection",
        [
            ("base_url", provider["base_url"]),
            ("wire_api", provider["wire_api"]),
        ],
    )
    print_review_section(
        "Authentication",
        [
            ("env_key", provider["env_key"]),
            ("prompt_api_key", provider.get("prompt_api_key", "")),
        ],
    )
    print_review_section(
        "Defaults",
        [
            ("default_profile", provider["default_profile"]),
            ("default_provider", "yes" if set_default_provider else "no"),
        ],
    )
    print("Profiles")
    for name, model in sorted(provider["profiles"].items()):
        marker = " (default)" if name == provider["default_profile"] else ""
        print(f"  - {name}: {model}{marker}")
    print()
    if export_snippet:
        print("Copy-ready shell export")
        print("```sh")
        print(export_snippet)
        print("```")


def build_export_snippet(env_key: str, secret: str) -> str:
    escaped = secret.replace("'", "'\"'\"'")
    return f"export {env_key}='{escaped}'"


def collect_provider_sections(existing: dict[str, Any] | None = None, existing_provider_ids: list[str] | None = None) -> tuple[dict[str, Any], bool, str | None, str | None] | None:
    current = deepcopy(existing or {})
    used_ids = set(existing_provider_ids or [])
    original_id = current.get("provider_id")
    if original_id:
        used_ids.discard(original_id)
    export_snippet: str | None = None
    set_default_provider = True
    rename_behavior: str | None = None
    step = 1

    while True:
        print_header("Provider Wizard")
        if step == 1:
            print("Step 1 of 5: Provider identity")
            print_screen_controls("Enter a human-friendly provider name first.", allow_back=True)
            provider_name = prompt_text("Provider name", default=current.get("provider_name"), allow_back=True, example="OpenRouter Demo")
            if provider_name == BACK:
                return None
            suggested_id = make_unique_provider_id(slugify_provider_name(provider_name), used_ids, current.get("provider_id"))
            provider_id_default = current.get("provider_id") or suggested_id
            if current.get("provider_name") != provider_name:
                provider_id_default = suggested_id
            provider_id = prompt_validated_text(
                "Provider ID",
                default=provider_id_default,
                allow_back=True,
                example="openrouter-demo",
                validator=is_valid_provider_id,
                error_message="Use lowercase letters, numbers, and dashes only.",
            )
            if provider_id == BACK:
                continue
            if provider_id in used_ids:
                print("Provider ID already exists.")
                prompt_to_continue()
                continue
            current["provider_name"] = provider_name
            current["provider_id"] = provider_id
            if original_id and provider_id != original_id:
                rename_behavior = choose_rename_behavior(original_id, provider_id)
                if rename_behavior is None:
                    continue
                if rename_behavior == "keep":
                    current["provider_id"] = original_id
                    rename_behavior = None
            else:
                rename_behavior = None
            step = 2
        elif step == 2:
            print("Step 2 of 5: Connection")
            print_screen_controls("Enter the provider endpoint and API style.", allow_back=True)
            base_url = prompt_validated_text(
                "Base URL",
                default=current.get("base_url"),
                allow_back=True,
                example="https://openrouter.ai/api/v1",
                validator=is_valid_base_url,
                error_message="Enter a full http:// or https:// URL.",
            )
            if base_url == BACK:
                step = 1
                continue
            print("Responses API is the newer default for most providers.")
            print("Chat Completions API is mainly for providers that expect the older chat-style request format.")
            print()
            wire_choices = [
                ("responses", "Responses API - recommended for most modern providers"),
                ("chat", "Chat Completions API - use when the provider expects chat-compatible payloads"),
            ]
            wire_values = [value for value, _label in wire_choices]
            current_wire = current.get("wire_api", "responses")
            default_wire_index = wire_values.index(current_wire) + 1 if current_wire in wire_values else 1
            wire_label = prompt_choice(
                "Choose the wire API",
                [label for _value, label in wire_choices],
                default_index=default_wire_index,
                allow_back=True,
            )
            if wire_label == BACK:
                continue
            wire_api = next(value for value, label in wire_choices if label == wire_label)
            current["base_url"] = base_url
            current["wire_api"] = wire_api
            step = 3
        elif step == 3:
            print("Step 3 of 5: Authentication")
            print_screen_controls("Configure env var references. Raw API keys are never saved.", allow_back=True)
            env_key = prompt_validated_text(
                "Environment variable name",
                default=normalize_env_var_name(current.get("env_key")),
                allow_back=True,
                example="OPENROUTER_API_KEY",
                validator=lambda value: is_valid_env_var_name(normalize_env_var_name(value) or ""),
                error_message="Use letters, numbers, and underscores like OPENROUTER_API_KEY.",
            )
            env_key = normalize_env_var_name(env_key)
            if env_key == BACK:
                step = 2
                continue
            prompt_api_key = prompt_validated_text(
                "Prompt API key variable name",
                default=normalize_env_var_name(current.get("prompt_api_key")) or env_key,
                allow_back=True,
                example="OPENROUTER_API_KEY",
                validator=lambda value: is_valid_env_var_name(normalize_env_var_name(value) or ""),
                error_message="Use letters, numbers, and underscores like OPENROUTER_API_KEY.",
            )
            prompt_api_key = normalize_env_var_name(prompt_api_key)
            if prompt_api_key == BACK:
                continue
            export_choice = prompt_yes_no("Generate a copy-ready shell export snippet for the API key?", default=False, allow_back=True)
            if export_choice == BACK:
                continue
            export_snippet = None
            if export_choice is True:
                secret = prompt_secret("Enter API key", allow_back=True)
                if secret == BACK:
                    continue
                if secret:
                    export_snippet = build_export_snippet(env_key, secret)
            current["env_key"] = env_key
            current["prompt_api_key"] = prompt_api_key
            step = 4
        elif step == 4:
            print("Step 4 of 5: Profiles")
            print_screen_controls("Manage profile names, models, and defaults.", allow_back=True)
            profiles = edit_profiles(existing=current.get("profiles"))
            if profiles == BACK:
                step = 3
                continue
            current["profiles"] = profiles
            step = 5
        elif step == 5:
            print("Step 5 of 5: Defaults")
            print_screen_controls("Choose the default profile and provider behavior.", allow_back=True)
            default_profile = choose_default_profile(current["profiles"], current.get("default_profile"))
            if default_profile == BACK:
                step = 4
                continue
            if current.get("provider_id") == load_state().get("default_provider"):
                print_confirmation_note("Choosing No will remove this provider from the managed default position.")
            default_provider_choice = prompt_yes_no("Set this provider as the managed default provider?", default=True, allow_back=True)
            if default_provider_choice == BACK:
                continue
            current["default_profile"] = default_profile
            set_default_provider = bool(default_provider_choice)
            normalized = normalize_provider(current)
            validate_provider(normalized)
            return normalized, set_default_provider, export_snippet, rename_behavior


def select_provider_id() -> str | None:
    provider_ids = list_provider_ids()
    if not provider_ids:
        print("No managed providers found.")
        prompt_to_continue()
        return None
    state = load_state()
    print_header("Select Provider")
    print(f"Managed providers: {len(provider_ids)}")
    print(f"Default provider: {state.get('default_provider') or 'None'}")
    print()
    print_screen_controls("Choose the provider you want to modify.", allow_back=True)
    return prompt_choice("Choose a provider", provider_ids, allow_back=True)


def run_create_provider() -> None:
    collected = collect_provider_sections(existing_provider_ids=list_provider_ids())
    if collected is None:
        print("Cancelled. Returned to the main menu.")
        prompt_to_continue()
        return
    provider, set_default, export_snippet, _rename_behavior = collected
    print_provider_summary(provider, set_default, export_snippet)
    print()
    print_confirmation_note("Nothing is written until you confirm save.")
    if prompt_yes_no("Save provider?", default=True):
        provider_id, path = apply_provider(provider, set_default)
        print_post_save_summary(provider_id, path, set_default, export_snippet)
        print(f"Saved provider '{provider_id}' to {path}")
        if export_snippet and prompt_yes_no("Show the export snippet again?", default=True):
            print("```sh")
            print(export_snippet)
            print("```")
    else:
        print("Cancelled without saving.")
    prompt_to_continue()


def run_edit_provider() -> None:
    selected = select_provider_id()
    if not selected or selected == BACK:
        return
    original_provider = load_provider(selected)
    collected = collect_provider_sections(
        existing=original_provider,
        existing_provider_ids=list_provider_ids(),
    )
    if collected is None:
        print("Cancelled. Returned to the main menu.")
        prompt_to_continue()
        return
    provider, set_default, export_snippet, rename_behavior = collected
    print_provider_summary(provider, set_default, export_snippet)
    print()
    print_confirmation_note("Nothing is written until you confirm save.")
    if prompt_yes_no("Save changes?", default=True):
        if selected != provider["provider_id"] and rename_behavior == "rename":
            old_path = provider_path(selected)
            if old_path.exists():
                old_path.unlink()
            state = load_state()
            state.get("providers", {}).pop(selected, None)
            if state.get("default_provider") == selected:
                state["default_provider"] = None
            save_state(state)
        provider_id, path = apply_provider(provider, set_default)
        print_post_save_summary(provider_id, path, set_default, export_snippet)
        print(f"Saved provider '{provider_id}' to {path}")
        if export_snippet and prompt_yes_no("Show the export snippet again?", default=True):
            print("```sh")
            print(export_snippet)
            print("```")
    else:
        print("Cancelled without saving.")
    prompt_to_continue()


def run_remove_provider() -> None:
    selected = select_provider_id()
    if not selected or selected == BACK:
        return
    state = load_state()
    provider = load_provider(selected)
    is_default = state.get("default_provider") == selected
    print_header("Remove Provider")
    print_screen_controls("Review the removal details before confirming.", allow_back=True)
    print_remove_summary(provider, is_default)
    print_remove_impact(is_default)
    print_confirmation_note(f"Removing '{selected}' deletes its managed provider file.")
    if is_default:
        print("Warning: this provider is currently the managed default provider.")
        print("Warning: removing it will clear the managed default setting.")
        print()
    confirm = prompt_yes_no(f"Remove provider '{selected}'?", default=False, allow_back=True)
    if confirm == BACK:
        print("Cancelled. Returned to the main menu.")
    elif confirm is True:
        remove_provider(selected)
        print()
        print("Removed")
        print(f"  provider_id: {selected}")
        print("  managed_state: updated")
        print(f"Removed provider '{selected}' from managed state")
    else:
        print("Removal cancelled. Nothing changed.")
    prompt_to_continue()


def run_doctor_view() -> None:
    state = load_state()
    print_header("Diagnostics")
    print_screen_controls("Review the managed configuration details.")
    print_doctor_summary(state)
    print("Scope")
    print("  user")
    print()
    print("Paths")
    print(f"  config_home: {CONFIG_HOME}")
    print(f"  providers_dir: {PROVIDERS_DIR}")
    print(f"  state_file: {STATE_FILE}")
    print()
    print_doctor_provider_list(state)
    print("State")
    print(f"  providers_dir_exists: {PROVIDERS_DIR.exists()}")
    print(f"  state_file_exists: {STATE_FILE.exists()}")
    print(f"  provider_count: {len(state.get('providers', {}))}")
    print(f"  default_provider: {state.get('default_provider')}")
    prompt_to_continue()


def cmd_wizard(args: argparse.Namespace) -> int:
    if not is_interactive_terminal() and not getattr(args, "allow_non_tty", False):
        print("Interactive wizard requires a TTY. Use a subcommand or run `codex-config-manager wizard` interactively.", file=sys.stderr)
        return 2
    try:
        while True:
            state = load_state()
            managed_providers = sorted(state.get("providers", {}).keys())
            print_header("Codex Config Manager")
            print("Interactive configuration")
            print("Dashboard")
            print(f"  managed_providers: {len(managed_providers)}")
            print(f"  default_provider: {state.get('default_provider') or 'None'}")
            print_screen_controls("Choose the next action.")
            print("Actions")
            print("  1. Create provider")
            print("     Build a new managed provider from scratch")
            print("  2. Edit provider")
            print("     Update an existing provider, profiles, or defaults")
            print("  3. Remove provider")
            print("     Delete a managed provider file and state entry")
            print("  4. Doctor view")
            print("     Review managed config paths, state, and provider list")
            print("  5. Exit")
            choice = input("Choose an action: ").strip()
            if choice == "1":
                run_create_provider()
            elif choice == "2":
                run_edit_provider()
            elif choice == "3":
                run_remove_provider()
            elif choice == "4":
                run_doctor_view()
            elif choice == "5":
                print("Goodbye.")
                return 0
            else:
                print("Invalid selection.")
                prompt_to_continue()
    except KeyboardInterrupt:
        print("\nWizard cancelled.")
        return 130


def cmd_apply(args: argparse.Namespace) -> int:
    if args.file:
        provider = parse_simple_yaml(Path(args.file).read_text())
        provider_id = provider.get("provider_id") or provider.get("id")
        if not provider_id:
            raise SystemExit("provider file must include provider_id")
    else:
        if not args.provider_id:
            raise SystemExit("--provider-id is required when --file is not used")
        provider = build_provider_record(args)
        provider_id = args.provider_id

    provider_id, path = apply_provider(provider, set_default_provider=True if args.default_profile else None)
    print(f"Applied provider '{provider_id}' to {path}")
    print(f"Config home: {CONFIG_HOME}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    state = load_state()
    print(f"scope={args.scope}")
    print(f"config_home={CONFIG_HOME}")
    print(f"providers_dir_exists={PROVIDERS_DIR.exists()}")
    print(f"state_file_exists={STATE_FILE.exists()}")
    print(f"provider_count={len(state.get('providers', {}))}")
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    remove_provider(args.provider_id)
    print(f"Removed provider '{args.provider_id}' from managed state")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Manage Codex provider configuration in user space.",
    )
    subparsers = parser.add_subparsers(dest="command")

    apply_parser = subparsers.add_parser("apply", help="Create or update a managed provider config")
    apply_parser.add_argument("--file", help="YAML file containing a provider definition")
    apply_parser.add_argument("--provider-id")
    apply_parser.add_argument("--provider-name")
    apply_parser.add_argument("--base-url")
    apply_parser.add_argument("--wire-api")
    apply_parser.add_argument("--env-key")
    apply_parser.add_argument("--profile", action="append")
    apply_parser.add_argument("--default-profile")
    apply_parser.add_argument("--prompt-api-key")
    apply_parser.add_argument("--yes", action="store_true", help="Accept non-interactive apply")
    apply_parser.set_defaults(func=cmd_apply)

    doctor_parser = subparsers.add_parser("doctor", help="Show managed configuration diagnostics")
    doctor_parser.add_argument("--scope", default="user", choices=["user", "project"])
    doctor_parser.set_defaults(func=cmd_doctor)

    uninstall_parser = subparsers.add_parser("uninstall", help="Remove a managed provider config")
    uninstall_parser.add_argument("--provider-id", required=True)
    uninstall_parser.add_argument("--yes", action="store_true")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    wizard_parser = subparsers.add_parser("wizard", help="Launch the interactive configuration wizard")
    wizard_parser.add_argument("--allow-non-tty", action="store_true", help=argparse.SUPPRESS)
    wizard_parser.set_defaults(func=cmd_wizard)

    return parser


def main() -> int:
    parser = build_parser()
    if len(sys.argv) == 1:
        if is_interactive_terminal():
            return cmd_wizard(argparse.Namespace(allow_non_tty=False))
        parser.print_help(sys.stderr)
        print("\nerror: no subcommand provided and no interactive TTY detected", file=sys.stderr)
        return 2
    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
