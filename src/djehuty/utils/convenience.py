"""
This module provides convenience functions that can be used throughout
the codebase.
"""

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

def to_camel (name):
    """Return a camel-casing string for a snake-casing string."""
    splitted = name.split("_")
    output = ""
    for part in splitted:
        output += part.capitalize()

    return output

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

def decimal_coord(txt, axis, digits=4):
    '''
    Converts txt to string with decimal coordinates or None if invalid.
    Accepts input like "42.597" or "5º 38’ 18.5’’ E".
    axis is 'N' or 'E'
    '''
    pat = r"^(-?\d+)º\s*(\d+)[’']\s*((\d+)(\.\d?)?)[’']{2}\s*([NESW]?)$"
    if txt is None:
        return None
    txt = txt.strip()
    deg = None
    ax = None
    try:
        deg = float(txt)
        ax = ''
    except:
        match = re.search(pat, txt)
        if match:
            g = match.groups()
            deg = int(g[0]) + int(g[1])/60 + float(g[2])/3600
            ax = g[-1]
            if ax:
                if ax in 'SW':
                    deg = - deg
                    ax = 'N' if ax == 'S' else 'E'
    if ax in (axis, ''):
        arc_rel = deg/90 if axis == 'N' else deg/180
        if abs(arc_rel) <= 1.:
            return f'{deg:.{digits}f}'

def decimal_coords(lat, lon, digits=4):
    '''
    Converts strings lat, lon to decimal coordinats or None if invalid.
    '''
    lat_validated = decimal_coord(lat, 'N', digits=digits)
    lon_validated = decimal_coord(lon, 'E', digits=digits)
    return (lat_validated, lon_validated)
