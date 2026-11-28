import chess
import pytest

from ui.board_widget import BoardWidget


def widget(fen=chess.STARTING_FEN):
    return BoardWidget(chess.Board(fen))


def test_promotion_uses_the_chosen_piece(qapp):
    w = widget("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    w._ask_promotion = lambda pos: chess.KNIGHT
    assert w._move_from_click(chess.A7, chess.A8, None) == chess.Move(chess.A7, chess.A8, chess.KNIGHT)


def test_promotion_dismissed_makes_no_move(qapp):
    w = widget("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    w._ask_promotion = lambda pos: None
    assert w._move_from_click(chess.A7, chess.A8, None) is None


def test_normal_and_illegal_moves_never_ask(qapp):
    w = widget()

    def fail(pos):
        pytest.fail("should not ask for a promotion piece")

    w._ask_promotion = fail
    assert w._move_from_click(chess.E2, chess.E4, None) == chess.Move.from_uci("e2e4")
    assert w._move_from_click(chess.E2, chess.E5, None) is None
