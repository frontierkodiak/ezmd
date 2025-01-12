"""
Manages environment variables for storing and retrieving
OpenAI and Google Gemini keys. Also checks availability.
"""

import os


def set_openai_key(key: str) -> None:
    """
    Sets or clears the openai key in the environment.
    If key is None or empty string, we remove it from env.
    # CLARIFY: We could also store in a .env or write to uv environment's 
      activate script if persistent is needed. 
    """
    if key:
        os.environ["EZMD_OPENAI_KEY"] = key
    else:
        if "EZMD_OPENAI_KEY" in os.environ:
            del os.environ["EZMD_OPENAI_KEY"]


def get_openai_key() -> str:
    return os.environ.get("EZMD_OPENAI_KEY", "")


def set_google_gemini_key(key: str) -> None:
    if key:
        os.environ["EZMD_GOOGLE_GEMINI_KEY"] = key
    else:
        if "EZMD_GOOGLE_GEMINI_KEY" in os.environ:
            del os.environ["EZMD_GOOGLE_GEMINI_KEY"]


def get_google_gemini_key() -> str:
    return os.environ.get("EZMD_GOOGLE_GEMINI_KEY", "")


def is_openai_available(config: dict) -> bool:
    """
    Returns True if openai is enabled in config and we have a key in env.
    """
    if not config:
        return False
    providers = config.get("providers", {})
    oinfo = providers.get("openai", {})
    if not oinfo.get("enabled", False):
        return False
    return len(get_openai_key()) > 0


def is_google_gemini_available(config: dict) -> bool:
    """
    Returns True if google gemini is enabled in config and we have a key in env.
    """
    if not config:
        return False
    providers = config.get("providers", {})
    ginfo = providers.get("google_gemini", {})
    if not ginfo.get("enabled", False):
        return False
    return len(get_google_gemini_key()) > 0