"""
Thin status bar below the toolbar showing connection stats.
"""
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel


class StatusBarWidget(QWidget):

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('status_bar')
        self.setFixedHeight(22)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(0)

        def sep():
            lbl = QLabel('│')
            lbl.setObjectName('sb_sep')
            lbl.setContentsMargins(8, 0, 8, 0)
            layout.addWidget(lbl)

        self._lbl_status   = QLabel('OFFLINE')
        self._lbl_bytes    = QLabel('rx 0 B')
        self._lbl_tx       = QLabel('tx 0 B')
        self._lbl_port     = QLabel('/dev/ttyUSB0')
        self._lbl_baud     = QLabel('9,600 baud')
        self._lbl_frame    = QLabel('8N1')
        self._lbl_term     = QLabel('term CR+LF')
        self._lbl_demo     = QLabel('')

        for lbl in (self._lbl_status, self._lbl_bytes, self._lbl_tx,
                    self._lbl_port, self._lbl_baud, self._lbl_frame,
                    self._lbl_term, self._lbl_demo):
            layout.addWidget(lbl)
            if lbl is not self._lbl_demo:
                sep()

        layout.addStretch()
        self._colors: dict[str, str] = {}

    # ── Public API ─────────────────────────────────────────────────────────
    def update_status(
        self,
        connected: bool,
        demo: bool,
        byte_count: int,
        tx_count: int,
        port: str,
        baud: int,
        data_bits: int,
        parity: str,
        stop_bits: float,
        active_terms: list[str],
    ) -> None:
        c = self._colors
        if not c:
            return

        if connected:
            self._lbl_status.setText('CONNECTED')
            self._lbl_status.setStyleSheet(f'color:{c["fg"]};')
        else:
            self._lbl_status.setText('OFFLINE')
            self._lbl_status.setStyleSheet(f'color:{c["fg_dim"]};')

        self._lbl_bytes.setText(f'rx {byte_count:,} B')
        self._lbl_tx.setText(f'tx {tx_count:,} B')
        self._lbl_port.setText(port)
        self._lbl_baud.setText(f'{baud:,} baud')
        self._lbl_frame.setText(
            f'{data_bits}{parity[0].upper()}{stop_bits}')
        term_str = ' + '.join(active_terms) if active_terms else 'none'
        self._lbl_term.setText(f'term {term_str}')

        if demo:
            self._lbl_demo.setText('[DEMO]')
            self._lbl_demo.setStyleSheet(f'color:{c["amber"]};')
        else:
            self._lbl_demo.setText('')

    def apply_theme(self, c: dict[str, str]) -> None:
        self._colors = c
        for child in self.findChildren(QLabel):
            if child.objectName() == 'sb_sep':
                child.setStyleSheet(f'color:{c["border"]};')
            else:
                child.setStyleSheet(f'color:{c["fg_dim"]};')
        # Re-apply live state color for status label
        self._lbl_status.setStyleSheet(f'color:{c["fg_dim"]};')
