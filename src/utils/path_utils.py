"""
路径工具模块
处理路径相关的常见问题

⚠️ 重要：Windows下的Unicode路径分隔符问题
某些库（如instaloader）可能使用Unicode分隔符字符而不是标准的 \ 或 /
这会导致文件被保存到错误的位置，必须在所有路径操作前进行清理！

经验教训：任何文件/文件夹创建操作都要首先考虑Unicode路径问题！
"""
import os
import re


def clean_unicode_path(path: str) -> str:
    """
    清理路径中的Unicode字符，确保使用标准路径分隔符
    
    常见问题字符：
    - ﹨ (U+FE68) Small Reverse Solidus -> \
    - ∕ (U+2215) Division Slash -> /
    - ⧵ (U+29F5) Reverse Solidus Operator -> \
    """
    if not path:
        return path
        
    # 替换Unicode路径分隔符为标准分隔符
    unicode_replacements = {
        '﹨': '\\',    # Small Reverse Solidus
        '∕': '/',      # Division Slash  
        '⧵': '\\',     # Reverse Solidus Operator
        '⁄': '/',      # Fraction Slash
        '／': '/',     # Fullwidth Solidus
        '＼': '\\',    # Fullwidth Reverse Solidus
    }
    
    cleaned_path = path
    for unicode_char, standard_char in unicode_replacements.items():
        cleaned_path = cleaned_path.replace(unicode_char, standard_char)
    
    # 标准化路径
    cleaned_path = os.path.normpath(cleaned_path)
    
    return cleaned_path


def ensure_valid_windows_path(path: str) -> str:
    """
    确保路径在Windows下有效
    """
    if not path:
        return path
        
    # 先清理Unicode字符
    path = clean_unicode_path(path)
    
    # 替换Windows不支持的字符
    invalid_chars = r'[<>:"|?*]'
    path = re.sub(invalid_chars, '-', path)
    
    # 确保不以点或空格结尾（Windows不允许）
    path_parts = path.split(os.sep)
    cleaned_parts = []
    for part in path_parts:
        if part:
            part = part.rstrip('. ')
            if part:  # 确保不为空
                cleaned_parts.append(part)
    
    return os.sep.join(cleaned_parts) if cleaned_parts else path
