"""
rsync_manager.py

This file encapsulates logic for performing an rsync operation to a remote host,
and testing connections to confirm the user's SSH environment is set up properly.

We store minimal code to keep the TUI code clean.
"""

import subprocess
import os

def rsync_file(local_file: str, ssh_host: str, remote_dir: str, timeout_sec: int = 10) -> bool:
    """
    Attempt to rsync the given local_file to the remote host's remote_dir.
    Returns True if successful, False if an error or timeout occurs.

    # ASSUMPTION: The user has set up passwordless SSH or SSH keys. 
    # We do not handle passphrase prompts here.
    """
    if not os.path.isfile(local_file):
        print(f"[!] rsync error: local file not found: {local_file}")
        return False

    # Force trailing slash on remote_dir
    if not remote_dir.endswith("/"):
        remote_dir += "/"

    command = [
        "rsync",
        "-avz",  # We assume typical flags; can be extended if user wants compression etc
        local_file,
        f"{ssh_host}:{remote_dir}"
    ]

    try:
        subprocess.run(command, check=True, timeout=timeout_sec, capture_output=True)
        return True
    except subprocess.TimeoutExpired:
        print(f"[!] rsync timed out after {timeout_sec} seconds.")
        return False
    except subprocess.CalledProcessError as e:
        # We can log e.stderr if we want more detail
        print(f"[!] rsync returned an error: {e.stderr}")
        return False
    except Exception as ex:
        print(f"[!] Unexpected rsync error: {ex}")
        return False


def test_rsync_connection(ssh_host: str, remote_dir: str, timeout_sec: int = 10) -> bool:
    """
    We do a quick test to see if rsync works with a dummy file.
    We'll create a small test file in /tmp, then run a --dry-run to confirm connectivity.

    Returns True if test is successful, False otherwise.
    """
    import tempfile
    import uuid

    test_filename = f"ezmd_test_{uuid.uuid4().hex}.txt"
    test_filepath = os.path.join("/tmp", test_filename)

    try:
        with open(test_filepath, "w", encoding="utf-8") as f:
            f.write("ezmd test\n")

        if not remote_dir.endswith("/"):
            remote_dir += "/"

        command = [
            "rsync",
            "--dry-run",
            "-avz",
            test_filepath,
            f"{ssh_host}:{remote_dir}"
        ]
        subprocess.run(command, check=True, timeout=timeout_sec, capture_output=True)
        return True

    except Exception as e:
        print(f"[!] test_rsync_connection error: {e}")
        return False
    finally:
        # Cleanup the local test file
        try:
            os.remove(test_filepath)
        except:
            pass