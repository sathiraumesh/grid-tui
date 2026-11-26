"""Opening an SSH session on a Grid'5000 site's frontend.

From outside Grid'5000 every connection goes through the access gateway:

    ssh -J alice@access.grid5000.fr alice@nancy

-J hops through the gateway, which knows each site by its name. On a
frontend (no login set) a site is reached directly: ssh nancy.

The login is the same as the API's (G5K_USER, or ~/.grid-secret); the
connection uses your SSH key, which must be added to your Grid'5000 account.
"""

from __future__ import annotations

import shutil
import subprocess

ACCESS = 'access.grid5000.fr'
SSH_FAILED = 255  # ssh's own exit code when it can't connect


def ssh_command(site: str, user: str = '') -> list[str]:
    """The command that opens a shell on a site's frontend.

    Args:
        site: The site, e.g. 'nancy'.
        user: Your Grid'5000 login; '' on a frontend, where none is needed.
    """
    if not user:
        return ['ssh', site]
    return ['ssh', '-J', f'{user}@{ACCESS}', f'{user}@{site}']


def ssh_available() -> bool:
    """Is there an ssh command to run."""
    return shutil.which('ssh') is not None


def run(command: list[str]) -> int:
    """Run a command in the terminal, wait for it, and give its exit code."""
    return subprocess.run(command, check=False).returncode
