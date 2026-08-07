#!/usr/bin/env python3
import asyncio
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
import google.api_core.exceptions as google_exc
import google.generativeai as genai
from playwright.sync_api import sync_playwright

from config import BASE_DIR, Config
from key_rotator import build_key_rotator

Config.ensure_dirs()


def check_dependencies():
    missing = []
    if not Config.GEMINI_API_KEYS:
        missing.append("GEMINI_API_KEY (ninguna key configurada)")
    if not Config.ELEVENLABS_API_KEY:
        missing.append("ELEVENLABS_API_KEY")
    if missing:
        print(f"Configura en .env o variables de entorno: {', '.join(missing)}")
        return False
    for cmd in ["ffmpeg", "ffprobe"]:
        if not shutil.which(cmd):
            print(f"Instala {cmd} y agrégalo al PATH: https://ffmpeg.org/download.html")
            return False
    return True


def _truncate_scenes(script: dict, max_len: int = 120) -> dict:
    for scene in script.get("scenes", []):
        if len(scene.get("text", "")) > max_len:
            scene["text"] = scene["text"][: max_len - 3] + "..."
    return script


_CATEGORY_HINTS = {
    "algebra": "Álgebra: usa graph_type 'function'/'multiple' con polinomios (x*x, 2*x+3, x*x-4), ecuaciones lineales y cuadráticas, y graph_type 'inequality' para regiones. Ejemplos: 2*x+1, x*x-4, x^3.",
    "trigonometry": "Trigonometría: usa graph_type 'parametric' para círculo (cos(t); sin(t)) y gráficas tipo 'function' para seno/coseno/tangente (Math.sin(x)). graph_type 'polar' para curvas polares (2*cos(theta), 1+cos(theta)). Incluye type 'visual' para círculo trigonométrico y triángulos.",
    "calculus": "Cálculo: usa graph_func con polinomios y racionales (1/x, x^3, Math.exp(x), Math.log(x)). graph_type 'inequality' para áreas bajo curvas. Muestra asíntotas (1/x, Math.tan(x)). Incluye \\int y \\frac en formulas LaTeX.",
    "geometry": "Geometría: usa type 'visual' para triángulos, círculos y figuras geométricas. Para circunferencias usa graph_type 'implicit' con 'x*x+y*y' e graph_implicit_eq '1' (radio 1). Incluye triángulo rectángulo con Pitágoras (a^2+b^2=c^2).",
    "graph_theory": "Teoría de Grafos: usa type 'visual' con visual_type='graph_theory', graph_nodes=['A','B','C',...], graph_edges=['0-1','1-2',...]. Incluye grafos dirigidos (graph_directed=true) y no dirigidos.",
    "statistics": "Estadística: usa graph_type 'function'/'multiple' para distribuciones normales (Math.exp(-x*x)), graph_type 'bar' con graph_bar_labels para barras, y graph_type 'scatter' para dispersión.",
    "arithmetic": "Aritmética: usa type 'step' para operaciones paso a paso. type 'visual' para fracciones (\\frac) y raíces (\\sqrt). graph_type 'bar' para sumas/visualizaciones de conteo.",
    "complex_analysis": "Análisis complejo: usa graph_func con funciones complejas como Math.sin(x), Math.exp(x), Math.log(x), 1/x. Muestra asíntotas y comportamiento asintótico.",
}

