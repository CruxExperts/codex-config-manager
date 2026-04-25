#!/usr/bin/env sh
set -eu
VERSION=${1:-$(date +%Y.%m.%d)}
OUT_DIR="dist/codex-config-manager_${VERSION}"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
cp codex_config_manager.py install.sh uninstall.sh README.md "$OUT_DIR/"
cp -R examples "$OUT_DIR/examples"
mkdir -p dist
tar -czf "dist/codex-config-manager_${VERSION}.tar.gz" -C dist "codex-config-manager_${VERSION}"
printf 'Created %s\n' "dist/codex-config-manager_${VERSION}.tar.gz"
