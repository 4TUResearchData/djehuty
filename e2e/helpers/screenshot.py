"""
Screenshot helper for capturing test progress screenshots.

Screenshots are saved to the test results directory (``--output``)
with the naming convention::

    <output-dir>/<test-name>/<index>-<description>.png

Usage in tests::

    def test_example(self, page, screenshot):
        page.goto("/portal")
        screenshot(page, "homepage-loaded")
        page.click("#login-button")
        screenshot(page, "after-login-click")
"""

import os
from pathlib import Path

from playwright.sync_api import Page


class ScreenshotHelper:
    """Captures sequentially numbered screenshots for a single test."""

    def __init__(self, output_dir: Path):
        self._output_dir = output_dir
        self._index = 0

    def __call__(self, page: Page, description: str) -> Path:
        """Take a screenshot and return its path.

        Parameters
        ----------
        page:
            The Playwright page to capture.
        description:
            Short kebab-case label (e.g. ``"dashboard-loaded"``).

        Returns
        -------
        Path to the saved screenshot file.
        """
        self._index += 1
        self._output_dir.mkdir(parents=True, exist_ok=True)
        filepath = self._output_dir / f"{self._index}-{description}.png"
        page.screenshot(path=str(filepath), full_page=True)
        return filepath