def generate_script(topic: str, category: str = "general") -> dict:
    cat_hint = _CATEGORY_HINTS.get(category, "")
    prompt = (
        "Eres un creador de videos educativos de MATEMÁTICAS. "
        "Genera un guion JSON para un video corto sobre: " + topic + "\n\n"
        "Categoría: " + (category if category != "general" else "Matemáticas general") + "\n"
        + (cat_hint + "\n" if cat_hint else "")
        + "Formato EXACTO (solo JSON, sin markdown, sin backticks):\n"
        '{\n'
        '  "title": "Título del video",\n'
        '  "scenes": [\n'
        '    {\n'
        '      "type": "hook|formula|step|graph|visual|conclusion",\n'
        '      "text": "texto en pantalla (máx 120 caracteres)",\n'
        '      "narration": "mismo texto pero solo para narración de audio, sin LaTeX ni notación matemática, lenguaje natural y fluido",\n'
        '      "formula": "LaTeX opcional",\n'
         '      "graph_func": "función opcional. String simple (x^2) o array [x^2, 2*x+1] para múltiples curvas. Para paramétricas: cos(t); sin(t). Usa sintaxis natural: 2x, x^2, pi, e, n!, etc.",\n'
         '      "graph_label": "etiqueta opcional. Si graph_func es array, graph_label también debe ser array",\n'
         '      "graph_type": "opcional: function (default), multiple, parametric, polar, inequality, implicit, scatter, bar",\n'
         '      "graph_inequality": "solo si graph_type=inequality: < o > para sombrear región",\n'
         '      "graph_implicit_eq": "solo si graph_type=implicit: lado derecho de la ecuación F(x,y)=valor, ej: \'1\' para x*x+y*y=1",\n'
         '      "graph_logx": "opcional: true para escala log en x",\n'
         '      "graph_logy": "opcional: true para escala log en y",\n'
         '      "graph_xmin/xmax/ymin/ymax": "opcionales: rango de ejes, ej: -3, 3, -2, 2",\n'
         '      "graph_bar_labels": "solo si graph_type=bar: array de etiquetas de barras",\n'
         '      "graph_points": "solo si graph_type=scatter: array de pares [x,y], ej: [[1,2],[2,4],[3,9]]"\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "REGLAS:\n"
        "- 5 a 8 escenas\n"
        "- type hook: pregunta intrigante, SIN fórmula\n"
        "- type formula: muestra una fórmula grande con LaTeX\n"
        "- type step: paso de solución, puede incluir fórmula\n"
        "- type graph: incluye graph_func (string para 1 función, array para múltiples curvas, o separado por ; para paramétricas)\n"
         "  · graph_type 'function' (default): graph_func string JS, ej: '2*x', 'x*x', 'Math.sin(x)'\n"
         "  · graph_type 'multiple': graph_func como array, ej: [\"x*x\", \"2*x+1\"], cada una con color diferente\n"
         "  · graph_type 'parametric': graph_func como 'x(t); y(t)', ej: 'cos(t); sin(t)' para círculo\n"
         "  · graph_type 'polar': graph_func como r(θ), ej: '2*cos(theta)' para cardioide\n"
          "  · graph_type 'inequality': sombrea región, añade graph_inequality '<' o '>' ej: 'x*x' con '<' sombrea y < x²\n"
          "  · graph_type 'implicit': curva implícita F(x,y)=graph_implicit_eq, ej: graph_func='x*x+y*y', graph_implicit_eq='1' para círculo unidad\n"
          "  · graph_type 'scatter': dispersión, añade graph_points como array de pares [x,y]\n"
          "  · graph_type 'bar': gráfica de barras, añade graph_func (array de valores) y graph_bar_labels (array de etiquetas)\n"
          "  · Escalas y rangos: graph_logx=true / graph_logy=true para logarítmica; graph_xmin, graph_xmax, graph_ymin, graph_ymax para controlar ejes\n"
          "  · Sintaxis de expresiones: usa ^ para potencia (x^2), multiplicación implícita (2x, x(x-1)), constantes e, pi, phi, factorial n!, funciones Math.* (sin, cos, tan, sqrt, abs, exp, log), log2, log10, ln, erf, gamma, sec/csc/cot y sus hiperbólicos\n"
          "- type visual: concepto visual/geométrico, puede incluir formula\n"
         "  · Para grafos (teoría de grafos): añade 'visual_type':'graph_theory', 'graph_nodes':['A','B','C'], 'graph_edges':['0-1','1-2','0-2'] (índices numéricos de nodes), 'graph_directed':true/false\n"
         "- type conclusion: resumen final, puede incluir formula\n"
         "- Cada text: 1 oración corta para pantalla, máx 120 caracteres\n"
         "- Cada narration: texto fluido para audio, sin fórmulas ni LaTeX, explica la idea en lenguaje natural\n"
         "- Las fórmulas LaTeX usan \\\\ para comandos (\\\\frac, \\\\sqrt, etc)\n"
         "- graph_func debe ser evaluable en JS (usa Math.* para funciones trigonométricas, sqrt, abs, etc)\n"
         "- Responde ÚNICAMENTE el JSON válido, nada más"
    )

    rotator = build_key_rotator()
    models = ["gemini-2.5-flash"]

    for model_name in models:
        print(f"  Probando {model_name}...")
        model_fatal = False

        for _ in range(rotator.total_keys):
            api_key = rotator.next_key()

            for attempt in range(2):
                try:
                    genai.configure(api_key=api_key.value)
                    model = genai.GenerativeModel(model_name)
                    response = model.generate_content(prompt)
                    text = response.text.strip()
                    fence_match = re.search(r'```(?:json)?\s*\n?(.*?)```', text, re.DOTALL)
                    if fence_match:
                        text = fence_match.group(1).strip()
                    script = _truncate_scenes(json.loads(text))
                    script["category"] = category
                    for sc in script.get("scenes", []):
                        sc["category"] = category
                    return script
                except google_exc.ResourceExhausted:
                    if attempt == 0:
                        time.sleep(1)
                    else:
                        print(f"  Cuota excedida key#{api_key.index+1} en {model_name}, rotando...")
                except google_exc.NotFound:
                    print(f"  Modelo {model_name} no disponible, probando siguiente...")
                    model_fatal = True
                    break
                except (json.JSONDecodeError, AttributeError) as e:
                    print(f"  Error de parsing con {model_name}, probando siguiente...")
                    model_fatal = True
                    break

            if model_fatal:
                break

        if model_fatal:
            continue

        print(f"  Keys agotadas en {model_name}, esperando 3s...")
        time.sleep(3)

    print("  APIs no disponibles, usando guion de respaldo...")
    script = _truncate_scenes(_fallback_script(topic))
    script["category"] = category
    for sc in script.get("scenes", []):
        sc["category"] = category
    return script


