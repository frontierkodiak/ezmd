"""
Handles saving/loading config from a JSON file in ~/.config/ezmd/config.json,
and a first-time setup wizard if no config file is found.

Now includes a default "remotes" field for the new rsync-based Remote Sync feature.
"""

import os
import json

# CLARIFY: We are assuming a simple JSON-based config. 
# We'll store only the minimal items and rely on environment variables for keys.

DEFAULT_CONFIG = {
    "base_context_dir": "~/context",
    "max_filename_length": 128,
    "force_overwrite_default": False,
    "providers": {
        "openai": {
            "enabled": False,
            "default_model": "gpt-4"
        },
        "google_gemini": {
            "enabled": False,
            "default_model": "gemini-2.0-flash-exp"
        }
    },
    "default_provider": None,
    # New field for storing remotes:
    # {
    #   "alias1": {
    #       "ssh_host": "myuser@myhost",
    #       "remote_dir": "~/my_remote_folder",
    #       "auto_sync": false
    #   }
    # }
    "remotes": {}
}

def get_config_path() -> str:
    """
    Returns the full path to the config file e.g. ~/.config/ezmd/config.json
    """
    home = os.path.expanduser("~")
    config_dir = os.path.join(home, ".config", "ezmd")
    if not os.path.exists(config_dir):
        try:
            os.makedirs(config_dir, exist_ok=True)
        except Exception:
            pass
    config_file = os.path.join(config_dir, "config.json")
    return config_file


def load_config() -> dict:
    """
    Loads the config from config.json.
    Returns None if no config found.
    """
    path = get_config_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Ensure "remotes" is present
            if "remotes" not in data:
                data["remotes"] = {}
            return data
    except Exception:
        # if there's a parse error, treat as no config
        return None


def save_config(cfg: dict) -> None:
    """
    Writes the config to config.json
    """
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        print(f"[!] Failed to write config: {e}")


def init_config_wizard() -> dict:
    """
    First-time setup wizard that returns a new config dict.
    """
    print("\n[No configuration found. Let's do initial setup.]\n")

    cfg = DEFAULT_CONFIG.copy()

    base_dir = input(f"base_context_dir [default={cfg['base_context_dir']}]: ").strip()
    if base_dir:
        cfg["base_context_dir"] = base_dir

    ml = input(f"max_filename_length [default={cfg['max_filename_length']}]: ").strip()
    if ml.isdigit():
        cfg["max_filename_length"] = int(ml)

    fwd = input(f"force_overwrite_default (Y/n) [default=n]: ").strip().lower()
    if fwd.startswith("y"):
        cfg["force_overwrite_default"] = True
    else:
        cfg["force_overwrite_default"] = False

    # openai
    en_oai = input("Enable openai provider? (Y/n): ").strip().lower()
    if en_oai.startswith("y"):
        cfg["providers"]["openai"]["enabled"] = True
        oai_key = input("Enter openai key (paste or blank to skip): ").strip()
        # We'll store it with the environment manager after we return from here
        if oai_key:
            os.environ["EZMD_OPENAI_KEY"] = oai_key
    else:
        cfg["providers"]["openai"]["enabled"] = False

    # google gemini
    en_gg = input("Enable google_gemini provider? (Y/n): ").strip().lower()
    if en_gg.startswith("y"):
        cfg["providers"]["google_gemini"]["enabled"] = True
        gg_key = input("Enter google gemini key (paste or blank to skip): ").strip()
        if gg_key:
            os.environ["EZMD_GOOGLE_GEMINI_KEY"] = gg_key
    else:
        cfg["providers"]["google_gemini"]["enabled"] = False

    # default provider
    defprov = input("Default provider (openai/google_gemini/none)? [none]: ").strip().lower()
    if defprov in ["openai", "google_gemini"]:
        cfg["default_provider"] = defprov
    else:
        cfg["default_provider"] = None

    # Remotes remain empty by default. 
    # We'll prompt user for them in the new "Manage Remotes" menu if needed.

    print("Setup complete! We'll store this config now.\n")
    return cfg