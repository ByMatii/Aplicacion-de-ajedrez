"""Game state: board, per-move history with its evaluation, undo, result and PGN.

No Qt in here, so it can be tested without a UI or Stockfish.
"""
import datetime
import io
from dataclasses import dataclass

import chess
import chess.engine
import chess.pgn

from core.evaluator import classify, cp_white, move_accuracy

PLAYER_NAME = "Jugador"  # PGN name of the human; the opponent is "Stockfish"
LEVEL_HEADER = "NivelBot"  # custom PGN header with the bot level


@dataclass(eq=False)  # identity comparison: two plies are never "the same" ply
class PlyRecord:
    move: chess.Move
    san: str
    number: int  # full-move number the ply belongs to
    color: chess.Color  # who moved
    is_user: bool
    fen_before: str
    fen_after: str
    score_before: chess.engine.PovScore | None = None
    score_after: chess.engine.PovScore | None = None
    best_move: chess.Move | None = None  # engine's best move from fen_before
    label: str | None = None  # set once both scores are known
    loss: int | None = None  # centipawns lost by the mover

    @property
    def numbered_san(self) -> str:
        return f"{self.number}. {self.san}" if self.color == chess.WHITE else f"{self.number}... {self.san}"


class BoardManager:
    def __init__(self, user_color: chess.Color = chess.WHITE):
        # `board` is created once and never replaced: the board widget keeps a reference to it.
        self.board = chess.Board()
        self.user_color = user_color
        self.plies: list[PlyRecord] = []
        self.evals: dict[str, tuple[chess.engine.PovScore, chess.Move | None]] = {}  # fen -> (score, best)

    # state ------------------------------------------------------------------------
    def new_game(self, user_color: chess.Color) -> None:
        self.board.reset()
        self.plies.clear()
        self.evals.clear()
        self.user_color = user_color

    @property
    def last_ply(self) -> PlyRecord | None:
        return self.plies[-1] if self.plies else None

    @property
    def user_to_move(self) -> bool:
        return self.board.turn == self.user_color

    @property
    def is_over(self) -> bool:
        return self.board.is_game_over()

    @property
    def result_text(self) -> str | None:
        outcome = self.board.outcome()
        return f"{self.board.result()} ({outcome.termination.name})" if outcome else None

    # moves ------------------------------------------------------------------------
    def push(self, move: chess.Move) -> PlyRecord:
        fen_before, san = self.board.fen(), self.board.san(move)
        number, color = self.board.fullmove_number, self.board.turn
        self.board.push(move)
        ply = PlyRecord(move, san, number, color, color == self.user_color, fen_before, self.board.fen())
        cached = self.evals.get(fen_before)
        if cached:
            ply.score_before, ply.best_move = cached
        # score_after is NOT taken from the cache on purpose: the fresh analysis arrives through
        # apply_eval(), so a replayed blunder gets judged (and paused on) again after an undo.
        self.plies.append(ply)
        return ply

    def apply_eval(self, fen: str, score: chess.engine.PovScore, best: chess.Move | None) -> PlyRecord | None:
        """Store an analysis. Returns the last ply if this analysis just allowed to classify it."""
        self.evals[fen] = (score, best)
        ply = self.last_ply
        if ply is not None and ply.fen_after == fen:
            ply.score_after = score
            if self._classify(ply):
                return ply
        return None

    def _classify(self, ply: PlyRecord) -> bool:
        if ply.label is not None or ply.score_before is None or ply.score_after is None:
            return False
        ply.label, ply.loss = classify(cp_white(ply.score_before), cp_white(ply.score_after),
                                       ply.color == chess.WHITE, ply.move == ply.best_move)
        return True

    def undo(self) -> bool:
        """Take back the user's last move (and the bot's reply, if it already answered)."""
        if not self.plies:
            return False
        self._pop()
        if self.board.turn != self.user_color and self.plies:
            self._pop()
        return True

    def _pop(self) -> None:
        self.board.pop()
        self.plies.pop()

    # statistics -------------------------------------------------------------------
    def acpl(self, color: chess.Color) -> float | None:
        losses = [p.loss for p in self.plies if p.color == color and p.loss is not None]
        return sum(losses) / len(losses) if losses else None

    def accuracy(self, color: chess.Color) -> float | None:
        """Mean move accuracy (0..100) of one side, over the moves already evaluated."""
        values = [move_accuracy(cp_white(p.score_before), cp_white(p.score_after), p.color == chess.WHITE)
                  for p in self.plies
                  if p.color == color and p.score_before is not None and p.score_after is not None]
        return sum(values) / len(values) if values else None

    # PGN --------------------------------------------------------------------------
    def to_pgn(self, level: str | None = None) -> str:
        """Export the game; each move carries its evaluation as a [%eval] comment."""
        game = chess.pgn.Game()
        game.headers["Event"] = "Partida de entrenamiento"
        game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
        bot = "Stockfish"
        white, black = (PLAYER_NAME, bot) if self.user_color == chess.WHITE else (bot, PLAYER_NAME)
        game.headers["White"], game.headers["Black"] = white, black
        if level:
            game.headers[LEVEL_HEADER] = level
        game.headers["Result"] = self.board.result()
        node = game
        for ply in self.plies:
            node = node.add_variation(ply.move)
            if ply.score_after is not None:
                node.set_eval(ply.score_after)
        return str(game)

    def load_pgn(self, text: str) -> str | None:
        """Replace the current game with the first game in `text`. Returns the saved bot level, if any.

        Raises ValueError (leaving the current game untouched) if the PGN can't be used.
        """
        game = chess.pgn.read_game(io.StringIO(text))
        if game is None:
            raise ValueError("El archivo no contiene ninguna partida.")
        if game.errors:
            raise ValueError("El PGN tiene jugadas ilegales o ilegibles.")
        if game.board().fen() != chess.STARTING_FEN:
            raise ValueError("Solo se pueden cargar partidas que empiezan desde la posición inicial.")
        headers = game.headers
        black_is_user = headers.get("Black") == PLAYER_NAME and headers.get("White") != PLAYER_NAME
        self.new_game(chess.BLACK if black_is_user else chess.WHITE)
        for node in game.mainline():
            ply = self.push(node.move)
            score = node.eval()
            if score is not None:
                ply.score_after = score
                self.evals[ply.fen_after] = (score, None)  # best move unknown: fresh analysis fills it in
                self._classify(ply)
        return headers.get(LEVEL_HEADER)
