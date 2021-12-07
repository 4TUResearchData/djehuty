"""
This module contains procedures to validate user input.
"""

class ValidationException(Exception):
    """Base class for validation errors."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message)

class InvalidIntegerValue(ValidationException):
    """Exception thrown when the 'limit' parameter holds no valid value."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class InvalidOrderDirection(ValidationException):
    """Exception thrown when the 'order_direction' parameter holds no valid value."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class MissingRequiredField(ValidationException):
    """Exception thrown when a required parameter holds no value."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

def order_direction (value, required=False):

    if (value is None and required):
        raise MissingRequiredField(
            message = f"Missing required value for '{field_name}'.",
            code    = "MissingRequiredField")

    if (value is not None and
        (not (value.lower() == "desc" or
              value.lower() == "asc"))):
        raise InvalidOrderDirection(
            message = "The value for 'order_direction' must be either 'desc' or 'asc'.",
            code    = "InvalidOrderDirectionValue")

    return True

def integer_value (value, field_name, minimum_value=None, maximum_value=None, required=False):

    prefix = field_name.capitalize()
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")

        return True

    try:
        value = int(value)
    except Exception as error:
        raise InvalidIntegerValue(
            message = f"The value for '{field_name}' must be an integer.",
            code    = f"Invalid{prefix}Value") from error

    if maximum_value is not None and value > maximum_value:
        raise InvalidIntegerValue(
            message = f"The maximum value for '{field_name}' is {maximum_value}.",
            code    = f"{prefix}ValueTooHigh")

    if minimum_value is not None and value < minimum_value:
        raise InvalidIntegerValue(
            message = f"The minimum value for '{field_name}' is {minimum_value}.",
            code    = f"{prefix}ValueTooLow")

    return True


def limit (value, required=False):
    return integer_value (value, "limit", minimum_value=1, maximum_value=1000, required=required)

def offset (value, required=False):
    return integer_value (value, "offset", required=required)

def institution (value, required=False):
    return integer_value (value, "institution", required=required)

def group (value, required=False):
    return integer_value (value, "group", required=required)

def page (value, required=False):
    return integer_value (value, "page", required=required)

def page_size (value, required=False):
    return integer_value (value, "page_size", required=required)

