"""Drawing the reservations: the time line, the week, the month (as plain text)."""

from datetime import datetime, timedelta

from grid_tui.models import Gantt, Mode, Node, Reservation
from grid_tui.widgets.timeline import TIMELINE_HEADER, WEEK_HEADER, draw, job_colors, label_step, window

H = timedelta(hours=1)
LOADED = datetime(2026, 11, 22, 14, 30).astimezone()  # Sunday 14:30


def at(h: float) -> datetime:
    return LOADED + h * H


def sample() -> Gantt:
    """gros-1: job 4521 now → +2h, job 4600 +3.5h → +5.5h (on gros-2 too);
    gros-2: besteffort until +0.5h; gros-10: dead."""
    return Gantt(
        nodes=[
            Node("gros-1", "alive", reservations=(
                Reservation(4521, at(-1), at(2), "bob", "default", "Running"),
                Reservation(4600, at(3.5), at(5.5), "eve", "default", "Waiting"))),
            Node("gros-2", "alive", reservations=(
                Reservation(9, at(-0.5), at(0.5), queue="besteffort"),
                Reservation(4600, at(3.5), at(5.5), "eve", "default", "Waiting"))),
            Node("gros-10", "dead"),
        ],
        loaded_at=LOADED,
    )


def plain(g: Gantt, width: int = 60) -> list[str]:
    lines, _, _ = draw(g, width)
    return [line.plain for line in lines]


def row(lines: list[str], name: str) -> str:
    for line in lines[TIMELINE_HEADER:]:
        if line[2:].startswith(name + " "):
            return line[2 + len("gros-10") + 1 :]
    raise AssertionError(f"no row for {name}")


def test_timeline_rows() -> None:
    lines = plain(sample())
    # cells from 14:00, an hour each; the now line (14:30) in the first
    assert row(lines, "gros-1").startswith("┃██·██···")
    assert row(lines, "gros-2").startswith("┃···██···")
    assert set(row(lines, "gros-10")[1:]) == {"×"}
    assert all(len(line) <= 60 for line in lines)


def test_timeline_header() -> None:
    g = sample()
    g.move_time(4)  # 18:00: gros-1's job 4600
    lines = plain(g, 120)
    assert "zoom 1h per cell" in lines[0] and "cursor 18:00" in lines[0]
    assert lines[1] == "gros-1 · #4600 eve · default · Waiting · 18:00→20:00 (2h) · on 2 nodes"
    assert "Sun 22" in lines[4] and "18:00" in lines[5]
    assert lines[6].lstrip().startswith("FREE")
    assert lines[7].rstrip().endswith("▲")


def test_free_row() -> None:
    free = plain(sample())[6].split("FREE", 1)[1].strip()
    # 14:00 1 of 2 free (gros-2's besteffort counts); 17:00 both; 18:00 none
    assert free[0] == "▄" and free[3] == "█" and free[4] == "·"


def test_numbers_fit_when_zoomed_in_and_avoid_the_now_line() -> None:
    g = sample()
    g.zoom_by(-2)  # 15 minutes: job 4521 is 8 cells from 14:30, now in the first
    assert row(plain(g), "gros-1").startswith("┃#4521██")
    g.clock = LOADED + H  # 15:30: 4 cells before the line
    assert row(plain(g), "gros-1").startswith("4521┃███")


def test_selected_free_and_down() -> None:
    g = sample()
    g.move_time(3)  # 17:00
    assert plain(g, 120)[1] == "gros-1 · free 16:30→18:00 (1h30m)"
    g.move_node(2)
    assert plain(g, 120)[1] == "gros-10 · down (dead)"


def test_the_now_line_goes_through_every_row() -> None:
    g = sample()
    g.clock = LOADED + 2 * H  # 16:30: the third cell
    lines = plain(g)
    col = row(lines, "gros-2").index("┃")
    assert col == 2
    offset = len(lines[TIMELINE_HEADER]) - len(row(lines, "gros-1"))
    for i in (TIMELINE_HEADER, TIMELINE_HEADER + 1, TIMELINE_HEADER + 2):
        assert lines[i][offset + col] == "┃", lines[i]


def test_jobs_next_to_each_other_get_different_colours() -> None:
    colors = job_colors(sample())
    assert set(colors) == {4521, 4600} and colors[4521] != colors[4600]


def test_label_step() -> None:
    assert label_step(15 * timedelta(minutes=1)) == 2 * H
    assert label_step(H) == 6 * H
    assert label_step(4 * H) == 24 * H
    assert label_step(12 * H) is None


def test_week() -> None:
    g = sample()
    g.set_mode(Mode.WEEK)  # Sun 22 14:00
    lines, pinned, focus = draw(g, 100)
    text = [line.plain for line in lines]
    assert text[0].startswith("week of Mon 16 Nov")
    assert text[1] == "Sun 22 14:00–16:00 · 1 of 2 nodes free all through · 1 job, 0 start"
    assert "Mon 16" in text[WEEK_HEADER - 1] and "Sun 22" in text[WEEK_HEADER - 1]
    now_row = WEEK_HEADER + 1 + 14 // 2  # after the 14:00 row
    assert text[now_row].startswith("14:30 ") and "━" in text[now_row]
    assert text[now_row - 1].startswith("14:00") and text[now_row + 1].startswith("16:00")
    assert focus == now_row - 1 and pinned == WEEK_HEADER
    g.move_day(slots=1)
    assert draw(g, 100)[2] == now_row + 1  # below the now line, focus counts it


def test_week_now_line_moves_with_the_clock() -> None:
    g = sample()
    g.clock = LOADED + 3 * H  # 17:30
    g.set_mode(Mode.WEEK)
    text = [line.plain for line in draw(g, 100)[0]]
    assert text[WEEK_HEADER + 1 + 16 // 2].startswith("17:30 ")
    g.move_day(days=7)
    assert not any("━" in t for t in (line.plain for line in draw(g, 100)[0]))


def test_month() -> None:
    g = sample()
    g.set_mode(Mode.MONTH)
    lines, pinned, focus = draw(g, 100)
    text = [line.plain for line in lines]
    assert text[0].startswith("November 2026")
    assert text[1] == "Sun 22 Nov · 0–2 of 2 nodes free · 2 jobs start"
    assert text[pinned - 1].startswith("Mon")
    assert (len(text) - pinned) // 2 == 6  # Nov 2026 starts on a Sunday: six weeks
    assert "0–2 free" in text[focus] and "22  2 jobs" in text[focus - 1]


def test_window() -> None:
    from rich.text import Text

    lines = [Text(c) for c in "PPabcdef"]
    assert [t.plain for t in window(lines, 2, 6, 5)] == list("PPcde")
    assert [t.plain for t in window(lines, 2, 0, 5)] == list("PPabc")
