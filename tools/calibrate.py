"""Estimate a bot level's Elo by playing it against Stockfish at a fixed UCI_Elo.

    python tools/calibrate.py "Principiante (~800)" --games 30 --anchor 1320

Elo is relative to Stockfish's own UCI_Elo scale (engine Elo, not chess.com/Lichess human ratings).
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chess
import chess.engine

from core.engine_service import LEVELS, bot_move, find_stockfish


def elo_diff(score: float) -> float:
    score = min(max(score, 0.01), 0.99)  # 0% or 100% has no finite Elo; clamp to a bound
    return -400 * math.log10(1 / score - 1)


def play_game(bot, anchor, level, anchor_limit, bot_white) -> float:
    board = chess.Board()
    while not board.is_game_over(claim_draw=True) and board.ply() < 300:
        if (board.turn == chess.WHITE) == bot_white:
            move = bot_move(bot, board, level)
        else:
            move = anchor.play(board, anchor_limit).move
        board.push(move)
    result = board.result(claim_draw=True)
    if result == "1/2-1/2" or result == "*":
        return 0.5
    return 1.0 if (result == "1-0") == bot_white else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("level", choices=list(LEVELS))
    ap.add_argument("--games", type=int, default=30)
    ap.add_argument("--anchor", type=int, default=1320, help="anchor UCI_Elo (Stockfish min is 1320)")
    ap.add_argument("--anchor-level", choices=list(LEVELS), help="use another bot level as the anchor instead")
    ap.add_argument("--anchor-elo", type=float, help="known Elo of --anchor-level")
    args = ap.parse_args()

    path = find_stockfish()
    bot = chess.engine.SimpleEngine.popen_uci(path)
    anchor = chess.engine.SimpleEngine.popen_uci(path)
    anchor_limit = chess.engine.Limit(time=0.1)
    opponent = anchor
    if args.anchor_level:
        class opponent:  # level vs level: anchor picks moves with the same weakening logic
            @staticmethod
            def play(board, _limit):
                return chess.engine.PlayResult(bot_move(anchor, board, args.anchor_level), None)
    else:
        anchor.configure({"UCI_LimitStrength": True, "UCI_Elo": args.anchor})
    total = 0.0
    try:
        for g in range(args.games):
            total += play_game(bot, opponent, args.level, anchor_limit, g % 2 == 0)
            print(f"game {g + 1}: {total}/{g + 1}", flush=True)
    finally:
        bot.quit()
        anchor.quit()
    score = total / args.games
    base = args.anchor_elo if args.anchor_level else args.anchor
    print(f"score {score:.2f} -> Elo ≈ {base + elo_diff(score):.0f} (±~150 with {args.games} games)")


if __name__ == "__main__":
    main()