def _fallback_script(topic: str) -> dict:
    library = {
        "derivada": {
            "title": "Derivada de x²",
            "scenes": [
                {"type": "hook", "text": "¿Cómo calculamos la pendiente de una curva?", "narration": "Como calculamos la pendiente de una curva"},
                {"type": "formula", "text": "La regla de potencias", "narration": "Usamos la regla de potencias", "formula": "\\frac{d}{dx} x^n = n \\cdot x^{n-1}"},
                {"type": "step", "text": "Aplicamos n = 2", "narration": "Aplicamos n igual a 2", "formula": "\\frac{d}{dx} x^2 = 2 \\cdot x^{2-1}"},
                {"type": "step", "text": "Simplificamos el exponente", "narration": "Simplificamos el exponente y obtenemos 2x", "formula": "\\frac{d}{dx} x^2 = 2x^1"},
                {"type": "graph", "text": "La pendiente cambia en cada punto", "narration": "La pendiente cambia en cada punto de la curva", "formula": "f'(x) = 2x", "graph_func": "2*x", "graph_label": "f'(x) = 2x"},
                {"type": "conclusion", "text": "La derivada de x² es 2x", "narration": "La derivada de x al cuadrado es 2x", "formula": "f'(x) = 2x"},
            ]
        },
        "integral": {
            "title": "Integral de x²",
            "scenes": [
                {"type": "hook", "text": "¿Cómo calcular el área bajo una curva?", "narration": "Como calcular el area bajo una curva"},
                {"type": "formula", "text": "La regla de integración", "narration": "Usamos la regla de integracion", "formula": "\\int x^n \\, dx = \\frac{x^{n+1}}{n+1} + C"},
                {"type": "step", "text": "Aplicamos n = 2", "narration": "Aplicamos n igual a 2", "formula": "\\int x^2 \\, dx = \\frac{x^{2+1}}{2+1} + C"},
                {"type": "step", "text": "Simplificamos", "narration": "Simplificamos y obtenemos x al cubo sobre 3 mas C", "formula": "\\int x^2 \\, dx = \\frac{x^3}{3} + C"},
                {"type": "graph", "text": "El área bajo la curva x²", "narration": "El area bajo la curva de x al cuadrado de 0 a 1 es un tercio", "formula": "\\int_0^1 x^2 \\, dx = \\frac{1}{3}", "graph_func": "x*x", "graph_label": "f(x) = x²"},
                {"type": "conclusion", "text": "La integral de x² es x³/3 + C", "narration": "La integral de x al cuadrado es x al cubo sobre 3 mas C", "formula": "\\int x^2 \\, dx = \\frac{x^3}{3} + C"},
            ]
        },
        "teorema de pitágoras": {
            "title": "Teorema de Pitágoras",
            "scenes": [
                {"type": "hook", "text": "¿Cuál es la relación entre los lados de un triángulo rectángulo?", "narration": "Cual es la relacion entre los lados de un triangulo rectangulo"},
                {"type": "formula", "text": "El teorema", "narration": "El teorema dice que a al cuadrado mas b al cuadrado es igual a c al cuadrado", "formula": "a^2 + b^2 = c^2"},
                {"type": "visual", "text": "En un triángulo rectángulo, a y b son los catetos", "narration": "En un triangulo rectangulo, a y b son los catetos", "formula": "a^2 + b^2 = c^2"},
                {"type": "step", "text": "Si a=3 y b=4, calculamos c", "narration": "Si a es 3 y b es 4, calculamos c", "formula": "c = \\sqrt{3^2 + 4^2} = \\sqrt{9 + 16}"},
                {"type": "step", "text": "Simplificamos", "narration": "Simplificamos y obtenemos raiz de 25, que es 5", "formula": "c = \\sqrt{25} = 5"},
                {"type": "conclusion", "text": "3² + 4² = 5² ¡El teorema funciona!", "narration": "3 al cuadrado mas 4 al cuadrado es igual a 5 al cuadrado. El teorema funciona", "formula": "3^2 + 4^2 = 5^2"},
            ]
        },
        "circunferencia": {
            "title": "Circunferencia y Trigonometría",
            "scenes": [
                {"type": "hook", "text": "¿Cómo se dibuja un círculo con funciones?", "narration": "Como se dibuja un circulo con funciones"},
                {"type": "formula", "text": "Ecuación paramétrica del círculo", "narration": "La ecuacion parametrica del circulo usa seno y coseno", "formula": "x = \\cos(t), \\quad y = \\sin(t)"},
                {"type": "graph", "text": "El círculo unitario", "narration": "Al variar t de 0 a 2 pi, obtenemos un circulo", "formula": "x^2 + y^2 = 1", "graph_func": "Math.cos(t); Math.sin(t)", "graph_type": "parametric", "graph_label": "Círculo unitario"},
                {"type": "step", "text": "Para cualquier ángulo t, (cos t, sen t) está en el círculo", "narration": "Para cualquier angulo t, el coseno y seno forman un punto en el circulo", "formula": "\\cos^2(t) + \\sin^2(t) = 1"},
                {"type": "conclusion", "text": "Las paramétricas describen curvas complejas fácilmente", "narration": "Las parametricas describen curvas complejas facilmente", "formula": "x = \\cos(t), y = \\sin(t)"},
            ]
        },
        "desigualdad cuadratica": {
            "title": "Desigualdad Cuadrática",
            "scenes": [
                {"type": "hook", "text": "¿Qué significa y < x²?", "narration": "Que significa y menor que x al cuadrado"},
                {"type": "formula", "text": "Desigualdad cuadrática", "narration": "Una desigualdad cuadratica relaciona y con x al cuadrado", "formula": "y < x^2"},
                {"type": "graph", "text": "Región sombreada debajo de la parábola", "narration": "La region sombreada debajo de la parabola representa todos los puntos donde y es menor que x al cuadrado", "formula": "y < x^2", "graph_func": "x*x", "graph_type": "inequality", "graph_inequality": "<", "graph_label": "y < x²"},
                {"type": "step", "text": "La parábola es el borde de la región", "narration": "La parabola es el borde de la region", "formula": "y = x^2"},
                {"type": "conclusion", "text": "El área sombreada muestra todas las soluciones", "narration": "El area sombreada muestra todas las soluciones de la desigualdad", "formula": "y < x^2"},
            ]
        },
        "funcion cuadratica": {
            "title": "Función Cuadrática",
            "scenes": [
                {"type": "hook", "text": "¿Qué forma tiene una función cuadrática?", "narration": "Que forma tiene una funcion cuadratica"},
                {"type": "formula", "text": "Forma general", "narration": "Su forma general es a por x al cuadrado mas b por x mas c", "formula": "f(x) = ax^2 + bx + c"},
                {"type": "graph", "text": "Su gráfica es una parábola", "narration": "Su grafica es una parabola", "formula": "f(x) = x^2 - 2x - 3", "graph_func": "x*x - 2*x - 3", "graph_label": "f(x) = x² - 2x - 3"},
                {"type": "step", "text": "El vértice está en x = -b/(2a)", "narration": "El vertice esta en x igual a menos b sobre 2a", "formula": "x_v = \\frac{-b}{2a} = \\frac{2}{2} = 1"},
                {"type": "step", "text": "Las raíces son los puntos donde cruza el eje x", "narration": "Las raices se calculan con la formula general", "formula": "x = \\frac{-b \\pm \\sqrt{b^2 - 4ac}}{2a}"},
                {"type": "conclusion", "text": "La parábola abre hacia arriba si a > 0", "narration": "La parabola abre hacia arriba si a es mayor que cero", "formula": "f(x) = x^2 - 2x - 3"},
            ]
        },
        "teorema de grafos": {
            "title": "Teorema de Grafos",
            "scenes": [
                {"type": "hook", "text": "¿Qué es un grafo y para qué sirve?", "narration": "Que es un grafo y para que sirve"},
                {"type": "visual", "text": "Un grafo tiene vértices y aristas", "narration": "Un grafo tiene vertices y aristas que los conectan", "formula": "G = (V, E)", "visual_type": "graph_theory", "graph_nodes": ["A","B","C","D","E"], "graph_edges": ["0-1","0-2","1-2","1-3","2-3","2-4","3-4"], "graph_directed": False},
                {"type": "step", "text": "Las aristas conectan pares de vértices", "narration": "Las aristas conectan pares de vertices"},
                {"type": "formula", "text": "Propiedades de grafos", "narration": "El grado de un vertice es el numero de aristas que inciden en el", "formula": "\\deg(v) = |\\{e \\in E : v \\in e\\}|"},
                {"type": "visual", "text": "Un grafo dirigido tiene aristas con dirección", "narration": "Un grafo dirigido tiene aristas con direccion", "formula": "\\vec{G}", "visual_type": "graph_theory", "graph_nodes": ["A","B","C","D"], "graph_edges": ["0-1","0-2","1-3","2-3","3-0"], "graph_directed": True},
                {"type": "conclusion", "text": "Los grafos modelan redes y relaciones", "narration": "Los grafos modelan redes y relaciones en muchas areas"},
            ]
        },
    }

    key = topic.lower().strip()
    if key in library:
        return library[key]

    return {
        "title": topic,
        "scenes": [
            {"type": "hook", "text": f"¿Qué sabemos sobre {topic}?", "narration": f"Que sabemos sobre {topic}"},
            {"type": "formula", "text": "La fórmula fundamental", "narration": "Esta es la formula fundamental", "formula": "f(x) = x"},
            {"type": "graph", "text": "Visualicemos el concepto", "narration": "Visualicemos el concepto", "formula": "f(x) = x", "graph_func": "x", "graph_label": "f(x) = x"},
            {"type": "step", "text": "Aplicamos el razonamiento paso a paso", "narration": "Aplicamos el razonamiento paso a paso"},
            {"type": "conclusion", "text": f"¡{topic} es más fácil de lo que parece!", "narration": f"{topic} es mas facil de lo que parece"},
        ]
    }


