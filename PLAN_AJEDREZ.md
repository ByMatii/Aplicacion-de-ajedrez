# Entrenador de Ajedrez — Planificación y contexto del proyecto

> **Para quien lea esto (otro chat / asistente):** este documento resume el proyecto, el estado actual (MVP hecho), las decisiones tomadas y el plan por etapas. Úsalo como contexto de partida. Idioma de la app y del código de cara al usuario: **español**. Última actualización: 28/11/2026.

---

## 1. Visión general

Aplicación de escritorio **nativa, offline, instalable y multiplataforma** para:

- Jugar contra bots de distintos niveles.
- Medir la ventaja en tiempo real (barra de evaluación).
- Aprender con un **profesor interactivo** que explica fundamentos, tácticas, estrategia y planes según la fase de la partida.

## 2. Stack tecnológico

| Capa | Tecnología | Notas |
|---|---|---|
| UI | **PySide6 (Qt for Python)** | Paneles acoplables, animaciones, QPainter |
| Reglas | **python-chess** | Legalidad, jaque/mate/tablas, FEN, PGN |
| Motor | **Stockfish** vía UCI (`chess.engine`) | Ejecutable local; hilo propio (`QThread`) |

`requirements.txt`: `chess>=1.11`, `PySide6>=6.6`.
Stockfish: en `assets/engines/`, o variable `STOCKFISH_PATH`, o en el PATH.

## 3. Estructura del proyecto

Objetivo final (lo marcado ✅ ya existe en el MVP):

```text
chess_trainer_app/
├── main.py                      ✅
├── requirements.txt / requirements-dev.txt / pytest.ini   ✅ (Etapa 1)
├── core/
│   ├── board_manager.py         ✅ (Etapa 1: BoardManager + PlyRecord)
│   ├── engine_service.py        ✅
│   └── evaluator.py             ✅
├── learning/
│   ├── puzzle_loader.py         (Etapa 4)
│   ├── coach_feedback.py        (Etapa 5)
│   ├── curriculum_manager.py    (Etapa 6)
│   ├── lesson_runner.py         (Etapa 6)
│   └── concept_detector.py      (Etapa 5)
├── ui/
│   ├── main_window.py           ✅
│   ├── board_widget.py          ✅
│   ├── eval_bar_widget.py       ✅
│   └── professor_panel.py       (Etapa 6)
├── tools/
│   └── calibrate.py             ✅ (calibración de niveles vs Stockfish)
├── tests/                       ✅ (pytest: conftest, test_mvp, test_board_manager, test_board_widget, test_engine_worker)
└── assets/
    ├── engines/                 ✅ (.gitkeep; binarios ignorados por git)
    ├── pieces/                  (Etapa 2)
    ├── puzzles/                 (Etapa 4)
    └── lessons/                 (Etapa 6)
```

## 4. Estado actual: MVP + Etapa 1 hechos

**Funciona hoy:**

- Tablero dibujado con `QPainter` (glifos Unicode, fuente "Segoe UI Symbol"): selección, puntos de destinos legales, resaltado de última jugada, flecha de pista, tablero girable.
- 5 niveles de bot: Iniciación (~400), Principiante (~800), Intermedio (~1400), Avanzado (~2000), Maestro (sin límite). Los niveles < 1320 usan Skill Level 0 + depth 1 + % de jugadas aleatorias (el mínimo de `UCI_Elo` en Stockfish es 1320).
- Elegir color (blancas/negras).
- Barra de ventaja vertical (`+1.8`, `#4`), curva logística `white_share`.
- Clasificación de jugadas por pérdida de centipeones: Mejor jugada / Buena / Imprecisión (50–100) / Error (100–250) / Error grave (>250), con la mejor alternativa.
- Entrenador en vivo: ante un error grave pausa al bot; botones **Deshacer** (reintentar) / **Continuar**.
- Pista (flecha con la mejor jugada), ACPL del jugador, lista de jugadas con etiqueta.
- Motor en dos procesos (análisis a 0.25 s y bot) dentro de un `QThread`.
- `tools/calibrate.py` para estimar Elo contra Stockfish.
- Test básico (`tests/test_mvp.py`, sin Stockfish: resultados falseados).

