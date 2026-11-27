"""Opening an SSH session on a Grid'5000 site's frontend, or on a job's machine.

From outside Grid'5000 every connection goes through the access gateway:

    ssh -J alice@access.grid5000.fr alice@nancy

-J hops through the gateway, which knows each site by its name. On a
frontend (no login set) a site is reached directly: ssh nancy.

A job's machine is reached the way you would by hand: SSH to its site's
frontend, and from there SSH to the machine (as you, or as root for a job of
type deploy, whose system you installed):

    ssh -t -J alice@access.grid5000.fr alice@nancy ssh gros-1

The second hop runs on the frontend, with its keys: nothing on your computer
needs to know the machine.

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


def machine_command(
    site: str, machine: str, user: str = '', deploy: bool = False
) -> list[str]:
    """The command that opens a shell on one machine of your job.

    It SSHes to the site's frontend, and from there to the machine.

    Args:
        site: The job's site, e.g. 'nancy'.
        machine: The machine, e.g. 'gros-1'.
        user: Your Grid'5000 login; '' on a frontend, where none is needed.
        deploy: The job is of type deploy: the machine is reached as root.
    """
    frontend = ssh_command(site, user)
    target = f'root@{machine}' if deploy else machine
    # -t: the frontend gets a terminal, so the second ssh gets one too
    return [frontend[0], '-t', *frontend[1:], 'ssh', target]


def ssh_available() -> bool:
    """Is there an ssh command to run."""
    return shutil.which('ssh') is not None


def run(command: list[str]) -> int:
    """Run a command in the terminal, wait for it, and give its exit code."""
    return subprocess.run(command, check=False).returncode