def _tts_cache_path(text: str, engine: str, voice: str) -> Path:
    """Ruta de caché de audio. Reutiliza el MP3 si el mismo texto+voz ya se generó."""
    key = hashlib.sha1(f"{engine}|{voice}|{text.strip()}".encode("utf-8")).hexdigest()[:16]
    return Config.DIRS["audio"] / f"narr_{key}.mp3"


def _tts_edge(text: str, voice: str, out: Path) -> None:
    import edge_tts
    asyncio.run(edge_tts.Communicate(text=text, voice=voice).save(str(out)))


def _tts_gtts(text: str, out: Path) -> None:
    from gtts import gTTS
    tts = gTTS(text=text, lang="es")
    tts.save(str(out))


def _tts_elevenlabs(text: str, voice: str, out: Path) -> None:
    import httpx
    model_id = Config.ELEVENLABS_MODEL_ID
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128"
    payload = {"text": text, "model_id": model_id}
    headers = {
        "xi-api-key": Config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    with httpx.Client(timeout=90) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()
    out.write_bytes(response.content)


def _tts_engine_order() -> list[str]:
    """Orden de motores TTS según TTS_ENGINE."""
    e = Config.TTS_ENGINE
    if e in ("elevenlabs", "edge", "gtts"):
        order = [e]
        if e == "elevenlabs" and not Config.ELEVENLABS_API_KEY:
            order = ["edge", "gtts"]
    else:  # auto
        order = []
        if Config.ELEVENLABS_API_KEY:
            order.append("elevenlabs")
        order += ["edge", "gtts"]
    return order


def _edge_voice_for(voice_id: str | None) -> str:
    if (voice_id and Config.ELEVENLABS_HOOK_VOICE_ID
            and voice_id == Config.ELEVENLABS_HOOK_VOICE_ID and Config.EDGE_TTS_HOOK_VOICE):
        return Config.EDGE_TTS_HOOK_VOICE
    return Config.EDGE_TTS_VOICE


def generate_audio(text: str, suffix: str = "", voice_id: str | None = None) -> Path:
    text = (text or "").strip()
    if not text:
        raise ValueError("generate_audio: texto vacío")
    voice_id = voice_id or Config.ELEVENLABS_VOICE_ID

    for engine in _tts_engine_order():
        voice = voice_id if engine == "elevenlabs" else (_edge_voice_for(voice_id) if engine == "edge" else "")
        cache = _tts_cache_path(text, engine, voice)
        if cache.exists() and cache.stat().st_size > 0:
            print(f"  Audio en caché ({engine})")
            return cache
        try:
            if engine == "elevenlabs":
                _tts_elevenlabs(text, voice, cache)
            elif engine == "edge":
                _tts_edge(text, voice, cache)
            else:
                _tts_gtts(text, cache)
            print(f"  Audio generado con {engine}")
            return cache
        except ImportError:
            print(f"  {engine} no disponible, probando siguiente motor...")
        except Exception as e:
            print(f"  {engine} falló ({e}), usando respaldo...")

    raise RuntimeError("No se pudo generar audio (ningún motor TTS disponible). "
                       "Instala edge-tts/gtts o configura ELEVENLABS_API_KEY.")


def generate_audio_batch(script: dict, suffix: str = "", progress_callback=None) -> tuple[list, list[float]]:
    """Genera las narraciones por escena EN PARALELO. Devuelve (paths, durations_escena).
    Salta las escenas `type:'end'` (no tienen narración). La primera escena / hooks usan voz enérgica."""
    scenes = script.get("scenes", [])
    jobs = []
    for i, s in enumerate(scenes):
        if s.get("type") == "end":
            continue
        text = (s.get("narration") or s.get("text") or "").strip()
        energetic = (i == 0) or s.get("type") == "hook" or s.get("voice") == "hook"
        voice = Config.ELEVENLABS_HOOK_VOICE_ID if (energetic and Config.ELEVENLABS_HOOK_VOICE_ID) else Config.ELEVENLABS_VOICE_ID
        jobs.append((i, text, voice))

    results: dict[int, tuple[Path, float]] = {}
    if jobs:
        workers = min(max(1, Config.TTS_WORKERS), len(jobs))

        def run(idx: int, text: str, voice: str) -> tuple[Path, float]:
            ap = generate_audio(text, f"{suffix}_s{idx}", voice_id=voice)
            return ap, get_audio_duration(ap)

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(run, idx, text, voice): idx for idx, text, voice in jobs}
            for fut in as_completed(futs):
                idx = futs[fut]
                try:
                    results[idx] = fut.result()
                except Exception as e:
                    print(f"  Error generando audio de escena {idx}: {e}")
                    results[idx] = (None, 0.0)
                if progress_callback:
                    progress_callback(len(results), len(jobs))

    paths, durations = [], []
    for i, s in enumerate(scenes):
        if s.get("type") == "end":
            continue
        ap, ad = results.get(i, (None, 0.0))
        paths.append(ap)
        durations.append(max(ad + Config.SCENE_TAIL, Config.MIN_SCENE) if ap else Config.MIN_SCENE)
    return paths, durations