**Agregado en la Etapa 1:**

- `core/board_manager.py`: `BoardManager` (tablero, historial, deshacer, resultado, estadísticas, PGN) y `PlyRecord` por jugada (jugada, SAN, FEN antes/después, score antes/después, mejor jugada, etiqueta, pérdida). Sin dependencias de Qt.
- Selector de coronación (dama/torre/alfil/caballo) con menú emergente en el tablero.
- Guardar/cargar PGN con la evaluación de cada jugada como `[%eval]`; se restauran color y nivel del bot (cabecera `NivelBot`) y la partida se retoma.
- Precisión % por bando (fórmula tipo Lichess sobre `white_share`, promedio por jugada), junto al ACPL.
- Recuperación del motor: si Stockfish muere, el worker se reinicia y reintenta una vez; si falla, avisa y "Nueva partida" intenta reiniciarlo.
- Corrección de un bug: `except EngineTerminatedError` iba después de `except EngineError` (su superclase) y nunca se ejecutaba.
- Tests con pytest (`pytest.ini`, `requirements-dev.txt`): evaluador, `BoardManager`, coronación, undo, round-trip de PGN y recuperación del motor.

**Deudas técnicas conocidas:**

- `MainWindow` ya no guarda estado de partida, pero sigue armando toda la interfaz (~220 líneas). Se extrae en la Etapa 2 (ítem 9), al pasar a paneles acoplables, para no escribirlo dos veces.
- Partidas cargadas desde PGN: la primera jugada no tiene etiqueta (no se guarda la evaluación de la posición inicial) y "Mejor jugada" aparece como "Buena" hasta reanalizar. Se resuelve en la Etapa 3 (ítem 8).
- Solo se cargan PGN que empiezan desde la posición inicial.
- Sin sprites de piezas ni empaquetado.
- Clasificación con umbrales fijos; a nivel alto conviene escala basada en probabilidad de victoria (Etapa 3).
- La fuente de glifos falla en Linux/macOS (la resuelven los sprites SVG de la Etapa 2).
- Salto de nivel 800 → 1400 (faltan niveles 1000–1300; Etapa 7).

## 5. Decisiones tomadas

### 5.1 Formato de lecciones y puzzles (decidido)

- **JSON** (o YAML) para la estructura de una lección o puzzle: `id`, `titulo`, `fase`, `fen`, `pistas`, `flechas`, `explicacion_conceptual`.
- **PGN** cuando la lección/ejercicio dependa de **secuencias de jugadas con variantes** (p. ej. qué pasa si el rival responde de tres formas distintas en una apertura o final). Se carga con `chess.pgn.read_game()`.

**Propuesta de integración (a validar):** el JSON es el "contenedor" de la lección y, cuando hace falta, apunta a un PGN con el árbol de variantes mediante un campo `pgn`. Así cada lección tiene metadatos uniformes (tema, fase, prerrequisitos, pistas) y las variantes se anotan en el formato estándar del ajedrez, editable con cualquier GUI (Lichess, ChessBase, Scid). Recomendación: usar **JSON** como único formato estructurado (stdlib, sin dependencia extra); YAML solo si se prioriza redactar a mano textos largos.

Ejemplo de **puzzle** (JSON, una sola posición/solución):

```json
{
  "id": "horquilla-001",
  "tipo": "puzzle",
  "titulo": "Horquilla de caballo",
  "fase": "medio_juego",
  "tema": ["horquilla"],
  "dificultad": 1,
  "fen": "r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4",
  "solucion": ["h5f7"],
  "pistas": ["Busca un ataque doble.", "Mira el caballo.", "Flecha sobre la mejor jugada."],
  "flechas": [{"desde": "c4", "hasta": "f7", "color": "verde"}],
  "explicacion_conceptual": "Texto que explica el porqué de la idea."
}
```

Ejemplo de **lección con variantes** (JSON que referencia un PGN):

```json
{
  "id": "apertura-principios-001",
  "tipo": "leccion",
  "titulo": "Control del centro: tres respuestas del rival",
  "fase": "apertura",
  "fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  "pgn": "assets/lessons/apertura_principios_001.pgn",
  "pistas": ["..."],
  "flechas": [],
  "explicacion_conceptual": "..."
}
```

