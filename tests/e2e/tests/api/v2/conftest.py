"""Auto-mark every test under tests/api/v2/ with @pytest.mark.api_v2."""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/api/v2/" in str(item.fspath):
            item.add_marker(pytest.mark.api_v2)