def generate_scene_audios(script: dict, suffix: str = "") -> tuple[list, list[float]]:
    """Wrapper síncrono (CLI): genera todas las narraciones por escena en paralelo."""
    return generate_audio_batch(script, suffix)


def get_audio_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True
    )
    raw = r.stdout.strip()
    if not raw:
        raise RuntimeError(f"No se pudo obtener la duración de {path}")
    return float(raw)


def scene_offsets(durations: list[float]) -> list[float]:
    """Offset de inicio de cada escena (con el lead antes de la narración)."""
    offsets, acc = [], 0.0
    for d in durations:
        offsets.append(acc + Config.SCENE_LEAD)
        acc += d
    return offsets


def inject_durations(script: dict, durations: list[float]) -> None:
    for scene, d in zip(script.get("scenes", []), durations):
        scene["d"] = round(d, 3)


def build_brand(script: dict | None = None) -> dict:
    """Configuración de marca con valores por defecto."""
    b = (script or {}).get("brand") or {}
    return {
        "name": b.get("name") or Config.BRAND_NAME,
        "tagline": b.get("tagline") if b.get("tagline") is not None else Config.BRAND_TAGLINE,
        "logo_image": b.get("logo_image", ""),
        "logo_color": b.get("logo_color") or Config.BRAND_COLOR,
        "subscribe_text": b.get("subscribe_text") if b.get("subscribe_text") is not None else Config.BRAND_SUBSCRIBE_TEXT,
        "subscribe_channel": b.get("subscribe_channel") if b.get("subscribe_channel") is not None else Config.BRAND_CHANNEL,
        "subscribe_button": b.get("subscribe_button", True),
    }


