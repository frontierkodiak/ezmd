"""
Manages environment variables for storing and retrieving
OpenAI and Google Gemini keys. Also checks availability.
Now persists these keys in ~/.config/ezmd/ezmd.env.
"""

import os
import re
# ASSUMPTION: We'll parse and rewrite a simple .env file in ~/.config/ezmd

from .config_manager import get_config_path

def _get_env_file_path() -> str:
    """
    Return the path to the environment (.env) file used by ezmd.
    We'll store this as <config_dir>/ezmd.env
    """
    cfg_path = get_config_path()  # e.g. ~/.config/ezmd/config.json
    config_dir = os.path.dirname(cfg_path)
    return os.path.join(config_dir, "ezmd.env")


def _load_env_file() -> dict:
    """
    Load environment variables from the .env file and return them as a dict.
    """
    env_path = _get_env_file_path()
    result = {}
    if not os.path.exists(env_path):
        return result
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # skip blanks/comments
                if not line or line.startswith("#"):
                    continue
                # parse KEY=val
                # naive parse
                if "=" in line:
                    key, val = line.split("=", 1)
                    result[key.strip()] = val.strip()
    except Exception:
        pass
    return result


def _save_env_file(envdict: dict) -> None:
    """
    Save the envdict to the .env file, overwriting its contents.
    """
    env_path = _get_env_file_path()
    lines = []
    for k, v in envdict.items():
        # If v has spaces or special chars, user must handle quotes etc.
        # We'll keep it simple and not do advanced quoting.
        lines.append(f"{k}={v}")
    try:
        with open(env_path, "w", encoding="utf-8") as f:
            f.write("# ezmd environment variables\n")
            for line in lines:
                f.write(line + "\n")
    except Exception as e:
        print(f"[!] Failed to write .env file: {e}")


def _persist_in_memory(envdict: dict) -> None:
    """
    Update the in-memory os.environ to match envdict.
    We do not remove other keys that might exist.
    """
    for k, v in envdict.items():
        os.environ[k] = v


# Let's load them upon import so that environment is available
_loaded = _load_env_file()
_persist_in_memory(_loaded)


def set_openai_key(key: str) -> None:
    """
    Sets or clears the openai key in the environment and .env file.
    If key is None or empty string, we remove it from env.
    """
    envdict = _load_env_file()

    if key:
        envdict["EZMD_OPENAI_KEY"] = key
        os.environ["EZMD_OPENAI_KEY"] = key
    else:
        if "EZMD_OPENAI_KEY" in envdict:
            del envdict["EZMD_OPENAI_KEY"]
        if "EZMD_OPENAI_KEY" in os.environ:
            del os.environ["EZMD_OPENAI_KEY"]

    _save_env_file(envdict)


def get_openai_key() -> str:
    """
    Returns the openai key from environment (which is also loaded from .env).
    """
    return os.environ.get("EZMD_OPENAI_KEY", "")


def set_google_gemini_key(key: str) -> None:
    """
    Sets or clears the google gemini key in the environment and .env file.
    """
    envdict = _load_env_file()

    if key:
        envdict["EZMD_GOOGLE_GEMINI_KEY"] = key
        os.environ["EZMD_GOOGLE_GEMINI_KEY"] = key
    else:
        if "EZMD_GOOGLE_GEMINI_KEY" in envdict:
            del envdict["EZMD_GOOGLE_GEMINI_KEY"]
        if "EZMD_GOOGLE_GEMINI_KEY" in os.environ:
            del os.environ["EZMD_GOOGLE_GEMINI_KEY"]

    _save_env_file(envdict)


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