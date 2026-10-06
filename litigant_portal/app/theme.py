"""Theme colours from src/main.css, and WCAG contrast ratios between them.

The Accessibility page measures our own palette, so it reads the colour
tokens straight from the Tailwind theme rather than keeping a copy that
could drift when the palette changes.
"""

import math
import re

from django.conf import settings

THEME_CSS = settings.BASE_DIR / "app" / "src" / "main.css"

_COLOR_TOKEN = re.compile(r"--color-([a-z]+-\d+):\s*(#[0-9a-fA-F]{3,6})\b")

# Tailwind provides these without a theme token.
_BUILT_IN_COLORS = {"white": "#ffffff", "black": "#000000"}


def theme_colors() -> dict[str, str]:
    """Map each theme colour token to its hex value: {"greyscale-900": "#1c1814"}.

    Read on every call, not cached, so a palette edit shows up on the next
    page load without a server restart.
    """
    css = THEME_CSS.read_text()
    tokens = {name: value.lower() for name, value in _COLOR_TOKEN.findall(css)}
    return {**_BUILT_IN_COLORS, **tokens}


def contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.2 contrast ratio between two hex colours, from 1.0 to 21.0.

    Rounded down to two decimals, never up: WCAG thresholds are strict, so
    4.497 must not display as a passing 4.50.
    https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio
    """
    lighter, darker = sorted(
        (_relative_luminance(foreground), _relative_luminance(background)),
        reverse=True,
    )
    return math.floor((lighter + 0.05) / (darker + 0.05) * 100) / 100


def contrast_level(ratio: float) -> str:
    """The highest WCAG text level a contrast ratio meets.

    7:1 is AAA (1.4.6), 4.5:1 is AA (1.4.3), and 3:1 meets AA only for
    large text (18pt, or 14pt bold).
    """
    if ratio >= 7:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3:
        return "AA large text"
    return "Fail"


def _relative_luminance(hex_color: str) -> float:
    """https://www.w3.org/TR/WCAG22/#dfn-relative-luminance"""
    digits = hex_color.lstrip("#")
    if len(digits) == 3:
        digits = "".join(digit * 2 for digit in digits)
    red, green, blue = (
        _linear_channel(int(digits[i : i + 2], 16) / 255) for i in (0, 2, 4)
    )
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _linear_channel(value: float) -> float:
    if value <= 0.04045:
        return value / 12.92
    return ((value + 0.055) / 1.055) ** 2.4
