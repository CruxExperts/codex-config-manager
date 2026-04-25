#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "codex-config-manager"
CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
PROVIDERS_DIR = CONFIG_HOME / "providers"
STATE_FILE = CONFIG_HOME / "state.json"


def ensure_dirs() -> None:
    PROVIDERS_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"default_provider": None, "providers": {}}
    try:
        return json.loads(STATE_FILE.read_text())
    except json.JSONDecodeError:
        return {"default_provider": None, "providers": {}}


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


def cmd_apply(args: argparse.Namespace) -> int:
    ensure_dirs()
    state = load_state()

    if args.file:
        provider = parse_simple_yaml(Path(args.file).read_text())
        provider_id = provider.get("provider_id") or provider.get("id")
        if not provider_id:
            raise SystemExit("provider file must include provider_id")
    else:
        if not args.provider_id:
            raise SystemExit("--provider-id is required when --file is not used")
        provider_id = args.provider_id
        provider = build_provider_record(args)

    provider_path = PROVIDERS_DIR / f"{provider_id}.json"
    provider_path.write_text(json.dumps(provider, indent=2, sort_keys=True) + "\n")
    state.setdefault("providers", {})[provider_id] = str(provider_path)
    if args.default_profile:
        state["default_provider"] = provider_id
    save_state(state)

    print(f"Applied provider '{provider_id}' to {provider_path}")
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
    state = load_state()
    provider_id = args.provider_id
    provider_path = PROVIDERS_DIR / f"{provider_id}.json"
    if provider_path.exists():
        provider_path.unlink()
        print(f"Removed provider file {provider_path}")
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

    print(f"Removed provider '{provider_id}' from managed state")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=APP_NAME,
        description="Manage Codex provider configuration in user space.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

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

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
