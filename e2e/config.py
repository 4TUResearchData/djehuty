"""
E2E test configuration.

Override settings via environment variables:
    E2E_BASE_URL          - Base URL of the djehuty instance (default: http://localhost:9001)
    E2E_AUTO_LOGIN_EMAIL  - Email for automatic login (default: dev@djehuty.com)
    E2E_TIMEOUT           - Default timeout in ms for Playwright actions (default: 30000)
    E2E_HEADED            - Run in headed mode: 1 or 0 (default: 0)
    E2E_SLOW_MO           - Slow down actions by N ms (default: 0)
"""

import os

BASE_URL = os.getenv("E2E_BASE_URL", "http://localhost:9001")
AUTO_LOGIN_EMAIL = os.getenv("E2E_AUTO_LOGIN_EMAIL", "dev@djehuty.com")
TIMEOUT = int(os.getenv("E2E_TIMEOUT", "30000"))
HEADED = os.getenv("E2E_HEADED", "0") == "1"
SLOW_MO = int(os.getenv("E2E_SLOW_MO", "0"))

ADMIN_EMAIL = AUTO_LOGIN_EMAIL

ADMIN_PAGES = ["dashboard", "users", "maintenance", "exploratory"]
DEPOSITOR_PAGES = ["dashboard", "datasets", "collections", "profile"]
