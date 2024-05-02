"""
This module contains procedures to validate user input.
"""

import re
from djehuty.utils import convenience as conv

def raise_or_return_error (error_list, error):
    """Adds the error to the ERROR_LIST or raises ERROR."""

    if error_list is None:
        raise error

    error_list.append ({ "field_name": error.field_name, "message": error.message })

class ValidationException(Exception):
    """Base class for validation errors."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(message)

class InvalidIntegerValue(ValidationException):
    """Exception thrown when the 'limit' parameter holds no valid value."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class InvalidOrderDirection(ValidationException):
    """Exception thrown when the 'order_direction' parameter holds no valid value."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class MissingRequiredField(ValidationException):
    """Exception thrown when a required parameter holds no value."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class ValueTooLong(ValidationException):
    """Exception thrown when a string parameter is too long."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class ValueTooShort(ValidationException):
    """Exception thrown when a string parameter is too short."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class InvalidValueType(ValidationException):
    """Exception thrown when the wrong type of a value was given."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class InvalidValue(ValidationException):
    """Exception thrown when the wrong value was given."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class InvalidOptionsValue(ValidationException):
    """Exception thrown when the wrong type of a value was given."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

class InvalidPagingOptions(ValidationException):
    """Exception thrown when paging is mixed with limit/offset."""

    def __init__(self, field_name, message, code):
        self.field_name = field_name
        self.message = message
        self.code    = code
        super().__init__(field_name, message, code)

def order_direction (record, field_name, required=False, error_list=None):
    """Validation procedure for the order direction field."""

    value = conv.value_or_none (record, field_name)
    if (value is None and required):
        return raise_or_return_error (error_list,
                    MissingRequiredField(
                        field_name = field_name,
                        message = "Missing required value for 'order_direction'.",
                        code    = "MissingRequiredField"))

    if (value is not None and
        (not (value.lower() == "desc" or
              value.lower() == "asc"))):
        return raise_or_return_error (error_list,
                    InvalidOrderDirection(
                        field_name = field_name,
                        message = "The value for 'order_direction' must be either 'desc' or 'asc'.",
                        code    = "InvalidOrderDirectionValue"))

    return value

def integer_value (record, field_name, minimum_value=None, maximum_value=None, required=False, error_list=None):
    """Validation procedure for integer values."""

    value   = conv.value_or_none (record, field_name)
    prefix  = field_name.capitalize() if isinstance(field_name, str) else ""

    if value is None or (isinstance(value, str) and value == ""):
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return None

    try:
        value = int(value)

        if maximum_value is not None and value > maximum_value:
            return raise_or_return_error (error_list,
                        InvalidIntegerValue(
                            field_name = field_name,
                            message = f"The maximum value for '{field_name}' is {maximum_value}.",
                            code    = f"{prefix}ValueTooHigh"))

        if minimum_value is not None and value < minimum_value:
            return raise_or_return_error (error_list,
                        InvalidIntegerValue(
                            field_name = field_name,
                            message = f"The minimum value for '{field_name}' is {minimum_value}.",
                            code    = f"{prefix}ValueTooLow"))

    except (ValueError, TypeError):
        return raise_or_return_error (error_list,
                    InvalidIntegerValue(
                        field_name = field_name,
                        message = f"Unexpected value '{value}' is not an integer.",
                        code    = f"Invalid{prefix}Value"))

    return value

def paging_to_offset_and_limit (record, error_list=None):
    """Procedure returns two values: offset and limit."""

    # Type and range-check the parameters.
    page      = integer_value (record, "page",      1)
    page_size = integer_value (record, "page_size", 1, 1000)
    offset    = integer_value (record, "offset",    0)
    limit     = integer_value (record, "limit",     1)

    # Check whether the parameters are mixed.
    if ((page is not None or page_size is not None) and
        (offset is not None or limit is not None)):
        return raise_or_return_error (error_list,
            InvalidPagingOptions(
                field_name = "page_size",
                message = ("Either use page/page-size or offset/limit. "
                           "Mixing is not supported."),
                code    = "InvalidPagingOptions"))

    # Translate page/page_size to offset/limit.
    if page is not None and page_size is not None:
        offset = page_size * (page - 1)
        limit  = page_size

    return offset, limit

def institution (value, required=False):
    """Validation procedure for the institution parameter."""
    return integer_value (value, "institution", required=required)

def group (value, required=False):
    """Validation procedure for the group parameter."""
    return integer_value (value, "group", required=required)

def search_filters (value, error_list=None):
    """Validation procedure for the search_filters parameter."""

    if value is None:
        return None

    __typed_value (value, "scopes",      list, "list",   error_list=error_list)
    __typed_value (value, "formats",     list, "list",   error_list=error_list)
    __typed_value (value, "operator",    str,  "string", error_list=error_list)
    __typed_value (value, "institution", str,  "string", error_list=error_list)

    for k, v in value.items():
        if k == "scopes":
            for elem in v:
                string_value ({ "value": elem }, "value", 1, 20, required=True)
                if elem not in ["title", "description", "tag"]:
                    return raise_or_return_error (error_list,
                                InvalidValue(
                                    field_name = "search_filters",
                                    message = "Invalid value in 'scopes'.",
                                    code    = "InvalidValue"))
        elif k == "formats":
            for elem in v:
                string_value ({ "value": elem }, "value", 1, 20, required=True)

        elif k == "institution":
            string_value ({ "value": v }, "value", 1, 50, required=True)

        elif k == "operator":
            string_value ({ "value": v }, "value", 1, 5, required=True)
            if v not in ["and", "or", "exact"]:
                return raise_or_return_error (error_list,
                            InvalidValueType(
                                field_name = "search_filters",
                                message = "Invalid value in 'operator'.",
                                code    = "WrongValueType"))

        else:
            return raise_or_return_error (error_list,
                        InvalidValue(
                            field_name = "search_filters",
                            message = f"Invalid key '{k}' in 'search_filters'.",
                            code    = "InvalidValue"))

    return value

def index_exists (value, index):
    """Procedure to test whether a list or string has a certain length."""

    try:
        value[index]
    except IndexError:
        return False

    return True

def string_value (record, field_name, minimum_length=0, maximum_length=None, required=False, error_list=None):
    """Validation procedure for string values."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return value

    if not isinstance (value, str):
        return raise_or_return_error (error_list,
                    InvalidValueType(
                        field_name = field_name,
                        message = f"Expected a string for '{field_name}'.",
                        code    = "WrongValueType"))

    if maximum_length is not None and index_exists (value, maximum_length):
        return raise_or_return_error (error_list,
                    ValueTooLong(
                        field_name = field_name,
                        message = f"The value for '{field_name}' is longer than {maximum_length}.",
                        code    = "ValueTooLong"))

    if minimum_length == 0 and value == "":
        return value

    minimum_length = max(minimum_length, 1)
    if not index_exists (value, minimum_length - 1):
        return raise_or_return_error (error_list,
                    ValueTooShort(
                        field_name = field_name,
                        message = f"The value for '{field_name}' needs to be longer than {minimum_length}.",
                        code    = "ValueTooShort"))

    return value

