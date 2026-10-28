#!/usr/bin/env bash
# Install or upgrade tradebot as a systemd service on a Linux VM (Ubuntu/Debian).
#
#   sudo ./deploy/install.sh            # from a checkout of the repo's trading-bot/ dir
#
# Layout:
#   /opt/tradebot/app        code (root-owned, read-only to the service)
#   /opt/tradebot/venv       Python virtualenv
#   /etc/tradebot/           configs (*.json) and env (secrets), root:tradebot 640
#   /var/lib/tradebot/       working dir: state/, logs, token, STOP file (tradebot 700)
#   /var/backups/tradebot/   daily state snapshots
#
# Safe to re-run for upgrades: existing configs and env are never overwritten, and
# running bot instances are not started, stopped or enabled. Restart them yourself
# (`systemctl restart tradebot@NAME`) once you've read the changes.
#
# TRADEBOT_INSTALL_ROOT=/some/dir installs under that prefix and skips user
# creation, ownership and systemctl, for testing the installer without root.
set -euo pipefail

ROOT=${TRADEBOT_INSTALL_ROOT:-}
SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PY=${PYTHON:-python3}
test_mode() { [[ -n "$ROOT" ]]; }
say() { printf '==> %s\n' "$*"; }

if ! test_mode && [[ $EUID -ne 0 ]]; then
    echo "run as root (sudo), or set TRADEBOT_INSTALL_ROOT for a test install" >&2
    exit 1
fi
"$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))' || {
    echo "Python 3.10+ required ($PY is $("$PY" -V 2>&1))" >&2; exit 1; }
[[ -f "$SRC/tradebot/__main__.py" ]] || { echo "run from the trading-bot checkout" >&2; exit 1; }

own() {   # own USER:GROUP MODE PATH...
    local ug=$1 mode=$2; shift 2
    chmod "$mode" "$@"
    test_mode || chown "$ug" "$@"
}

if ! test_mode && ! id tradebot >/dev/null 2>&1; then
    say "creating system user tradebot"
    useradd --system --home-dir /var/lib/tradebot --shell /usr/sbin/nologin tradebot
fi

say "installing code to $ROOT/opt/tradebot/app"
mkdir -p "$ROOT/opt/tradebot"
staging="$ROOT/opt/tradebot/app.new"
rm -rf "$staging"
mkdir -p "$staging"
cp -r "$SRC/tradebot" "$SRC/deploy" "$SRC/config" "$SRC/requirements.txt" "$SRC/README.md" "$staging/"
find "$staging" -name '__pycache__' -prune -exec rm -rf {} +
# Swap in one rename so a running instance never sees a half-copied tree on restart.
if [[ -d "$ROOT/opt/tradebot/app" ]]; then
    rm -rf "$ROOT/opt/tradebot/app.old"
    mv "$ROOT/opt/tradebot/app" "$ROOT/opt/tradebot/app.old"
fi
mv "$staging" "$ROOT/opt/tradebot/app"
own root:root go-w -R "$ROOT/opt/tradebot/app"

if [[ ! -x "$ROOT/opt/tradebot/venv/bin/python" ]]; then
    say "creating virtualenv"
    "$PY" -m venv "$ROOT/opt/tradebot/venv"
fi
if [[ -n "${TRADEBOT_SKIP_PIP:-}" ]]; then
    say "skipping pip install (TRADEBOT_SKIP_PIP set)"
else
    say "installing Python dependencies"
    "$ROOT/opt/tradebot/venv/bin/pip" install -q --upgrade pip
    "$ROOT/opt/tradebot/venv/bin/pip" install -q -r "$ROOT/opt/tradebot/app/requirements.txt"
fi

say "creating state, backup and config directories"
mkdir -p "$ROOT/var/lib/tradebot/state" "$ROOT/var/backups/tradebot" "$ROOT/etc/tradebot"
own tradebot:tradebot 700 "$ROOT/var/lib/tradebot" "$ROOT/var/lib/tradebot/state" "$ROOT/var/backups/tradebot"
own root:tradebot 750 "$ROOT/etc/tradebot"

for f in "$SRC"/config/*.json; do
    dest="$ROOT/etc/tradebot/$(basename "$f")"
    if [[ -e "$dest" ]]; then
        say "keeping existing $(basename "$f")"
    else
        cp "$f" "$dest"
        own root:tradebot 640 "$dest"
        say "installed config $(basename "$f")"
    fi
done
if [[ ! -e "$ROOT/etc/tradebot/env" ]]; then
    cp "$SRC/deploy/env.example" "$ROOT/etc/tradebot/env"
    own root:tradebot 640 "$ROOT/etc/tradebot/env"
    say "installed env template: fill in $ROOT/etc/tradebot/env"
else
    say "keeping existing env"
fi

say "installing systemd units and the tradebot CLI"
mkdir -p "$ROOT/etc/systemd/system" "$ROOT/usr/local/bin"
for u in tradebot@.service tradebot-backup.service tradebot-backup.timer; do
    install -m 644 "$SRC/deploy/$u" "$ROOT/etc/systemd/system/$u"
done
install -m 755 "$SRC/deploy/tradebot.sh" "$ROOT/usr/local/bin/tradebot"

if test_mode; then
    say "test install complete under $ROOT (systemctl skipped)"
    exit 0
fi

systemctl daemon-reload
systemctl enable --now tradebot-backup.timer

if [[ $(timedatectl show -p NTPSynchronized --value 2>/dev/null || echo no) != yes ]]; then
    echo "WARNING: system clock is not NTP-synchronised. Bar timing depends on it:" >&2
    echo "         sudo timedatectl set-ntp true" >&2
fi

cat <<'NEXT'

Installed. Nothing is running yet. Next steps:
  1. Edit /etc/tradebot/env (alerts, Kite keys) and /etc/tradebot/<config>.json
     (symbols, sectors, holidays, capital).
  2. Kite developer console: whitelist this machine's static IP; set the redirect URL.
  3. sudo tradebot login                       # every trading morning
  4. sudo systemctl enable --now tradebot@swing  # paper mode until env says live
  5. sudo tradebot status -c /etc/tradebot/swing.json
     journalctl -u tradebot@swing -f
NEXT
