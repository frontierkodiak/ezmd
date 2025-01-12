"""
Handles the actual process of:
1) Determining final filenames,
2) Downloading/copying raw docs,
3) Calling MarkItDown,
4) Returning the path to the final .md file.

We also handle collisions by appending _vN if overwrite=False.
"""

import os
import re
import shutil
import requests
import time
from urllib.parse import urlparse
from .provider_manager import get_openai_key, get_google_gemini_key
from .config_manager import save_config
# CLARIFY: We assume MarkItDown supports a "generic LLM client".
# If we want to do Google Gemini, we might need to adapt.
# We'll do best guess with an approach parallel to openai's usage.

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
    using MarkItDown with an optional LLM provider.

    Returns the path to the final .md file.
    """
    base_context = os.path.expanduser(config.get("base_context_dir", "~/context"))
    raw_dir = os.path.join(base_context, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    max_len = config.get("max_filename_length", 128)

    # sanitize the title -> underscores
    sanitized = re.sub(r"[^\w\s-]", "", title)  # remove weird chars
    sanitized = re.sub(r"\s+", "_", sanitized.strip())  # convert spaces to underscores
    # limit length
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]

    # Attempt to guess extension from source
    ext = None
    if source.startswith("http"):
        parsed = urlparse(source)
        path_part = parsed.path
        _, extension = os.path.splitext(path_part)
        if extension:
            ext = extension
        else:
            # If no extension, guess .bin
            ext = ".bin"
    else:
        _, extension = os.path.splitext(source)
        if extension:
            ext = extension
        else:
            ext = ".bin"

    if not ext:
        ext = ".bin"

    # Next, handle collisions in raw folder
    raw_base = os.path.join(raw_dir, sanitized)
    raw_path = raw_base + ext

    final_raw_path = _resolve_collision_path(raw_path, overwrite)

    # Similarly for the .md
    out_path = os.path.join(base_context, sanitized + ".md")
    final_md_path = _resolve_collision_path(out_path, overwrite)

    # If it's a URL, download
    if source.startswith("http"):
        _download_file(source, final_raw_path)
    else:
        # local path
        shutil.copy2(source, final_raw_path)

    # Now call MarkItDown with optional LLM
    llm_client = None
    llm_model = None
    # CLARIFY: MarkItDown's code expects "llm_client" if we want image descriptions
    if provider == "openai":
        # quick approach
        import openai
        key = get_openai_key()
        if key:
            openai.api_key = key
            llm_client = openai
            # default model
            llm_model = config.get("providers", {}).get("openai", {}).get("default_model", "gpt-4")
    elif provider == "google_gemini":
        # # CLARIFY: MarkItDown may not natively support google's genai client 
        # We'll do best guess:
        try:
            from google import genai
            gemini_key = get_google_gemini_key()
            if gemini_key:
                # # ASSUMPTION: This block doesn't actually enable MarkItDown's image usage automatically,
                # because it expects an OpenAI-like API. 
                # We are just making a placeholder "llm_client" object.
                llm_client = genai # Possibly not correct
                llm_model = config.get("providers", {}).get("google_gemini", {}).get("default_model", "gemini-2.0-flash-exp")
        except ImportError:
            pass

    md_instance = MarkItDown(
        llm_client=llm_client,
        llm_model=llm_model,
    )

    result = md_instance.convert(final_raw_path)
    with open(final_md_path, "w", encoding="utf-8") as f:
        f.write(result.text_content)

    return final_md_path


def _download_file(url: str, dest: str) -> None:
    """
    Download the file from url and write to dest.
    """
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


def _resolve_collision_path(path: str, overwrite: bool) -> str:
    """
    If overwrite=True, we can just use path (if it exists, we overwrite).
    Otherwise, if path exists, append _v2, _v3 until no collision.
    """
    if overwrite:
        return path

    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    # e.g. base=..., ext=.pdf
    idx = 2
    while True:
        candidate = f"{base}_v{idx}{ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1