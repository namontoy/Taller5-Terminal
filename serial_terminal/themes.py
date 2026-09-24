"""
Theme definitions and QSS stylesheet generator.
Colors are computed accurately from the original OKLCH values.
"""
import math


# ── Control character names ────────────────────────────────────────────────
CTRL_NAMES: dict[int, str] = {
    0: 'NUL',  1: 'SOH',  2: 'STX',  3: 'ETX',  4: 'EOT',  5: 'ENQ',
    6: 'ACK',  7: 'BEL',  8: 'BS',   9: 'HT',  10: 'LF',  11: 'VT',
   12: 'FF',  13: 'CR',  14: 'SO',  15: 'SI',  16: 'DLE', 17: 'DC1',
   18: 'DC2', 19: 'DC3', 20: 'DC4', 21: 'NAK', 22: 'SYN', 23: 'ETB',
   24: 'CAN', 25: 'EM',  26: 'SUB', 27: 'ESC', 28: 'FS',  29: 'GS',
   30: 'RS',  31: 'US', 127: 'DEL',
}

BAUDS = [300, 1200, 2400, 4800, 9600, 14400, 19200, 38400,
         57600, 115200, 230400, 460800, 921600]

BUILT_IN_TERMS = [
    {'label': 'LF',    'key': '0x0A',      'bytes': [0x0A]},
    {'label': 'CR',    'key': '0x0D',      'bytes': [0x0D]},
    {'label': 'CR+LF', 'key': '0x0D 0x0A', 'bytes': [0x0D, 0x0A]},
    {'label': 'NUL',   'key': '0x00',      'bytes': [0x00]},
]


# ── OKLCH → hex conversion ─────────────────────────────────────────────────
def oklch_to_hex(L: float, C: float, H_deg: float) -> str:
    """Convert an OKLCH color to #RRGGBB hex string."""
    h = math.radians(H_deg)
    a = C * math.cos(h)
    b = C * math.sin(h)

    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.2914855480 * b) ** 3

    r  =  4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_
    g  = -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_
    bv = -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_

    def _u8(c: float) -> int:
        c = max(0.0, min(1.0, c))
        c = 12.92 * c if c <= 0.0031308 else 1.055 * c ** (1.0 / 2.4) - 0.055
        return round(c * 255)

    return '#{:02X}{:02X}{:02X}'.format(_u8(r), _u8(g), _u8(bv))


_o = oklch_to_hex   # shorthand


# ── Theme color palettes ───────────────────────────────────────────────────
THEMES: dict[str, dict[str, str]] = {
    'matrix': {
        'bg': '#080908', 'bg2': '#0e100e', 'bg3': '#131513', 'bg4': '#0a0c0a',
        'border': '#222422', 'border2': '#1a1c1a',
        'fg':       _o(0.76, 0.19, 142),
        'fg_dim':   _o(0.64, 0.16, 142),
        'fg_faint': _o(0.52, 0.12, 142),
        'fg_ghost': _o(0.28, 0.06, 142),
        'label':    _o(0.72, 0.17, 142),
        'amber':     _o(0.78, 0.16, 75),
        'amber_dim': _o(0.52, 0.12, 75),
        'red':       _o(0.65, 0.18, 25),
        'input_bg': '#090b09',
        'hex_offset': _o(0.62, 0.14, 220),
        'hex_ctrl':   _o(0.55, 0.10, 30),
        'pad_bg':     '#0e100e',
        'pad_border': '#2a2e2a',
        'pad_fg':     _o(0.60, 0.14, 142),
        'pad_hover':  _o(0.76, 0.19, 142),
        'pad_center': _o(0.65, 0.18, 142),
    },
    'light': {
        'bg': '#eef0ed', 'bg2': '#e4e7e3', 'bg3': '#dde0dc', 'bg4': '#e8ebe7',
        'border': '#c8cdc7', 'border2': '#d4d8d3',
        'fg': '#1a2018', 'fg_dim': '#4a5648',
        'fg_faint': '#7a887a', 'fg_ghost': '#a8b4a8',
        'label': '#2a3828',
        'amber': '#b06010', 'amber_dim': '#c07830',
        'red': '#b02020', 'input_bg': '#f4f6f3',
        'hex_offset': '#2060b0', 'hex_ctrl': '#b04020',
        'pad_bg': '#dde0dc', 'pad_border': '#b8bdb7',
        'pad_fg': '#4a5648', 'pad_hover': '#1a2018', 'pad_center': '#2a6040',
    },
    'matte': {
        'bg': '#1c1814', 'bg2': '#231f1a', 'bg3': '#2a2520', 'bg4': '#1f1b17',
        'border': '#3a3430', 'border2': '#302c28',
        'fg':       _o(0.78, 0.07, 55),
        'fg_dim':   _o(0.55, 0.05, 55),
        'fg_faint': _o(0.38, 0.04, 55),
        'fg_ghost': _o(0.28, 0.03, 55),
        'label':    _o(0.72, 0.09, 55),
        'amber':     _o(0.72, 0.14, 55),
        'amber_dim': _o(0.52, 0.10, 55),
        'red':       _o(0.58, 0.14, 28),
        'input_bg': '#1a1612',
        'hex_offset': _o(0.62, 0.10, 200),
        'hex_ctrl':   _o(0.60, 0.12, 28),
        'pad_bg': '#2a2520', 'pad_border': '#403c38',
        'pad_fg':     _o(0.55, 0.06, 55),
        'pad_hover':  _o(0.78, 0.07, 55),
        'pad_center': _o(0.68, 0.10, 55),
    },
}

