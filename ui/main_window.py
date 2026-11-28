"""UI coordinator. Game state lives in core.board_manager; the engine runs in core.engine_service.

Flow: user move -> analyse -> classify (maybe pause) -> bot move -> analyse -> user turn.
"""
import chess
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from core.board_manager import BoardManager, PlyRecord
from core.engine_service import LEVELS, EngineService
from core.evaluator import BEST, BLUNDER, cp_white, format_score
from ui.board_widget import BoardWidget
from ui.eval_bar_widget import EvalBarWidget


class MainWindow(QMainWindow):
    def __init__(self, engine_path: str):
        super().__init__()
        self.setWindowTitle("Entrenador de Ajedrez")
        self.game = BoardManager()
        self.board = self.game.board  # same object the board widget draws
        self.pending_retry = False
        self.engine_ok = True

        self.engine = EngineService(engine_path)
        self.engine.worker.analysed.connect(self.on_analysed)
        self.engine.worker.bot_moved.connect(self.on_bot_moved)
        # bound methods, not lambdas: Qt queues them onto the UI thread; a lambda would run in the engine thread
        self.engine.worker.failed.connect(self.on_engine_failed)
        self.engine.worker.restarted.connect(self.on_engine_restarted)

        self.board_view = BoardWidget(self.board)
        self.board_view.move_made.connect(self.on_user_move)
        self.eval_bar = EvalBarWidget()

        self.level = QComboBox()
        self.level.addItems(LEVELS)
        self.color = QComboBox()
        self.color.addItems(["Juego con blancas", "Juego con negras"])
        self.coach = QCheckBox("Entrenador: frenar ante errores graves")
        self.coach.setChecked(True)
        new_btn, hint_btn, self.undo_btn, self.continue_btn, save_btn, load_btn = (
            QPushButton(t) for t in ("Nueva partida", "Pista", "Deshacer", "Continuar", "Guardar PGN", "Cargar PGN"))
        new_btn.clicked.connect(self.new_game)
        hint_btn.clicked.connect(self.show_hint)
        self.undo_btn.clicked.connect(self.undo)
        self.continue_btn.clicked.connect(self.continue_after_blunder)
        save_btn.clicked.connect(self.save_game)
        load_btn.clicked.connect(self.load_game)
        self.feedback = QLabel()
        self.feedback.setWordWrap(True)
        self.accuracy = QLabel()
        self.moves = QListWidget()

        side = QVBoxLayout()
        for w in (QLabel("Nivel del bot"), self.level, self.color, self.coach, new_btn, hint_btn,
                  self.undo_btn, self.continue_btn, save_btn, load_btn, self.feedback, self.accuracy, self.moves):
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
        self.game.new_game(chess.WHITE if self.color.currentIndex() == 0 else chess.BLACK)
        self._begin()

    def _begin(self):
        """Common start for a new or a loaded game: reset UI state, analyse the position."""
        self.pending_retry = False
        self.board_view.flipped = self.eval_bar.flipped = self.game.user_color == chess.BLACK
        self.feedback.setText("")
        self.refresh()
        if not self.engine_ok:  # queued before the analysis, so the engine is back by then
            self.engine.request_restart.emit()
        self.analyse_current()

    def analyse_current(self):
        self.board_view.interactive = False
        self.engine.request_analysis.emit(self.board.fen())

    def on_analysed(self, fen, score, best):
        if fen != self.board.fen():
            return  # stale: board changed (undo/new game) while the engine was thinking
        judged = self.game.apply_eval(fen, score, best)
        self.eval_bar.set_eval(cp_white(score), format_score(score))
        if judged and judged.is_user:
            self.judge_user_move(judged)
        else:
            self.next_turn()

    def judge_user_move(self, ply: PlyRecord):
        text = f"{ply.san}: {ply.label}"
        if ply.label != BEST and ply.best_move:
            text += f" (−{ply.loss / 100:.1f}). Mejor era {chess.Board(ply.fen_before).san(ply.best_move)}."
        self.feedback.setText(text)
        self.refresh()
        if ply.label == BLUNDER and self.coach.isChecked():
            self.pending_retry = True
            self.feedback.setText(text + "\nPulsa Deshacer para reintentar o Continuar para seguir.")
            self.refresh()
            return
        self.next_turn()

    def next_turn(self):
        if self.game.is_over:
            self.feedback.setText(f"{self.feedback.text()}\nFin: {self.game.result_text}.")
            self.board_view.interactive = False
            return
        if self.game.user_to_move:
            self.board_view.interactive = True
        else:
            self.engine.request_move.emit(self.board.fen(), self.level.currentText())

    def on_user_move(self, move):
        self.game.push(move)
        self.refresh()
        self.analyse_current()

    def on_bot_moved(self, fen, move):
        if fen != self.board.fen():
            return
        self.game.push(move)
        self.refresh()
        self.analyse_current()

    def on_engine_failed(self, msg):
        self.engine_ok = False  # the next "Nueva partida" asks the worker to restart Stockfish
        QMessageBox.warning(self, "Motor", msg)

    def on_engine_restarted(self):
        self.engine_ok = True
        self.statusBar().showMessage("Stockfish se reinició.", 5000)

    def continue_after_blunder(self):
        if self.pending_retry:
            self.pending_retry = False
            self.refresh()
            self.next_turn()

    def undo(self):
        if not self.game.undo():
            return
        self.pending_retry = False
        self.feedback.setText("Jugada deshecha. Prueba otra.")
        self.refresh()
        cached = self.game.evals.get(self.board.fen())
        if cached:
            self.eval_bar.set_eval(cp_white(cached[0]), format_score(cached[0]))
            self.next_turn()
        else:
            self.analyse_current()

    def show_hint(self):
        cached = self.game.evals.get(self.board.fen())
        if self.game.user_to_move and cached and cached[1]:
            self.board_view.arrows = [cached[1]]
            self.board_view.update()

    # save / load --------------------------------------------------------------
    def save_game(self):
        path, _ = QFileDialog.getSaveFileName(self, "Guardar partida", "partida.pgn", "PGN (*.pgn)")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.game.to_pgn(self.level.currentText()) + "\n")
        except OSError as e:
            QMessageBox.warning(self, "Guardar partida", f"No se pudo guardar: {e}")

    def load_game(self):
        path, _ = QFileDialog.getOpenFileName(self, "Cargar partida", "", "PGN (*.pgn);;Todos los archivos (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig") as f:
                level = self.game.load_pgn(f.read())
        except (OSError, UnicodeDecodeError, ValueError) as e:
            QMessageBox.warning(self, "Cargar partida", f"No se pudo cargar: {e}")
            return
        if level in LEVELS:
            self.level.setCurrentText(level)
        self.color.setCurrentIndex(0 if self.game.user_color == chess.WHITE else 1)
        self._begin()  # re-analyses the position; if it's the bot's turn it moves, so the game resumes

    # helpers ------------------------------------------------------------------
    @staticmethod
    def _ply_text(ply: PlyRecord) -> str:
        # only the user's moves show their label in the list
        return f"{ply.numbered_san}   — {ply.label}" if ply.is_user and ply.label else ply.numbered_san

    def refresh(self):
        self.board_view.arrows = []
        self.board_view.selected = None
        self.board_view.update()
        self.continue_btn.setEnabled(self.pending_retry)
        self.moves.clear()
        self.moves.addItems([self._ply_text(p) for p in self.game.plies])
        self.moves.scrollToBottom()
        me, bot = self.game.accuracy(self.game.user_color), self.game.accuracy(not self.game.user_color)
        acpl = self.game.acpl(self.game.user_color)
        lines = []
        if me is not None:
            lines.append(f"Precisión: tú {me:.0f} %" + (f" · bot {bot:.0f} %" if bot is not None else ""))
        if acpl is not None:
            lines.append(f"ACPL (tu pérdida media): {acpl:.0f}")
        self.accuracy.setText("\n".join(lines))

    def closeEvent(self, event):
        self.engine.shutdown()
        super().closeEvent(event)
