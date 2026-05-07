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

if [ ! -f "$MARKER" ]; then
    touch "$MARKER"
    exec "$@" --initialize --config-file "$CONFIG"
fi

exec "$@" --config-file "$CONFIG"
