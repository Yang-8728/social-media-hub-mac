import os
import re


def clean_unicode_path(path: str) -> str:
    if not path:
        return path
    unicode_replacements = {
        '﹨': '\\',
        '∕': '/',
        '⧵': '\\',
        '⁄': '/',
        '／': '/',
        '＼': '\\',
    }
    cleaned_path = path
    for unicode_char, standard_char in unicode_replacements.items():
        cleaned_path = cleaned_path.replace(unicode_char, standard_char)
    return os.path.normpath(cleaned_path)


def ensure_valid_windows_path(path: str) -> str:
    if not path:
        return path
    path = clean_unicode_path(path)
    invalid_chars = r'[<>:"|?*]'
    path = re.sub(invalid_chars, '-', path)
    path_parts = path.split(os.sep)
    cleaned_parts = []
    for part in path_parts:
        if part:
            part = part.rstrip('. ')
            if part:
                cleaned_parts.append(part)
    return os.sep.join(cleaned_parts) if cleaned_parts else path
