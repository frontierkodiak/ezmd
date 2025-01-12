"""
Main entry point for the ezmd CLI tool.
Handles the initial loading of config, 
and dispatches control to the TUI main menu.
"""

import sys
import os

# CLARIFY: We assume that uv sets up environment variables appropriately for the session,
# but we will attempt to manage them in local processes for now.

from .config_manager import load_config, init_config_wizard, save_config
from .tui import main_menu


def entry_point():
    """
    This is invoked when a user types 'ezmd' from the shell, 
    assuming pyproject.toml has [project.scripts] ezmd="ezmd.main:entry_point".
    """
    config = load_config()

    if config is None:
        # We have no config, let's run the wizard.
        config = init_config_wizard()
        save_config(config)

    while True:
        main_menu(config)
        # TUI handles changes that might need saving. 
        # If they do changes, it calls save_config internally or we can do it after returning.
        # For now, we assume the TUI calls save_config as needed.

        # If the TUI-based actions do not exit, it returns here. 
        # This loop can be used to reload config if needed in the future.

        # If you want to break out, we can do so from within the TUI.
        break


def debug_entry_point():
    """
    Alternate entry point if debugging with debugpy or VSCode 
    so that you can set breakpoints easily.
    """
    entry_point()


if __name__ == "__main__":
    entry_point()