"""
This module contains procedures to validate user input.
"""

class ValidationException(Exception):
    """Base class for validation errors."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code

class InvalidIntegerValue(ValidationException):
    """Exception thrown when the 'limit' parameter holds no valid value."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code

class InvalidOrderDirection(ValidationException):
    """Exception thrown when the 'order_direction' parameter holds no valid value."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code

def order_direction (value):
    if (value is not None and
        (not (value.lower() == "desc" or
              value.lower() == "asc"))):
        raise InvalidOrderDirection(
            message = "The value for 'order_direction' must be either 'desc' or 'asc'.",
            code    = "InvalidOrderDirectionValue")

    return True

def integer_value (value, field_name, minimum_value=None, maximum_value=None):

    prefix = field_name.capitalize()
    if value is None:
        return True

    try:
        value = int(value)
    except:
        raise InvalidIntegerValue(
            message = f"The value for '{field_name}' must be an integer.",
            code    = f"Invalid{prefix}Value")

    if maximum_value is not None and value > maximum_value:
        raise InvalidIntegerValue(
            message = f"The maximum value for '{field_name}' is {maximum_value}.",
            code    = f"{prefix}ValueTooHigh")

    if minimum_value is not None and value < minimum_value:
        raise InvalidIntegerValue(
            message = f"The minimum value for '{field_name}' is {minimum_value}.",
            code    = f"{prefix}ValueTooLow")

    return True


def limit (value):
    return integer_value (value, "limit", minimum_value=1, maximum_value=1000)

def offset (value):
    return integer_value (value, "offset")

def institution (value):
    return integer_value (value, "institution")

def group (value):
    return integer_value (value, "group")

def page (value):
    return integer_value (value, "page")

def page_size (value):
    return integer_value (value, "page_size")