def url_value (record, field_name, required=False, error_list=None):
    """Validation procedure for URL values."""

    value = string_value (record, field_name, required=required, error_list=error_list)
    if is_valid_url (value):
        return value

    return raise_or_return_error (error_list,
                InvalidValueType(
                    field_name = field_name,
                    message = f"Expected a URL for '{field_name}'.",
                    code    = "WrongValueFormat"))

def date_value (record, field_name, required=False, error_list=None):
    """Validation procedure for date values."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return None

    if not isinstance (value, str):
        return raise_or_return_error (error_list,
                    InvalidValueType(
                        field_name = field_name,
                        message = f"Expected '{field_name}' in the form YYYY-MM-DD.",
                        code    = "WrongValueType"))

    ## Don't process input that is too long.
    try:
        if value[10]:
            return raise_or_return_error (error_list,
                        InvalidValueType(
                            field_name = field_name,
                            message = f"Expected '{field_name}' in the form YYYY-MM-DD.",
                            code    = "ValueTooLong"))
    except IndexError:
        pass

    ## Check its form.
    pattern = "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
    if re.match(pattern, value) is None:
        return raise_or_return_error (error_list,
                    InvalidValueType(
                        field_name = field_name,
                        message = f"Expected '{field_name}' in the form YYYY-MM-DD.",
                        code    = "WrongValueFormat"))

    return value

def boolean_value (record, field_name, required=False, when_none=None, error_list=None):
    """Validation procedure for boolean values."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return when_none

    if value in (0, 1):
        value = bool(value)

    if isinstance(value, str):
        if value.lower() == "true":
            value = True
        elif value.lower() == "false":
            value = False

    if not isinstance (value, bool):
        return raise_or_return_error (error_list,
                    InvalidValueType(
                        field_name = field_name,
                        message = f"Expected a boolean value for '{field_name}'.",
                        code    = "WrongValueType"))

    return value

def options_value (record, field_name, options, required=False, error_list=None):
    """Validation procedure for pre-defined options fields."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return value

    if value not in options:
        return raise_or_return_error (error_list,
                    InvalidOptionsValue(
                        field_name = field_name,
                        message = f"Invalid value for '{field_name}'. It must be one of {options}",
                        code    = "InvalidValue"))

    return value

def __typed_value (record, field_name, expected_type=None, type_name=None, required=False, error_list=None):
    """Procedure to validate multiple-values fields."""

    value = conv.value_or_none (record, field_name)
    if value is None:
        if required:
            return raise_or_return_error (error_list,
                        MissingRequiredField(
                            field_name = field_name,
                            message = f"Missing required value for '{field_name}'.",
                            code    = "MissingRequiredField"))
        return value

    if not isinstance (value, expected_type):
        return raise_or_return_error (error_list,
                    InvalidValueType(
                        field_name = field_name,
                        message = f"Expected {type_name} for '{field_name}'.",
                        code    = "WrongValueType"))

    return value

def array_value (value, field_name, required=False, error_list=None):
    """Validation procedure for array values."""
    return __typed_value (value, field_name, list, "array", required, error_list)

def object_value (value, field_name, required=False, error_list=None):
    """Validation procedure for object values."""
    return __typed_value (value, field_name, dict, "object", required, error_list)

def string_fits_pattern (value, max_length, pattern):
    """Returns True when VALUE is a string and not longer than MAX_LENGTH."""

    ## Accept strings only.
    if not isinstance(value, str):
        return False

    ## Don't process input that is too long.
    try:
        if value[max_length]:
            return False
    except IndexError:
        pass

    ## Check its form.
    if re.match(pattern, value) is None:
        return False

    return True

def is_valid_uuid (value):
    """Returns True when VALUE looks like a UUID, False otherwise."""
    return string_fits_pattern (value, 36, "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")

def is_valid_url (value):
    """Returns True when VALUE looks like a URL, False otherwise."""
    return string_fits_pattern (value, 1024, "^(https?|ftps?)://[-a-zA-Z0-9@:%._\\+~#?&//=]{2,1024}$")

dataset_types = [
    "figure", "online resource", "preprint", "book",
    "conference contribution", "media", "dataset",
    "poster", "journal contribution", "presentation",
    "thesis", "software"
]

embargo_types = [ "file", "article" ]
