"""Unit tests for convenience helpers."""

import pytest

from djehuty.utils.convenience import strip_parenthesized_suffix


class TestStripParenthesizedSuffix:
    """Login names appended by identity providers must be stripped."""

    @pytest.mark.parametrize(
        "value, expected",
        [
            ("Surname, N. (namesurname)", "Surname, N."),
            ("Doe, J.(jdoe)", "Doe, J."),
            ("Doe, J. (jdoe) ", "Doe, J."),
            ("van Doe, J. (jvandoedoe) ", "van Doe, J."),
            ("Jansen, P.", "Jansen, P."),
            ("Robert (Bob) Smith", "Robert (Bob) Smith"),
            ("(jdoe)", "(jdoe)"),
            (" Jansen, P. ", "Jansen, P."),
            ("", ""),
        ],
    )
    def test_strips_only_trailing_parenthesized_token(self, value, expected):
        assert strip_parenthesized_suffix(value) == expected

    @pytest.mark.parametrize("value", [None, 42])
    def test_non_string_values_pass_through(self, value):
        assert strip_parenthesized_suffix(value) is value
