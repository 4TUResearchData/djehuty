"""
This module provides convenience functions that can be used throughout
the codebase.
"""

import re
import logging

def value_or (record, key, other):
    """Return the value of KEY or OTHER."""
    try:
        return record[key]
    except KeyError:
        return other
    except TypeError:
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

def decimal_coord(raw_input, axis, digits=5):
    '''
    Converts txt to string with decimal coordinates or None if invalid.
    Accepts input like "42.597" or "5º 38’ 18.5’’ E".
    axis is 'N' or 'E'
    5 digits is accuracy (RMS) of 40 cm.
    '''
    pattern = r"""^(-?\d+)º\s*(\d+)[’']\s*((\d+)(\.\d?)?)((’’)|('')|")\s*([NESW]?)$"""
    if raw_input is not None:
        raw_input = str(raw_input) #fix for cases where raw_input is already numerical (bug)
        raw_input = raw_input.strip()
        try:
            deg = float(raw_input)
        except ValueError:
            match = re.search(pattern, raw_input)
            if match:
                components = match.groups()
                deg = int(components[0]) + int(components[1])/60 + float(components[2])/3600
                direction = components[-1] #direction may be N,E,S,W, axis N,E.
                if (direction == 'S' and axis == 'N') or (direction == 'W' and axis == 'E'):
                    deg = -deg
                elif direction != axis:
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
    except ValueError:
        return False
    except TypeError:
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
             else author['full_name']) for author in auths[:max_cited_authors]])
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
    try:
        return url.split("/")[2] == "opendap.4tu.nl"
    except (AttributeError, IndexError, KeyError):
        return False
