"""Evaluator labels + one end-to-end case of the game loop (engine results are faked)."""
import chess
from chess.engine import Cp, Mate, PovScore
from PySide6.QtWidgets import QMessageBox

from core.evaluator import BEST, BLUNDER, GOOD, INACCURACY, MISTAKE, classify, cp_white, format_score


def test_evaluator():
    assert classify(30, 30, True, True) == (BEST, 0)
    assert classify(30, 0, True, False) == (GOOD, 30)
    assert classify(30, -40, True, False) == (INACCURACY, 70)
    assert classify(30, -170, True, False) == (MISTAKE, 200)
    assert classify(30, -400, True, False)[0] == BLUNDER
    assert classify(-30, 400, False, False)[0] == BLUNDER  # black lost 4.3
    assert cp_white(PovScore(Mate(3), chess.BLACK)) == -1000
    assert format_score(PovScore(Cp(-180), chess.BLACK)) == "+1.8"
    assert format_score(PovScore(Mate(4), chess.WHITE)) == "#4"


def test_game_loop_pauses_on_blunder_and_undo_retries(qapp, monkeypatch):
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: None)  # the missing engine reports a failure
    from ui.main_window import MainWindow
    w = MainWindow("missing-engine")
    for signal in (w.engine.request_move, w.engine.request_analysis, w.engine.request_restart):
        signal.disconnect()  # keep the fake from reaching a real worker
    w.grab()  # paints board + bar once

    start = w.board.fen()
    w.on_analysed(start, PovScore(Cp(30), chess.WHITE), chess.Move.from_uci("e2e4"))
    assert w.board_view.interactive
    w.on_user_move(chess.Move.from_uci("f2f3"))
    w.on_analysed(w.board.fen(), PovScore(Cp(-400), chess.WHITE), None)
    assert w.pending_retry and "Error grave" in w.feedback.text()
    assert "Precisión" in w.accuracy.text()
    w.undo()
    assert w.board.fen() == start and w.board_view.interactive and not w.pending_retry
    w.engine.shutdown()
