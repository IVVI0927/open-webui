"""Tests for open_webui/utils/sanitize.py"""

import pytest
from open_webui.utils.sanitize import (
    sanitize_code,
    strip_ansi_codes,
    strip_markdown_code_fences,
)


# ---------------------------------------------------------------------------
# strip_ansi_codes
# ---------------------------------------------------------------------------


class TestStripAnsiCodes:
    def test_color_codes_removed(self):
        assert strip_ansi_codes('\x1b[31mhello\x1b[0m') == 'hello'

    def test_multiple_color_codes_removed(self):
        assert strip_ansi_codes('\x1b[32mgreen\x1b[0m and \x1b[31mred\x1b[0m') == 'green and red'

    def test_plain_text_unchanged(self):
        assert strip_ansi_codes('plain text') == 'plain text'

    def test_empty_string(self):
        assert strip_ansi_codes('') == ''

    def test_cursor_movement_removed(self):
        assert strip_ansi_codes('\x1b[1A\x1b[2J') == ''

    def test_reset_code_removed(self):
        assert strip_ansi_codes('\x1b[39mtext\x1b[0m') == 'text'

    def test_code_with_ansi_preserved_logic(self):
        code = '\x1b[33mprint("hello")\x1b[0m'
        assert strip_ansi_codes(code) == 'print("hello")'


# ---------------------------------------------------------------------------
# strip_markdown_code_fences
# ---------------------------------------------------------------------------


class TestStripMarkdownCodeFences:
    def test_python_fence_removed(self):
        assert strip_markdown_code_fences('```python\nprint("hi")\n```') == 'print("hi")'

    def test_generic_fence_removed(self):
        assert strip_markdown_code_fences('```\ncode\n```') == 'code'

    def test_py_shorthand_fence_removed(self):
        assert strip_markdown_code_fences('```py\nx = 1\n```') == 'x = 1'

    def test_no_fence_unchanged(self):
        assert strip_markdown_code_fences('x = 1') == 'x = 1'

    def test_empty_string(self):
        assert strip_markdown_code_fences('') == ''

    def test_whitespace_trimmed(self):
        assert strip_markdown_code_fences('  ```python\nx = 1\n```  ') == 'x = 1'

    def test_multiline_code_preserved(self):
        code = '```python\ndef foo():\n    return 1\n```'
        assert strip_markdown_code_fences(code) == 'def foo():\n    return 1'

    def test_only_opening_fence(self):
        result = strip_markdown_code_fences('```python\ncode')
        assert '```' not in result
        assert 'code' in result


# ---------------------------------------------------------------------------
# sanitize_code (composed function)
# ---------------------------------------------------------------------------


class TestSanitizeCode:
    def test_strips_ansi_and_fence(self):
        code = '```python\n\x1b[32mprint("hi")\x1b[0m\n```'
        assert sanitize_code(code) == 'print("hi")'

    def test_plain_code_unchanged(self):
        assert sanitize_code('x = 1') == 'x = 1'

    def test_only_ansi_stripped(self):
        assert sanitize_code('\x1b[31mx = 1\x1b[0m') == 'x = 1'

    def test_only_fence_stripped(self):
        assert sanitize_code('```\nx = 1\n```') == 'x = 1'

    def test_empty_string(self):
        assert sanitize_code('') == ''
