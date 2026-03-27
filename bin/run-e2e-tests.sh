#!/usr/bin/env bash

set -e

if [ $# -eq 0 ]; then
    PYTEST_ARGS="-v"
else
    PYTEST_ARGS="$*"
fi

docker compose exec djehuty bash -c "\
    source /opt/djehuty/virtual-env/bin/activate && \
    cd /opt/djehuty/djehuty/e2e && \
    E2E_BASE_URL=http://localhost:8080 python -m pytest tests/ $PYTEST_ARGS"
