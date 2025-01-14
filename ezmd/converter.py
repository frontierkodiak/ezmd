"""
Handles:
1) Final filenames with collision resolution,
2) Download/copy,
3) MarkItDown usage with OpenAI if relevant,
4) Returns the .md path.

Now includes logic to detect arXiv IDs or abstract links, unify to PDF links, and .pdf extension.
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

    If the user provided an ArXiv ID or link, we unify it to the official PDF link.
    """
    base_context = os.path.expanduser(config.get("base_context_dir", "~/context"))
    raw_dir = os.path.join(base_context, "raw")
    os.makedirs(raw_dir, exist_ok=True)

    # If user typed just an arxiv ID, convert to https://arxiv.org/pdf/<ID>.pdf
    # If user typed arxiv.org/abs/..., also unify.
    source = _canonicalize_arxiv_source(source)

    max_len = config.get("max_filename_length", 128)
    sanitized = re.sub(r"[^\w\s-]", "", title)
    sanitized = re.sub(r"\s+", "_", sanitized.strip())
    if len(sanitized) > max_len:
        sanitized = sanitized[:max_len]

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
            if get_use_llm_img_desc():
                import openai
                openai.api_key = openai_key
                llm_client = openai
                llm_model = get_img_desc_model()

    md_instance = MarkItDown(llm_client=llm_client, llm_model=llm_model)
    result = md_instance.convert(final_raw)

    with open(final_md, "w", encoding="utf-8") as f:
        f.write(result.text_content)

    return final_md


def _canonicalize_arxiv_source(source: str) -> str:
    """
    If user typed something like "2306.02564" or "arxiv.org/abs/2306.02564",
    unify to "https://arxiv.org/pdf/2306.02564.pdf".
    # CLARIFY: We'll do a naive pattern check. 
    """
    # if user typed plain ID e.g. "2306.02564" or "2306.02564v2"
    m = re.match(r"^(\d{4}\.\d{4,5}(v\d+)?)$", source.strip())
    if m:
        arxiv_id = m.group(1)
        return f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    if "arxiv.org" in source.lower():
        # if "abs/" -> replace with "pdf/"
        # if it ends with .pdf, it's already canonical
        # else unify
        # We skip full robust parse. We'll do a quick approach:
        src_lower = source.lower()
        if "/abs/" in src_lower:
            # extract the id
            # e.g. https://arxiv.org/abs/2306.02564v2 -> 2306.02564v2
            m2 = re.search(r"arxiv\.org/abs/([^/]+)$", src_lower)
            if m2:
                arxiv_id = m2.group(1)
                return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        elif "/pdf/" in src_lower and src_lower.endswith(".pdf"):
            # Already canonical
            return source
        else:
            # fallback, e.g. "arxiv.org/2306.01234" -> add /pdf/ + .pdf
            # might not always be correct, but let's do best guess
            # parse out last path seg?
            parsed = urlparse(source)
            id_candidate = parsed.path.strip("/")
            if id_candidate:
                return f"https://arxiv.org/pdf/{id_candidate}.pdf"
            # else do normal
            return source

    # else
    return source


def _guess_extension(source: str) -> str:
    # special check for arxiv
    if "arxiv.org/pdf/" in source.lower():
        return ".pdf"

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
        user_input = input("Enter new filename (absolute path), press Enter to accept proposed, or 'c' to cancel: ").strip()
        if user_input.lower() == "c":
            return None
        elif user_input == "":
            return proposed
        else:
            if os.path.exists(user_input):
                print("[!] That path also exists, let's try again.")
                continue
            return user_input