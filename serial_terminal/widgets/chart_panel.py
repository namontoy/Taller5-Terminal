"""
Chart panel: real-time line chart using matplotlib.
Parses numeric values from the incoming serial character stream.

Supported line formats:
  CSV / semicolon / space:   1.23, 4.56, 7.89
  Key=value or key:value:    temp:23.5  hum:65  press:1013
"""
from __future__ import annotations

import re
from collections import deque

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy

from serial_terminal import Char
from serial_terminal.logging_setup import get_logger

_log = get_logger('chart')

try:
    import matplotlib
    matplotlib.rcParams['toolbar'] = 'None'
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    _MPL_OK = True
except ImportError:
    _MPL_OK = False

_MAX_POINTS = 200   # rolling window length per series
_MAX_SERIES = 8     # cap so we don't run wild on noisy data

# Vibrant palette — readable on dark and light backgrounds
_PALETTE = [
    '#00cc66', '#ffaa00', '#22aaff', '#ff4477',
    '#aa44ff', '#00cccc', '#ff7700', '#aacc00',
]

_KV_RE  = re.compile(r'([A-Za-z_]\w*)\s*[=:]\s*(-?\d+\.?\d*(?:[eE][+-]?\d+)?)')
_NUM_RE = re.compile(r'-?\d+\.?\d*(?:[eE][+-]?\d+)?')


def _parse_line(line: str) -> tuple[list[str], list[float]] | None:
    """Return (labels, values) from a line, or None if no numeric data found."""
    line = line.strip()
    if not line:
        return None

    # Key=value / key:value pairs have priority
    kv = _KV_RE.findall(line)
    if kv:
        return [m[0] for m in kv], [float(m[1]) for m in kv]

    # Positional: split by comma, semicolon, or whitespace
    parts = re.split(r'[,;\t]+|\s+', line)
    values = []
    for p in parts:
        try:
            values.append(float(p.strip()))
        except ValueError:
            pass
    if values:
        return [str(i) for i in range(len(values))], values

    return None


class ChartPanel(QWidget):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('chart_panel')
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._colors:   dict[str, str]          = {}
        self._series:   dict[str, deque[float]] = {}
        self._line_buf: str                     = ''
        self._dirty:    bool                    = False
        self._draw_failed: bool                 = False  # stop after a redraw error

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if _MPL_OK:
            self._fig    = Figure(tight_layout=True)
            self._ax     = self._fig.add_subplot(111)
            self._canvas = FigureCanvasQTAgg(self._fig)
            self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding,
                                       QSizePolicy.Policy.Expanding)
            layout.addWidget(self._canvas)
        else:
            self._canvas = None
            lbl = QLabel(
                'matplotlib is not installed.\n\n'
                'Install it inside the conda environment:\n\n'
                '  conda run -n taller5 pip install matplotlib'
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setObjectName('chart_no_mpl')
            layout.addWidget(lbl)

        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._redraw)
        self._timer.start()

    # ── Public API ─────────────────────────────────────────────────────────

    def push_chars(self, chars: list[Char]) -> None:
        """Buffer incoming bytes; parse complete lines for numeric data."""
        for ch in chars:
            if ch.sent:
                continue            # skip echoed TX chars
            if ch.code == 10:       # LF — line is complete
                result = _parse_line(self._line_buf)
                if result is not None:
                    labels, values = result
                    for label, val in zip(labels, values):
                        if label not in self._series:
                            if len(self._series) >= _MAX_SERIES:
                                continue
                            self._series[label] = deque(maxlen=_MAX_POINTS)
                        self._series[label].append(val)
                    self._dirty = True
                self._line_buf = ''
            elif ch.code == 13:     # CR — ignore
                pass
            elif 32 <= ch.code < 127:
                self._line_buf += chr(ch.code)

    def clear_buffer(self) -> None:
        self._series.clear()
        self._line_buf = ''
        self._dirty = True
        self._draw_failed = False

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        if _MPL_OK and self._canvas:
            self._fig.patch.set_facecolor(c['bg'])
        else:
            for lbl in self.findChildren(QLabel):
                lbl.setStyleSheet(
                    f'color:{c["fg_dim"]};background:{c["bg"]};'
                    f'font-family:"IBM Plex Mono",monospace;font-size:11px;'
                )
        self._dirty = True

    # ── Internal ───────────────────────────────────────────────────────────

    def _redraw(self) -> None:
        if (not self._dirty or not _MPL_OK or not self._colors
                or self._draw_failed):
            return
        self._dirty = False
        try:
            self._redraw_impl()
        except Exception:
            # Don't let a plotting error abort the app; log once and give up
            # redrawing until the next clear/theme change resets state.
            self._draw_failed = True
            _log.exception('Chart redraw failed — disabling live redraw')

    def _redraw_impl(self) -> None:
        c  = self._colors
        ax = self._ax
        ax.clear()

        if not self._series:
            ax.text(
                0.5, 0.5,
                'Waiting for numeric data…\n\n'
                'Supported line formats:\n'
                '  1.23, 4.56, 7.89\n'
                '  temp:23.5  hum:65\n'
                '  val1=1.2; val2=3.4',
                transform=ax.transAxes,
                ha='center', va='center',
                color=c['fg_faint'],
                fontsize=9,
                linespacing=1.7,
            )
        else:
            for i, (label, data) in enumerate(self._series.items()):
                color = _PALETTE[i % len(_PALETTE)]
                ys = list(data)
                xs = list(range(len(ys)))
                ax.plot(xs, ys,
                        color=color, linewidth=1.4, label=label,
                        solid_capstyle='round', solid_joinstyle='round')

            ax.legend(
                loc='upper right',
                fontsize=8,
                facecolor=c['bg2'],
                edgecolor=c['border'],
                labelcolor=c['fg_dim'],
                framealpha=0.85,
            )
            ax.set_xlim(left=max(0, len(next(iter(self._series.values()))) - _MAX_POINTS))

        # Axes styling — matches active theme
        ax.set_facecolor(c['bg'])
        ax.tick_params(axis='both', colors=c['fg_faint'], labelsize=8)
        for spine in ('top', 'right'):
            ax.spines[spine].set_visible(False)
        for spine in ('bottom', 'left'):
            ax.spines[spine].set_color(c['border'])
        ax.grid(True, color=c['border2'], linewidth=0.5,
                linestyle='--', alpha=0.8)

        self._canvas.draw_idle()
