"""
Provides all the TUI (text user interface) flows for ezmd:
 - Main menu
 - Convert flow
 - Config menu
 - Provider sub-menu
 - NEW: Remote sync flows (remotes sub-menu) and post-conversion sync logic
"""

import os
import time
import sys
import subprocess
from .converter import convert_document
from .config_manager import save_config, load_config
from .provider_manager import (
    is_openai_available,
    is_google_gemini_available,
    set_openai_key,
    set_google_gemini_key,
)
from .windows_path_utils import is_windows_path, translate_windows_path_to_wsl
from .rsync_manager import rsync_file, test_rsync_connection

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
    Post-conversion, we handle remote sync logic.
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
        # Post-conversion, let's handle remote sync
        if md_path:
            # In future, if multiple files, we might pass a list. For now, single-file approach.
            _handle_post_conversion_rsync(md_path, config)


def _handle_post_conversion_rsync(md_path: str, config: dict):
    """
    This function:
      1) Auto-syncs to all remotes with auto_sync=true
      2) If there are other remotes, prompts the user to optionally sync to multiple
    """
    remotes = config.get("remotes", {})
    if not remotes:
        return  # No remotes configured

    # 1) Auto-sync
    any_auto = False
    for alias, info in remotes.items():
        if info.get("auto_sync", False):
            any_auto = True
            success = rsync_file(md_path, info["ssh_host"], info["remote_dir"], timeout_sec=10)
            if not success:
                print(f"[!] Warning: auto-sync to remote '{alias}' failed.")
    # 2) Multi-select if user wants
    # If there are no auto-sync or the user might want additional
    # We'll ask "Would you like to sync to additional remote(s)?"
    if not any_auto:
        # No auto-sync, so let's see if user wants to sync
        choice = input("Sync new .md file(s) to a remote? (y/N): ").strip().lower()
        if choice.startswith("y"):
            # We'll do multi-select
            _choose_and_sync_remotes(md_path, remotes)
    else:
        # Some auto-sync happened. Do we also want to let them sync to additional?
        choice = input("Sync to additional remote(s) as well? (y/N): ").strip().lower()
        if choice.startswith("y"):
            _choose_and_sync_remotes(md_path, remotes)


def _choose_and_sync_remotes(md_path: str, remotes: dict):
    """
    Let the user pick multiple remote aliases from a list. 
    Then for each chosen alias, do an rsync.
    """
    if not remotes:
        return
    aliases = list(remotes.keys())
    print("\nAvailable remotes:")
    for idx, alias in enumerate(aliases, start=1):
        print(f" ({idx}) {alias} -> {remotes[alias]['ssh_host']}:{remotes[alias]['remote_dir']}")

    print("\nEnter a comma-separated list of remotes to sync (e.g. '1,3') or blank to skip.")
    sel = input("Selection: ").strip()
    if not sel:
        return

    # parse selection
    choices = []
    for part in sel.split(","):
        part = part.strip()
        try:
            i = int(part)
            if 1 <= i <= len(aliases):
                choices.append(aliases[i-1])
        except:
            print(f"[!] Invalid selection: {part}")

    # Now perform rsync for each
    for alias in choices:
        info = remotes[alias]
        success = rsync_file(md_path, info["ssh_host"], info["remote_dir"], timeout_sec=10)
        if not success:
            print(f"[!] Warning: sync to '{alias}' failed.")


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
        print("│ Remotes:                       │")
        # Show a quick summary of the user's configured remotes
        for alias, info in config.get("remotes", {}).items():
            ssh_host = info.get("ssh_host", "???")
            rdir = info.get("remote_dir", "???")
            autos = info.get("auto_sync", False)
            print(f"│   {alias} -> {ssh_host}:{rdir}, auto_sync={autos}")
        print("├──────────────────────────────────┤")
        print("│ a) Edit base_context_dir        │")
        print("│ b) Edit max_filename_length     │")
        print("│ c) Toggle force_overwrite       │")
        print("│ d) Edit default_provider        │")
        print("│ e) Manage providers...          │")
        print("│ r) Manage remotes...            │")
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
        elif choice == "r":
            manage_remotes_menu(config)
        elif choice == "f":
            break
        else:
            print("[!] Invalid choice")


