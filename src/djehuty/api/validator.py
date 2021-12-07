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

def index_exists (value, index):
    try:
        char = value[index]
    except IndexError as error:
        return False

    return True

def string_field (value, field_name, minimum_length=None, maximum_length=None, required=False):

    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return True

    if index_exists (value, maximum_length):
        raise ValueTooLong(
            message = f"The value for '{field_name}' is longer than {maximum_length}.",
            code    = "ValueTooLong")

    if minumum_length < 1:
        minimum_length = 1

    if not index_exists (value, minimum_length - 1):
        raise ValueTooShort(
            message = f"The value for '{field_name}' needs to be longer than {minimum_length}.",
            code    = "ValueTooShort")

    return True

def __typed_field (value, field_name, expected_type=None, type_name=None, required=False):
    if value is None:
        if required:
            raise MissingRequiredField(
                message = f"Missing required value for '{field_name}'.",
                code    = "MissingRequiredField")
        return True

    if not isinstance (value, expected_type):
        raise InvalidValueType(
                message = f"Expected {type_name} for '{field_name}'.",
                code    = "WrongValueType")

    return True

def array_field (value, field_name, required=False):
    return __typed_field (value, field_name, list, "array", required)

def object_field (value, field_name, required=False):
    return __typed_field (value, field_name, dict, "object", required)
