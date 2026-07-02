"""Auto-mark every test under tests/api/v3/ with @pytest.mark.api_v3."""

import pytest


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/api/v3/" in str(item.fspath):
            item.add_marker(pytest.mark.api_v3)
