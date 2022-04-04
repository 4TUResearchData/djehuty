"""
This module contains procedures to validate user input.
"""

from djehuty.utils import convenience as conv

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

class ValueTooLong(ValidationException):
    """Exception thrown when a string parameter is too long."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class ValueTooShort(ValidationException):
    """Exception thrown when a string parameter is too short."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class InvalidValueType(ValidationException):
    """Exception thrown when the wrong type of a value was given."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class InvalidValue(ValidationException):
    """Exception thrown when the wrong value was given."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class InvalidOptionsValue(ValidationException):
    """Exception thrown when the wrong type of a value was given."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

class InvalidPagingOptions(ValidationException):
    """Exception thrown when paging is mixed with limit/offset."""

    def __init__(self, message, code):
        self.message = message
        self.code    = code
        super().__init__(message, code)

def order_direction (value, required=False):
    """Validation procedure for the order direction field."""

    if (value is None and required):
        raise MissingRequiredField(
            message = "Missing required value for 'order_direction'.",
            code    = "MissingRequiredField")

    if (value is not None and
        (not (value.lower() == "desc" or
              value.lower() == "asc"))):
        raise InvalidOrderDirection(
            message = "The value for 'order_direction' must be either 'desc' or 'asc'.",
            code    = "InvalidOrderDirectionValue")

    return True

def integer_value (record, field_name, minimum_value=None, maximum_value=None, required=False):
    """Validation procedure for integer values."""

    value = conv.value_or_none (record, field_name)
    prefix = field_name.capitalize() if isinstance(field_name, str) else ""
    if value is None or (isinstance(value, str) and value == ""):
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")

        return None

    try:
        value = int(value)

        if maximum_value is not None and value > maximum_value:
            raise InvalidIntegerValue(
                message = f"The maximum value for '{field_name}' is {maximum_value}.",
                code    = f"{prefix}ValueTooHigh")

        if minimum_value is not None and value < minimum_value:
            raise InvalidIntegerValue(
                message = f"The minimum value for '{field_name}' is {minimum_value}.",
                code    = f"{prefix}ValueTooLow")

        return value

    except Exception as error:
        raise InvalidIntegerValue(
            message = f"Unexpected value '{value}' is not an integer.",
            code    = f"Invalid{prefix}Value") from error


def paging_to_offset_and_limit (record):
    """Procedure returns two values: offset and limit."""

    # Type and range-check the parameters.
    page      = integer_value (record, "page",      1)
    page_size = integer_value (record, "page_size", 1, 1000)
    offset    = integer_value (record, "offset",    0)
    limit     = integer_value (record, "limit",     1)

    # Check whether the parameters are mixed.
    if ((page is not None or page_size is not None) and
        (offset is not None or limit is not None)):
        raise InvalidPagingOptions(
            message = ("Either use page/page-size or offset/limit. "
                       "Mixing is not supported."),
            code    = "InvalidPagingOptions")

    # Translate page/page_size to offset/limit.
    if page is not None and page_size is not None:
        offset = page_size * (page - 1)
        limit  = page_size

    return offset, limit

def limit (value, required=False):
    """Validation procedure for the limit parameter."""
    return integer_value (value, "limit", minimum_value=1, maximum_value=1000, required=required)

def offset (value, required=False):
    """Validation procedure for the offset parameter."""
    return integer_value (value, "offset", required=required)

def institution (value, required=False):
    """Validation procedure for the institution parameter."""
    return integer_value (value, "institution", required=required)

def group (value, required=False):
    """Validation procedure for the group parameter."""
    return integer_value (value, "group", required=required)

def page (value, required=False):
    """Validation procedure for the page parameter."""
    return integer_value (value, "page", required=required)

def page_size (value, required=False):
    """Validation procedure for the page_size parameter."""
    return integer_value (value, "page_size", required=required)

def index_exists (value, index):
    """Procedure to test whether a list or string has a certain length."""

    try:
        value[index]
    except IndexError:
        return False

    return True

def string_value (record, field_name, minimum_length=0, maximum_length=None, required=False):
    """Validation procedure for string values."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return value

    if not isinstance (value, str):
        raise InvalidValueType(
                message = f"Expected a string for '{field_name}'.",
                code    = "WrongValueType")

    if maximum_length is not None and index_exists (value, maximum_length):
        raise ValueTooLong(
            message = f"The value for '{field_name}' is longer than {maximum_length}.",
            code    = "ValueTooLong")

    minimum_length = max(minimum_length, 1)
    if not index_exists (value, minimum_length - 1):
        raise ValueTooShort(
            message = f"The value for '{field_name}' needs to be longer than {minimum_length}.",
            code    = "ValueTooShort")

    return value

def boolean_value (record, field_name, required=False):
    """Validation procedure for boolean values."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return value

    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False

    if not isinstance (value, bool):
        raise InvalidValueType(
            message = f"Expected a boolean value for '{field_name}'.",
            code    = "WrongValueType")

    return value

def options_value (record, field_name, options, required=False):
    """Validation procedure for pre-defined options fields."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return value

    if value not in options:
        raise InvalidOptionsValue(
            message = f"Invalid value for '{field_name}'. It must be one of {options}",
            code    = "InvalidValue")

    return value

def __typed_value (record, field_name, expected_type=None, type_name=None, required=False):
    """Procedure to validate multiple-values fields."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return value

    if not isinstance (value, expected_type):
        raise InvalidValueType(
                message = f"Expected {type_name} for '{field_name}'.",
                code    = "WrongValueType")

    return value

def array_value (value, field_name, required=False):
    """Validation procedure for array values."""
    return __typed_value (value, field_name, list, "array", required)

def object_value (value, field_name, required=False):
    """Validation procedure for object values."""
    return __typed_value (value, field_name, dict, "object", required)
