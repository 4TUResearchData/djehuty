"""
API response helper for saving responses from API tests.

Responses are saved to the test results directory (``--output``)
with a file extension derived from the response Content-Type::

    <output-dir>/<test-name>/<index>-<description>.<ext>

Usage in tests::

    def test_example(self, page, save_response):
        response = page.request.get("/v2/articles")
        save_response(response, "list-articles")
"""

import json
from pathlib import Path

from playwright.sync_api import APIResponse

CONTENT_TYPE_TO_EXT = {
    "application/json": ".json",
    "application/xml": ".xml",
    "text/xml": ".xml",
    "text/html": ".html",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "image/svg+xml": ".svg",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/octet-stream": ".bin",
}


def _ext_from_content_type(content_type: str) -> str:
    """Derive a file extension from a Content-Type header value."""
    # Strip parameters (e.g. "application/json; charset=utf-8" → "application/json")
    mime = content_type.split(";")[0].strip().lower() if content_type else ""
    return CONTENT_TYPE_TO_EXT.get(mime, ".txt")


class ApiResponseHelper:
    """Saves sequentially numbered API responses for a single test."""

    def __init__(self, output_dir: Path):
        self._output_dir = output_dir
        self._index = 0

    def __call__(self, response: APIResponse, description: str) -> Path:
        """Save the API response body and return its path.

        The file extension is determined by the response Content-Type header.
        JSON responses are pretty-printed; all others are saved as-is.

        Parameters
        ----------
        response:
            The Playwright APIResponse to capture.
        description:
            Short kebab-case label (e.g. ``"list-articles"``).

        Returns
        -------
        Path to the saved file.
        """
        self._index += 1
        self._output_dir.mkdir(parents=True, exist_ok=True)

        content_type = response.headers.get("content-type", "")
        ext = _ext_from_content_type(content_type)
        filepath = self._output_dir / f"{self._index}-{description}{ext}"

        if ext == ".json":
            try:
                body = response.json()
            except Exception:
                body = response.text()
            filepath.write_text(json.dumps(body, indent=2, default=str))
        elif ext in (".png", ".jpg", ".pdf", ".zip", ".bin"):
            filepath.write_bytes(response.body())
        else:
            filepath.write_text(response.text())

        return filepath
