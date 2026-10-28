#!/usr/bin/env bash
# Snapshot the bot's state (positions, pending orders, halts, trades, logs).
# The Kite access token is excluded: it's a secret and expires daily anyway.
# Usage: backup.sh STATE_DIR BACKUP_DIR [KEEP_DAYS]
set -euo pipefail

state_dir=${1:?state dir}
backup_dir=${2:?backup dir}
keep_days=${3:-30}

[[ -d "$state_dir" ]] || { echo "no state dir $state_dir" >&2; exit 1; }
mkdir -p "$backup_dir"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
out="$backup_dir/tradebot-state-$stamp.tar.gz"
tmp="$out.partial"

tar --exclude='kite_token.json' --exclude='*.tmp' --exclude='*.lock' \
    -czf "$tmp" -C "$state_dir" .
mv "$tmp" "$out"
find "$backup_dir" -maxdepth 1 -name 'tradebot-state-*.tar.gz' -mtime +"$keep_days" -delete
echo "wrote $out"
