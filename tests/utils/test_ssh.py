"""Tests for the SSH commands: to a site's frontend, and to a job's machine."""

from grid_tui.utils.ssh import machine_command, ssh_command


def test_through_the_access_gateway() -> None:
    """With a login, it hops through access.grid5000.fr to the site."""
    assert ssh_command('nancy', 'alice') == [
        'ssh',
        '-J',
        'alice@access.grid5000.fr',
        'alice@nancy',
    ]


def test_on_a_frontend_directly() -> None:
    """With no login (on a frontend), it goes straight to the site."""
    assert ssh_command('lyon') == ['ssh', 'lyon']


def test_a_jobs_machine_through_its_sites_frontend() -> None:
    """A job's machine: SSH to the site (through the gateway), then to the machine."""
    assert machine_command('nancy', 'gros-1', 'alice') == [
        'ssh',
        '-t',
        '-J',
        'alice@access.grid5000.fr',
        'alice@nancy',
        'ssh',
        'gros-1',
    ]


def test_a_jobs_machine_from_a_frontend() -> None:
    """With no login (on a frontend): to the site, then to the machine."""
    assert machine_command('lyon', 'nova-1') == ['ssh', '-t', 'lyon', 'ssh', 'nova-1']


def test_a_deploy_jobs_machine_as_root_from_the_frontend() -> None:
    """A deploy job's machine: as root, still from the site's frontend."""
    command = machine_command('nancy', 'gros-1', 'alice', deploy=True)
    assert command[-3:] == ['alice@nancy', 'ssh', 'root@gros-1']
