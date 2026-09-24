"""
Right sidebar: command input, terminators, saved presets, keypad, theme.
"""
from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QScrollArea, QComboBox, QGridLayout, QFrame,
    QSizePolicy, QStackedWidget,
)

from serial_terminal.config import PRESET_COUNT
from serial_terminal.protocol import format_hex_input
from serial_terminal.themes import BUILT_IN_TERMS, THEME_DISPLAY


# ── Helpers ────────────────────────────────────────────────────────────────

class _SectionTitle(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setObjectName('sb_title')


def _pad_presets(saved: list[str] | None) -> list[str]:
    """Return saved presets padded with blanks up to PRESET_COUNT.

    Older configs stored only 6 entries; never truncate, so no saved
    command is ever dropped.
    """
    data = list(saved or [])
    return data + [''] * (PRESET_COUNT - len(data))


class _HSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedHeight(1)


class _TermChip(QPushButton):
    """Toggle-style chip button for line terminators."""

    def __init__(self, label: str, code_str: str, parent=None) -> None:
        super().__init__(f'{label}  {code_str}', parent)
        self.setCheckable(True)
        self._label    = label
        self._code_str = code_str
        self.setToolTip(code_str)

    def sizeHint(self) -> QSize:
        return QSize(70, 24)


class _KpButton(QPushButton):
    """Square keypad direction button."""

    def __init__(self, symbol: str, parent=None) -> None:
        super().__init__(symbol, parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self) -> QSize:
        s = super().sizeHint()
        side = max(s.width(), s.height(), 34)
        return QSize(side, side)

    def resizeEvent(self, event) -> None:
        side = min(self.width(), self.height())
        self.setFixedSize(side, side)


class _ThemeSwatch(QPushButton):
    """Colored rectangle swatch for theme quick-select."""

    SWATCH_BG = {
        'matrix': ('#080908', '#4ade80'),
        'light':  ('#eef0ed', '#2a3828'),
        'matte':  ('#1c1814', '#c8a86a'),
    }

    def __init__(self, theme_key: str, parent=None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self._theme_key = theme_key
        self.setFixedHeight(18)
        self.setToolTip(THEME_DISPLAY.get(theme_key, theme_key))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        bg1, bg2 = self.SWATCH_BG.get(theme_key, ('#888', '#ccc'))
        self.setStyleSheet(
            f'background: qlineargradient(x1:0,y1:0,x2:1,y2:1,'
            f'stop:0 {bg1}, stop:1 {bg2});'
            f'border:1px solid #444;border-radius:2px;'
        )

    @property
    def theme_key(self) -> str:
        return self._theme_key


# ── Main sidebar widget ────────────────────────────────────────────────────

class Sidebar(QWidget):

    # Signals
    send_command         = pyqtSignal(str, str)  # (text, mode) mode='ASCII'|'HEX'
    send_preset          = pyqtSignal(str, str)  # (text, mode)
    send_keypad          = pyqtSignal(str)        # direction label or 'START'/'STOP'
    terms_changed        = pyqtSignal(list)       # list of active term keys
    theme_changed        = pyqtSignal(str)        # theme key
    presets_changed      = pyqtSignal(list)       # list of ASCII preset strings
    hex_presets_changed  = pyqtSignal(list)       # list of HEX preset strings
    custom_terms_changed = pyqtSignal(list)       # list of custom term keys (for persistence)

    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('sidebar')
        self.setFixedWidth(240)

        self._connected   = False
        self._cmd_mode    = 'ASCII'
        self._active_terms: list[str] = list(cfg.get('active_terms', ['0x0D 0x0A']))
        self._custom_terms: list[str] = list(cfg.get('custom_terms', []))
        self._custom_chip_rows: dict[str, QWidget] = {}
        self._kp_running  = False
        self._colors: dict[str, str] = {}
        self._preset_tab_idx = 0  # 0 = ASCII, 1 = HEX

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── 1. Command ────────────────────────────────────────────────────
        root.addWidget(self._build_command_section())
        root.addWidget(_HSep())

        # ── 2. Terminators ────────────────────────────────────────────────
        root.addWidget(self._build_terminator_section())
        root.addWidget(_HSep())

        # ── 3. Saved commands header (title + tab buttons) ────────────────
        self._preset_hdr = QWidget()
        self._preset_hdr.setObjectName('sb_section')
        ph = QVBoxLayout(self._preset_hdr)
        ph.setContentsMargins(10, 8, 10, 6)
        ph.setSpacing(4)
        ph.addWidget(_SectionTitle('Saved commands'))

        tab_row = QWidget()
        tab_row.setObjectName('preset_tabs_row')
        tr = QHBoxLayout(tab_row)
        tr.setContentsMargins(0, 0, 0, 0)
        tr.setSpacing(3)
        self._btn_preset_ascii = QPushButton('ASCII')
        self._btn_preset_ascii.setObjectName('preset_tab_btn')
        self._btn_preset_ascii.setCheckable(True)
        self._btn_preset_ascii.setChecked(True)
        self._btn_preset_ascii.setFixedHeight(22)
        self._btn_preset_hex_tab = QPushButton('HEX')
        self._btn_preset_hex_tab.setObjectName('preset_tab_btn')
        self._btn_preset_hex_tab.setCheckable(True)
        self._btn_preset_hex_tab.setFixedHeight(22)
        for btn in (self._btn_preset_ascii, self._btn_preset_hex_tab):
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._btn_preset_ascii.clicked.connect(lambda: self._switch_preset_tab(0))
        self._btn_preset_hex_tab.clicked.connect(lambda: self._switch_preset_tab(1))
        tr.addWidget(self._btn_preset_ascii)
        tr.addWidget(self._btn_preset_hex_tab)
        ph.addWidget(tab_row)
        root.addWidget(self._preset_hdr)

        # ── 3b. Stacked scroll areas (ASCII / HEX) ────────────────────────
        self._preset_stack = QStackedWidget()

        # ASCII scroll area
        self._ascii_scroll = QScrollArea()
        self._ascii_scroll.setWidgetResizable(True)
        self._ascii_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._ascii_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._ascii_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ascii_inner = QWidget()
        ascii_inner.setObjectName('preset_inner')
        ascii_inner.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._ascii_preset_layout = QVBoxLayout(ascii_inner)
        self._ascii_preset_layout.setContentsMargins(10, 4, 10, 8)
        self._ascii_preset_layout.setSpacing(5)
        self._presets_data: list[str] = _pad_presets(cfg.get('presets'))
        self._preset_inputs: list[QLineEdit] = []
        self._build_preset_rows(
            self._ascii_preset_layout, self._preset_inputs, self._presets_data, 'ASCII')
        self._ascii_scroll.setWidget(ascii_inner)

        # HEX scroll area
        self._hex_scroll = QScrollArea()
        self._hex_scroll.setWidgetResizable(True)
        self._hex_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._hex_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._hex_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        hex_inner = QWidget()
        hex_inner.setObjectName('preset_inner')
        hex_inner.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._hex_preset_layout = QVBoxLayout(hex_inner)
        self._hex_preset_layout.setContentsMargins(10, 4, 10, 8)
        self._hex_preset_layout.setSpacing(5)
        self._hex_presets_data: list[str] = _pad_presets(cfg.get('hex_presets'))
        self._hex_preset_inputs: list[QLineEdit] = []
        self._build_preset_rows(
            self._hex_preset_layout, self._hex_preset_inputs, self._hex_presets_data, 'HEX')
        self._hex_scroll.setWidget(hex_inner)

        self._preset_stack.addWidget(self._ascii_scroll)
        self._preset_stack.addWidget(self._hex_scroll)
        root.addWidget(self._preset_stack, 1)   # stretch

        root.addWidget(_HSep())

        # ── 4. Keypad ─────────────────────────────────────────────────────
        root.addWidget(self._build_keypad_section())
        root.addWidget(_HSep())

        # ── 5. Theme ──────────────────────────────────────────────────────
        root.addWidget(self._build_theme_section(cfg.get('theme', 'matrix')))

    # ── Section builders ───────────────────────────────────────────────────

    def _build_command_section(self) -> QWidget:
        w = QWidget()
        w.setObjectName('sb_section')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(_SectionTitle('Command'))

        # ASCII / HEX mode selector
        mode_row = QWidget()
        mr = QHBoxLayout(mode_row)
        mr.setContentsMargins(0, 0, 0, 0)
        mr.setSpacing(4)
        self._btn_ascii = QPushButton('ASCII')
        self._btn_ascii.setCheckable(True)
        self._btn_ascii.setChecked(True)
        self._btn_ascii.setObjectName('mode_btn')
        self._btn_hex = QPushButton('HEX')
        self._btn_hex.setCheckable(True)
        self._btn_hex.setObjectName('mode_btn')
        for btn in (self._btn_ascii, self._btn_hex):
            btn.setFixedHeight(24)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            mr.addWidget(btn)
        self._btn_ascii.clicked.connect(lambda: self._set_mode('ASCII'))
        self._btn_hex.clicked.connect(lambda: self._set_mode('HEX'))
        lay.addWidget(mode_row)

        # Input + send
        cmd_row = QWidget()
        cr = QHBoxLayout(cmd_row)
        cr.setContentsMargins(0, 0, 0, 0)
        cr.setSpacing(5)
        self._cmd_input = QLineEdit()
        self._cmd_input.setObjectName('cmd_input')
        self._cmd_input.setPlaceholderText('command…')
        self._cmd_input.setEnabled(False)
        self._cmd_input.returnPressed.connect(self._on_send_cmd)
        self._cmd_input.textChanged.connect(self._on_hex_reformat)
        self._cmd_input.textChanged.connect(
            lambda t: self._btn_send.setEnabled(bool(t.strip()) and self._connected))
        cr.addWidget(self._cmd_input)
        self._btn_send = QPushButton('Send')
        self._btn_send.setFixedHeight(28)
        self._btn_send.setEnabled(False)
        self._btn_send.clicked.connect(self._on_send_cmd)
        cr.addWidget(self._btn_send)
        lay.addWidget(cmd_row)

        # Hex hint label
        self._hex_hint = QLabel('space-separated bytes: FF 0D 1B')
        self._hex_hint.setObjectName('hex_hint')
        self._hex_hint.setVisible(False)
        lay.addWidget(self._hex_hint)
        return w

    def _build_terminator_section(self) -> QWidget:
        w = QWidget()
        w.setObjectName('sb_section')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(_SectionTitle('End of command'))

        # Built-in chips — 2 columns × 2 rows
        chips_grid = QWidget()
        grid = QGridLayout(chips_grid)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)
        self._term_chips: list[_TermChip] = []
        for i, t in enumerate(BUILT_IN_TERMS):
            chip = _TermChip(t['label'], t['key'])
            chip.setChecked(t['key'] in self._active_terms)
            chip.toggled.connect(lambda checked, k=t['key']: self._toggle_term(k, checked))
            chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._term_chips.append(chip)
            grid.addWidget(chip, i // 2, i % 2)
        lay.addWidget(chips_grid)

        # Custom chips container
        self._custom_chips_container = QWidget()
        ccl = QVBoxLayout(self._custom_chips_container)
        ccl.setContentsMargins(0, 0, 0, 0)
        ccl.setSpacing(4)
        self._custom_chips_container.setVisible(False)
        lay.addWidget(self._custom_chips_container)

        # Custom input + add
        custom_row = QWidget()
        cusr = QHBoxLayout(custom_row)
        cusr.setContentsMargins(0, 0, 0, 0)
        cusr.setSpacing(5)
        self._custom_term_input = QLineEdit()
        self._custom_term_input.setFixedWidth(60)
        self._custom_term_input.setPlaceholderText('0x.. or @')
        self._custom_term_input.returnPressed.connect(self._add_custom_term)
        cusr.addWidget(self._custom_term_input)
        btn_add = QPushButton('+ Add')
        btn_add.setFixedHeight(24)
        btn_add.clicked.connect(self._add_custom_term)
        cusr.addWidget(btn_add)
        cusr.addStretch()
        lay.addWidget(custom_row)

        for key in self._custom_terms:
            self._add_custom_chip_widget(key)

        return w

    def _build_preset_rows(
        self,
        layout: QVBoxLayout,
        inputs: list,
        data: list[str],
        mode: str,
    ) -> None:
        """Populate a preset layout with one numbered row per entry in *data*."""
        for i, text in enumerate(data):
            row = QWidget()
            row.setObjectName('preset_row')
            row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(4)

            num = QLabel(str(i + 1))
            num.setObjectName('preset_num')
            num.setFixedWidth(20)
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            rl.addWidget(num)

            inp = QLineEdit(text)
            inp.setObjectName('preset_input')
            inp.setPlaceholderText('FF 0A…' if mode == 'HEX' else f'command {i + 1}…')
            rl.addWidget(inp)
            inputs.append(inp)

            btn = QPushButton('↵')
            btn.setFixedSize(26, 24)
            btn.setObjectName('preset_send')
            btn.setEnabled(bool(text) and self._connected)
            btn.clicked.connect(lambda _, idx=i, m=mode: self._send_preset(idx, m))

            if mode == 'HEX':
                inp.textChanged.connect(
                    lambda _, i_=inp, b=btn: self._on_hex_preset_changed(i_, b))
            else:
                inp.textChanged.connect(
                    lambda t, b=btn: (
                        b.setEnabled(bool(t) and self._connected),
                        self._save_presets(),
                    )
                )
            rl.addWidget(btn)
            layout.addWidget(row)
        layout.addStretch()

    def _build_keypad_section(self) -> QWidget:
        w = QWidget()
        w.setObjectName('keypad_section')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(6)
        lay.addWidget(_SectionTitle('Keypad'))

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(4)

        KEYPAD = [
            ('↖', 'NW'), ('↑', 'N'),  ('↗', 'NE'),
            ('←', 'W'),  (None, None), ('→', 'E'),
            ('↙', 'SW'), ('↓', 'S'),  ('↘', 'SE'),
        ]
        for idx, (sym, label) in enumerate(KEYPAD):
            r, c = divmod(idx, 3)
            if sym is None:
                self._kp_center = _KpButton('▶')
                self._kp_center.setObjectName('kp_center')
                self._kp_center.setToolTip('Start (send START)')
                self._kp_center.clicked.connect(self._on_kp_center)
                grid.addWidget(self._kp_center, r, c)
            else:
                btn = _KpButton(sym)
                btn.setObjectName('kp_dir')
                btn.setToolTip(f'Send DIR:{label}')
                btn.clicked.connect(lambda _, lbl=label: self._on_kp_dir(lbl))
                grid.addWidget(btn, r, c)

        lay.addWidget(grid_w, 0, Qt.AlignmentFlag.AlignHCenter)
        return w

    def _build_theme_section(self, current_theme: str) -> QWidget:
        w = QWidget()
        w.setObjectName('theme_section')
        lay = QVBoxLayout(w)
        lay.setContentsMargins(10, 10, 10, 12)
        lay.setSpacing(6)
        lay.addWidget(_SectionTitle('Theme'))

        self._theme_combo = QComboBox()
        for key, display in THEME_DISPLAY.items():
            self._theme_combo.addItem(display, key)
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == current_theme:
                self._theme_combo.setCurrentIndex(i)
        self._theme_combo.currentIndexChanged.connect(
            lambda: self.theme_changed.emit(self._theme_combo.currentData()))
        lay.addWidget(self._theme_combo)

        swatch_row = QWidget()
        sr = QHBoxLayout(swatch_row)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.setSpacing(5)
        self._swatches: list[_ThemeSwatch] = []
        for key in THEME_DISPLAY:
            sw = _ThemeSwatch(key)
            sw.setChecked(key == current_theme)
            sw.clicked.connect(lambda _, k=key: self._select_theme(k))
            self._swatches.append(sw)
            sr.addWidget(sw)
        lay.addWidget(swatch_row)
        return w

    # ── Slots ──────────────────────────────────────────────────────────────

    def _switch_preset_tab(self, idx: int) -> None:
        self._preset_tab_idx = idx
        self._btn_preset_ascii.setChecked(idx == 0)
        self._btn_preset_hex_tab.setChecked(idx == 1)
        self._preset_stack.setCurrentIndex(idx)
        self._apply_preset_tab_styles()

    def _set_mode(self, mode: str) -> None:
        self._cmd_mode = mode
        self._btn_ascii.setChecked(mode == 'ASCII')
        self._btn_hex.setChecked(mode == 'HEX')
        self._cmd_input.clear()
        self._hex_hint.setVisible(mode == 'HEX')
        placeholder = 'FF 0A 1B…' if mode == 'HEX' else 'command…'
        self._cmd_input.setPlaceholderText(placeholder)
        fam = '"IBM Plex Mono", monospace' if mode == 'HEX' else '"JetBrains Mono", monospace'
        self._cmd_input.setStyleSheet(f'font-family:{fam};')

    def _on_hex_reformat(self, text: str) -> None:
        if self._cmd_mode != 'HEX':
            return
        formatted = format_hex_input(text)
        if formatted != text:
            self._cmd_input.blockSignals(True)
            self._cmd_input.setText(formatted)
            self._cmd_input.blockSignals(False)

    def _on_hex_preset_changed(self, inp: QLineEdit, btn: QPushButton) -> None:
        """Reformat hex input, update button state, and persist."""
        text = inp.text()
        formatted = format_hex_input(text)
        if formatted != text:
            inp.blockSignals(True)
            inp.setText(formatted)
            inp.blockSignals(False)
        btn.setEnabled(bool(formatted.strip()) and self._connected)
        self._save_hex_presets()

    def _on_send_cmd(self) -> None:
        text = self._cmd_input.text().strip()
        if not text or not self._connected:
            return
        self.send_command.emit(text, self._cmd_mode)
        self._cmd_input.clear()

    def _toggle_term(self, key: str, checked: bool) -> None:
        if checked and key not in self._active_terms:
            self._active_terms.append(key)
        elif not checked and key in self._active_terms:
            self._active_terms.remove(key)
        self.terms_changed.emit(list(self._active_terms))

    def _add_custom_term(self) -> None:
        v = self._custom_term_input.text().strip()
        if not v or v in self._custom_terms:
            return
        self._custom_terms.append(v)
        if v not in self._active_terms:
            self._active_terms.append(v)
        self._add_custom_chip_widget(v)
        self._custom_term_input.clear()
        self.terms_changed.emit(list(self._active_terms))
        self.custom_terms_changed.emit(list(self._custom_terms))
        self._apply_chip_styles()

    def _add_custom_chip_widget(self, key: str) -> None:
        row = QWidget()
        row.setObjectName('custom_chip_row')
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(4)

        chip = _TermChip(key, key)
        chip.setChecked(key in self._active_terms)
        chip.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        chip.toggled.connect(lambda checked, k=key: self._toggle_term(k, checked))
        rl.addWidget(chip)

        btn_remove = QPushButton('×')
        btn_remove.setObjectName('chip_remove')
        btn_remove.setFixedSize(22, 24)
        btn_remove.setToolTip(f'Remove  {key}')
        btn_remove.clicked.connect(lambda _, k=key: self._remove_custom_term(k))
        rl.addWidget(btn_remove)

        self._custom_chip_rows[key] = row
        self._custom_chips_container.layout().addWidget(row)
        self._custom_chips_container.setVisible(True)

    def _remove_custom_term(self, key: str) -> None:
        row = self._custom_chip_rows.pop(key, None)
        if row:
            row.setParent(None)
            row.deleteLater()
        if key in self._custom_terms:
            self._custom_terms.remove(key)
        if key in self._active_terms:
            self._active_terms.remove(key)
        self._custom_chips_container.setVisible(bool(self._custom_chip_rows))
        self.terms_changed.emit(list(self._active_terms))
        self.custom_terms_changed.emit(list(self._custom_terms))

    def _send_preset(self, idx: int, mode: str) -> None:
        inputs = self._hex_preset_inputs if mode == 'HEX' else self._preset_inputs
        text = inputs[idx].text().strip()
        if text and self._connected:
            self.send_preset.emit(text, mode)

    def _save_presets(self) -> None:
        self.presets_changed.emit([inp.text() for inp in self._preset_inputs])

    def _save_hex_presets(self) -> None:
        self.hex_presets_changed.emit([inp.text() for inp in self._hex_preset_inputs])

    def _on_kp_dir(self, label: str) -> None:
        if self._connected:
            self.send_keypad.emit(f'DIR:{label}')

    def _on_kp_center(self) -> None:
        self._kp_running = not self._kp_running
        self.send_keypad.emit('STOP' if not self._kp_running else 'START')
        self._kp_center.setText('■' if self._kp_running else '▶')
        self._kp_center.setToolTip(
            'Stop (send STOP)' if self._kp_running else 'Start (send START)')
        self._apply_kp_center_style()

    def _select_theme(self, key: str) -> None:
        for i in range(self._theme_combo.count()):
            if self._theme_combo.itemData(i) == key:
                self._theme_combo.setCurrentIndex(i)
                break
        for sw in self._swatches:
            sw.setChecked(sw.theme_key == key)
        self.theme_changed.emit(key)

    # ── Public API ─────────────────────────────────────────────────────────

    def set_connected(self, connected: bool) -> None:
        self._connected = connected
        self._cmd_input.setEnabled(connected)
        self._btn_send.setEnabled(connected and bool(self._cmd_input.text()))
        self._cmd_input.setPlaceholderText(
            ('FF 0A 1B…' if self._cmd_mode == 'HEX' else 'command…')
            if connected else 'offline'
        )
        for inp in self._preset_inputs:
            btn = inp.parent().findChild(QPushButton, 'preset_send')
            if btn:
                btn.setEnabled(bool(inp.text()) and connected)
        for inp in self._hex_preset_inputs:
            btn = inp.parent().findChild(QPushButton, 'preset_send')
            if btn:
                btn.setEnabled(bool(inp.text().strip()) and connected)

    def get_active_terms(self) -> list[str]:
        return list(self._active_terms)

    def get_presets(self) -> list[str]:
        return [inp.text() for inp in self._preset_inputs]

    def get_hex_presets(self) -> list[str]:
        return [inp.text() for inp in self._hex_preset_inputs]

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c

        for lbl in self.findChildren(QLabel, 'sb_title'):
            lbl.setStyleSheet(
                f'color:{c["fg_dim"]};font-family:"IBM Plex Mono",monospace;'
                f'font-size:9px;font-weight:500;letter-spacing:1px;background:transparent;'
            )

        for sep in self.findChildren(_HSep):
            sep.setStyleSheet(f'background:{c["border2"]};')

        for btn in (self._btn_ascii, self._btn_hex):
            btn.setStyleSheet(
                f'QPushButton{{border:1px solid {c["border"]};color:{c["fg_dim"]};'
                f'font-family:"IBM Plex Mono",monospace;font-size:9px;font-weight:500;'
                f'text-transform:uppercase;letter-spacing:1px;border-radius:2px;}}'
                f'QPushButton:hover{{border-color:{c["fg_dim"]};color:{c["fg"]};'
                f'background:{c["fg_ghost"]};}}'
                f'QPushButton:checked{{border-color:{c["fg"]};color:{c["fg"]};'
                f'background:{c["fg_ghost"]};}}'
            )

        self._hex_hint.setStyleSheet(
            f'color:{c["fg_ghost"]};font-family:"IBM Plex Mono",monospace;'
            f'font-size:8px;background:transparent;letter-spacing:1px;'
        )

        self._apply_chip_styles()

        for btn in self.findChildren(QPushButton, 'chip_remove'):
            btn.setStyleSheet(
                f'QPushButton{{background:transparent;border:1px solid {c["border"]};'
                f'color:{c["red"]};font-size:12px;border-radius:2px;padding:0;}}'
                f'QPushButton:hover{{border-color:{c["red"]};'
                f'background:rgba(220,50,50,20);}}'
            )

        for lbl in self.findChildren(QLabel, 'preset_num'):
            lbl.setStyleSheet(
                f'color:{c["fg_dim"]};font-family:"IBM Plex Mono",monospace;'
                f'font-size:11px;background:transparent;'
            )

        for btn in self.findChildren(_KpButton, 'kp_dir'):
            btn.setStyleSheet(
                f'QPushButton{{background:{c["pad_bg"]};border:1px solid {c["pad_border"]};'
                f'color:{c["pad_fg"]};font-size:15px;border-radius:3px;}}'
                f'QPushButton:hover{{border-color:{c["pad_hover"]};color:{c["pad_hover"]};'
                f'background:rgba(100,200,100,15);}}'
                # Qt QSS has no 'transform' — use a background shift for the
                # pressed feedback so it actually renders (and stops flooding
                # the log with "Unknown property transform" warnings).
                f'QPushButton:pressed{{background:{c["pad_border"]};}}'
            )
        self._apply_kp_center_style()

        self._theme_combo.setStyleSheet(
            f'QComboBox{{background:{c["input_bg"]};border:1px solid {c["border"]};'
            f'color:{c["fg"]};font-family:"IBM Plex Mono",monospace;font-size:10px;'
            f'padding:5px 8px;border-radius:2px;}}'
            f'QComboBox QAbstractItemView{{background:{c["bg2"]};color:{c["fg"]};'
            f'border:1px solid {c["border"]};selection-background-color:{c["fg_ghost"]};}}'
        )

        for sw in self._swatches:
            border = c['fg'] if sw.isChecked() else c['border']
            sw.setStyleSheet(
                sw.styleSheet().split('border:')[0] +
                f'border:1px solid {border};border-radius:2px;'
            )

        # Preset header and both scroll areas share the same background
        self._preset_hdr.setStyleSheet(f'background:{c["bg3"]};')
        for scroll in (self._ascii_scroll, self._hex_scroll):
            scroll.setStyleSheet(
                f'QScrollArea{{background:{c["bg3"]};border:none;}}'
                f'QWidget#preset_inner{{background:{c["bg3"]};}}'
            )

        self._apply_preset_tab_styles()

    def _apply_chip_styles(self) -> None:
        c = self._colors
        if not c:
            return
        for chip in self.findChildren(_TermChip):
            chip.setStyleSheet(
                f'QPushButton{{border:1px solid {c["border"]};color:{c["fg_dim"]};'
                f'font-family:"IBM Plex Mono",monospace;font-size:10px;'
                f'border-radius:2px;padding:3px 7px;background:transparent;}}'
                f'QPushButton:hover{{border-color:{c["fg_dim"]};color:{c["fg"]};}}'
                f'QPushButton:checked{{border-color:{c["fg"]};color:{c["fg"]};'
                f'background:{c["fg_ghost"]};}}'
            )

    def _apply_kp_center_style(self) -> None:
        c = self._colors
        if not c:
            return
        color = c['red'] if self._kp_running else c['pad_center']
        self._kp_center.setStyleSheet(
            f'QPushButton{{background:{c["pad_bg"]};border:1px solid {color};'
            f'color:{color};font-size:13px;border-radius:3px;}}'
            f'QPushButton:hover{{background:rgba(100,200,100,20);}}'
        )

    def _apply_preset_tab_styles(self) -> None:
        c = self._colors
        if not c:
            return
        for btn in (self._btn_preset_ascii, self._btn_preset_hex_tab):
            btn.setStyleSheet(
                f'QPushButton{{border:1px solid {c["border"]};color:{c["fg_dim"]};'
                f'font-family:"IBM Plex Mono",monospace;font-size:9px;font-weight:500;'
                f'letter-spacing:1px;border-radius:2px;background:transparent;}}'
                f'QPushButton:hover{{border-color:{c["fg_dim"]};color:{c["fg"]};'
                f'background:{c["fg_ghost"]};}}'
                f'QPushButton:checked{{border-color:{c["fg"]};color:{c["fg"]};'
                f'background:{c["fg_ghost"]};}}'
            )
