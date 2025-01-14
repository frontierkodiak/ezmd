"""
Main entry point for the ezmd CLI tool.
Handles the initial loading of config, 
and dispatches control to the TUI main menu.

Now catches Ctrl-C (KeyboardInterrupt) to avoid messy traceback.
"""

import sys
import os

from .config_manager import load_config, init_config_wizard, save_config
from .tui import main_menu

def entry_point():
    """
    Invoked when user types 'ezmd'.
    """
    try:
        config = load_config()
        if config is None:
            # We have no config, let's run the wizard.
            config = init_config_wizard()
            save_config(config)
            # Prompt user if they'd like to configure remotes now
            _ask_configure_remotes(config)

        while True:
            main_menu(config)
            # TUI handles changes that might need saving.
            # If the TUI-based actions do not exit, it returns here.
            break

    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)

def _ask_configure_remotes(config: dict) -> None:
    """
    After the wizard completes, ask if user wants to manage remotes now.
    """
    choice = input("Would you like to configure a remote now? (y/N): ").strip().lower()
    if choice.startswith("y"):
        # We'll import from tui to call manage_remotes_menu
        from .tui import manage_remotes_menu
        manage_remotes_menu(config)
        save_config(config)


def debug_entry_point():
    """
    Alternate entry point for debugging with debugpy or VSCode.
    """
    entry_point()


if __name__ == "__main__":
    entry_point()