#!/usr/bin/env sh
set -eu

DEFAULT_COMMAND_NAME="codex-config-manager"
PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PREFIX="$HOME/.local"
COMMAND_NAME="$DEFAULT_COMMAND_NAME"
NO_SHELL_HOOK=0
ASSUME_YES=0
SCRIPT_NAME="codex_config_manager.py"
REPO_RAW_BASE=${CODEX_CONFIG_MANAGER_RAW_BASE:-"https://raw.githubusercontent.com/CruxExperts/codex-config-manager/main"}
MANAGED_BEGIN="# BEGIN managed by codex-config-manager installer"
MANAGED_END="# END managed by codex-config-manager installer"
RELOAD_CMD=""

usage() {
  cat <<USAGE
Usage: ./install.sh [OPTIONS]
  --prefix PATH
  --command-name NAME
  --no-shell-hook
  --yes
USAGE
}

log() {
  printf '%s\n' "$*"
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

expand_path() {
  case "$1" in
    "~") printf '%s\n' "$HOME" ;;
    "~/"*) printf '%s/%s\n' "$HOME" "${1#~/}" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --prefix)
      [ "$#" -ge 2 ] || fail "--prefix requires a value"
      PREFIX=$(expand_path "$2")
      shift 2
      ;;
    --command-name)
      [ "$#" -ge 2 ] || fail "--command-name requires a value"
      COMMAND_NAME="$2"
      shift 2
      ;;
    --no-shell-hook)
      NO_SHELL_HOOK=1
      shift
      ;;
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/codex-config-manager"
INSTALL_SCRIPT_PATH="$SHARE_DIR/$SCRIPT_NAME"
SHIM_PATH="$BIN_DIR/$COMMAND_NAME"
EXAMPLES_DIR="$SHARE_DIR/examples"
EXAMPLES_MANIFEST="examples/manifest.txt"

check_python() {
  command -v python3 >/dev/null 2>&1 || fail "python3 is required"
  python3 - <<'PY' || fail "python3 3.10+ is required"
import sys
raise SystemExit(0 if sys.version_info >= (3, 10) else 1)
PY
}

download_file() {
  src_url="$1"
  dest_path="$2"
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL "$src_url" -o "$dest_path"
  elif command -v wget >/dev/null 2>&1; then
    wget -qO "$dest_path" "$src_url"
  else
    fail "curl or wget is required when install.sh is run without local project files"
  fi
}

copy_or_fetch_main_script() {
  mkdir -p "$SHARE_DIR"
  if [ -f "$PROJECT_DIR/$SCRIPT_NAME" ]; then
    cp "$PROJECT_DIR/$SCRIPT_NAME" "$INSTALL_SCRIPT_PATH"
    return 0
  fi
  log "Local $SCRIPT_NAME not found; downloading from $REPO_RAW_BASE"
  download_file "$REPO_RAW_BASE/$SCRIPT_NAME" "$INSTALL_SCRIPT_PATH"
}

copy_examples_from_local() {
  mkdir -p "$EXAMPLES_DIR"
  cp -R "$PROJECT_DIR/examples/." "$EXAMPLES_DIR/"
}

copy_examples_from_remote() {
  tmp_manifest=$(mktemp)
  if ! download_file "$REPO_RAW_BASE/$EXAMPLES_MANIFEST" "$tmp_manifest"; then
    rm -f "$tmp_manifest"
    log "No remote examples manifest found; skipping examples copy"
    return 0
  fi
  mkdir -p "$EXAMPLES_DIR"
  while IFS= read -r example_path; do
    [ -n "$example_path" ] || continue
    example_dest="$EXAMPLES_DIR/$(basename "$example_path")"
    download_file "$REPO_RAW_BASE/$example_path" "$example_dest"
  done < "$tmp_manifest"
  rm -f "$tmp_manifest"
}

copy_examples_if_present() {
  rm -rf "$EXAMPLES_DIR"
  if [ -d "$PROJECT_DIR/examples" ]; then
    copy_examples_from_local
    return 0
  fi
  copy_examples_from_remote
}

write_shim() {
  mkdir -p "$BIN_DIR"
  cat > "$SHIM_PATH" <<SHIM
#!/usr/bin/env sh
exec python3 "$INSTALL_SCRIPT_PATH" "\$@"
SHIM
  chmod +x "$SHIM_PATH"
}

detect_shell_and_rc() {
  shell_name=$(basename "${SHELL:-sh}")
  case "$shell_name" in
    bash)
      printf '%s\n%s\n' "bash" "$HOME/.bashrc"
      ;;
    zsh)
      printf '%s\n%s\n' "zsh" "$HOME/.zshrc"
      ;;
    fish)
      printf '%s\n%s\n' "fish" "$HOME/.config/fish/config.fish"
      ;;
    *)
      printf '%s\n%s\n' "profile" "$HOME/.profile"
      ;;
  esac
}

path_contains_bin_dir() {
  case ":$PATH:" in
    *":$BIN_DIR:"*) return 0 ;;
    *) return 1 ;;
  esac
}

backup_file() {
  target="$1"
  [ -f "$target" ] || return 0
  cp "$target" "$target.bak.$(date +%Y%m%d%H%M%S)"
}

ensure_shell_hook() {
  [ "$NO_SHELL_HOOK" -eq 0 ] || return 0
  if path_contains_bin_dir; then
    log "$BIN_DIR is already on PATH; skipping shell hook"
    return 0
  fi

  shell_name_and_rc=$(detect_shell_and_rc)
  shell_name=$(printf '%s' "$shell_name_and_rc" | sed -n '1p')
  rc_file=$(printf '%s' "$shell_name_and_rc" | sed -n '2p')
  mkdir -p "$(dirname "$rc_file")"
  [ -f "$rc_file" ] || : > "$rc_file"

  if grep -F "$MANAGED_BEGIN" "$rc_file" >/dev/null 2>&1; then
    log "Managed shell hook already present in $rc_file"
  else
    backup_file "$rc_file"
    {
      printf '\n%s\n' "$MANAGED_BEGIN"
      if [ "$shell_name" = "fish" ]; then
        printf 'fish_add_path "%s"\n' "$BIN_DIR"
      else
        printf 'export PATH="%s:$PATH"\n' "$BIN_DIR"
      fi
      printf '%s\n' "$MANAGED_END"
    } >> "$rc_file"
    log "Added PATH hook to $rc_file"
  fi

  case "$shell_name" in
    bash) RELOAD_CMD="source ~/.bashrc" ;;
    zsh) RELOAD_CMD="source ~/.zshrc" ;;
    fish) RELOAD_CMD="source ~/.config/fish/config.fish" ;;
    *) RELOAD_CMD="source ~/.profile" ;;
  esac
}

check_python
mkdir -p "$SHARE_DIR" "$BIN_DIR"
copy_or_fetch_main_script
copy_examples_if_present
write_shim
ensure_shell_hook

log "Installed script: $INSTALL_SCRIPT_PATH"
log "Installed command: $SHIM_PATH"
if [ -n "$RELOAD_CMD" ]; then
  log "Reload shell: $RELOAD_CMD"
fi
log "Next step: $COMMAND_NAME --help"
