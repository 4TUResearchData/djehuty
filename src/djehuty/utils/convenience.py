"""
This module provides convenience functions that can be used throughout
the codebase.
"""

import logging
import re
from html import escape, unescape
from html.parser import HTMLParser

from djehuty.utils.constants import allowed_html_tags


class HTMLStripper(HTMLParser):
    """Overriden HTMLParser to strip HTML tags inspired by Django's implementation."""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.reset()
        self.state = []

    def handle_data(self, data):
        self.state.append(data)

    def handle_entityref(self, name):
        self.state.append(f"&{name};")

    def handle_charref(self, name):
        self.state.append(f"&#{name};")

    def get_data(self):
        """Return stripped HTML."""
        return "".join(self.state)


def html_to_plaintext(value, respect_newlines=False):
    """
    Outputs plain text without HTML tags.
    When RESPECT_NEWLINES is set to True, it will convert line
    breaks to newline characters.
    """
    if respect_newlines:
        value = value.replace("</p>", "</p>\n\n")
        value = value.replace("<br>", "\n")
        value = value.replace("<br/>", "\n")
        value = value.replace("<br />", "\n")

    while "<" in value and ">" in value:
        tag_count = value.count("<")
        html = HTMLStripper()
        html.feed(value)
        html.close()
        value = html.get_data()
        if tag_count == value.count("<"):
            break

    return value


def contains_disallowed_html(value):
    """Return True when there is a disallowed tag in VALUE, False otherwise."""

    if value is None:
        return False

    stripped_value = unescape(value)
    for tag in allowed_html_tags:
        stripped_value = stripped_value.replace(f"<{tag}>", "")
        stripped_value = stripped_value.replace(f"</{tag}>", "")

    return html_to_plaintext(stripped_value) != stripped_value


def encode_html(value, allow_simple_tags=True, allow_some_punctuation=True):
    """
    Returns VALUE but with encoded HTML entities.  When ALLOW_SIMPLE_TAGS is
    True, it doesn't encode HTML tags in constants.allowed_html_tags.
    """
    encoded_value = escape(value)
    if allow_simple_tags:
        for tag in allowed_html_tags:
            encoded_value = encoded_value.replace(f"&lt;{tag}&gt;", f"<{tag}>")
            encoded_value = encoded_value.replace(f"&lt;/{tag}&gt;", f"</{tag}>")

    if allow_some_punctuation:
        for character in [("&", "&amp;"), ('"', "&quot;"), (" ", "&nbsp;")]:
            encoded_value = encoded_value.replace(character[1], character[0])

    return encoded_value


def value_or(record, key, other):
    """Return the value of KEY or OTHER."""
    try:
        return record[key]
    except (IndexError, KeyError, TypeError):
        return other


def value_or_none(record, key):
    """Return the value of KEY or None."""
    return value_or(record, key, None)


def pretty_print_size(num_bytes):
    """Return pretty-printed file size."""

    output = ""
    if not isinstance(num_bytes, int):
        output = "0B"
    elif num_bytes < 1000:
        output = f"{num_bytes}B"
    elif num_bytes < 1000000:
        output = f"{num_bytes / 1000:.2f}KB"
    elif num_bytes < 1000000000:
        output = f"{num_bytes / 1000000:.2f}MB"
    elif num_bytes < 1000000000000:
        output = f"{num_bytes / 1000000000:.2f}GB"
    elif num_bytes < 1000000000000000:
        output = f"{num_bytes / 1000000000000:.2f}TB"
    else:
        output = f"{num_bytes / 1000000000000000:.2f}PB"

    return output


def opendap_sizes_to_bytes(size, units):
    """Return the bytes for a pretty-printed SIZE with UNITS."""
    output = size

    if units == "Pbytes":
        output = size * 1000000000000000
    elif units == "Tbytes":
        output = size * 1000000000000
    elif units == "Gbytes":
        output = size * 1000000000
    elif units == "Mbytes":
        output = size * 1000000
    elif units == "Kbytes":
        output = size * 1000

    return output


def decimal_coord(raw_input, axis, digits=5):
    """
    Converts txt to string with decimal coordinates or None if invalid.
    Accepts input like "42.597" or "5º 38’ 18.5’’ E".
    axis is 'N' or 'E'
    5 digits is accuracy (RMS) of 40 cm.
    """
    pattern = r"""^(-?\d+)[º°]\s*(\d+)[’']\s*((\d+)(\.\d?)?)((’’)|('')|"|”)\s*([NESW]?)$"""
    if raw_input is not None:
        try:
            deg = float(raw_input)
        except ValueError:
            raw_input = str(raw_input).strip()
            match = re.search(pattern, raw_input)
            if match:
                components = match.groups()
                deg = int(components[0]) + int(components[1]) / 60 + float(components[2]) / 3600
                direction = components[-1]  # direction may be N,E,S,W, axis N,E.
                if (direction == "S" and axis == "N") or (direction == "W" and axis == "E"):
                    deg = -deg
                elif direction not in (axis, ""):
                    return None  # something is wrong, probably mixed up lat and lon
            else:
                return None  # something is wrong, undecipherable gibberish
        arc_rel = deg / 90 if axis == "N" else deg / 180
        if abs(arc_rel) <= 1.0:
            return f"{deg:.{digits}f}"

    return None


