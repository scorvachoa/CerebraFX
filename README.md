# CerebraFX

Generador de videos educativos de matemáticas con IA. Crea videos animados con narración, fórmulas LaTeX, gráficos y música de fondo.

## Stack

- **IA**: Gemini 2.5 Flash (guion), ElevenLabs / edge-tts / gTTS (narración)
- **Animación**: Canvas API + KaTeX
- **Render**: Playwright (headless Chromium, frame a frame, determinista)
- **Video**: FFmpeg (frames → MP4, mezcla de audio + música)
- **Web**: FastAPI + vanilla JS

## Requisitos

- Python 3.13+
- [FFmpeg](https://ffmpeg.org/download.html) en PATH
- Chromium (Playwright)

## Instalación

```powershell
python -m venv env
.\env\Scripts\Activate
pip install -r requirements.txt
playwright install chromium
```

## Configuración

Copia `.env.example` a `.env` y agrega tus API keys:

```env
Gemini_key_1=tu_key
Gemini_key_2=tu_key
ELEVENLABS_API_KEY=tu_key
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM
ELEVENLABS_HOOK_VOICE_ID=otra_voz  # opcional: voz del hook (más enérgica)
```

> Las keys de Gemini se rotan automáticamente al alcanzar cuota. Soporta formato `Gemini_key_N` (indexado) o `GEMINI_API_KEYS` (CSV).

## Marca y pantalla de cierre

Cada video lleva la **marca persistente** (logo/letra inicial + nombre) fija arriba al centro durante toda la duración, y termina con una **pantalla de cierre** animada: logo grande, canal, botón de suscripción con latido/anillo de progreso y eslogan. No lleva narración (se añade como escena `type:"end"`).

La marca se configura por video desde el editor web (panel **🏷️ Marca**) o con defaults en `.env`:

```env
BRAND_NAME=CerebraFX
BRAND_TAGLINE=Aprende mates con visuales increíbles
BRAND_COLOR=#6c63ff
BRAND_CHANNEL=@cerebrafx
BRAND_SUBSCRIBE_TEXT=Suscríbete
END_SCREEN=4.0        # duración de la pantalla final (s)
```

Si `END_SCREEN > 0`, `create_final_video` usa `[aout]apad[aoutpad]` para que `-shortest` no recorte la pantalla de cierre (no tiene narración).

> El texto del botón de suscripción también se configura con `BRAND_SUBSCRIBE_TEXT` (default `Suscríbete`).

## Uso

### Web (recomendado)

```powershell
.\env\Scripts\python.exe run.py
```

Abrir `http://127.0.0.1:8080`

1. Ingresa un tema matemático → "Generar guion"
2. Selecciona una **categoría matemática** (Álgebra, Cálculo, Teoría de Grafos, etc.) para guiar el contenido
3. Revisa las escenas generadas
4. Usa **✎ Avanzado** para editar transiciones, animaciones, textos y colores
5. "Generar video" → pipeline async con progreso
6. Descarga el MP4

### CLI

```powershell
.\env\Scripts\python.exe main.py
```

## Pipeline

```
Guion (Gemini) → Audio por escena (ElevenLabs → edge-tts → gTTS, en paralelo) → HTML + Canvas → Frames deterministas (Playwright) → FFmpeg (+ pantalla de cierre)
```

Cada paso se ejecuta en segundo plano con polling de estado desde el frontend.

## Render determinista por frames

A diferencia de grabar en tiempo real, el motor renderiza **frame a frame**:

1. `templates/scene.html` expone `window.renderFrame(f)`: dado un índice de frame, calcula el estado exacto de toda la animación (opacidades, palabras, fórmulas, gráficos) sin depender del reloj.
2. Playwright llama a `renderFrame(f)` y captura un PNG por frame.
3. FFmpeg codifica la secuencia de PNGs en un MP4 mudo.
4. FFmpeg mezcla las narraciones por escena (con `adelay` al inicio de cada escena) y la música de fondo.

Ventajas: resultados deterministas (el frame N siempre es igual), render **independiente del tiempo real** y sincronización precisa narración-escena.

Configuración en `.env`:

```env
FPS=24                # fotogramas por segundo
RENDER_SCALE=1.0      # escala de render (0.5 = mitad de resolución, más rápido; escala el diseño 1080×1920 al viewport sin recortar)
SCENE_LEAD=0.35       # pausa antes de la narración (s)
SCENE_TAIL=0.45       # margen después de la narración (s)
MIN_SCENE=2.5         # duración mínima de escena (s)
```

## Audio por escena

Cada escena genera su propia narración. La duración de la escena se calcula como `narración + SCENE_TAIL` (mínimo `MIN_SCENE`), y la narración se coloca `SCENE_LEAD` segundos después del inicio de la escena. Así el texto y la voz quedan sincronizados en cada escena en lugar de repartir la duración de forma uniforme.

**Voces por escena**: si `ELEVENLABS_HOOK_VOICE_ID` está definida, la primera escena (`hook`) y cualquier escena con `"voice": "hook"` usan esa voz alternativa; el resto usa `ELEVENLABS_VOICE_ID`. Las escenas `type:"end"` no generan audio.

**Motores TTS y velocidad**: la generación de audio se hace **en paralelo por escena** (`TTS_WORKERS`) y con **caché por texto+voz** (regenerar el mismo video reutiliza el MP3 sin red). Orden de motores (`TTS_ENGINE=auto`): ElevenLabs (si hay `ELEVENLABS_API_KEY`) → `edge-tts` (Microsoft neural, ~2s/escena) → gTTS (lento, último recurso).

```env
TTS_ENGINE=auto            # auto | elevenlabs | edge | gtts
TTS_WORKERS=6              # escenas generadas en paralelo
EDGE_TTS_VOICE=es-MX-DaliaNeural
EDGE_TTS_HOOK_VOICE=es-MX-JorgeNeural
```

## Guardar / Cargar proyecto

- **💾 Guardar proyecto** — Descarga un archivo `.cerebra.json` con el guion, categoría, tema y marca
- **📂 Cargar proyecto** — Restaura el proyecto guardado (incluida la marca) para editar escenas, transiciones y efectos sin regenerar el guion
- Al generar video desde un proyecto cargado se reusa el guion existente y solo se regeneran audio + video

## Categorías matemáticas

| Categoría | Comportamiento |
|---|---|
| General | Prompt estándar |
| Álgebra | Ecuaciones, factorización, sistemas |
| Trigonometría | Seno, coseno, tangente, identidades |
| Cálculo | Derivadas, integrales, límites |
| Geometría | Figuras, teoremas, áreas |
| Teoría de Grafos | Nodos, aristas, grafos dirigidos/no dirigidos |
| Estadística | Media, mediana, desviación, distribuciones |
| Aritmética | Operaciones básicas, fracciones, porcentajes |
| Análisis complejo | Funciones complejas, asíntotas, comportamiento asintótico |

Cada categoría modifica el prompt de Gemini e inyecta metadata en las escenas para priorizar los tipos de gráfico y visualización adecuados.

## Motor de gráficas (`graph_engine.js`)

`templates/graph_engine.js` es un motor matemático compartido por `scene.html` y `preview.html` (se inyecta en ambos al generar el HTML). Expone `window.drawGraph`, `window.drawVisual` y `window.compileMathExpr`.

### Sintaxis de expresiones

El preprocesador entiende notación matemática natural además de JS:

- **Potencias**: `x^2`, `10^x`, `x^3`
- **Multiplicación implícita**: `2x`, `x(x-1)`, `2(x+1)`
- **Constantes**: `e`, `pi`, `phi` (φ), `PI`, `tau`
- **Factorial**: `n!`, `x!`
- **Notación científica**: `1e5`, `2.5e-3`
- **Funciones**: `sin, cos, tan, asin, acos, atan, atan2, sinh, cosh, tanh, asinh, acosh, atanh, sqrt, cbrt, abs, exp, ln, log2, log10, log, sec, csc, cot, sech, csch, coth, fact, gamma, erf, erfc` (todas usables sin prefijo `Math.`)
- **Superscripts Unicode**: `x²`, `x³`

## Tipos de gráfico

| `graph_type` | Descripción | Formato |
|---|---|---|
| `function` | Función simple | String (`"2x^2-4"`) |
| `multiple` | Múltiples funciones | Array de strings |
| `parametric` | Curva paramétrica | `"x(t); y(t)"` separado por `;` |
| `polar` | Coordenadas polares | `"r(theta)"` (ej: `"2*cos(theta)"`) |
| `inequality` | Desigualdad 2D | Con `graph_inequality`: `<`, `>`, `≤`, `≥` |
| `implicit` | Curva implícita `F(x,y)=k` | `graph_func` = lado izquierdo, `graph_implicit_eq` = valor k (ej: `"x*x+y*y"` con `"1"` = circunferencia unidad) |
| `scatter` | Dispersión | `graph_points`: array de pares `[[x,y],...]` |
| `bar` | Barras | `graph_func` = array de valores, `graph_bar_labels` = etiquetas |

### Opciones adicionales

- `graph_xmin`, `graph_xmax`, `graph_ymin`, `graph_ymax` — rango de ejes
- `graph_logx`, `graph_logy` — escala logarítmica
- `graph_label` — etiqueta / leyenda (array si hay varias curvas)
- `tMin`, `tMax` — rango del parámetro (paramétricas/polares)

## Visualización

| Escena | Canvas |
|---|---|
| `graph` + `graph_func` | Gráfico matemático con ejes (8 tipos: function/multiple/parametric/polar/inequality/implicit/scatter/bar) |
| `visual` (trigonometría) | Círculo unitario |
| `visual` (triángulo) | Triángulo rectángulo |
| `visual` (raíz) | Símbolo de raíz |
| `visual` (potencia) | Curva exponencial |
| `visual` (integral) | Área bajo la curva |
| `visual` (fracción) | Barra de fracción |
| `visual` (límite) | Asíntota |
| `visual` (matriz) | Matriz 3×3 |
| `visual` (teoría de grafos) | Nodos en círculo + aristas animadas |
| `visual` (default) | Fórmula como texto con glow |

## Teoría de Grafos

Las escenas con `visual_type: 'graph_theory'` (o `graph_nodes`/`graph_edges`) dibujan:
- **Nodos** distribuidos en un círculo con etiquetas numeradas
- **Aristas** animadas progresivamente según el progreso del video
- **Flechas** si `graph_directed: true`

## Preview por escena

Cada escena tiene un botón de vista previa que abre una ventana con la animación en tiempo real, permitiendo ver cómo se verá antes de generar el video completo.

## Batch processing

El modo lote permite ingresar múltiples temas (uno por línea) y generar videos para cada uno secuencialmente.

## Música de fondo

Coloca un archivo MP3 en `assets/mixkit-tech-house-vibes-130.mp3`. Se mezcla automáticamente a -20dB con loop infinito. Si no existe, el video solo tiene narración.

## Editor avanzado

El editor (✎ Avanzado) permite modificar por escena:
- **text** — Contenido textual (soporta LaTeX inline con `\comando{arg}`)
- **narration** — Texto de narración
- **formula** — Fórmula LaTeX
- **graph_type** — Tipo de gráfico (function/multiple/parametric/polar/inequality/implicit/scatter/bar)
- **graph_func** — Expresión(es) del gráfico (sintaxis natural: `x^2`, `2x+1`, `sin(x)`)
- **graph_inequality** — Signo de desigualdad
- **graph_implicit_eq** — Valor k en curva implícita `F(x,y)=k`
- **graph_bar_labels** — Etiquetas para `graph_type=bar`
- **graph_points** — Puntos `[[x,y],...]` para `graph_type=scatter`
- **graph_nodes** / **graph_edges** — Nodos y aristas del grafo
- **transition** — Efecto de transición entre escenas
- **animation** — Animación de entrada del texto
- **textPos** — Posición del texto (mid/top/bottom)
- **themeColor** — Color de acento de la escena

## Estructura

```
CerebraFX/
├── web/
│   ├── server.py          # FastAPI (9 endpoints: script, preview, video, batch, status, download, health...)
│   ├── services.py        # Wrappers async + pipeline
│   └── templates/
│       └── index.html     # Frontend SPA
├── templates/
│   ├── scene.html         # Animación determinista por frames + KaTeX + marca/end screen
│   ├── preview.html       # Preview individual por escena
│   └── graph_engine.js    # Motor matemático de gráficas (compartido)
├── assets/                # Música de fondo
├── config.py              # Config desde .env
├── key_rotator.py         # Rotación de API keys (singleton)
├── main.py                # CLI + pipeline core
├── run.py                 # Entrypoint web
├── .env.example           # Template de configuración
├── .gitignore
└── requirements.txt
```

## .gitignore

El proyecto incluye `.gitignore` que cubre: `.env`, `env/`, `__pycache__/`, `*.pyc`, media generados (`*.webm`, `*.mp3`, `*.mp4`), directorios de output (`output/`, `videos/`), y archivos de IDE (`.vscode/`, `.idea/`).

## Licencia

MIT
