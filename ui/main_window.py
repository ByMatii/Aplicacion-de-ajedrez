"""Game loop: user move -> analyse -> classify (maybe pause) -> bot move -> analyse -> user turn."""
import chess
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from core.engine_service import LEVELS, EngineService
from core.evaluator import BEST, BLUNDER, classify, cp_white, format_score
from ui.board_widget import BoardWidget
from ui.eval_bar_widget import EvalBarWidget


class MainWindow(QMainWindow):
    def __init__(self, engine_path: str):
        super().__init__()
        self.setWindowTitle("Entrenador de Ajedrez")
        self.board = chess.Board()
        self.evals: dict[str, tuple] = {}  # fen -> (PovScore, best move)
        self.notes: list[tuple[str, int | None]] = []  # per ply: (text for list, user's cp loss or None)
        self.user_color = chess.WHITE
        self.pending_retry = False

        self.engine = EngineService(engine_path)
        self.engine.worker.analysed.connect(self.on_analysed)
        self.engine.worker.bot_moved.connect(self.on_bot_moved)
        # bound methods, not lambdas: Qt queues them onto the UI thread; a lambda would run in the engine thread
        self.engine.worker.failed.connect(self.on_engine_failed)

        self.board_view = BoardWidget(self.board)
        self.board_view.move_made.connect(self.on_user_move)
        self.eval_bar = EvalBarWidget()

        self.level = QComboBox()
        self.level.addItems(LEVELS)
        self.color = QComboBox()
        self.color.addItems(["Juego con blancas", "Juego con negras"])
        self.coach = QCheckBox("Entrenador: frenar ante errores graves")
        self.coach.setChecked(True)
        new_btn, hint_btn, self.undo_btn, self.continue_btn = (
            QPushButton(t) for t in ("Nueva partida", "Pista", "Deshacer", "Continuar"))
        new_btn.clicked.connect(self.new_game)
        hint_btn.clicked.connect(self.show_hint)
        self.undo_btn.clicked.connect(self.undo)
        self.continue_btn.clicked.connect(self.continue_after_blunder)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.accuracy = QLabel()
        self.moves = QListWidget()

        side = QVBoxLayout()
        for w in (QLabel("Nivel del bot"), self.level, self.color, self.coach, new_btn, hint_btn,
                  self.undo_btn, self.continue_btn, self.feedback, self.accuracy, self.moves):
            side.addWidget(w)
        row = QHBoxLayout()
        row.addWidget(self.eval_bar)
        row.addWidget(self.board_view, 1)
        row.addLayout(side)
        central = QWidget()
        central.setLayout(row)
        self.setCentralWidget(central)
        self.resize(980, 640)
        self.new_game()

    # flow ---------------------------------------------------------------------
    def new_game(self):
        self.board.reset()
        self.evals.clear()
        self.notes.clear()
        self.pending_retry = False
        self.user_color = chess.WHITE if self.color.currentIndex() == 0 else chess.BLACK
        self.board_view.flipped = self.eval_bar.flipped = self.user_color == chess.BLACK
        self.feedback.setText("")
        self.refresh()
        self.analyse_current()

    def analyse_current(self):
        self.board_view.interactive = False
        self.engine.request_analysis.emit(self.board.fen())

    def on_analysed(self, fen, score, best):
        if fen != self.board.fen():
            return  # stale: board changed (undo/new game) while the engine was thinking
        self.evals[fen] = (score, best)
        self.eval_bar.set_eval(cp_white(score), format_score(score))
        if self.board.move_stack and self.board.turn != self.user_color:
            self.judge_user_move(score)
        else:
            self.next_turn()

    def judge_user_move(self, score_after):
        move = self.board.peek()
        before = self.board.copy()
        before.pop()
        score_before, best = self.evals[before.fen()]
        label, loss = classify(cp_white(score_before), cp_white(score_after),
                               self.user_color == chess.WHITE, move == best)
        san = before.san(move)
        self.notes[-1] = (f"{self._num(before)}{san}   — {label}", loss)
        text = f"{san}: {label}"
        if label != BEST and best:
            text += f" (−{loss / 100:.1f}). Mejor era {before.san(best)}."
        self.feedback.setText(text)
        self.refresh()
        if label == BLUNDER and self.coach.isChecked():
            self.pending_retry = True
            self.feedback.setText(text + "\nPulsa Deshacer para reintentar o Continuar para seguir.")
            self.refresh()
            return
        self.next_turn()

    def next_turn(self):
        if self.board.is_game_over():
            outcome = self.board.outcome()
            self.feedback.setText(f"{self.feedback.text()}\nFin: {self.board.result()} ({outcome.termination.name}).")
            self.board_view.interactive = False
            return
        if self.board.turn == self.user_color:
            self.board_view.interactive = True
        else:
            self.engine.request_move.emit(self.board.fen(), self.level.currentText())

    def on_user_move(self, move):
        self._push(move)
        self.analyse_current()

    def on_bot_moved(self, fen, move):
        if fen != self.board.fen():
            return
        self._push(move)
        self.analyse_current()

    def on_engine_failed(self, msg):
        QMessageBox.warning(self, "Motor", msg)

    def continue_after_blunder(self):
        if self.pending_retry:
            self.pending_retry = False
            self.refresh()
            self.next_turn()

    def undo(self):
        if not self.board.move_stack:
            return
        self.board.pop()
        if self.board.turn != self.user_color and self.board.move_stack:
            self.board.pop()
        del self.notes[len(self.board.move_stack):]
        self.pending_retry = False
        self.feedback.setText("Jugada deshecha. Prueba otra.")
        self.refresh()
        cached = self.evals.get(self.board.fen())
        if cached:
            self.eval_bar.set_eval(cp_white(cached[0]), format_score(cached[0]))
            self.next_turn()
        else:
            self.analyse_current()

    def show_hint(self):
        cached = self.evals.get(self.board.fen())
        if self.board.turn == self.user_color and cached and cached[1]:
            self.board_view.arrows = [cached[1]]
            self.board_view.update()

    # helpers ------------------------------------------------------------------
    def _push(self, move):
        san = self.board.san(move)
        num = self._num(self.board)
        self.board.push(move)
        self.notes.append((f"{num}{san}", None))
        self.refresh()

    @staticmethod
    def _num(board: chess.Board) -> str:
        return f"{board.fullmove_number}. " if board.turn == chess.WHITE else f"{board.fullmove_number}... "

    def refresh(self):
        self.board_view.arrows = []
        self.board_view.selected = None
        self.board_view.update()
        self.continue_btn.setEnabled(self.pending_retry)
        self.moves.clear()
        self.moves.addItems([text for text, _ in self.notes])
        self.moves.scrollToBottom()
        losses = [loss for _, loss in self.notes if loss is not None]
        self.accuracy.setText(f"ACPL (tu pérdida media): {sum(losses) / len(losses):.0f}" if losses else "")

    def closeEvent(self, event):
        self.engine.shutdown()
        super().closeEvent(event)
