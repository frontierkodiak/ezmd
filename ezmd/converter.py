"""
Handles:
1) Final filenames with collision resolution,
2) Download/copy,
3) MarkItDown usage with OpenAI if relevant,
4) Returns the .md path.
"""

import os
import re
import shutil
import requests
import time
from typing import Optional
from urllib.parse import urlparse

from .provider_manager import (
    get_openai_key,
    get_use_llm_img_desc,
    get_img_desc_model,
)
from .config_manager import save_config
from markitdown import MarkItDown


def convert_document(
    title: str,
    source: str,
    config: dict,
    provider: str,
    overwrite: bool,
) -> str:
    """
    Convert the given source to markdown in base_context_dir 
    using MarkItDown if user picks "openai" and we have an OpenAI key + user-enabled LLM usage.

    Returns the final .md path.
    """
    base_context = os.path.expanduser(config.get("base_context_dir", "~/context"))
    raw_dir = os.path.join(base_context, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    max_len = config.get("max_filename_length", 128)

    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]

    # guess extension from source
    ext = _guess_extension(source)
    raw_path = os.path.join(raw_dir, sanitized + ext)
    md_path = os.path.join(base_context, sanitized + ".md")

    final_raw = _resolve_collision_path_interactive(raw_path, overwrite)
    if final_raw is None:
        raise Exception("User canceled the job due to collision in raw path.")

    final_md = _resolve_collision_path_interactive(md_path, overwrite)
    if final_md is None:
        raise Exception("User canceled the job due to collision in output md path.")

    if source.startswith("http"):
        _download_file(source, final_raw)
    else:
        shutil.copy2(source, final_raw)

    # Decide whether to attach the LLM
    llm_client = None
    llm_model = None
    if provider == "openai":
        from .provider_manager import get_openai_key
        openai_key = get_openai_key()
        if openai_key:
            # only attach if user has "USE_LLM_IMG_DESC" = "true"
            if get_use_llm_img_desc():
                import openai
                openai.api_key = openai_key
                llm_client = openai
                # read model from env or fallback
                llm_model = get_img_desc_model()
            else:
                # user doesn't want image LLM usage
                pass

    md_instance = MarkItDown(llm_client=llm_client, llm_model=llm_model)
    result = md_instance.convert(final_raw)

    with open(final_md, "w", encoding="utf-8") as f:
        f.write(result.text_content)

    return final_md


def _guess_extension(source: str) -> str:
    parsed = None
    if source.startswith("http"):
        parsed = urlparse(source)
        _, extension = os.path.splitext(parsed.path)
        if extension:
            return extension
        return ".bin"
    else:
        _, extension = os.path.splitext(source)
        return extension if extension else ".bin"


def _download_file(url: str, dest: str) -> None:
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def _resolve_collision_path_interactive(path: str, overwrite: bool) -> Optional[str]:
    """
    If overwrite=True, return path, even if it exists.
    If overwrite=False, check for collisions and propose a new path or let user rename.
    """
    if overwrite:
        return path

    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    idx = 2
    while True:
        proposed = f"{base}_v{idx}{ext}"
        idx += 1
        if not os.path.exists(proposed):
            break

    while True:
        print(f"\n[COLLISION] File already exists: {path}")
        print(f"Proposed: {proposed}")
        user_input = input("Enter new filename (absolute path) or press Enter to accept proposed, or 'c' to cancel: ").strip()
        if user_input.lower() == "c":
            return None
        elif user_input == "":
            return proposed
        else:
            if os.path.exists(user_input):
                print("[!] That path also exists, let's try again.")
                continue
            return user_input