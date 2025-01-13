"""
Handles the actual process of:
1) Determining final filenames with interactive collision resolution,
2) Downloading/copying raw docs,
3) Calling MarkItDown,
4) Potentially doing a custom call for Google Gemini if the user selected that provider,
5) Returning the path to the final .md file.
"""

import os
import re
import shutil
import requests
import time
from urllib.parse import urlparse
from .provider_manager import get_openai_key, get_google_gemini_key
from .config_manager import save_config
# We still rely on MarkItDown, but only for openai usage.
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
    using MarkItDown if openai is chosen for LLM usage, 
    or skip LLM usage if google_gemini is chosen, 
    followed by a custom gemini-based step if provider=google_gemini.

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
            ext = ".bin"
    else:
        _, extension = os.path.splitext(source)
        if extension:
            ext = extension
        else:
            ext = ".bin"

    if not ext:
        ext = ".bin"

    # Proposed raw path
    raw_base = os.path.join(raw_dir, sanitized)
    raw_path = raw_base + ext

    # Proposed md path
    out_path = os.path.join(base_context, sanitized + ".md")

    # If we have collisions, do interactive approach
    final_raw_path = _resolve_collision_path_interactive(raw_path, overwrite)
    if final_raw_path is None:
        # user canceled
        raise Exception("User canceled the job due to collision in raw path.")

    final_md_path = _resolve_collision_path_interactive(out_path, overwrite)
    if final_md_path is None:
        # user canceled
        raise Exception("User canceled the job due to collision in output md path.")

    # If it's a URL, download
    if source.startswith("http"):
        _download_file(source, final_raw_path)
    else:
        shutil.copy2(source, final_raw_path)

    # MarkItDown usage
    # If user picks openai, we pass an openai client
    # If user picks google_gemini, we do no LLM usage here
    llm_client = None
    llm_model = None

    if provider == "openai":
        import openai
        key = get_openai_key()
        if key:
            openai.api_key = key
            llm_client = openai
            llm_model = config.get("providers", {}).get("openai", {}).get("default_model", "gpt-4")

    # If google_gemini, skip the MarkItDown LLM usage and do a custom approach
    # => We'll do normal MarkItDown with no llm client
    md_instance = MarkItDown(
        llm_client=llm_client,
        llm_model=llm_model,
    )

    result = md_instance.convert(final_raw_path)
    with open(final_md_path, "w", encoding="utf-8") as f:
        f.write(result.text_content)

    # If user selected google_gemini, do a custom pass
    # This is a placeholder: the user can define more advanced image or doc transformations
    if provider == "google_gemini":
        _do_gemini_processing(final_md_path, config)

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


def _resolve_collision_path_interactive(path: str, overwrite: bool) -> str or None:
    """
    If overwrite=True, we can just use path. If it exists, we overwrite.
    If overwrite=False, then if path exists, we propose <path>_v2, _v3, etc.
    and ask user for confirmation or a custom name. 
    The user can also type 'c' to cancel.

    Returns the final chosen path, or None if user canceled.
    """
    if overwrite:
        return path

    if not os.path.exists(path):
        return path

    # If there's a collision, propose version increments
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
            # user accepts proposed
            return proposed
        else:
            # user typed a path
            # check if that path also exists
            if os.path.exists(user_input):
                print("[!] That path also exists, let's try again.")
                continue
            return user_input


def _do_gemini_processing(md_path: str, config: dict) -> None:
    """
    This is a placeholder for custom Gemini usage. 
    If we want to do e.g. image annotation or advanced doc transformations, 
    we can do so here, reading the .md file, applying transformations, 
    and rewriting it.

    # ASSUMPTION: We'll just append a note that "Gemini was used" for now.
    """
    from .provider_manager import get_google_gemini_key
    gem_key = get_google_gemini_key()
    if not gem_key:
        return  # No key, can't do anything.

    # In a real scenario, we might do something like:
    #  from google import genai
    #  client = genai.Client(api_key=gem_key, model="gemini-2.0-flash-exp")
    #  ... do something with md_path ...
    #
    # For demonstration, we'll just append a line to the MD file:

    try:
        with open(md_path, "a", encoding="utf-8") as f:
            f.write("\n\n---\n_Google Gemini custom processing step was invoked._\n")
    except Exception as e:
        print(f"[!] Gemini post-processing error: {e}")