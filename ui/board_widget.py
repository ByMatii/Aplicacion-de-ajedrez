"""Clickable chessboard drawn with QPainter (Unicode glyphs, no image assets needed)."""
import math

import chess
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QMenu, QWidget

LIGHT, DARK = QColor("#f0d9b5"), QColor("#b58863")
SELECTED, LAST_MOVE = QColor(246, 246, 105, 170), QColor(205, 210, 106, 140)
ARROW = QColor(40, 160, 70, 200)
PROMOTION_CHOICES = (("Dama", chess.QUEEN), ("Torre", chess.ROOK), ("Alfil", chess.BISHOP), ("Caballo", chess.KNIGHT))


class BoardWidget(QWidget):
    move_made = Signal(object)  # chess.Move, already legal

    def __init__(self, board: chess.Board):
        super().__init__()
        self.board = board
        self.flipped = False
        self.interactive = True
        self.selected: int | None = None
        self.arrows: list[chess.Move] = []
        self.setMinimumSize(320, 320)

    # geometry ---------------------------------------------------------------
    def _side(self) -> float:
        return min(self.width(), self.height()) / 8

    def _rect(self, sq: int) -> QRectF:
        f, r = chess.square_file(sq), chess.square_rank(sq)
        col, row = (7 - f, r) if self.flipped else (f, 7 - r)
        s = self._side()
        return QRectF(col * s, row * s, s, s)

    def _square_at(self, x: float, y: float) -> int | None:
        s = self._side()
        col, row = int(x // s), int(y // s)
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        return chess.square(7 - col, row) if self.flipped else chess.square(col, 7 - row)

    # input ------------------------------------------------------------------
    def _ask_promotion(self, global_pos) -> int | None:
        """Pop-up menu with the four pieces; None if the user dismisses it."""
        menu = QMenu(self)
        actions = {menu.addAction(name): piece_type for name, piece_type in PROMOTION_CHOICES}
        return actions.get(menu.exec(global_pos))

    def _move_from_click(self, from_sq: int, to_sq: int, global_pos) -> chess.Move | None:
        """Legal move from_sq -> to_sq, asking for the promotion piece when a pawn reaches the last rank."""
        move = chess.Move(from_sq, to_sq)
        if move in self.board.legal_moves:
            return move
        if chess.Move(from_sq, to_sq, chess.QUEEN) not in self.board.legal_moves:
            return None  # not a promotion either: illegal
        piece_type = self._ask_promotion(global_pos)
        return chess.Move(from_sq, to_sq, piece_type) if piece_type else None

    def mousePressEvent(self, event):
        if not self.interactive:
            return
        sq = self._square_at(event.position().x(), event.position().y())
        if sq is None:
            return
        if self.selected is not None and sq != self.selected:
            move = self._move_from_click(self.selected, sq, event.globalPosition().toPoint())
            if move:
                self.selected = None
                self.move_made.emit(move)
                return
        piece = self.board.piece_at(sq)
        self.selected = sq if piece and piece.color == self.board.turn else None
        self.update()

    # drawing ----------------------------------------------------------------
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        s = self._side()
        last = self.board.move_stack[-1] if self.board.move_stack else None

        for sq in chess.SQUARES:
            rect = self._rect(sq)
            light = (chess.square_file(sq) + chess.square_rank(sq)) % 2 == 1
            p.fillRect(rect, LIGHT if light else DARK)
            if last and sq in (last.from_square, last.to_square):
                p.fillRect(rect, LAST_MOVE)
            if sq == self.selected:
                p.fillRect(rect, SELECTED)

        if self.selected is not None:  # legal-target dots
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 60))
            for m in self.board.legal_moves:
                if m.from_square == self.selected:
                    p.drawEllipse(self._rect(m.to_square).center(), s * 0.15, s * 0.15)

        font = QFont("Segoe UI Symbol")
        font.setPixelSize(int(s * 0.8))
        font.setStyleStrategy(QFont.NoFontMerging)  # else ♟ etc. fall back to other fonts' glyphs
        for sq, piece in self.board.piece_map().items():
            # filled glyph for both colours, then paint it white or black with an outline
            glyph = chess.Piece(piece.piece_type, chess.BLACK).unicode_symbol()
            rect = self._rect(sq)
            path = QPainterPath()
            path.addText(0, 0, font, glyph)
            path.setFillRule(Qt.WindingFill)
            path = path.simplified()  # merge the glyph's overlapping contours so it fills solid
            br = path.boundingRect()
            path.translate(rect.center() - br.center())
            p.setPen(QPen(QColor("#111"), max(1.0, s / 70)))  # thin + dark: the glyph's inner detail lines get stroked too
            p.setBrush(QColor("#fff") if piece.color else QColor("#111"))
            p.drawPath(path)

        for move in self.arrows:
            self._draw_arrow(p, self._rect(move.from_square).center(), self._rect(move.to_square).center(), s)
        p.end()

    def _draw_arrow(self, p: QPainter, a: QPointF, b: QPointF, s: float):
        angle = math.atan2(b.y() - a.y(), b.x() - a.x())
        head = s * 0.4
        tip_base = b - QPointF(math.cos(angle) * head, math.sin(angle) * head)
        p.setPen(QPen(ARROW, s * 0.15, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a, tip_base)
        left = tip_base + QPointF(math.sin(angle) * head * 0.6, -math.cos(angle) * head * 0.6)
        right = tip_base - QPointF(math.sin(angle) * head * 0.6, -math.cos(angle) * head * 0.6)
        p.setPen(Qt.NoPen)
        p.setBrush(ARROW)
        p.drawPolygon(QPolygonF([b, left, right]))