En el PGN, cada variante lleva comentarios (`{...}`) con la explicación y NAGs (`$1`, `$2`…) para marcar calidad; `lesson_runner.py` recorre el árbol con `game.variations` / `node.variations`.

Campos opcionales recomendados para ambos: `prerrequisitos` (ids), `jugadas_validas` (alternativas aceptadas), `explicacion_alternativas` (por jugada errónea), `licencia`/`fuente`.

### 5.2 Otras decisiones de diseño ya tomadas

- Stockfish corre en su propio hilo; análisis en vivo con límite de 0.25 s; el bot usa un proceso aparte para no heredar opciones débiles.
- Los mates se recortan a ±1000 cp para que un mate perdido cuente como error grave.
- El código de cara al usuario está en español.
- `BoardManager` crea el `chess.Board` una sola vez y nunca lo reemplaza: el widget del tablero conserva la referencia.
- `PlyRecord` compara por identidad (`eq=False`). `push()` no toma `score_after` de la caché a propósito: el análisis nuevo llega por `apply_eval()`, así una jugada repetida tras *Deshacer* vuelve a juzgarse (y a pausar ante un error grave).
- PGN propio: cabeceras `White`/`Black` (`Jugador`/`Stockfish`) y `NivelBot`; evaluaciones en `[%eval]`. `load_pgn` valida antes de tocar la partida actual.
- Recuperación del motor: un reintento tras reiniciar; si falla de nuevo se avisa al usuario (`failed`), y `restarted` solo informa en la barra de estado.

## 6. Plan por etapas

### Etapa 1 — Consolidación y calidad del núcleo ✅ (cerrada el 28/11/2026: 20 tests pasan)
Objetivo: base sólida antes de sumar funciones.

1. ✅ Extraer `core/board_manager.py` (estado, historial, deshacer, resultado). `MainWindow` delega el estado; el armado de la interfaz que le queda se extrae en la Etapa 2 (ítem 9).
2. ✅ Modelo de datos de partida: lista de `PlyRecord` (jugada, SAN, FEN antes/después, score antes/después, etiqueta, pérdida, mejor jugada). Base del gráfico, la revisión y el profesor.
3. ✅ Selector de coronación (dama/torre/alfil/caballo).
4. ✅ Guardar/cargar PGN (con comentarios de evaluación) y reanudar partida.
5. ✅ Precisión % por bando (`103.17·exp(−0.04354·ΔWin%) − 3.17`, usando `white_share`).
6. ✅ Tests con pytest: `board_manager`, coronación, undo, PGN round-trip, recuperación del motor.
7. ✅ Manejo de errores: motor caído → reinicio del worker y un reintento.

**Salida:** se puede guardar, cargar y retomar una partida. La lógica de partida salió de `MainWindow`; reducirlo a < ~200 líneas queda para la Etapa 2.

### Etapa 2 — Experiencia de juego y pulido visual (1–2 semanas)

1. Sprites SVG en `assets/pieces/` (`QSvgRenderer`), con conmutador glifos/sprites (resuelve también la fuente de glifos que falla en Linux/macOS).
2. Animación de movimientos (`QPropertyAnimation`) y arrastrar y soltar.
3. Coordenadas (a–h, 1–8), resaltado de jaque, capturas y ventaja material.
4. Reloj opcional y sonidos (jugada/captura/jaque).
5. Paneles acoplables (`QDockWidget`): historial clicable, feedback, controles.
6. Navegación por la partida (← →) sin romper el flujo.
7. Ajustes persistentes (`QSettings`): nivel, color, entrenador, tema, sonido.
8. Flechas y casillas manuales con clic derecho (útil luego para el profesor).
9. Extraer de `MainWindow` el armado de la interfaz (p. ej. un `ControlsPanel`) al migrar a `QDockWidget`, dejándolo como coordinador con < ~200 líneas.

**Salida:** se ve y se siente como una app terminada en Windows, Linux y macOS.

### Etapa 3 — Análisis y revisión post-partida (2 semanas)