def apply_branding(script: dict, brand: dict | None = None) -> dict:
    """Fija la marca del video y añade la pantalla de cierre (end scene).
    La escena final no tiene narración y dura Config.END_SCREEN segundos."""
    merged = build_brand(script)
    if brand:
        merged.update(brand)
    script["brand"] = merged
    scenes = script.get("scenes", [])
    if not (scenes and scenes[-1].get("type") == "end"):
        scenes.append({"type": "end", "text": "", "narration": "", "d": Config.END_SCREEN})
    return script


def generate_html(script: dict, duration: float, suffix: str = "", fps: int | None = None) -> Path:
    template = (Config.DIRS["templates"] / "scene.html").read_text(encoding="utf-8")
    engine = (Config.DIRS["templates"] / "graph_engine.js").read_text(encoding="utf-8")
    engine = engine.replace("</script>", "<\\/script>").replace("</", "<\\/")
    parts = template.split("{{GRAPH_ENGINE}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{GRAPH_ENGINE}}")
    template = parts[0] + engine + parts[1]
    scenes_json = json.dumps(script["scenes"], ensure_ascii=False).replace("</", "<\\/")
    parts = template.split("{{SCENES}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{SCENES}}")
    html = parts[0] + scenes_json + parts[1]
    parts = html.split("{{DURATION}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{DURATION}}")
    html = parts[0] + str(duration) + parts[1]
    parts = html.split("{{FPS}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{FPS}}")
    html = parts[0] + str(fps or Config.FPS) + parts[1]
    brand_json = json.dumps(build_brand(script), ensure_ascii=False).replace("</", "<\\/")
    parts = html.split("{{BRAND}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{BRAND}}")
    html = parts[0] + brand_json + parts[1]
    filename = f"scene_playback_{suffix}.html" if suffix else "scene_playback.html"
    out = Config.DIRS["scenes"] / filename
    out.write_text(html, encoding="utf-8")
    return out


