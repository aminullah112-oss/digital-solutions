#!/usr/bin/env bash
# Operator CLI on the server, e.g.:
#   tradebot status -c /etc/tradebot/swing.json
#   tradebot login
#   tradebot reset  -c /etc/tradebot/swing.json
# Always runs as the `tradebot` user with the service's environment, so files it
# writes (token, state) stay owned by the service account.
set -euo pipefail

ROOT=${TRADEBOT_INSTALL_ROOT:-}
if [[ $(id -un) != tradebot && -z "$ROOT" ]]; then
    exec sudo -u tradebot -- "$0" "$@"
fi
# Load the env file the way systemd's EnvironmentFile does: plain KEY=value lines,
# optional surrounding quotes, never evaluated as shell (secrets may contain $ or `).
while IFS= read -r line || [[ -n "$line" ]]; do
    [[ "$line" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]] || continue
    key=${BASH_REMATCH[1]} val=${BASH_REMATCH[2]}
    if [[ "$val" =~ ^\"(.*)\"$ || "$val" =~ ^\'(.*)\'$ ]]; then
        val=${BASH_REMATCH[1]}
    fi
    export "$key=$val"
done < "$ROOT/etc/tradebot/env"
cd "$ROOT/var/lib/tradebot"
PYTHONPATH="$ROOT/opt/tradebot/app" exec "$ROOT/opt/tradebot/venv/bin/python" -m tradebot "$@"
