#!/bin/sh
set -e

CONFIG="${DJEHUTY_CONFIG:-/config/djehuty/djehuty-dev-config.xml}"
MARKER="/data/.initialized"

# When DJEHUTY_COVERAGE=1, run djehuty under coverage.py so the e2e
# stack can collect coverage from the running server.
if [ "${DJEHUTY_COVERAGE:-0}" = "1" ]; then
    set -- coverage run -m djehuty.ui web
else
    set -- djehuty web
fi

# DJEHUTY_FORCE_INITIALIZE=1 always re-runs --initialize. Used by the
# e2e stack so a stale volume cannot leave the SPARQL store out of sync
# with the configured account or state-graph.
if [ "${DJEHUTY_FORCE_INITIALIZE:-0}" = "1" ] || [ ! -f "$MARKER" ]; then
    touch "$MARKER"
    exec "$@" --initialize --config-file "$CONFIG"
fi

exec "$@" --config-file "$CONFIG"
