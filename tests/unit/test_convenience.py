"""Unit tests for convenience helpers."""

import pytest

from djehuty.utils.convenience import css_string, encode_html, strip_parenthesized_suffix


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


class TestEncodeHtml:
    """Stored string values keep safe punctuation literal, encode markup."""

    def test_apostrophe_is_kept_literal(self):
        assert encode_html("someone's thing") == "someone's thing"

    def test_ampersand_and_double_quotes_pass_through(self):
        assert encode_html('Data & code "quoted"') == 'Data & code "quoted"'

    def test_angle_brackets_are_encoded(self):
        assert encode_html("a < b > c") == "a &lt; b &gt; c"


class TestCssString:
    """CSS-string escaping for values interpolated into single-quoted CSS strings."""

    def test_escapes_backslashes_and_quotes(self):
        assert css_string("O'Brien & Sons") == "O\\'Brien & Sons"
        assert css_string("C:\\fonts") == "C:\\\\fonts"

    def test_escapes_newlines(self):
        assert css_string("Example\nSans") == "Example\\A Sans"
        assert css_string("Example\r\nSans") == "Example\\A Sans"
        assert css_string("Example\rSans") == "Example\\A Sans"