def render_video(html_path: Path, duration: float, suffix: str = "") -> Path:
    """Render determinista por frames: cada frame se calcula con renderFrame(f),
    se captura como PNG y se codifica con FFmpeg. No depende del tiempo real."""
    fps = Config.FPS
    scale = Config.RENDER_SCALE
    view_w = max(2, int(Config.WIDTH * scale))
    view_h = max(2, int(Config.HEIGHT * scale))

    dirname = f"frames_{suffix}" if suffix else "frames"
    frames_dir = Config.DIRS["output"] / dirname
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": view_w, "height": view_h},
            device_scale_factor=1,
        )
        page = context.new_page()
        file_url = html_path.resolve().as_uri()
        page.goto(file_url, wait_until="load", timeout=60000)
        page.wait_for_function("() => window.__READY === true", timeout=30000)
        total_frames = page.evaluate("() => window.totalFrames")
        for f in range(total_frames):
            page.evaluate(f"window.renderFrame({f})")
            page.screenshot(path=str(frames_dir / f"f_{f:05d}.png"))
        browser.close()

    silent_name = f"silent_{suffix}.mp4" if suffix else "silent.mp4"
    silent = Config.DIRS["scenes"] / silent_name
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", str(frames_dir / "f_%05d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
        str(silent),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(frames_dir)
    return silent