1. Gráfico de evolución de la ventaja (`QPainter` propio o `pyqtgraph`), con puntos de inflexión y clic para ir a la posición.
2. Detector de momentos clave (pérdida sobre umbral o cambio de signo de la evaluación).
3. Modo revisión guiada: muestra la posición *antes* del error, pide hallar la mejor jugada y luego revela la solución con flecha y explicación.
4. Análisis profundo post-partida (hilo aparte, barra de progreso, **cancelable**).
5. Resumen de partida: precisión por bando, conteo por etiqueta, por fase.
6. Importar partidas externas (PGN).
7. Clasificación mejorada: umbrales según la evaluación (perder 1.0 estando +8 ≠ estando 0); etiquetas extra opcionales (Brillante, Perdió oportunidad).
8. Reanalizar las partidas cargadas desde PGN para completar etiquetas y mejores jugadas (hoy la primera jugada queda sin etiqueta y "Mejor jugada" aparece como "Buena").

**Salida:** al terminar una partida, el usuario ve el gráfico y repasa sus 3–5 peores momentos de forma interactiva.

### Etapa 4 — Puzzles y finales (2 semanas)

1. `learning/puzzle_loader.py`: carga desde JSON (formato de §5.1) y PGN/FEN/CSV en `assets/puzzles/`.
2. Modo puzzle: posiciona el tablero, el usuario juega la solución; validación con la línea guardada y, si hay alternativas, con Stockfish (aceptar jugadas de evaluación equivalente).
3. Respuesta automática del "adversario" en puzzles multijugada.
4. Pistas progresivas: tema → pieza → flecha.
5. Finales prácticos (K+Q vs K, torre, peones): el bot defiende al máximo y se valida el objetivo (mate / tablas / promoción).
6. Progreso persistente (SQLite o JSON): resueltos, fallos, tiempo, repetición espaciada básica.
7. Pack inicial: 100–200 puzzles curados por tema (mate en 1/2, horquillas, clavadas…), con licencia clara (p. ej. base Lichess CC0 filtrada).

**Salida:** sesión de puzzles por tema con estadísticas persistentes.

### Etapa 5 — Detector de fase y profesor contextual (2–3 semanas)

1. `learning/concept_detector.py`:
   - Fase: apertura / medio juego / final (por jugadas, piezas desarrolladas, material no peón).
   - Tácticos (python-chess): pieza colgada/sin defensa, horquilla, clavada, ataque descubierto, mate en N ignorado.
   - Posicionales: rey sin enroque, desarrollo atrasado, columna abierta sin torre, peones doblados/aislados/pasados.
2. `learning/coach_feedback.py`: (jugada + etiqueta + conceptos + mejor alternativa) → mensaje claro: *qué pasó, por qué, qué hacer*. Plantillas en español con variación.
3. Panel del profesor integrado al juego: tarjeta con el concepto y botón "Ver ejemplo / practicar".
4. Etiquetado de errores por tema y estadísticas ("Tus errores: 40 % piezas colgadas") que alimentan recomendaciones.
5. Validación: posiciones de prueba por detector para evitar falsos positivos (un consejo equivocado daña más que ninguno).

**Salida:** tras un error grave, la app nombra el concepto implicado con precisión aceptable y ofrece un ejercicio relacionado.

### Etapa 6 — Currícula y lecciones interactivas (3 semanas)

1. Formato de lección: JSON (+ PGN para variantes) en `assets/lessons/` según §5.1.
2. `learning/curriculum_manager.py`: árbol Fundamentos → Táctica → Estrategia → Aperturas → Medio juego → Finales; prerrequisitos, avance y desbloqueo.
3. `learning/lesson_runner.py`: máquina de estados (explicar → demostrar → practicar → evaluar), validación con python-chess + Stockfish; recorre variantes de PGN.
4. `ui/professor_panel.py`: texto enriquecido, navegación por pasos, mapa de la currícula.
5. Contenido por oleadas (lo que más tiempo lleva):
   - A: Fundamentos (≈10 lecciones).
   - B: Táctica (≈12).
   - C: Finales básicos (≈8).
   - D: Aperturas (principios + 5–6 familias por ideas), estrategia y medio juego.
6. Práctica temática: partidas contra el bot desde posiciones de la lección.
7. Recomendador: sugiere la siguiente lección según los errores detectados (Etapa 5).

