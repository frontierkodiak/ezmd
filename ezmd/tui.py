"""
Provides all the TUI (text user interface) flows for ezmd:
 - Main menu
 - Convert flow
 - Config menu
 - Provider sub-menu
"""

import os
import time
import sys
from .converter import convert_document
from .config_manager import save_config
from .provider_manager import (
    is_openai_available,
    is_google_gemini_available,
    set_openai_key,
    set_google_gemini_key,
)
from .windows_path_utils import is_windows_path, translate_windows_path_to_wsl


def main_menu(config: dict) -> None:
    """
    Display the main menu in a loop, until user selects exit.
    """
    while True:
        print("\n┌────────────────────────────────┐")
        print("│ ezmd - Easy Markdown Tool     │")
        print("├────────────────────────────────┤")
        print("│ 1) Convert a Document         │")
        print("│ 2) Configuration              │")
        print("│ 3) Exit                       │")
        print("└────────────────────────────────┘")

        choice = input("Select an option: ").strip()
        if choice == "1":
            convert_document_flow(config)
        elif choice == "2":
            config_menu(config)
        elif choice == "3":
            print("Exiting ezmd...")
            sys.exit(0)
        else:
            print("[!] Invalid choice, please try again.")


def convert_document_flow(config: dict) -> None:
    """
    Interactive flow for converting a document. 
    Prompts user for title, source, provider, overwrite, etc.
    """
    print("\n[Convert Document]\n")
    title = input("Enter Title: ").strip()
    source = input("Enter Source (URL or local path): ").strip()

    # Determine available providers
    available_providers = []
    if is_openai_available(config):
        available_providers.append("openai")
    if is_google_gemini_available(config):
        available_providers.append("google_gemini")

    default_provider = config.get("default_provider", None)
    if default_provider not in available_providers:
        default_provider = None

    print("\nAvailable LLM Providers:")
    print(" (0) None (no LLM usage)")
    for idx, prov in enumerate(available_providers, start=1):
        mark = "(default)" if prov == default_provider else ""
        print(f" ({idx}) {prov} {mark}")

    provider_choice = input("Choose LLM provider [Press Enter for default]: ").strip()
    chosen_provider = None
    if provider_choice == "":
        chosen_provider = default_provider
    else:
        if provider_choice == "0":
            chosen_provider = None
        else:
            try:
                numeric = int(provider_choice)
                if 1 <= numeric <= len(available_providers):
                    chosen_provider = available_providers[numeric - 1]
                else:
                    print("[!] Invalid provider selection, ignoring.")
                    chosen_provider = None
            except ValueError:
                print("[!] Invalid provider selection, ignoring.")
                chosen_provider = None

    # Overwrite or interactive version approach
    force_overwrite_default = config.get("force_overwrite_default", False)
    prompt = (
        f"Overwrite if file exists? (Y/n) [default={'Y' if force_overwrite_default else 'N'}]: "
    )
    ow_input = input(prompt).strip().lower()

    if ow_input == "":
        overwrite = True if force_overwrite_default else False
    elif ow_input.startswith("y"):
        overwrite = True
    else:
        overwrite = False

    # local path check
    if not source.startswith("http"):
        if is_windows_path(source):
            source = translate_windows_path_to_wsl(source)

        if not os.path.exists(source):
            print(f"[!] Local file path does not exist: {source}")
            return

    print("\n[Converting... please wait]")
    import threading

    spinner_stop = False

    def spinner_run():
        symbols = ["-", "\\", "|", "/"]
        idx = 0
        while not spinner_stop:
            sys.stdout.write("\r" + "[Converting... " + symbols[idx] + "]")
            sys.stdout.flush()
            idx = (idx + 1) % len(symbols)
            time.sleep(0.1)
        sys.stdout.write("\r[✔ Conversion Complete]     \n")

    thread = threading.Thread(target=spinner_run)
    thread.start()

    md_path = None
    error_message = None
    try:
        md_path = convert_document(
            title=title,
            source=source,
            config=config,
            provider=chosen_provider,
            overwrite=overwrite,
        )
    except Exception as ex:
        error_message = str(ex)

    spinner_stop = True
    thread.join()

    if error_message:
        print(f"[!] Error during conversion: {error_message}")
    else:
        print(f"[+] Output saved to {md_path}")


