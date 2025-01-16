from ndetect.utils import format_preview_text


def test_format_preview_text_line_limit() -> None:
    text = "Line 1\nLine 2\nLine 3\nLine 4"
    result = format_preview_text(text, max_lines=2, max_chars=100)
    assert result == "Line 1\nLine 2..."


def test_format_preview_text_char_limit() -> None:
    text = "Line 1\nLine 2\nLine 3"
    result = format_preview_text(
        text, max_lines=10, max_chars=10, truncation_marker="..."
    )
    assert result == "Line 1..."


def test_format_preview_text_both_limits() -> None:
    text = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
    result = format_preview_text(
        text, max_lines=3, max_chars=12, truncation_marker="..."
    )
    assert result == "Line 1..."


def test_format_preview_text_empty() -> None:
    assert format_preview_text("", max_lines=3, max_chars=10) == ""


def test_format_preview_text_exact_fit() -> None:
    text = "12345"
    result = format_preview_text(
        text, max_lines=1, max_chars=5, truncation_marker="..."
    )
    assert result == "12345"


def test_format_preview_text_newline_handling() -> None:
    # Test how newlines are handled at truncation points
    text = "abc\ndef\nghi"
    result = format_preview_text(
        text, max_lines=3, max_chars=5, truncation_marker="..."
    )
    assert result == "ab..."


def test_format_preview_text_longer_limit() -> None:
    # With max_chars=20, we can fit multiple complete lines
    text = "Line 1\nLine 2\nLine 3"
    result = format_preview_text(text, max_lines=2, max_chars=20)
    assert result == "Line 1\nLine 2..."


def test_format_preview_text_single_line() -> None:
    # Single line with no truncation needed
    text = "Short"
    result = format_preview_text(text, max_lines=1, max_chars=10)
    assert result == "Short"


def test_format_preview_text_single_line_truncated() -> None:
    # Single line that needs truncation
    text = "This is too long"
    result = format_preview_text(
        text, max_lines=1, max_chars=10, truncation_marker="..."
    )
    assert result == "This is..."
