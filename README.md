# CerebraFX

Generador de videos educativos de matemáticas con IA. Crea videos animados con narración, fórmulas LaTeX, gráficos y música de fondo.

## Stack

- **IA**: Gemini 2.5 Flash (guion), ElevenLabs / gTTS (narración)
- **Animación**: GSAP + KaTeX + Canvas API
- **Render**: Playwright (headless Chromium)
- **Video**: FFmpeg (combinación + música fondo)
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
```

> Las keys de Gemini se rotan automáticamente al alcanzar cuota. Soporta formato `Gemini_key_N` (indexado) o `GEMINI_API_KEYS` (CSV).

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
Guion (Gemini) → Audio (ElevenLabs) → HTML + GSAP → Render (Playwright) → FFmpeg
```

Cada paso se ejecuta en segundo plano con polling de estado desde el frontend.

## Guardar / Cargar proyecto

- **💾 Guardar proyecto** — Descarga un archivo `.cerebra.json` con el guion, categoría y tema
- **📂 Cargar proyecto** — Restaura el proyecto guardado para editar escenas, transiciones y efectos sin regenerar el guion
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

Cada categoría modifica el prompt de Gemini e inyecta metadata en las escenas para priorizar los tipos de gráfico y visualización adecuados.

## Tipos de gráfico

| `graph_type` | Descripción | Formato |
|---|---|---|
| `function` | Función simple | String JS (`"Math.sin(x)"`) |
| `multiple` | Múltiples funciones | Array de strings |
| `parametric` | Curva paramétrica | `"x(t); y(t)"` separado por `;` |
| `polar` | Coordenadas polares | `"r(theta)"` |
| `inequality` | Desigualdad 2D | Con `graph_inequality`: `<`, `>`, `≤`, `≥` |

## Visualización

| Escena | Canvas |
|---|---|
| `graph` + `graph_func` | Gráfico de funciones con ejes (5 tipos) |
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
- **graph_type** — Tipo de gráfico (function/multiple/parametric/polar/inequality)
- **graph_func** — Expresión(es) del gráfico
- **graph_inequality** — Signo de desigualdad
- **graph_nodes** / **graph_edges** — Nodos y aristas del grafo
- **transition** — Efecto de transición entre escenas
- **animation** — Animación de entrada del texto
- **textPos** — Posición del texto (mid/top/bottom)
- **themeColor** — Color de acento de la escena

## Estructura

```
CerebraFX/
├── web/
│   ├── server.py          # FastAPI (7+ endpoints)
│   ├── services.py        # Wrappers async
│   └── templates/
│       └── index.html     # Frontend SPA
├── templates/
│   ├── scene.html         # Animación GSAP + KaTeX
│   └── preview.html       # Preview individual por escena
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
