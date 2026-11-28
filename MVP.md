# MVP — Entrenador de Ajedrez (escritorio, offline)

Objetivo: la versión más pequeña que ya **se juega** y ya **enseña algo** en cada jugada.
Actualizado tras la Etapa 1 (consolidación del núcleo): ver `PLAN_AJEDREZ.md`.

## Entra en el MVP

| Área | Qué hace | Dónde |
|---|---|---|
| Jugar contra bot | 5 niveles (Iniciación ~400, Principiante ~800, Intermedio ~1400, Avanzado ~2000, Maestro). Elegir color. Los niveles <1320 añaden jugadas al azar; calibrados con `tools/calibrate.py`. | `core/engine_service.py` |
| Reglas | Movimientos legales, jaque, mate, tablas, ahogado, coronación (a elección: dama, torre, alfil o caballo). | `python-chess` + `ui/board_widget.py` |
| Estado de la partida | Tablero, historial por jugada (`PlyRecord`), deshacer, resultado. | `core/board_manager.py` |
| Barra de ventaja | Evaluación en vivo (`+1.8`, `#4`) en un hilo aparte. | `ui/eval_bar_widget.py` |
| Clasificación de jugadas | Mejor jugada / Buena / Imprecisión (0.5–1.0) / Error (1.0–2.5) / Error grave (>2.5), con la mejor alternativa. | `core/evaluator.py` |
| Entrenador en vivo | Ante un error grave frena al bot: *Deshacer* para reintentar o *Continuar*. | `ui/main_window.py` |
| Pista | Flecha con la mejor jugada del motor. | `ui/board_widget.py` |
| Precisión | Precisión % por bando (tú / bot) y ACPL del jugador. | `core/board_manager.py`, `ui/main_window.py` |
| Guardar / cargar | PGN con la evaluación de cada jugada; al cargar se retoma la partida (color y nivel incluidos). | `core/board_manager.py`, `ui/main_window.py` |
| Motor resistente | Si Stockfish se cae, se reinicia y se reintenta una vez; si falla, se avisa. | `core/engine_service.py` |

## Queda fuera (siguientes iteraciones, en este orden)

1. Gráfico de evolución de la ventaja + revisión post-partida guiada (incluye reanalizar las partidas cargadas desde PGN).
2. Puzzles/finales desde PGN/FEN (`learning/puzzle_loader.py`).
3. Detector de fase y profesor contextual (`learning/concept_detector.py`, `coach_feedback.py`).
4. Currícula y lecciones interactivas (`learning/curriculum_manager.py`, `lesson_runner.py`, `ui/professor_panel.py`).
5. Sprites de piezas en `assets/pieces/` (arregla la fuente de glifos en Linux/macOS), paneles acoplables con la extracción del armado de `MainWindow`, e instalador.

## Requisitos

```bash
pip install -r requirements.txt        # para jugar
pip install -r requirements-dev.txt    # además, pytest
```

Stockfish: descargar de https://stockfishchess.org/download/ y dejar el `.exe` en `assets/engines/`
(o definir `STOCKFISH_PATH`, o tenerlo en el PATH).

```bash
python main.py
pytest
```

## Flujo

Jugada del usuario → se analiza la posición resultante (hilo del motor) → se compara con la evaluación
previa y se clasifica → si es error grave y el entrenador está activo, se pausa → si no, el bot responde →
se analiza la nueva posición → turno del usuario.
