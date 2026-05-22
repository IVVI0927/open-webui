from open_webui.utils.sanitize import sanitize_code


def test_sanitize_code_strips_markdown_fence_and_ansi_codes():
    code = '```python\n\x1b[32mprint("hello")\x1b[0m\n```'

    assert sanitize_code(code) == 'print("hello")'
