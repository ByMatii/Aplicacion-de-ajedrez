"""Vertical advantage bar: white share grows from White's side of the board."""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from core.evaluator import white_share


class EvalBarWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.cp = 0
        self.text = "0.0"
        self.flipped = False
        self.setFixedWidth(34)

    def set_eval(self, cp: int, text: str):
        self.cp, self.text = cp, text
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        w, h = self.width(), self.height()
        white_h = h * white_share(self.cp)
        p.fillRect(0, 0, w, h, QColor("#333"))
        white_rect = QRectF(0, 0, w, white_h) if self.flipped else QRectF(0, h - white_h, w, white_h)
        p.fillRect(white_rect, QColor("#eee"))
        winning_white = self.cp >= 0
        # label sits on the leader's end of the bar
        at_bottom = winning_white != self.flipped
        p.setPen(QColor("#333") if winning_white else QColor("#eee"))
        label_rect = QRectF(0, h - 22, w, 20) if at_bottom else QRectF(0, 2, w, 20)
        p.drawText(label_rect, Qt.AlignCenter, self.text)
        p.end()
