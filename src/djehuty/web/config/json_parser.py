"""JSON configuration parser for djehuty.

Provides JsonConfigElement, a wrapper that makes a JSON dict behave
like an XML Element so existing parsing code works unchanged.

Supports k8s-friendly secret references in any string value:
    "${env:NAME}"      → value of environment variable NAME
    "${file:/path}"    → stripped contents of the file at /path
The full string must be the placeholder; partial interpolation is not supported.
"""

import json
import logging
import os
import re

from defusedxml import ElementTree


_SECRET_REF_RE = re.compile(r"^\$\{(env|file):([^}]+)\}$")


class ConfigurationError(Exception):
    """Raised when a referenced env var or secret file is missing/unreadable."""


def _resolve_reference(value):
    """Resolve a ${env:NAME} or ${file:/path} placeholder. Pass-through otherwise."""
    if not isinstance(value, str):
        return value
    match = _SECRET_REF_RE.match(value)
    if not match:
        return value
    kind, target = match.groups()
    if kind == "env":
        resolved = os.environ.get(target)
        if resolved is None:
            raise ConfigurationError(
                f"environment variable '{target}' referenced in config is not set"
            )
        return resolved
    # kind == "file"
    try:
        with open(target, "r", encoding="utf-8") as handle:
            return handle.read().strip()
    except OSError as exc:
        raise ConfigurationError(
            f"could not read secret file '{target}': {exc}"
        ) from exc


class JsonConfigElement:
    """Wraps a JSON dict to expose the same interface as xml.etree.Element."""

    def __init__(self, tag, data):
        self._tag = tag
        self._attrib = {}
        self._text = None
        self._children = []

        if isinstance(data, dict):
            for key, value in data.items():
                # Back-compat: explicit @attr and #text markers are still accepted.
                if key.startswith("@"):
                    self._attrib[key[1:]] = _resolve_reference(str(value))
                    continue
                if key == "#text":
                    self._text = _resolve_reference(str(value))
                    continue

                if isinstance(value, dict):
                    self._children.append(JsonConfigElement(key, value))
                elif isinstance(value, list):
                    for item in value:
                        self._children.append(JsonConfigElement(key, item))
                else:
                    # Scalar: expose under both .attrib (XML-attribute access)
                    # and as a child element (XML find() access).
                    resolved = _resolve_reference(str(value)) if value is not None else ""
                    self._attrib[key] = resolved
                    self._children.append(JsonConfigElement(key, value))
        elif isinstance(data, bool):
            self._text = "1" if data else "0"
        elif data is not None:
            self._text = _resolve_reference(str(data))

    @property
    def tag(self):
        return self._tag

    @property
    def text(self):
        return self._text

    @property
    def attrib(self):
        return self._attrib

    def get(self, key, default=None):
        return self._attrib.get(key, default)

    def find(self, path):
        parts = path.replace("./", "").split("/")
        current = self
        for part in parts:
            if not part:
                continue
            match = re.match(r"([\w][\w-]*)\[@([\w][\w_]*)='([^']+)'\]", part)
            if match:
                tag_name, attr_name, attr_value = match.groups()
                found = None
                for child in current._children:
                    if child.tag == tag_name and child._attrib.get(attr_name) == attr_value:
                        found = child
                        break
                current = found
            else:
                found = None
                for child in current._children:
                    if child.tag == part:
                        found = child
                        break
                current = found
            if current is None:
                return None
        return current

    def iter(self, tag):
        if self._tag == tag:
            yield self
        for child in self._children:
            yield from child.iter(tag)

    def __iter__(self):
        return iter(self._children)

    def __bool__(self):
        return True

    def __len__(self):
        return len(self._children)


def parse_config_root(config_file):
    """Parse a configuration file and return its root element.

    Auto-detects format based on file extension (.json or .xml).
    Returns either a JsonConfigElement or an xml.etree.Element.
    """
    if config_file.endswith(".json"):
        with open(config_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict) and "djehuty" in data:
            return JsonConfigElement("djehuty", data["djehuty"])
        return JsonConfigElement("djehuty", data)

    logging.getLogger(__name__).warning(
        "XML configuration is deprecated and will be removed December 2026. "
        "Migrate to JSON (see etc/djehuty/djehuty-example-config.json)."
    )
    tree = ElementTree.parse(config_file)
    return tree.getroot()
