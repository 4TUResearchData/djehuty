"""
This module provides convenience functions that can be used throughout
the codebase.
"""

import os
import re
import logging
import mimetypes

def value_or (record, key, other):
    """Return the value of KEY or OTHER."""
    try:
        return record[key]
    except (IndexError, KeyError, TypeError):
        return other

def value_or_none (record, key):
    """Return the value of KEY or None."""
    return value_or (record, key, None)

def pretty_print_size (num_bytes):
    """Return pretty-printed file size."""

    output = ""
    if not isinstance(num_bytes, int):
        output = "0B"
    elif num_bytes < 1000:
        output = f"{num_bytes}B"
    elif num_bytes < 1000000:
        output = f"{num_bytes/1000:.2f}KB"
    elif num_bytes < 1000000000:
        output = f"{num_bytes/1000000:.2f}MB"
    elif num_bytes < 1000000000000:
        output = f"{num_bytes/1000000000:.2f}GB"
    else:
        output = f"{num_bytes/1000000000000:.2f}TB"

    return output

def opendap_sizes_to_bytes (size, units):
    """Return the bytes for a pretty-printed SIZE with UNITS."""
    output = size

    if units == "Tbytes":
        output = size * 1000000000000
    elif units == "Gbytes":
        output = size * 1000000000
    elif units == "Mbytes":
        output = size * 1000000
    elif units == "Kbytes":
        output = size * 1000

    return output

def decimal_coord(raw_input, axis, digits=5):
    '''
    Converts txt to string with decimal coordinates or None if invalid.
    Accepts input like "42.597" or "5º 38’ 18.5’’ E".
    axis is 'N' or 'E'
    5 digits is accuracy (RMS) of 40 cm.
    '''
    pattern = r"""^(-?\d+)[º°]\s*(\d+)[’']\s*((\d+)(\.\d?)?)((’’)|('')|"|”)\s*([NESW]?)$"""
    if raw_input is not None:
        try:
            deg = float(raw_input)
        except ValueError:
            raw_input = str(raw_input).strip()
            match = re.search(pattern, raw_input)
            if match:
                components = match.groups()
                deg = int(components[0]) + int(components[1])/60 + float(components[2])/3600
                direction = components[-1] #direction may be N,E,S,W, axis N,E.
                if (direction == 'S' and axis == 'N') or (direction == 'W' and axis == 'E'):
                    deg = -deg
                elif not direction in (axis, ''):
                    return None #something is wrong, probably mixed up lat and lon
            else:
                return None #something is wrong, undecipherable gibberish
        arc_rel = deg/90 if axis == 'N' else deg/180
        if abs(arc_rel) <= 1.:
            return f'{deg:.{digits}f}'

    return None

def decimal_coords(lat, lon, digits=5):
    '''
    Converts raw input lat, lon to decimal coordinats or None if invalid.
    '''
    lat_validated = decimal_coord(lat, 'N', digits=digits)
    lon_validated = decimal_coord(lon, 'E', digits=digits)
    return (lat_validated, lon_validated)

def self_or_value_or_none(record, key):
    '''
    Return record[key]['value'] or record[key] or none.
    Use: deal with triples where table2rdf transformed a string into a number.
    '''
    if key in record:
        return value_or (record[key], 'value', record[key])

    return None

def parses_to_int (input_string):
    """Return True when wrapping in int() would succeed, False otherwise."""
    try:
        int(input_string)
    except (ValueError, TypeError):
        return False

    return True

def deduplicate_list (alist):
    """
    Return deduplicated list, retaining original ordering,
    based on first occurrence of duplicates.
    """
    try:
        return list({item[1]:item[0] for item in list(enumerate(alist))})
    except TypeError:
        logging.error('Wrong type of %s in deduplicate_list', alist)
        return None

def make_citation (authors, year, title, version, item_type, doi,
                   publisher='4TU.ResearchData', max_cited_authors=5):
    """Return citation in standard Datacite format."""
    try:
        auths = [{key:val for key,val in author.items() if val}
                 for author in authors]   #remove empty name parts
        citation = '; '.join([
            (f"{author['last_name']}, {author['first_name']}" if
             not {'first_name','last_name'}-set(author)
             else value_or (author, 'full_name', "Unknown")) for author in auths[:max_cited_authors]])
        if authors[max_cited_authors:max_cited_authors+1]:
            citation += ' et. al.'
        citation += f' ({year}): {title}'
        if not citation.endswith('.'):
            citation += '.'
        citation += f' Version {version}. {publisher}. {item_type}. https://doi.org/{doi}'
        return citation
    except TypeError:
        logging.error('could not make citation for %s', doi)
        return None

def custom_field_name (name):
    """Return a predicatable name for a custom field."""

    name = name.lower().replace(" ", "_")

    ## Exceptions to the custom field names.
    if name == "licence_remarks":
        name = "license_remarks"
    if name == "geolocation_latitude":
        name = "latitude"
    if name == "geolocation_longitude":
        name = "longitude"

    return name

def is_opendap_url (url):
    """Returns True when URL links to 4TU's OPeNDAP server, False otherwise."""
    try:
        return url.split("/")[2] == "opendap.4tu.nl"
    except (AttributeError, IndexError, KeyError):
        return False

