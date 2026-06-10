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

Abrir `http://127.0.0.1:8000`

1. Ingresa un tema matemático → "Generar guion"
2. Revisa las escenas generadas
3. "Generar video" → pipeline async con progreso
4. Descarga el MP4

### CLI

```powershell
.\env\Scripts\python.exe main.py
```

## Pipeline

```
Guion (Gemini) → Audio (ElevenLabs) → HTML + GSAP → Render (Playwright) → FFmpeg
```

Cada paso se ejecuta en segundo plano con polling de estado desde el frontend.

## Guion

Cada escena tiene dos campos:
- `text` — Se muestra en pantalla (con notación)
- `narration` — Texto para audio (lenguaje natural, sin LaTeX)

Si Gemini falla, usa guiones de respaldo locales (derivadas, integrales, Pitágoras, cuadráticas).

## Visualización

| Escena | Canvas |
|---|---|
| `graph` + `graph_func` | Gráfico de funciones con ejes |
| `visual` (trigonometría) | Círculo unitario |
| `visual` (triángulo) | Triángulo rectángulo |
| `visual` (raíz) | Símbolo de raíz |
| `visual` (potencia) | Curva exponencial |
| `visual` (integral) | Área bajo la curva |
| `visual` (fracción) | Barra de fracción |
| `visual` (límite) | Asíntota |
| `visual` (matriz) | Matriz 3×3 |
| `visual` (default) | Fórmula como texto con glow |

## Música de fondo

Coloca un archivo MP3 en `assets/mixkit-tech-house-vibes-130.mp3`. Se mezcla automáticamente a -20dB con loop infinito. Si no existe, el video solo tiene narración.

## Estructura

```
CerebraFX/
├── web/
│   ├── server.py          # FastAPI (5 endpoints)
│   ├── services.py        # Wrappers async
│   └── templates/
│       └── index.html     # Frontend estilo Runway
├── templates/
│   └── scene.html         # Animación GSAP + KaTeX
├── assets/                # Música de fondo
├── config.py              # Config desde .env
├── key_rotator.py         # Rotación de API keys
├── main.py                # CLI
├── run.py                 # Entrypoint web
├── .env.example           # Template de configuración
├── .gitignore
└── requirements.txt
```

## .gitignore

El proyecto incluye `.gitignore` que cubre: `.env`, `env/`, `__pycache__/`, `*.pyc`, media generados (`*.webm`, `*.mp3`, `*.mp4`), directorios de output (`output/`, `videos/`), y archivos de IDE (`.vscode/`, `.idea/`).

## Licencia

MIT
