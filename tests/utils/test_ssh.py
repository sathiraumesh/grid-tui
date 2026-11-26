"""Tests for the SSH command to a site's frontend."""

from grid_tui.utils.ssh import ssh_command


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
