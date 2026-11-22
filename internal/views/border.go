package views

import (
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Lip Gloss can't put text into a border, so the panel is drawn with a
// plain border and then its top or bottom line is replaced by one with
// text set into it, on the left and on the right:
//
//	┌─  site: nancy  ───  cluster: gros  ─────────── updated 14:30:05 ─┐
//	│ ...                                                               │
//	└─ $ curl …/clusters/gros/status ──────────────────────── 4-9 of 30 ─┘

type edge int

const (
	edgeTop edge = iota
	edgeBottom
)

// withBorderText redraws the top or bottom border line of box with left
// after its left corner and right before its right corner, joined by
// border pieces so the line is exactly width wide. If right doesn't fit it
// is left out; if left doesn't fit either, box is returned unchanged.
func withBorderText(box string, e edge, left, right string, width int) string {
	b := lipgloss.NormalBorder()
	leftCorner, rightCorner, piece := b.TopLeft, b.TopRight, b.Top
	if e == edgeBottom {
		leftCorner, rightCorner, piece = b.BottomLeft, b.BottomRight, b.Bottom
	}

	tail := ""
	if right != "" {
		tail = right + borderLine.Render(piece)
	}
	fill := width - 3 - lipgloss.Width(left) - lipgloss.Width(tail) // 3 = "┌─" and "┐"
	if fill < 1 && tail != "" {
		tail = ""
		fill = width - 3 - lipgloss.Width(left)
	}
	if fill < 1 {
		return box
	}
	line := borderLine.Render(leftCorner+piece) + left +
		borderLine.Render(strings.Repeat(piece, fill)) + tail + borderLine.Render(rightCorner)

	if e == edgeTop {
		_, rest, ok := strings.Cut(box, "\n")
		if !ok {
			return box
		}
		return line + "\n" + rest
	}
	i := strings.LastIndex(box, "\n")
	if i < 0 {
		return box
	}
	return box[:i+1] + line
}

// borderLabel is text set into a border with a space on each side.
func borderLabel(style lipgloss.Style, text string) string {
	if text == "" {
		return ""
	}
	return style.Render(" " + text + " ")
}

// labelRow joins labels with border pieces between them: "[a]───[b]".
func labelRow(labels ...string) string {
	sep := borderLine.Render(strings.Repeat(lipgloss.NormalBorder().Top, labelGap))
	return " " + strings.Join(labels, sep) + " "
}
