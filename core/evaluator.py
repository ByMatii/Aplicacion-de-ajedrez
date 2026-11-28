"""Turns engine scores into numbers for the eval bar and labels for the coach."""
import math

import chess.engine

BEST, GOOD, INACCURACY, MISTAKE, BLUNDER = "Mejor jugada", "Buena", "Imprecisión", "Error", "Error grave"

CP_CLAMP = 1000  # mates count as ±10 pawns so a missed mate reads as a blunder, not an infinite loss


def cp_white(score: chess.engine.PovScore) -> int:
    """Centipawns from White's point of view, clamped."""
    cp = score.white().score(mate_score=100_000)
    return max(-CP_CLAMP, min(CP_CLAMP, cp))


def format_score(score: chess.engine.PovScore) -> str:
    w = score.white()
    if w.is_mate():
        return f"#{w.mate()}"
    return f"{w.score() / 100:+.1f}"


def white_share(cp: int) -> float:
    """0..1 portion of the bar for White (logistic, like a win probability)."""
    return 1 / (1 + 10 ** (-cp / 400))


def classify(cp_before: int, cp_after: int, white_moved: bool, is_best: bool) -> tuple[str, int]:
    """Label a move by how many centipawns the mover lost. Returns (label, loss)."""
    loss = cp_before - cp_after if white_moved else cp_after - cp_before
    loss = max(0, loss)
    if is_best:
        return BEST, loss
    if loss > 250:
        return BLUNDER, loss
    if loss > 100:
        return MISTAKE, loss
    if loss >= 50:
        return INACCURACY, loss
    return GOOD, loss


def move_accuracy(cp_before: int, cp_after: int, white_moved: bool) -> float:
    """Accuracy 0..100 of one move: Lichess-style curve over the mover's win-probability drop."""
    drop = 100 * (white_share(cp_before) - white_share(cp_after))
    if not white_moved:
        drop = -drop
    drop = max(0.0, drop)
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * drop) - 3.1669))
