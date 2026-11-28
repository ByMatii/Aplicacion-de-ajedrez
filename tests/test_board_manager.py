"""BoardManager + accuracy. No Qt, no Stockfish: engine results are faked."""
import chess
import pytest
from chess.engine import Cp, PovScore

from core.board_manager import PLAYER_NAME, BoardManager
from core.evaluator import BEST, BLUNDER, cp_white, move_accuracy

START = chess.STARTING_FEN


def score(cp):
    return PovScore(Cp(cp), chess.WHITE)


def mv(uci):
    return chess.Move.from_uci(uci)


def test_push_records_the_ply():
    g = BoardManager()
    ply = g.push(mv("e2e4"))
    assert (ply.san, ply.number, ply.color, ply.is_user) == ("e4", 1, chess.WHITE, True)
    assert ply.numbered_san == "1. e4"
    assert ply.fen_before == START and ply.fen_after == g.board.fen()
    assert g.push(mv("e7e5")).numbered_san == "1... e5" and not g.last_ply.is_user


def test_blunder_is_judged_with_cached_best_move():
    g = BoardManager()
    assert g.apply_eval(START, score(30), mv("e2e4")) is None  # nothing to judge yet
    g.push(mv("f2f3"))
    judged = g.apply_eval(g.board.fen(), score(-400), None)
    assert judged is g.last_ply and judged.label == BLUNDER and judged.loss == 430
    assert judged.best_move == mv("e2e4")


def test_best_move_label():
    g = BoardManager()
    g.apply_eval(START, score(30), mv("e2e4"))
    g.push(mv("e2e4"))
    assert g.apply_eval(g.board.fen(), score(30), None).label == BEST


def test_undo_takes_back_user_move_and_bot_reply():
    g = BoardManager()
    g.push(mv("e2e4"))
    g.push(mv("e7e5"))  # bot answered: user is on move again
    assert g.undo() and g.board.fen() == START and not g.plies
    g.push(mv("e2e4"))  # bot hasn't answered yet: only the user's move goes
    assert g.undo() and g.board.fen() == START
    assert not g.undo()  # nothing left


def test_replaying_a_blunder_after_undo_is_judged_again():
    g = BoardManager()
    g.apply_eval(START, score(30), mv("e2e4"))
    g.push(mv("f2f3"))
    assert g.apply_eval(g.board.fen(), score(-400), None).label == BLUNDER
    g.undo()
    g.push(mv("f2f3"))
    assert g.apply_eval(g.board.fen(), score(-400), None).label == BLUNDER  # cached eval must not skip the judging


def test_game_over_result():
    g = BoardManager()
    assert g.result_text is None
    for u in ("f2f3", "e7e5", "g2g4", "d8h4"):  # fool's mate
        g.push(mv(u))
    assert g.is_over and g.result_text == "0-1 (CHECKMATE)"


def test_accuracy_and_acpl():
    g = BoardManager()
    assert g.accuracy(chess.WHITE) is None and g.acpl(chess.WHITE) is None
    g.apply_eval(START, score(30), mv("e2e4"))
    g.push(mv("f2f3"))
    g.apply_eval(g.board.fen(), score(-400), None)
    assert g.accuracy(chess.WHITE) < 30
    assert g.acpl(chess.WHITE) == 430
    assert g.accuracy(chess.BLACK) is None  # bot has no move with both evaluations yet


def test_move_accuracy_curve():
    assert move_accuracy(30, 30, True) > 99
    assert move_accuracy(30, 200, True) > 99  # improving the position isn't penalised
    assert move_accuracy(30, -400, True) < 30
    assert move_accuracy(-30, 400, False) == pytest.approx(move_accuracy(30, -400, True))  # symmetric for Black


def test_pgn_round_trip():
    g = BoardManager()
    g.new_game(chess.BLACK)
    g.apply_eval(START, score(20), mv("e2e4"))
    g.push(mv("e2e4"))  # bot
    g.apply_eval(g.board.fen(), score(20), mv("e7e5"))
    g.push(mv("e7e5"))  # user
    g.apply_eval(g.board.fen(), score(30), mv("g1f3"))
    g.push(mv("g1f3"))
    g.apply_eval(g.board.fen(), score(-30), None)

    pgn = g.to_pgn("Principiante (~800)")
    assert PLAYER_NAME in pgn and "[%eval" in pgn

    h = BoardManager()
    assert h.load_pgn(pgn) == "Principiante (~800)"
    assert h.user_color == chess.BLACK
    assert [p.move for p in h.plies] == [p.move for p in g.plies]
    assert h.board.fen() == g.board.fen()
    assert abs(cp_white(h.plies[-1].score_after) - (-30)) <= 1  # [%eval] has 2 decimals
    assert h.plies[0].label is None and h.plies[1].label is not None  # first ply has no "before" eval


@pytest.mark.parametrize("text", ["", "1. e4 e5 2. Ke5 *"])
def test_bad_pgn_is_rejected_and_game_untouched(text):
    g = BoardManager()
    g.push(mv("e2e4"))
    with pytest.raises(ValueError):
        g.load_pgn(text)
    assert len(g.plies) == 1 and g.board.fen() == g.plies[0].fen_after
