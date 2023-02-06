"""
This module tests the validator procedures.
"""

import unittest
from djehuty.web import validator

class TestValidatorFunctionality(unittest.TestCase):
    """Class to test the validator procedures."""

    def __init__(self, *args, **kwargs):
        super(TestValidatorFunctionality, self).__init__(*args, **kwargs)

    def test_string_validator (self):
        """Tests validating strings."""

        record = {
            "one": '"Hello world"',
            "two": 12345,
            "three": ["Hello"],
            "four": None,
            "five": ""
        }

        with self.assertRaises(validator.ValueTooLong):
            validator.string_value (
                record, "one",
                minimum_length=0,
                maximum_length=3)

        with self.assertRaises(validator.ValueTooShort):
            validator.string_value (
                record, "one",
                minimum_length=32)

        with self.assertRaises(validator.MissingRequiredField):
            validator.string_value (record, "four", required=True)

        output = validator.string_value (record, "one")
        self.assertEqual (output, "\"Hello world\"")

        errors = []
        validator.string_value (record, "one", error_list=errors)
        validator.string_value (record, "two", error_list=errors)
        validator.string_value (record, "three", error_list=errors)
        validator.string_value (record, "four", required=True, error_list=errors)

        self.assertEqual (len(errors), 3)
        self.assertIsNone (validator.string_value (record, "four"))
        self.assertEqual ("", validator.string_value (record, "five"))

    def test_numeric_validator (self):
        """Tests validating numbers."""

        record = {
            "number-1": "123456",
            "number-2": "16",
            "number-3": 12345678,
            "number-4": "not-a-number",
            "number-5": None,
        }
        with self.assertRaises(validator.InvalidIntegerValue):
            validator.integer_value (
                record, "number-1",
                minimum_value = 0,
                maximum_value = 16,
                required      = False)

        with self.assertRaises(validator.InvalidIntegerValue):
            validator.integer_value (
                record, "number-2",
                minimum_value = 17,
                maximum_value = 250,
                required      = False)

        with self.assertRaises(validator.InvalidIntegerValue):
            validator.integer_value (
                record, "number-4",
                minimum_value = 16,
                maximum_value = 250,
                required      = False)

        with self.assertRaises(validator.MissingRequiredField):
            validator.integer_value (record, "number-5", required=True)

        output = validator.integer_value (record, "number-1")
        self.assertEqual (output, 123456)

        output = validator.integer_value (record, "number-3")
        self.assertEqual (output, 12345678)

        output = validator.integer_value (record, "number-2",
                                          minimum_value=16,
                                          maximum_value=16)
        self.assertEqual (output, 16)

        errors = []
        validator.integer_value (record, "number-1", error_list=errors)
        validator.integer_value (record, "number-2", error_list=errors)
        validator.integer_value (record, "number-3", error_list=errors)
        validator.integer_value (record, "number-5", required=True, error_list=errors)

        self.assertEqual (len(errors), 1)

    def test_date_validator (self):
        """Tests date and time validators."""

        record = {
            "date-1": "2022-01-01",
            "date-2": 12345678,
            "date-3": "2022-01-01T01:01:01+00:00",
            "date-4": "2022-01-01 01:02:03",
            "date-5": "1234567890"
        }

        with self.assertRaises (validator.MissingRequiredField):
            validator.date_value (record, "date-6", required=True)

        with self.assertRaises (validator.InvalidValueType):
            validator.date_value (record, "date-2")

        errors = []
        validator.date_value (record, "date-1", error_list=errors)
        validator.date_value (record, "date-2", error_list=errors)
        validator.date_value (record, "date-3", error_list=errors)
        validator.date_value (record, "date-4", error_list=errors)
        validator.date_value (record, "date-5", error_list=errors)
        self.assertEqual(len(errors), 4)
        self.assertEqual (record["date-1"], validator.date_value (record, "date-1"))
        self.assertEqual (None, validator.date_value (record, "date-6"))

    def test_boolean_validator (self):
        """Tests boolean validator."""

        record = {
            "one": True, "two": False,
            "three": "true", "four": "false",
            "five": []
        }

        self.assertEqual (None, validator.boolean_value (record, "seven"))
        self.assertTrue (validator.boolean_value (record, "one"))
        self.assertTrue (validator.boolean_value (record, "three"))
        self.assertFalse (validator.boolean_value (record, "two"))
        self.assertFalse (validator.boolean_value (record, "four"))

        with self.assertRaises (validator.MissingRequiredField):
            validator.boolean_value (record, "six", required=True)

        with self.assertRaises (validator.InvalidValueType):
            validator.boolean_value (record, "five")
    def test_list_validator (self):
        """Tests list and array validators."""

        record = {
            "one": [ 1, 2, 3, 4 ],
            "two": { "1": 2, "3": 4 }
        }

        with self.assertRaises (validator.MissingRequiredField):
            validator.array_value (record, "three", required=True)

        with self.assertRaises (validator.InvalidValueType):
            validator.array_value (record, "two")

        with self.assertRaises (validator.MissingRequiredField):
            validator.array_value (record, "four", required=True)

        self.assertEqual (None, validator.array_value (record, "three"))
        self.assertEqual (None, validator.object_value (record, "four"))
        self.assertEqual (record["one"], validator.array_value (record, "one"))
        self.assertEqual (record["two"], validator.object_value (record, "two"))

    def test_options_validator (self):
        """Tests the pre-defined values validator."""

        record = {
            "one": "software",
            "two": None,
            "three": "something-else"
        }
        options = [ "software", "dataset" ]
        with self.assertRaises(validator.MissingRequiredField):
            validator.options_value (record, "two", options, required=True)

        with self.assertRaises(validator.InvalidOptionsValue):
            validator.options_value (record, "three", options)

        output = validator.options_value (record, "one", options, required=True)
        self.assertEqual (output, "software")
        self.assertEqual (None, validator.options_value (record, "five", options))

    def test_paging_validator (self):
        """Tests order and paging validators."""

        record = { "page": 3, "page_size": 15 }
        offset, limit = validator.paging_to_offset_and_limit (record)

        self.assertEqual (offset, 30)
        self.assertEqual (limit, 15)

        record = { "page": 1, "offset": 15 }
        with self.assertRaises (validator.InvalidPagingOptions):
            offset, limit = validator.paging_to_offset_and_limit (record)

        record = { "order": "title", "order_direction": "desc", "id": None }
        output = validator.order_direction (record, "order_direction")
        self.assertEqual (output, "desc")

        with self.assertRaises (validator.InvalidOrderDirection):
            validator.order_direction (record, "order")

        with self.assertRaises (validator.MissingRequiredField):
            validator.order_direction (record, "id", required=True)

    def test_uuid (self):
        """Tests the UUID values validator."""
        self.assertFalse (validator.is_valid_uuid ("00000-00000-00000-00000-00000"))
        self.assertFalse (validator.is_valid_uuid ("00000000-0000-0000-0000-000000000000"))
        self.assertFalse (validator.is_valid_uuid (123456789))
        self.assertFalse (validator.is_valid_uuid ("00514bea-360d-4955-ac171-629168e04e61"))
        self.assertTrue  (validator.is_valid_uuid ("0013272c-d233-4be7-8864-2426ac792e6a"))

    def test_url (self):
        """Tests the URL values validator."""

        url = "https://data.4tu.nl"
        record = { "1": url, "2": 123, "3": "javascript:onclick('alert()')" }
        self.assertEqual (url, validator.url_value (record, "1"))

        with self.assertRaises (validator.InvalidValueType):
            validator.url_value (record, "2")

        with self.assertRaises (validator.InvalidValueType):
            validator.url_value (record, "3")