**Contenido temático de la currícula:**
- *Fundamentos:* valor de piezas, control central, desarrollo, seguridad del rey, estructura de peones, enroque, captura al paso, coronación.
- *Táctica:* clavadas, horquillas, descubiertas, desviación, atracción, eliminación del defensor, mates básicos.
- *Estrategia:* casillas débiles, pareja de alfiles, columnas abiertas, cambios convenientes, iniciativa.
- *Aperturas:* principios, familias, ideas y planes típicos (no memorización mecánica).
- *Medio juego:* transición, planes sin táctica inmediata, ataques al enroque, profilaxis.
- *Finales:* oposición, regla del cuadrado, activación del rey, finales de torres, mates elementales.

**Salida:** un principiante puede recorrer Fundamentos completo con práctica y evaluación.

### Etapa 7 — Bots más humanos y calibración (1–2 semanas, paralelizable)

1. Calibrar y fijar niveles con `tools/calibrate.py` (100+ partidas para bajar el margen ±150) y documentar.
2. Bots por personalidad/estilo (agresivo, posicional, "comete errores tácticos") con MultiPV y ponderación.
3. Apertura variada: pequeño libro Polyglot.
4. Errores "humanos": fallo más probable en posiciones complejas o con poco tiempo, no uniforme.
5. Niveles 1000–1300 (hoy hay salto 800 → 1400).

### Etapa 8 — Distribución y mantenimiento (1–2 semanas)

1. Empaquetado: PyInstaller (o Nuitka) con Stockfish por plataforma; instaladores (Inno Setup/MSI, `.dmg`, AppImage/`.deb`).
2. Detección de CPU para elegir el binario Stockfish (AVX2/popcnt/baseline).
3. Licencias: Stockfish GPLv3, PySide6 LGPL, contenido de puzzles.
4. CI (GitHub Actions): tests + build multiplataforma.
5. Internacionalización (`QTranslator`).
6. Registro de errores y pantalla "Acerca de / Licencias".
7. Documentación y guía de contribución de contenido.

## 7. Dependencias entre etapas

| Etapa | Depende de | Entrega principal |
|---|---|---|
| 1 Consolidación | MVP | Modelo de partida, PGN, precisión % |
| 2 UX y pulido | 1 | Sprites, animación, ajustes, navegación |
| 3 Revisión | 1 | Gráfico + revisión guiada |
| 4 Puzzles/finales | 1, 2 | Entrenamiento táctico con progreso |
| 5 Profesor contextual | 1, 3 | Detector de conceptos + feedback |
| 6 Currícula | 4, 5 | Lecciones interactivas |
| 7 Bots humanos | MVP (paralelo) | Niveles calibrados y con estilo |
| 8 Distribución | todas | Instaladores y CI |

## 8. Orden sugerido y riesgos

- **Orden:** 1 → 3 → 2 → 4 → 5 → 6 → 8, con la 7 intercalada. La 3 va antes que la 2 porque aporta más valor pedagógico y reutiliza el modelo de la Etapa 1.
- **Riesgo mayor:** el *contenido* (lecciones y puzzles), no el código. Empezar a escribirlo en paralelo desde la Etapa 4; acotar la currícula inicial a Fundamentos + Táctica + Finales básicos.
- **Segundo riesgo:** falsos positivos del detector de conceptos. Pocos detectores muy precisos antes que muchos dudosos.
- **Rendimiento:** el análisis en vivo de 0.25 s basta para jugar, pero la revisión post-partida debe reanalizar con más profundidad y ser una tarea cancelable desde el diseño.
- ~~Decisión pendiente: formato de lecciones y puzzles~~ → **resuelta** (ver §5.1).

## 9. Próximos pasos inmediatos

1. **Etapa 3 (siguiente)** (gráfico de evolución de la ventaja + revisión guiada): reutiliza `PlyRecord`; incluir ahí el reanálisis de partidas cargadas (ítem 8).
2. Definir y fijar el esquema JSON final de lecciones/puzzles (§5.1) antes de la Etapa 4, y crear 2–3 ejemplos reales (un puzzle y una lección con PGN) para probar `puzzle_loader.py`.
3. Etapa 2 cuando toque pulir la interfaz: incluye extraer el armado de `MainWindow` (ítem 9).
