"""Tests for Job: one of your jobs, its cores, cluster and run time."""

from grid_tui.models import Job

DETAILS = {
    'uid': 42,
    'state': 'running',
    'queue': 'default',
    'walltime': 3600,
    'submitted_at': 900,
    'started_at': 1000,
    'assigned_nodes': ['gros-1.nancy.grid5000.fr', 'gros-2.nancy.grid5000.fr'],
    'resources_by_type': {'cores': ['1', '2', '3', '4']},
}


def test_reads_cores_and_site() -> None:
    """from_api counts the cores and keeps the site."""
    job = Job.from_api(DETAILS, 'nancy')
    assert (job.uid, job.site, job.cores) == (42, 'nancy', 4)


def test_cluster_from_its_nodes() -> None:
    """The cluster is the node name without its number: 'gros'."""
    assert Job.from_api(DETAILS, 'nancy').cluster == 'gros'
    hyphen = {**DETAILS, 'assigned_nodes': ['abacus-one-3.rennes.grid5000.fr']}
    assert Job.from_api(hyphen, 'rennes').cluster == 'abacus-one'
    assert Job.from_api({'uid': 1}, 'nancy').cluster == ''


def test_a_list_item_has_no_nodes_or_cores() -> None:
    """The jobs list gives neither: zero cores, no nodes."""
    job = Job.from_api({'uid': 1, 'assigned_nodes': None}, 'nancy')
    assert (job.cores, job.assigned_nodes) == (0, ())


def test_running_counts_up_to_now() -> None:
    """A running job ran from its start until now (at most its walltime)."""
    job = Job.from_api(DETAILS, 'nancy')
    assert job.ran(now=1500) == (1000, 1500)
    assert job.ran(now=99999) == (1000, 4600)  # never past its walltime


def test_a_finished_job_ran_until_it_stopped() -> None:
    """A stopped job ran until it stopped."""
    job = Job.from_api({**DETAILS, 'state': 'terminated', 'stopped_at': 1200}, 'n')
    assert job.ran(now=99999) == (1000, 1200)
    assert not job.is_active


def test_not_started_did_not_run() -> None:
    """A waiting job (started_at 0) hasn't run."""
    job = Job.from_api({**DETAILS, 'state': 'waiting', 'started_at': 0}, 'nancy')
    assert job.ran(now=99999) is None
    assert job.is_active
    assert not job.is_running
