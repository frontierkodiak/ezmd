"""
Provides all the TUI flows for ezmd, including:
 - Main menu
 - Convert flow
 - Config menu
 - Providers sub-menu (OpenAI only)
 - Manage Remotes sub-menu
"""

import os
import time
import sys
import subprocess
from typing import Optional

from .converter import convert_document
from .config_manager import save_config, load_config
from .provider_manager import (
    is_openai_available,
    set_openai_key,
    get_openai_key,
    set_use_llm_img_desc,
    get_use_llm_img_desc,
    set_img_desc_model,
    get_img_desc_model,
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
    Post-conversion, handle remote sync.
    """
    print("\n[Convert Document]\n")
    title = input("Enter Title: ").strip()
    source = input("Enter Source (URL or local path): ").strip()

    # Only openai (or None) from now on. 
    # But let's keep code flexible if we re-add more providers.
    default_provider = config.get("default_provider", None)
    provider: Optional[str] = None

    if is_openai_available(config):
        # default is openai if config says so
        provider = default_provider if default_provider == "openai" else None

    # Ask user if they'd like to use an LLM
    if provider is None:
        # user has no default or not openai
        # ask them if they'd like to enable openai for this job
        if is_openai_available(config):
            choice = input("Use OpenAI LLM for images? (y/N): ").strip().lower()
            if choice.startswith("y"):
                provider = "openai"

    force_overwrite_default = config.get("force_overwrite_default", False)
    ow_input = input(
        f"Overwrite if file exists? (Y/n) [default={'Y' if force_overwrite_default else 'N'}]: "
    ).strip().lower()

    if ow_input == "":
        overwrite = True if force_overwrite_default else False
    elif ow_input.startswith("y"):
        overwrite = True
    else:
        overwrite = False

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
            provider=provider if provider else "",
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
        if md_path:
            _handle_post_conversion_rsync(md_path, config)


def _handle_post_conversion_rsync(md_path: str, config: dict):
    remotes = config.get("remotes", {})
    if not remotes:
        return

    any_auto = False
    for alias, info in remotes.items():
        if info.get("auto_sync", False):
            any_auto = True
            success = rsync_file(md_path, info["ssh_host"], info["remote_dir"], timeout_sec=10)
            if not success:
                print(f"[!] Warning: auto-sync to remote '{alias}' failed.")

    if not any_auto:
        choice = input("Sync new .md file(s) to a remote? (y/N): ").strip().lower()
        if choice.startswith("y"):
            _choose_and_sync_remotes(md_path, remotes)
    else:
        choice = input("Sync to additional remote(s) as well? (y/N): ").strip().lower()
        if choice.startswith("y"):
            _choose_and_sync_remotes(md_path, remotes)


def _choose_and_sync_remotes(md_path: str, remotes: dict):
    if not remotes:
        return
    aliases = list(remotes.keys())
    print("\nAvailable remotes:")
    for idx, alias in enumerate(aliases, start=1):
        info = remotes[alias]
        print(f" ({idx}) {alias} -> {info['ssh_host']}:{info['remote_dir']}")

    sel = input("\nEnter comma-separated list of remotes (e.g. '1,3') or blank to skip: ").strip()
    if not sel:
        return

    choices = []
    for part in sel.split(","):
        part = part.strip()
        try:
            i = int(part)
            if 1 <= i <= len(aliases):
                choices.append(aliases[i-1])
        except:
            print(f"[!] Invalid selection: {part}")

    for alias in choices:
        info = remotes[alias]
        success = rsync_file(md_path, info["ssh_host"], info["remote_dir"], timeout_sec=10)
        if not success:
            print(f"[!] Warning: sync to '{alias}' failed.")


def config_menu(config: dict) -> None:
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
            new_val = input("Enter default provider name (openai) or blank to disable default: ").strip()
            if new_val in ["openai"]:
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


def providers_submenu(config: dict) -> None:
    """
    Submenu to manage OpenAI configuration:
      1) Toggle openai enable/disable in config
      2) Edit openai key
      3) Set default model (EZMD_IMG_DESC_MODEL)
      4) Toggle "use LLM for images" (EZMD_USE_LLM_IMG_DESC)
    """
    provs = config.get("providers", {})
    if "openai" not in provs:
        provs["openai"] = {"enabled": False, "default_model": "gpt-4o-mini"}

    while True:
        print("\n┌──────────────────────────────────┐")
        print("│ Manage Providers (OpenAI)      │")
        print("├──────────────────────────────────┤")
        openai_cfg = provs["openai"]
        en = openai_cfg.get("enabled", False)
        key = get_openai_key()
        default_model = get_img_desc_model()  # from env
        use_llm = get_use_llm_img_desc()

        print(f"OpenAI -> enabled: {en}")
        key_str = f"<Yes, starts with {key[:6]}...>" if key else "<No key>"
        print(f"    Key in env: {key_str}")
        print(f"    default_model (env): {default_model}")
        print(f"    use LLM for images? {use_llm}")
        print("├──────────────────────────────────┤")
        print("1) Toggle openai enable/disable")
        print("2) Edit openai key")
        print("3) Select default model (gpt-4, gpt-4o, gpt-4o-mini...)")
        print("4) Toggle LLM usage for images")
        print("5) Return to config menu")
        print("└──────────────────────────────────┘")

        choice = input("Select an option: ").strip()
        if choice == "1":
            openai_cfg["enabled"] = not openai_cfg["enabled"]
            provs["openai"] = openai_cfg
            config["providers"] = provs
            save_config(config)
        elif choice == "2":
            newkey = input("Enter new openai key (blank to remove): ").strip()
            set_openai_key(newkey if newkey else "")
        elif choice == "3":
            newmodel = input("Enter new default model (e.g., gpt-4, gpt-4o, gpt-4o-mini): ").strip()
            if not newmodel:
                print("[!] Skipped.")
            else:
                set_img_desc_model(newmodel)
        elif choice == "4":
            # flip
            current = get_use_llm_img_desc()
            set_use_llm_img_desc(not current)
        elif choice == "5":
            break
        else:
            print("[!] Invalid choice")

    config["providers"] = provs
    save_config(config)


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
                print(f"      auto_sync: {info.get('auto_sync',False)}\n")
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
    alias = input("Enter alias (e.g. 'mylaptop'): ").strip()
    if not alias:
        print("[!] Alias is empty, aborting.")
        return
    if alias in remotes:
        print("[!] That alias already exists.")
        return

    ssh_host = input("ssh_host (e.g. user@myhost): ").strip()
    remote_dir = input("remote_dir (default=~): ").strip() or "~"

    print("\nTesting rsync connection with a dummy file (dry-run)...")
    success = test_rsync_connection(ssh_host, remote_dir, timeout_sec=10)
    if not success:
        print("[!] Test failed. You can still add this remote, but it might not work.")
        choice = input("Add anyway? (y/N): ").strip().lower()
        if not choice.startswith("y"):
            return

    auto_sync = False
    ask_sync = input("Enable auto_sync for this remote by default? (y/N): ").strip().lower()
    if ask_sync.startswith("y"):
        auto_sync = True

    remotes[alias] = {
        "ssh_host": ssh_host,
        "remote_dir": remote_dir,
        "auto_sync": auto_sync
    }
    print(f"[+] Remote '{alias}' added.")


def _edit_remote(remotes: dict, config: dict):
    if not remotes:
        print("[!] No remotes to edit.")
        return
    aliases = list(remotes.keys())
    print("\nWhich remote do you want to edit?")
    for idx, a in enumerate(aliases, start=1):
        print(f" {idx}) {a}")

    choice = input("Selection: ").strip()
    try:
        i = int(choice)
        alias = aliases[i-1]
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

    test_choice = input("Test connection again? (y/N): ").strip().lower()
    if test_choice.startswith("y"):
        success = test_rsync_connection(info["ssh_host"], info["remote_dir"], timeout_sec=10)
        if success:
            print("[+] Test succeeded.")
        else:
            print("[!] Test failed. You can proceed, but it might not work in practice.")

    ask_sync = input(f"auto_sync? [current={info.get('auto_sync',False)}] (y=enable / n=disable / Enter=skip): ").strip().lower()
    if ask_sync == "y":
        info["auto_sync"] = True
    elif ask_sync == "n":
        info["auto_sync"] = False

    remotes[alias] = info
    config["remotes"] = remotes
    print("[+] Remote updated.")


def _remove_remote(remotes: dict, config: dict):
    if not remotes:
        print("[!] No remotes to remove.")
        return
    aliases = list(remotes.keys())
    print("\nWhich remote do you want to remove?")
    for idx, a in enumerate(aliases, start=1):
        print(f" {idx}) {a}")

    choice = input("Selection: ").strip()
    try:
        i = int(choice)
        alias = aliases[i-1]
    except:
        print("[!] Invalid choice.")
        return

    confirm = input(f"Are you sure you want to remove remote '{alias}'? (y/N): ").strip().lower()
    if confirm.startswith("y"):
        del remotes[alias]
        config["remotes"] = remotes
        print(f"[+] Remote '{alias}' removed.")