THEME_DISPLAY = {
    'matrix': 'The Matrix',
    'light':  'Light',
    'matte':  'Matte',
}


# ── QSS stylesheet generator ───────────────────────────────────────────────
def build_qss(c: dict[str, str]) -> str:
    """Generate a complete QSS stylesheet from a theme color dict."""
    return f"""
/* ── Base ─────────────────────────────────────────────────── */
QWidget {{
    background-color: {c['bg']};
    color: {c['fg']};
    font-family: "JetBrains Mono", "Courier New", monospace;
    font-size: 11px;
    border: none;
    outline: none;
}}
QMainWindow {{ background-color: {c['bg']}; }}

/* ── Toolbar ──────────────────────────────────────────────── */
QWidget#toolbar {{
    background-color: {c['bg2']};
    border-bottom: 1px solid {c['border']};
}}
QWidget#toolbar QLabel {{
    color: {c['label']};
    font-family: "IBM Plex Mono", "Courier New", monospace;
    font-size: 10px;
    font-weight: 500;
    background-color: transparent;
}}
QWidget#toolbar QLineEdit,
QWidget#toolbar QComboBox {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    color: {c['fg']};
    font-size: 11px;
    padding: 3px 6px;
    border-radius: 2px;
}}
QWidget#toolbar QLineEdit:focus,
QWidget#toolbar QComboBox:focus {{ border-color: {c['fg_dim']}; }}
QWidget#toolbar QLineEdit:disabled,
QWidget#toolbar QComboBox:disabled {{
    color: {c['fg_faint']};
    background-color: {c['bg2']};
}}

/* ── Status bar ───────────────────────────────────────────── */
QWidget#status_bar {{
    background-color: {c['bg2']};
    border-bottom: 1px solid {c['border2']};
}}
QWidget#status_bar QLabel {{
    font-family: "IBM Plex Mono", "Courier New", monospace;
    font-size: 10px;
    background: transparent;
    color: {c['fg_dim']};
}}

/* ── Tab bar ──────────────────────────────────────────────── */
QWidget#panel_tabs {{
    background-color: {c['bg2']};
    border-bottom: 1px solid {c['border']};
}}

/* ── Terminal panel ───────────────────────────────────────── */
QWidget#panel_chars {{
    background-color: {c['bg']};
}}
QPlainTextEdit, QTextEdit {{
    background-color: {c['bg']};
    color: {c['fg']};
    border: none;
    selection-background-color: {c['fg_faint']};
    selection-color: {c['bg']};
}}

/* ── ASCII strip ──────────────────────────────────────────── */
QWidget#ascii_strip {{
    background-color: {c['bg2']};
    border-top: 1px solid {c['border2']};
    border-bottom: 1px solid {c['border2']};
}}

/* ── Bottom bar ───────────────────────────────────────────── */
QWidget#bottom_bar {{
    background-color: {c['bg2']};
    border-top: 1px solid {c['border']};
}}

/* ── Hex panel ────────────────────────────────────────────── */
QWidget#hex_panel {{
    background-color: {c['bg4']};
    border-left: 1px solid {c['border']};
}}

/* ── Sidebar ──────────────────────────────────────────────── */
QWidget#sidebar {{
    background-color: {c['bg3']};
    border-left: 1px solid {c['border']};
}}

/* ── Global QLineEdit ─────────────────────────────────────── */
QLineEdit {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    color: {c['fg']};
    font-size: 11px;
    padding: 4px 7px;
    border-radius: 2px;
}}
QLineEdit:focus {{ border-color: {c['fg_dim']}; }}
QLineEdit:disabled {{ color: {c['fg_faint']}; background-color: {c['bg2']}; }}

/* ── Global QComboBox ─────────────────────────────────────── */
QComboBox {{
    background-color: {c['input_bg']};
    border: 1px solid {c['border']};
    color: {c['fg']};
    font-size: 11px;
    padding: 3px 6px 3px 6px;
    border-radius: 2px;
    min-width: 40px;
}}
QComboBox:focus {{ border-color: {c['fg_dim']}; }}
QComboBox:disabled {{ color: {c['fg_faint']}; background-color: {c['bg2']}; }}
QComboBox::drop-down {{ border: none; width: 16px; subcontrol-origin: padding; }}
QComboBox QAbstractItemView {{
    background-color: {c['bg2']};
    color: {c['fg']};
    border: 1px solid {c['border']};
    selection-background-color: {c['fg_ghost']};
    selection-color: {c['fg']};
    outline: none;
    padding: 2px;
}}

/* ── Global QPushButton ───────────────────────────────────── */
QPushButton {{
    background-color: transparent;
    border: 1px solid {c['border']};
    color: {c['fg_dim']};
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    border-radius: 2px;
    padding: 4px 10px;
}}
QPushButton:hover {{
    border-color: {c['fg_dim']};
    color: {c['fg']};
    background-color: {c['fg_ghost']};
}}
QPushButton:pressed {{ background-color: {c['fg_faint']}; }}
QPushButton:disabled {{ color: {c['fg_ghost']}; border-color: {c['border2']}; }}
QPushButton:checked {{
    border-color: {c['fg']};
    color: {c['fg']};
    background-color: {c['fg_ghost']};
}}

/* ── Scrollbars ───────────────────────────────────────────── */
QScrollBar:vertical {{
    background: transparent; width: 5px; margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {c['border']}; border-radius: 3px; min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

QScrollBar:horizontal {{
    background: transparent; height: 3px; margin: 0;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {c['border']}; border-radius: 2px; min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}

/* ── QCheckBox ────────────────────────────────────────────── */
QCheckBox {{
    color: {c['fg_dim']};
    font-family: "IBM Plex Mono", monospace;
    font-size: 9px;
    spacing: 4px;
    background: transparent;
}}
QCheckBox::indicator {{
    width: 11px; height: 11px;
    border: 1px solid {c['border']};
    border-radius: 2px;
    background: transparent;
}}
QCheckBox::indicator:checked {{
    background-color: {c['fg_ghost']};
    border-color: {c['fg_dim']};
}}

/* ── QScrollArea ──────────────────────────────────────────── */
QScrollArea {{ border: none; background: transparent; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}

/* ── QToolTip ─────────────────────────────────────────────── */
QToolTip {{
    background-color: {c['bg3']};
    color: {c['fg']};
    border: 1px solid {c['border']};
    padding: 3px 6px;
    font-size: 10px;
}}
"""
