#!/bin/sh
set -e

CONFIG="/config/djehuty/djehuty-dev-config.xml"
MARKER="/data/.initialized"

if [ ! -f "$MARKER" ]; then
    touch "$MARKER"
    exec djehuty web --initialize --config-file "$CONFIG"
fi

exec djehuty web --config-file "$CONFIG"
