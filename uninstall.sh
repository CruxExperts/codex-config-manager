#!/usr/bin/env sh
set -eu

PREFIX="$HOME/.local"
COMMAND_NAME="codex-config-manager"
ASSUME_YES=0
MANAGED_BEGIN="# BEGIN managed by codex-config-manager installer"
MANAGED_END="# END managed by codex-config-manager installer"

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
    --yes)
      ASSUME_YES=1
      shift
      ;;
    -h|--help)
      printf 'Usage: ./uninstall.sh [--prefix PATH] [--command-name NAME] [--yes]\n'
      exit 0
      ;;
    *)
      fail "unknown option: $1"
      ;;
  esac
done

BIN_DIR="$PREFIX/bin"
SHARE_DIR="$PREFIX/share/codex-config-manager"
SHIM_PATH="$BIN_DIR/$COMMAND_NAME"

remove_managed_block() {
  shell_name=$(basename "${SHELL:-sh}")
  case "$shell_name" in
    bash) rc_file="$HOME/.bashrc" ;;
    zsh) rc_file="$HOME/.zshrc" ;;
    fish) rc_file="$HOME/.config/fish/config.fish" ;;
    *) rc_file="$HOME/.profile" ;;
  esac
  [ -f "$rc_file" ] || return 0
  tmp_file="$rc_file.tmp.$$"
  awk -v begin="$MANAGED_BEGIN" -v end="$MANAGED_END" '
    $0 == begin {skip=1; next}
    $0 == end {skip=0; next}
    skip != 1 {print}
  ' "$rc_file" > "$tmp_file"
  if ! cmp -s "$rc_file" "$tmp_file"; then
    cp "$rc_file" "$rc_file.bak.$(date +%Y%m%d%H%M%S)"
    mv "$tmp_file" "$rc_file"
    printf 'Removed managed PATH hook from %s\n' "$rc_file"
  else
    rm -f "$tmp_file"
  fi
}

rm -f "$SHIM_PATH"
printf 'Removed shim: %s\n' "$SHIM_PATH"

if [ -d "$SHARE_DIR" ]; then
  if [ "$ASSUME_YES" -eq 1 ]; then
    rm -rf "$SHARE_DIR"
    printf 'Removed app directory: %s\n' "$SHARE_DIR"
  else
    printf 'Remove app directory %s? [y/N] ' "$SHARE_DIR"
    read answer || answer="n"
    case "$answer" in
      y|Y|yes|YES)
        rm -rf "$SHARE_DIR"
        printf 'Removed app directory: %s\n' "$SHARE_DIR"
        ;;
      *)
        printf 'Kept app directory: %s\n' "$SHARE_DIR"
        ;;
    esac
  fi
fi

if [ "$ASSUME_YES" -eq 1 ]; then
  remove_managed_block
else
  printf 'Remove managed PATH hook from your shell rc file? [y/N] '
  read hook_answer || hook_answer="n"
  case "$hook_answer" in
    y|Y|yes|YES) remove_managed_block ;;
  esac
fi

printf 'Managed Codex configs are not removed by default.\n'
printf 'To remove a provider config, run: %s\n' "$COMMAND_NAME uninstall --provider-id PROVIDER_ID"