def decimal_coords(lat, lon, digits=5):
    """
    Converts raw input lat, lon to decimal coordinats or None if invalid.
    """
    lat_validated = decimal_coord(lat, "N", digits=digits)
    lon_validated = decimal_coord(lon, "E", digits=digits)
    return (lat_validated, lon_validated)


def self_or_value_or_none(record, key):
    """
    Return record[key]['value'] or record[key] or none.
    Use: deal with triples where table2rdf transformed a string into a number.
    """
    if key in record:
        return value_or(record[key], "value", record[key])

    return None


def parses_to_int(input_string):
    """Return True when wrapping in int() would succeed, False otherwise."""
    try:
        int(input_string)
    except (ValueError, TypeError):
        return False

    return True


def deduplicate_list(alist):
    """
    Return deduplicated list, retaining original ordering,
    based on first occurrence of duplicates.
    """
    try:
        return list({item[1]: item[0] for item in list(enumerate(alist))})
    except TypeError:
        logging.error("Wrong type of %s in deduplicate_list", alist)
        return None


def make_citation(
    authors, year, title, version, item_type, doi, publisher="4TU.ResearchData", max_cited_authors=5
):
    """Return citation in standard Datacite format."""
    try:
        auths = [
            {key: val for key, val in author.items() if val} for author in authors
        ]  # remove empty name parts
        citation = "; ".join(
            [
                (
                    f"{author['last_name']}, {author['first_name']}"
                    if not {"first_name", "last_name"} - set(author)
                    else value_or(author, "full_name", "Unknown")
                )
                for author in auths[:max_cited_authors]
            ]
        )
        if authors[max_cited_authors : max_cited_authors + 1]:
            citation += " et. al."
        citation += f" ({year}): {title}"
        if not citation.endswith("."):
            citation += "."
        citation += f" Version {version}. {publisher}. {item_type}. https://doi.org/{doi}"
        return citation
    except TypeError:
        logging.error("could not make citation for %s", doi)
        return None


def custom_field_name(name):
    """Return a predictable name for a custom field."""

    name = name.lower().replace(" ", "_")

    ## Exceptions to the custom field names.
    if name == "licence_remarks":
        name = "license_remarks"
    if name == "geolocation_latitude":
        name = "latitude"
    if name == "geolocation_longitude":
        name = "longitude"

    return name


def is_opendap_url(url):
    """Returns True when URL links to 4TU's OPeNDAP server, False otherwise."""
    try:
        return url.split("/")[2] == "opendap.4tu.nl"
    except (AttributeError, IndexError, KeyError):
        return False


