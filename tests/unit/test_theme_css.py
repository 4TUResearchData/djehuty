"""Tests for rendered theme CSS templates."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from djehuty.utils.convenience import css_string

TEMPLATES_DIR = (
    Path(__file__).resolve().parents[2] / "src" / "djehuty" / "web" / "resources" / "html_templates"
)


def render_fonts_css(fonts):
    environment = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    environment.filters["css_string"] = css_string
    template = environment.get_template("fonts.css")

    return template.render(fonts=fonts)


class TestFontsCss:
    def test_renders_font_faces_and_variables(self):
        """Render font faces and configured font-family variables."""
        fonts = {
            "font_faces": [
                {
                    "family": "Example Sans",
                    "src": "/assets/fonts/example-sans.woff2",
                    "format": "woff2",
                    "weight": "400 700",
                    "style": "normal",
                    "display": "swap",
                },
            ],
            "body_font": "'Example Sans', sans-serif",
            "ui_font": "'Example Sans', sans-serif",
            "mono_font": "'Example Mono', monospace",
        }

        css = render_fonts_css(fonts)

        assert "font-family: 'Example Sans';" in css
        assert "src: url('/assets/fonts/example-sans.woff2') format('woff2');" in css
        assert "font-weight: 400 700;" in css
        assert "font-style: normal;" in css
        assert "font-display: swap;" in css
        assert "--font-body: 'Example Sans', sans-serif;" in css
        assert "--font-ui: 'Example Sans', sans-serif;" in css
        assert "--font-mono: 'Example Mono', monospace;" in css

    def test_omits_unspecified_optional_font_properties(self):
        """Omit optional CSS declarations when their values are absent."""
        fonts = {
            "font_faces": [
                {
                    "family": "Example Sans",
                    "src": "/assets/fonts/example-sans.woff2",
                    "format": "woff2",
                    "weight": None,
                    "style": None,
                    "display": None,
                },
            ],
            "body_font": None,
            "ui_font": None,
            "mono_font": None,
        }

        css = render_fonts_css(fonts)

        assert "font-family: 'Example Sans';" in css
        assert "font-weight:" not in css
        assert "font-style:" not in css
        assert "font-display:" not in css
        assert "--font-" not in css

    def test_renders_empty_stylesheet_without_font_configuration(self):
        """Render no CSS when fonts are not configured."""
        assert render_fonts_css(None).strip() == ""
