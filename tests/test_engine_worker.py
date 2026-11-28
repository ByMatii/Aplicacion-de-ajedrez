"""Crash recovery of the engine worker, with a fake `action` instead of a real Stockfish."""
import chess.engine

from core.engine_service import EngineWorker


def make_worker(monkeypatch, launch_ok=True):
    w = EngineWorker("fake")
    launches, restarted, failures = [], [], []
    monkeypatch.setattr(w, "_launch", lambda: launches.append(1) or launch_ok)
    w.restarted.connect(lambda: restarted.append(1))
    w.failed.connect(failures.append)
    return w, launches, restarted, failures


def crash():
    raise chess.engine.EngineTerminatedError("boom")


def test_restarts_and_retries_once(qapp, monkeypatch):
    w, launches, restarted, failures = make_worker(monkeypatch)
    calls = []

    def flaky():
        calls.append(1)
        if len(calls) == 1:
            crash()
        return "ok"

    assert w._guarded(flaky, "analizar") == "ok"
    assert launches == [1] and restarted == [1] and not failures


def test_gives_up_if_it_keeps_crashing(qapp, monkeypatch):
    w, launches, restarted, failures = make_worker(monkeypatch)
    assert w._guarded(crash, "jugar") is None
    assert len(failures) == 1 and "jugar" in failures[0]


def test_stops_if_restart_fails(qapp, monkeypatch):
    w, launches, restarted, failures = make_worker(monkeypatch, launch_ok=False)
    assert w._guarded(crash, "jugar") is None
    assert launches == [1] and not restarted  # _launch reports its own failure


def test_other_engine_errors_are_reported_without_restart(qapp, monkeypatch):
    w, launches, restarted, failures = make_worker(monkeypatch)

    def bad():
        raise chess.engine.EngineError("illegal position")

    assert w._guarded(bad, "analizar") is None
    assert not launches and len(failures) == 1
