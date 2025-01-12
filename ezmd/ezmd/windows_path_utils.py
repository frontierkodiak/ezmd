"""
Detects if a path is Windows-style (like C:\\Users\\front...) and 
translates to a WSL-friendly path (/mnt/c/Users/front...).
"""

import re

def is_windows_path(path: str) -> bool:
    """
    Returns True if 'C:\\' or 'D:\\' etc recognized 
    # CLARIFY: We are ignoring some exotic cases like UNC paths
    """
    return bool(re.match(r"^[a-zA-Z]:\\\\", path))


def translate_windows_path_to_wsl(path: str) -> str:
    """
    Convert e.g. C:\\Users\\front to /mnt/c/Users/front
    # ASSUMPTION: 
    # - We do a naive approach: just convert drive letter to lower, prefix /mnt/.
    # - We also replace backslashes with forward slashes.
    """
    # e.g. "C:\Users\front\Zotero\paper.pdf"
    drive_letter_match = re.match(r"^([a-zA-Z]):\\\\(.*)", path)
    if drive_letter_match:
        drive = drive_letter_match.group(1).lower()
        remainder = drive_letter_match.group(2)
        # Now convert remainder's backslashes to forward slashes:
        remainder = remainder.replace("\\", "/")
        return f"/mnt/{drive}/{remainder}"
    return path