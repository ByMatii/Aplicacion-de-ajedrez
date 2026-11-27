# MVP — Entrenador de Ajedrez (escritorio, offline)

Objetivo: la versión más pequeña que ya **se juega** y ya **enseña algo** en cada jugada.

## Entra en el MVP

| Área | Qué hace | Dónde |
|---|---|---|
| Jugar contra bot | 4 niveles (Principiante ~800, Intermedio ~1400, Avanzado ~2000, Maestro). Elegir color. | `core/engine_service.py` |
| Reglas | Movimientos legales, jaque, mate, tablas, ahogado, coronación (a dama). | `python-chess` directo |
| Barra de ventaja | Evaluación en vivo (`+1.8`, `#4`) en un hilo aparte. | `ui/eval_bar_widget.py` |
| Clasificación de jugadas | Mejor jugada / Buena / Imprecisión (0.5–1.0) / Error (1.0–2.5) / Error grave (>2.5), con la mejor alternativa. | `core/evaluator.py` |
| Entrenador en vivo | Ante un error grave frena al bot: *Deshacer* para reintentar o *Continuar*. | `ui/main_window.py` |
| Pista | Flecha con la mejor jugada del motor. | `ui/board_widget.py` |
| Precisión | ACPL del jugador en la partida. | `ui/main_window.py` |

## Queda fuera (siguientes iteraciones, en este orden)

1. Gráfico de evolución de la ventaja + revisión post-partida guiada.
2. Puzzles/finales desde PGN/FEN (`learning/puzzle_loader.py`).
3. Detector de fase y profesor contextual (`learning/concept_detector.py`, `coach_feedback.py`).
4. Currícula y lecciones interactivas (`learning/curriculum_manager.py`, `lesson_runner.py`, `ui/professor_panel.py`).
5. Elegir pieza al coronar, guardar/cargar PGN, sprites de piezas en `assets/pieces/`, instalador.

## Requisitos

```bash
pip install -r requirements.txt
```

Stockfish: descargar de https://stockfishchess.org/download/ y dejar el `.exe` en `assets/engines/`
(o definir `STOCKFISH_PATH`, o tenerlo en el PATH).

```bash
python main.py
```

## Flujo

Jugada del usuario → se analiza la posición resultante (hilo del motor) → se compara con la evaluación
previa y se clasifica → si es error grave y el entrenador está activo, se pausa → si no, el bot responde →
se analiza la nueva posición → turno del usuario.