def add_logging_level(level_name, level_number, method_name=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `level_name` becomes an attribute of the `logging` module with the value
    `level_number`. `method_name` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `method_name` is not specified, `level_name.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    not overwrite existing attributes.

    Code copied and adapted from the following Stack Overflow post:
    https://stackoverflow.com/questions/2183233/35804945#35804945
    """
    if not method_name:
        method_name = level_name.lower()

    if (
        hasattr(logging, level_name)
        or hasattr(logging, method_name)
        or hasattr(logging.getLoggerClass(), method_name)
    ):
        return

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(level_number):
            self._log(level_number, message, args, **kwargs)  # pylint: disable=protected-access

    def log_to_root(message, *args, **kwargs):
        logging.log(level_number, message, *args, **kwargs)

    logging.addLevelName(level_number, level_name)
    setattr(logging, level_name, level_number)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)


def landing_page_url(item_id, version=None, item_type="dataset", base_url=""):
    """Returns (a version-specific) URL to an item's landing page."""
    url = f"{base_url}/{item_type}s/{item_id}"
    if version:
        url += f"/{version}"
    return url


def split_author_name(name):
    """Procedure to split name of author into first and last name.
    Works for often occurring name patterns:
    * first_name (initials) last_name
    * first_name I.N.I.T. last_name
    * first_name last_name
    * last_name"""
    name = re.sub(r"\s+", " ", name)
    if ")" in name:
        parts = name.split(")", 1)
        parts[0] += ")"
    elif "." in name:
        parts = name[::-1].split(".", 1)
        parts = [part[::-1] for part in parts][::-1]
        parts[0] += "."
    else:
        parts = name.split(" ", 1)
    parts = [part.strip() for part in parts]
    parts = ([""] + parts)[-2:]
    return parts


def split_string(input_string, delimiter="\\s", is_quoted=False, maxsplit=-1):
    """Splits a string by a delimiter character and strips whitespace."""
    if not isinstance(input_string, str) or input_string == "":
        return None
    if input_string.count(delimiter) == 0:
        return [input_string]
    regex_pattern = re.compile(rf"""((?:[^{delimiter}])+)""")
    if is_quoted:
        regex_pattern = re.compile(rf"""((?:[^{delimiter}"']|"[^"]*"|'[^']*')+)""")
    words = regex_pattern.split(input_string)[1::2]
    if maxsplit == 0:
        return [input_string]
    if 0 < maxsplit < len(words):
        tmp_words = []
        tmp_words = words[:maxsplit]
        tmp_words.append(delimiter.join(words[maxsplit:]))
        words = tmp_words
    words[:] = [word.strip() for word in words]
    words[:] = [word for word in words if word]
    if is_quoted:
        for index, word in enumerate(words):
            if word[0] == word[-1] and word[0] in ['"', "'"]:
                words[index] = word[1:-1]

    return words


def strip_string(input_string):
    """Removes whitespace from the beginning and end of a string."""
    if isinstance(input_string, str):
        return input_string.strip()
    return input_string


def strip_parenthesized_suffix(value):
    """Removes a trailing parenthesized token from VALUE.

    'Surname, N. (nsurname)' -> 'Surname, N.'
    """
    if not isinstance(value, str):
        return value
    stripped = re.sub(r"\s*\([^()]*\)\s*$", "", value).strip()
    return stripped if stripped else value.strip()


def normalize_identifier(value, prefix_url):
    """Procedure to rewrite URLs to URIs."""
    # Don't process invalid entries
    if not isinstance(value, str):
        return None
    # Don't store empty values.
    value = value.strip()
    if value == "":
        return None
    # Strip the URI prefix from identifiers.
    if value.startswith(prefix_url):
        return value[len(prefix_url) :]

    return value


def normalize_orcid(orcid):
    """Procedure to make storing ORCID identifiers consistent."""
    return normalize_identifier(orcid, "https://orcid.org/")


def normalize_doi(doi):
    """Procedure to make storing DOIs consistent."""
    return normalize_identifier(normalize_identifier(doi, "https://doi.org/"), "doi.org/")


def parse_search_terms(search_for):
    """Parse search terms and operators in a string into the structured form
    ``SparqlInterface.datasets``/``collections`` expect for full-text search.

    Framework-neutral extraction of ``ApiServer.parse_search_terms``. A
    non-string value is returned unchanged. Passing the raw string instead of
    this structure makes the full-text filter a no-op (it matches everything).
    """
    if not isinstance(search_for, str):
        return search_for

    search_for = search_for.strip()
    operators_mapping = {"(": "(", ")": ")", "AND": "&&", "OR": "||"}
    operators = operators_mapping.keys()

    fields = ["title", "resource_title", "description", "format", "tag", "organizations"]
    re_field = ":(" + "|".join(fields + ["search_term"]) + "):"

    search_tokens = re.findall(r'[^" ]+|"[^"]+"|\([^)]+\)', search_for)
    search_tokens = [s.strip('"') for s in search_tokens]
    has_operators = any((operator in search_for) for operator in operators)
    has_fieldsearch = re.search(re_field, search_for) is not None

    # Concatenate field name and its following token as one token.
    for idx, token in enumerate(search_tokens):
        if token is None:
            continue
        if re.search(re_field, token) is not None:
            matched = re.split(":", token)[1::2][0]
            if matched in fields:
                try:
                    search_tokens[idx] = f"{token} {search_tokens[idx + 1]}"
                    search_tokens[idx + 1] = None
                except IndexError:
                    return search_for

    search_tokens = [x for x in search_tokens if x is not None]

    # Unpacking this construction to replace AND and OR for && and || results
    # in a query where && is stripped out.
    if has_operators:
        is_parenthesized = False
        lparen_count = search_tokens.count("(")
        rparen_count = search_tokens.count(")")
        if lparen_count > 0 and lparen_count == rparen_count:
            is_parenthesized = True
        for idx, element in enumerate(search_tokens):
            if element in operators:
                if element in ["(", ")"] and not is_parenthesized:
                    continue
                search_tokens[idx] = {"operator": operators_mapping[element]}
    else:
        # No operators found in the search query. Adding OR operators.
        index = -1
        while len(search_tokens) + index > 0:
            search_tokens.insert(index, {"operator": "||"})
            index = index - 2

    for idx, search_term in enumerate(search_tokens):
        if isinstance(search_term, dict):
            continue

        if re.search(re_field, search_term) is not None:
            field_name = re.split(":", search_term)[1::2][0]
            value = list(filter(None, [s.strip() for s in re.split(":", search_term)[0::2]]))[0]

            if field_name in fields:
                search_tokens[idx] = {field_name: value}
            elif field_name == "search_term":
                search_dict = {}
                for field_name in fields:
                    search_dict[field_name] = value
                search_tokens[idx] = search_dict

            field_name = None

        elif has_fieldsearch is False:
            search_dict = {}
            for field in fields:
                search_dict[field] = search_term
            search_tokens[idx] = search_dict

    return search_tokens
