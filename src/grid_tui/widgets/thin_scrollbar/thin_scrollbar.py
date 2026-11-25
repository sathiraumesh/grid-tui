"""Scrollbars drawn as thin lines, the same thickness both ways.

Textual draws a scrollbar as a filled block of cells. A terminal cell is about
twice as tall as it is wide, so a 1-row horizontal bar looks thicker than a
1-column vertical one. Drawing both with line characters (┃ and ━) makes them
look equally thin.

Use it for every scrollbar in the app with:

    ScrollBar.renderer = ThinScrollBarRender
"""

from math import ceil

from rich.color import Color as RichColor
from rich.segment import Segment, Segments
from rich.style import Style
from textual.color import Color
from textual.scrollbar import ScrollBarRender


class ThinScrollBarRender(ScrollBarRender):
    """Draws the thumb as a thick line and the track as a thin, faint line."""

    THUMB = {True: '┃', False: '━'}  # vertical, horizontal
    TRACK = {True: '│', False: '─'}

    @classmethod
    def render_bar(
        cls,
        size: int = 25,
        virtual_size: float = 50,
        window_size: float = 20,
        position: float = 0,
        thickness: int = 1,
        vertical: bool = True,
        back_color: RichColor = RichColor.parse('#555555'),
        bar_color: RichColor = RichColor.parse('#fab387'),
    ) -> Segments:
        """Draw one scrollbar.

        Args:
            size: How many cells long the bar is.
            virtual_size: How long the whole content is.
            window_size: How much of the content fits on screen.
            position: How far the content is scrolled.
            thickness: How many cells thick the bar is (from scrollbar-size).
            vertical: True for the bar on the right, False for the bottom.
            back_color: scrollbar-background: behind the line.
            bar_color: scrollbar-color: the part you drag.
        """
        width = thickness if vertical else 1
        back = Color.from_rich_color(back_color)
        bar = Color.from_rich_color(bar_color)
        track_color = bar.blend(back, 0.75)  # a faint version of the bar

        # what a click does on each part: the same as Textual's own scrollbar
        grab = {'@mouse.down': 'grab'}
        up = {'@mouse.down': 'scroll_up'}
        down = {'@mouse.down': 'scroll_down'}

        def cell(glyph: str, color: Color, meta: dict) -> Segment:
            return Segment(
                glyph * width,
                Style(color=color.rich_color, bgcolor=back.rich_color, meta=meta),
            )

        track = cls.TRACK[vertical]
        if window_size and size and virtual_size and size != virtual_size:
            # the same thumb size and place as Textual's own scrollbar
            thumb_size = max(1, ceil(window_size / (virtual_size / size)))
            scroll_range = virtual_size - window_size
            ratio = position / scroll_range if scroll_range > 0 else 0
            start = round((size - thumb_size) * ratio)
            end = min(size, start + thumb_size)
            segments = (
                [cell(track, track_color, up)] * start
                + [cell(cls.THUMB[vertical], bar, grab)] * (end - start)
                + [cell(track, track_color, down)] * (size - end)
            )
        else:
            segments = [cell(track, track_color, {})] * int(size)

        if vertical:
            return Segments(segments, new_lines=True)
        return Segments((segments + [Segment.line()]) * thickness, new_lines=False)
