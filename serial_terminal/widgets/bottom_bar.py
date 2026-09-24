"""
Bottom control bar: clear, auto-scroll, buffer size selector, file save.
"""
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QLineEdit, QCheckBox, QFrame,
)


class _VSep(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.VLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedWidth(1)
        self.setFixedHeight(22)


class BottomBar(QWidget):

    clear_clicked       = pyqtSignal()
    auto_scroll_changed = pyqtSignal(bool)
    buf_size_changed    = pyqtSignal(int)
    save_clicked        = pyqtSignal(str)   # emits filename
    auto_save_changed   = pyqtSignal(bool)

    def __init__(self, cfg: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName('bottom_bar')
        self.setFixedHeight(44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(7)

        # Clear buffer
        btn_clear = QPushButton('✕')
        btn_clear.setFixedSize(28, 28)
        btn_clear.setToolTip('Clear buffer')
        btn_clear.clicked.connect(self.clear_clicked)
        layout.addWidget(btn_clear)

        # Auto-scroll toggle
        self._btn_scroll = QPushButton('⬇')
        self._btn_scroll.setFixedSize(28, 28)
        self._btn_scroll.setCheckable(True)
        self._btn_scroll.setChecked(True)
        self._btn_scroll.setToolTip('Toggle auto-scroll')
        self._btn_scroll.toggled.connect(self.auto_scroll_changed)
        layout.addWidget(self._btn_scroll)

        layout.addWidget(_VSep())

        # Buffer size
        lbl_buf = QLabel('buf')
        lbl_buf.setObjectName('bar_label')
        layout.addWidget(lbl_buf)

        self._buf_select = QComboBox()
        self._buf_select.setObjectName('bar_select')
        for n in [1000, 5000, 10000, 50000]:
            label = f'{n // 1000}k' if n >= 1000 else str(n)
            self._buf_select.addItem(label, n)
        initial_buf = cfg.get('buf_size', 10000)
        for i in range(self._buf_select.count()):
            if self._buf_select.itemData(i) == initial_buf:
                self._buf_select.setCurrentIndex(i)
                break
        self._buf_select.currentIndexChanged.connect(
            lambda: self.buf_size_changed.emit(self._buf_select.currentData()))
        layout.addWidget(self._buf_select)

        layout.addWidget(_VSep())

        # File save
        lbl_file = QLabel('file')
        lbl_file.setObjectName('bar_label')
        layout.addWidget(lbl_file)

        self._filename = QLineEdit(cfg.get('save_filename', 'capture.txt'))
        self._filename.setFixedWidth(130)
        self._filename.setPlaceholderText('capture.txt')
        layout.addWidget(self._filename)

        btn_save = QPushButton('Save')
        btn_save.setObjectName('btn_primary')
        btn_save.setFixedHeight(28)
        btn_save.setToolTip('Save buffer to file')
        btn_save.clicked.connect(lambda: self.save_clicked.emit(self._filename.text()))
        layout.addWidget(btn_save)

        self._chk_auto = QCheckBox('auto')
        self._chk_auto.setToolTip('Auto-save capture to a timestamped file on close')
        self._chk_auto.toggled.connect(self.auto_save_changed)
        layout.addWidget(self._chk_auto)

        layout.addStretch()

    # ── Public API ─────────────────────────────────────────────────────────
    def set_auto_scroll(self, value: bool) -> None:
        self._btn_scroll.blockSignals(True)
        self._btn_scroll.setChecked(value)
        self._btn_scroll.setText('⬇' if value else '⏸')
        self._btn_scroll.blockSignals(False)

    def get_filename(self) -> str:
        return self._filename.text() or 'capture.txt'

    def apply_theme(self, c: dict[str, str]) -> None:
        for lbl in self.findChildren(QLabel):
            if lbl.objectName() == 'bar_label':
                lbl.setStyleSheet(
                    f'color:{c["fg_dim"]};'
                    f'font-family:"IBM Plex Mono",monospace;'
                    f'font-size:9px;background:transparent;'
                )
        for sep in self.findChildren(_VSep):
            sep.setStyleSheet(f'color:{c["border"]};')

        self._buf_select.setStyleSheet(
            f'background:{c["input_bg"]};border:1px solid {c["border"]};'
            f'color:{c["fg"]};font-family:"IBM Plex Mono",monospace;font-size:10px;'
            f'padding:3px 5px;border-radius:2px;'
        )
