#!/usr/bin/env bash

set -e

RESULTS_DIR="test-results"

if [ $# -eq 0 ]; then
    PYTEST_ARGS="-v"
else
    PYTEST_ARGS="$*"
fi

docker compose exec djehuty bash -c "\
    source /opt/djehuty/virtual-env/bin/activate && \
    cd /opt/djehuty/djehuty/e2e && \
    rm -rf $RESULTS_DIR && \
    E2E_BASE_URL=http://localhost:8080 python -m pytest tests/ \
        --output=$RESULTS_DIR \
        --screenshot=only-on-failure \
        $PYTEST_ARGS"