def add_logging_level (level_name, level_number, method_name=None):
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

    if (hasattr(logging, level_name) or
        hasattr(logging, method_name) or
        hasattr(logging.getLoggerClass(), method_name)):
        return

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def log_for_level(self, message, *args, **kwargs):
        if self.isEnabledFor(level_number):
            self._log(level_number, message, args, **kwargs) # pylint: disable=protected-access

    def log_to_root(message, *args, **kwargs):
        logging.log(level_number, message, *args, **kwargs)

    logging.addLevelName(level_number, level_name)
    setattr(logging, level_name, level_number)
    setattr(logging.getLoggerClass(), method_name, log_for_level)
    setattr(logging, method_name, log_to_root)

def landing_page_url (item_id, version=None, item_type="dataset", base_url=""):
    """Returns (a version-specific) URL to an item's landing page."""
    url = f"{base_url}/{item_type}s/{item_id}"
    if version:
        url += f"/{version}"
    return url

def split_author_name(name):
    """ Procedure to split name of author into first and last name.
        Works for often occurring name patterns:
        * first_name (initials) last_name
        * first_name I.N.I.T. last_name
        * first_name last_name
        * last_name """
    name = re.sub(r'\s+', ' ', name)
    if ')' in name:
        parts = name.split(')', 1)
        parts[0] += ')'
    elif '.' in name:
        parts = name[::-1].split('.', 1)
        parts = [part[::-1] for part in parts][::-1]
        parts[0] += '.'
    else:
        parts = name.split(' ', 1)
    parts = [part.strip() for part in parts]
    parts = ([''] + parts)[-2:]
    return parts

def split_string (input_string, delimiter='\\s' , is_quoted=False, maxsplit=-1):
    """Splits a string by a delimiter character and strips whitespace."""
    if not isinstance(input_string, str) or input_string == "":
        return None
    if input_string.count(delimiter) == 0:
        return [input_string]
    regex_pattern = re.compile(fr'''((?:[^{delimiter}])+)''')
    if is_quoted:
        regex_pattern = re.compile(fr'''((?:[^{delimiter}"']|"[^"]*"|'[^']*')+)''')
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

def strip_string (input_string):
    """Removes whitespace from the beginning and end of a string."""
    if isinstance (input_string, str):
        return input_string.strip()
    return input_string

def guess_file_types (dataset_format, files):
    """Guess the file types based on the djht:format and file extensions."""
    guessed_mimetypes = set()
    extensions = set()
    for file in files:
        if "name" not in file:
            continue
        file_extension = os.path.splitext (file["name"])[1]
        if file_extension:
            extensions.add (file_extension.lower())

    if not dataset_format and not extensions:
        return None

    path_resource_etc = os.path.join (os.path.dirname (__file__),
                                      "../web/resources/static/etc")
    mimetypes.init(files=[f"{path_resource_etc}/mime.types",
                          f"{path_resource_etc}/mime.types.override"])

    for extension in extensions:
        guessed_type = mimetypes.guess_type(f"file.{extension}")
        if guessed_type[0] is not None:
            guessed_mimetypes.add(guessed_type[0])

    format_tokens = set()
    if dataset_format:
        format_tokens = set(re.split(r'[\s+;\n\r,:()"\']', dataset_format))
        format_tokens = {token.strip() for token in format_tokens}
        format_tokens = {token for token in format_tokens if token}
        format_tokens = {token.lower() for token in format_tokens}

    for format_token in format_tokens:
        if '://' in format_token: # skip URLs
            continue

        is_guessed = False
        # Is the token a file extension with a leading dot?
        if format_token.startswith('*.') or format_token.startswith('.'):
            if format_token.startswith('*'):
                format_token = format_token[1:]

            guessed_type = mimetypes.guess_type(f"file{format_token}")
            if guessed_type[0] is not None:
                guessed_mimetypes.add(guessed_type[0])
                is_guessed = True
        # Is the token a MIME type?
        elif '/' in format_token:
            guessed_extension = mimetypes.guess_extension(format_token)
            if guessed_extension is not None:
                guessed_mimetypes.add(format_token)
                is_guessed = True

        if is_guessed:
            continue

        # Is the token a non-standard MIME type? i.e. script/m, survey/pdf
        maybe_extensions = set()
        if '/' in format_token:
            extension_tokens = format_token.split('/')
            tokens_set = set()
            if len(extension_tokens) == 2:
                tokens_set.add(extension_tokens[1])
            elif len(extension_tokens) > 2:
                tokens_set = set(extension_tokens)

            for maybe_extension in tokens_set:
                if maybe_extension.startswith('.'):
                    maybe_extension = extension_tokens[1:]
                maybe_extensions.add(f".{maybe_extension}")
        # Is the token a file extension having no leading dot?
        else:
            maybe_extensions.add(f".{format_token}")

        for maybe_extension in maybe_extensions:
            guessed_type = mimetypes.guess_type(f"file.{maybe_extension}")
            if guessed_type[0] is not None:
                guessed_mimetypes.add(guessed_type[0])

    annotation = ""
    if guessed_mimetypes:
        annotation = ";".join(guessed_mimetypes)
    if extensions:
        annotation += ";"
        annotation += ';'.join(extensions)

    return annotation if annotation else None