def config_menu(config: dict) -> None:
    """
    Show the configuration menu. 
    Allows editing base_context_dir, max_filename_length,
    force_overwrite_default, default_provider, etc.
    """
    while True:
        print("\n┌──────────────────────────────────┐")
        print("│ ezmd Configuration             │")
        print("├──────────────────────────────────┤")
        base_context_dir = config.get("base_context_dir", "~/context")
        max_len = config.get("max_filename_length", 128)
        fwd = config.get("force_overwrite_default", False)
        defprov = config.get("default_provider", None)

        print(f"│ base_context_dir: {base_context_dir}")
        print(f"│ max_filename_length: {max_len}")
        print(f"│ force_overwrite_default: {fwd}")
        print(f"│ default_provider: {defprov}")
        print("├──────────────────────────────────┤")
        print("│ Providers:                     │")
        provs = config.get("providers", {})
        for pname, pinfo in provs.items():
            en = pinfo.get("enabled", False)
            print(f"│   {pname} -> enabled: {en}")
        print("├──────────────────────────────────┤")
        print("│ a) Edit base_context_dir        │")
        print("│ b) Edit max_filename_length     │")
        print("│ c) Toggle force_overwrite       │")
        print("│ d) Edit default_provider        │")
        print("│ e) Manage providers...          │")
        print("│ f) Return to main menu          │")
        print("└──────────────────────────────────┘")

        choice = input("Select an option: ").strip().lower()
        if choice == "a":
            new_val = input("New base_context_dir (blank to skip): ").strip()
            if new_val:
                config["base_context_dir"] = new_val
                save_config(config)
        elif choice == "b":
            new_val = input("New max_filename_length (blank to skip): ").strip()
            if new_val.isdigit():
                config["max_filename_length"] = int(new_val)
                save_config(config)
        elif choice == "c":
            config["force_overwrite_default"] = not config.get("force_overwrite_default", False)
            save_config(config)
            print(f"force_overwrite_default is now {config['force_overwrite_default']}")
        elif choice == "d":
            new_val = input("Enter default provider name (openai/google_gemini) or blank to disable default: ").strip()
            if new_val in ["openai", "google_gemini"]:
                config["default_provider"] = new_val
            else:
                config["default_provider"] = None
            save_config(config)
        elif choice == "e":
            providers_submenu(config)
        elif choice == "f":
            break
        else:
            print("[!] Invalid choice")


def providers_submenu(config: dict) -> None:
    """
    Manage providers: toggle enable, set keys, etc.
    """
    while True:
        print("\n┌──────────────────────────────────┐")
        print("│ Manage Providers               │")
        print("├──────────────────────────────────┤")
        provs = config.get("providers", {})
        if "openai" not in provs:
            provs["openai"] = {"enabled": False, "default_model": "gpt-4"}
        if "google_gemini" not in provs:
            provs["google_gemini"] = {"enabled": False, "default_model": "gemini-2.0-flash-exp"}

        print(f"│ openai -> (enabled={provs['openai']['enabled']}) ")
        openai_key = os.environ.get("EZMD_OPENAI_KEY", None)
        openai_key_str = f"<Yes, starts with {openai_key[:6]}...>" if openai_key else "<No>"
        print(f"│   Key in env: {openai_key_str}")
        print(f"│ google_gemini -> (enabled={provs['google_gemini']['enabled']}) ")
        google_key = os.environ.get("EZMD_GOOGLE_GEMINI_KEY", None)
        google_key_str = f"<Yes, starts with {google_key[:6]}...>" if google_key else "<No>"
        print(f"│   Key in env: {google_key_str}")
        print("├──────────────────────────────────┤")
        print("│ 1) Toggle openai enable/disable │")
        print("│ 2) Toggle google_gemini         │")
        print("│ 3) Set/Change openai key        │")
        print("│ 4) Set/Change google gemini key │")
        print("│ 5) Return...                    │")
        print("└──────────────────────────────────┘")

        choice = input("Select an option: ").strip()
        if choice == "1":
            provs["openai"]["enabled"] = not provs["openai"]["enabled"]
            config["providers"] = provs
            save_config(config)
        elif choice == "2":
            provs["google_gemini"]["enabled"] = not provs["google_gemini"]["enabled"]
            config["providers"] = provs
            save_config(config)
        elif choice == "3":
            newkey = input("Enter new key for openai (blank to remove): ").strip()
            set_openai_key(newkey if newkey else "")
        elif choice == "4":
            newkey = input("Enter new key for google_gemini (blank to remove): ").strip()
            set_google_gemini_key(newkey if newkey else "")
        elif choice == "5":
            break
        else:
            print("[!] Invalid selection")
    config["providers"] = provs
    save_config(config)