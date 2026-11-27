"""Stockfish over UCI, running in its own QThread so the UI never blocks."""
import glob
import os
import shutil

import chess
import chess.engine
from PySide6.QtCore import QObject, QThread, Signal, Slot

Limit = chess.engine.Limit

# Every level sets all strength options so switching levels never inherits the previous one.
# Stockfish's UCI_Elo floor is ~1320, so the beginner level uses Skill Level 0 + tiny depth instead.
LEVELS = {
    "Principiante (~800)": ({"Skill Level": 0, "UCI_LimitStrength": False}, Limit(depth=1)),
    "Intermedio (~1400)": ({"Skill Level": 20, "UCI_LimitStrength": True, "UCI_Elo": 1400}, Limit(time=0.3)),
    "Avanzado (~2000)": ({"Skill Level": 20, "UCI_LimitStrength": True, "UCI_Elo": 2000}, Limit(time=0.5)),
    "Maestro (sin límite)": ({"Skill Level": 20, "UCI_LimitStrength": False}, Limit(time=1.0)),
}
ANALYSIS_LIMIT = Limit(time=0.25)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_stockfish() -> str | None:
    if os.environ.get("STOCKFISH_PATH"):
        return os.environ["STOCKFISH_PATH"]
    # recursive: the official download unzips into its own folder (sources + binary)
    local = sorted(glob.glob(os.path.join(ROOT, "assets", "engines", "**", "stockfish*"), recursive=True))
    local = [p for p in local if os.path.isfile(p) and (p.endswith(".exe") if os.name == "nt" else os.access(p, os.X_OK))]
    return local[0] if local else shutil.which("stockfish")


class EngineWorker(QObject):
    analysed = Signal(str, object, object)  # fen, PovScore, best move (or None)
    bot_moved = Signal(str, object)  # fen it played from, move
    failed = Signal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path
        self.analyst = self.bot = None  # two processes: analysis must stay full strength

    @Slot()
    def start(self):
        try:
            self.analyst = chess.engine.SimpleEngine.popen_uci(self.path)
            self.bot = chess.engine.SimpleEngine.popen_uci(self.path)
        except Exception as e:
            self.failed.emit(f"No se pudo iniciar Stockfish ({self.path}): {e}")

    @Slot(str)
    def analyse(self, fen: str):
        if not self.analyst:
            return
        try:
            info = self.analyst.analyse(chess.Board(fen), ANALYSIS_LIMIT)
            pv = info.get("pv") or [None]
            self.analysed.emit(fen, info["score"], pv[0])
        except chess.engine.EngineError as e:
            self.failed.emit(f"Error del motor al analizar: {e}")
        except chess.engine.EngineTerminatedError:
            self.failed.emit("Stockfish se cerró inesperadamente.")

    @Slot(str, str)
    def play(self, fen: str, level: str):
        if not self.bot:
            return
        options, limit = LEVELS[level]
        try:
            self.bot.configure(options)
            result = self.bot.play(chess.Board(fen), limit)
            self.bot_moved.emit(fen, result.move)
        except chess.engine.EngineError as e:
            self.failed.emit(f"Error del motor al jugar: {e}")
        except chess.engine.EngineTerminatedError:
            self.failed.emit("Stockfish se cerró inesperadamente.")

    def close(self):
        for engine in (self.analyst, self.bot):
            if engine:
                try:
                    engine.quit()
                except chess.engine.EngineTerminatedError:
                    pass


class EngineService(QObject):
    """Owns the worker thread. Emit request_* from the UI; listen on .worker signals."""
    request_analysis = Signal(str)
    request_move = Signal(str, str)

    def __init__(self, path: str):
        super().__init__()
        self._thread = QThread()  # not `self.thread`: that would shadow QObject.thread()
        self.worker = EngineWorker(path)
        self.worker.moveToThread(self._thread)
        self._thread.started.connect(self.worker.start)
        self.request_analysis.connect(self.worker.analyse)
        self.request_move.connect(self.worker.play)
        self._thread.start()

    def shutdown(self):
        self._thread.quit()
        self._thread.wait()
        self.worker.close()