def manage_remotes_menu(config: dict) -> None:
    """
    Submenu to manage the rsync-based remote sync configurations.
    """
    while True:
        print("\n┌──────────────────────────────────┐")
        print("│ Manage Remotes                 │")
        print("├──────────────────────────────────┤")
        remotes = config.get("remotes", {})
        if not isinstance(remotes, dict):
            config["remotes"] = {}
            remotes = config["remotes"]

        # Show a summary
        if remotes:
            for alias, info in remotes.items():
                print(f"   ALIAS: {alias}")
                print(f"      ssh_host: {info.get('ssh_host','???')}")
                print(f"      remote_dir: {info.get('remote_dir','???')}")
                print(f"      auto_sync: {info.get('auto_sync',False)}")
                print("")
        else:
            print("  (No remotes configured)")

        print("├──────────────────────────────────┤")
        print("│ 1) Add Remote                   │")
        print("│ 2) Edit Remote                  │")
        print("│ 3) Remove Remote                │")
        print("│ 4) Return...                    │")
        print("└──────────────────────────────────┘")

        choice = input("Select an option: ").strip()
        if choice == "1":
            _add_new_remote(remotes)
            save_config(config)
        elif choice == "2":
            _edit_remote(remotes, config)
        elif choice == "3":
            _remove_remote(remotes, config)
        elif choice == "4":
            break
        else:
            print("[!] Invalid selection")


def _add_new_remote(remotes: dict):
    """
    Prompt the user for a new alias, ssh_host, remote_dir. 
    Then attempt a test run. If success, optionally set auto_sync.
    """
    alias = input("Enter alias (e.g. 'mylaptop'): ").strip()
    if not alias:
        print("[!] Alias is empty, aborting.")
        return
    if alias in remotes:
        print("[!] That alias already exists.")
        return

    ssh_host = input("ssh_host (e.g. user@myhost): ").strip()
    remote_dir = input("remote_dir (default=~): ").strip() or "~"

    # Test the connection
    print("\nTesting rsync connection with a dummy file (dry-run)...")
    success = test_rsync_connection(ssh_host, remote_dir, timeout_sec=10)
    if not success:
        print("[!] Test failed. You can still add this remote, but it might not work.")
        choice = input("Add anyway? (y/N): ").strip().lower()
        if not choice.startswith("y"):
            return

    # auto_sync
    ask_sync = input("Enable auto_sync for this remote by default? (y/N): ").strip().lower()
    auto_sync = True if ask_sync.startswith("y") else False

    # Save
    remotes[alias] = {
        "ssh_host": ssh_host,
        "remote_dir": remote_dir,
        "auto_sync": auto_sync
    }
    print(f"[+] Remote '{alias}' added.")


def _edit_remote(remotes: dict, config: dict):
    """
    Let user pick a remote alias to edit. Then let them update fields, re-test, etc.
    """
    if not remotes:
        print("[!] No remotes to edit.")
        return
    aliases = list(remotes.keys())
    print("\nWhich remote do you want to edit?")
    for idx, a in enumerate(aliases, start=1):
        print(f" {idx}) {a}")

    choice = input("Selection: ").strip()
    try:
        idx = int(choice)
        alias = aliases[idx-1]
    except:
        print("[!] Invalid choice.")
        return

    info = remotes[alias]
    print(f"Editing remote '{alias}'...")

    new_ssh = input(f"ssh_host [current={info['ssh_host']}] (blank to skip): ").strip()
    if new_ssh:
        info["ssh_host"] = new_ssh

    new_dir = input(f"remote_dir [current={info['remote_dir']}] (blank to skip): ").strip()
    if new_dir:
        info["remote_dir"] = new_dir

    # test
    test_choice = input("Test connection again? (y/N): ").strip().lower()
    if test_choice.startswith("y"):
        success = test_rsync_connection(info["ssh_host"], info["remote_dir"], timeout_sec=10)
        if success:
            print("[+] Test succeeded.")
        else:
            print("[!] Test failed. You can proceed, but it might not work in practice.")

    # auto_sync
    ask_sync = input(f"auto_sync? [current={info.get('auto_sync',False)}] (y=enable / n=disable / Enter=skip): ").strip().lower()
    if ask_sync == "y":
        info["auto_sync"] = True
    elif ask_sync == "n":
        info["auto_sync"] = False

    remotes[alias] = info
    print("[+] Remote updated.")
    # We don't strictly need to do config object merges, but let's do it
    config["remotes"] = remotes


def _remove_remote(remotes: dict, config: dict):
    """
    Pick an alias to remove from the dictionary.
    """
    if not remotes:
        print("[!] No remotes to remove.")
        return
    aliases = list(remotes.keys())
    print("\nWhich remote do you want to remove?")
    for idx, a in enumerate(aliases, start=1):
        print(f" {idx}) {a}")

    choice = input("Selection: ").strip()
    try:
        idx = int(choice)
        alias = aliases[idx-1]
    except:
        print("[!] Invalid choice.")
        return

    confirm = input(f"Are you sure you want to remove remote '{alias}'? (y/N): ").strip().lower()
    if confirm.startswith("y"):
        del remotes[alias]
        config["remotes"] = remotes
        print(f"[+] Remote '{alias}' removed.")