def create_final_video(video_path: Path, audio_paths: list, offsets: list[float], suffix: str = "") -> Path:
    """Combina el video mudo con las narraciones por escena (adelay) y la música de fondo."""
    out_name = f"final_video_{suffix}.mp4" if suffix else "final_video.mp4"
    out = Config.DIRS["videos"] / out_name
    bg_music = BASE_DIR / "assets" / "mixkit-tech-house-vibes-130.mp3"

    pairs = [(p, o) for p, o in zip(audio_paths, offsets) if p is not None]
    if not pairs:
        raise RuntimeError("No hay narración para ninguna escena")

    cmd = ["ffmpeg", "-y", "-i", str(video_path)]
    if bg_music.exists():
        cmd.extend(["-stream_loop", "-1", "-i", str(bg_music)])
    for ap, _ in pairs:
        cmd.extend(["-i", str(ap)])

    src_idx = 2 if bg_music.exists() else 1
    fc = []
    if bg_music.exists():
        fc.append("[1:a]volume=-20dB[a_bg]")
    labels = []
    for i, (ap, off) in enumerate(pairs):
        ms = int(round(off * 1000))
        fc.append(
            f"[{src_idx + i}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,"
            f"adelay={ms}:all=1[a{i}]"
        )
        labels.append(f"[a{i}]")
    inputs = ["[a_bg]"] + labels if bg_music.exists() else labels
    fc.append("".join(inputs) + f"amix=inputs={len(inputs)}:duration=longest:normalize=0[aout]")
    fc.append("[aout]apad[aoutpad]")

    cmd.extend([
        "-filter_complex", ";".join(fc),
        "-map", "0:v:0", "-map", "[aoutpad]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        str(out),
    ])
    subprocess.run(cmd, check=True, capture_output=True)
    return out


def main():
    if not check_dependencies():
        sys.exit(1)

    topic = input("Tema del video: ").strip()
    if not topic:
        print("Debes ingresar un tema.")
        return

    print(f"Generando guion para: {topic}")
    script = generate_script(topic)
    print(f"  Título: {script['title']}")
    print(f"  Escenas: {len(script['scenes'])}")

    print("Generando audio por escena...")
    t0 = time.time()
    audio_paths, durations = generate_scene_audios(script)
    offsets = scene_offsets(durations)
    inject_durations(script, durations)
    apply_branding(script)
    total = sum(durations) + Config.END_SCREEN
    print(f"  {len(durations)} narraciones, duración total: {total:.1f}s ({time.time()-t0:.1f}s)")

    print("Generando HTML...")
    html_path = generate_html(script, total)
    print(f"  HTML: {html_path}")

    print("Renderizando frames con Playwright...")
    t0 = time.time()
    video_path = render_video(html_path, total)
    print(f"  Video mudo: {video_path} ({time.time()-t0:.1f}s)")

    print("Creando video final...")
    final = create_final_video(video_path, audio_paths, offsets)
    mb = final.stat().st_size / 1024 / 1024
    print(f"Video final: {final} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
