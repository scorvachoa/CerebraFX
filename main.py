#!/usr/bin/env python3
import json
import re
import shutil
import subprocess
import sys
import time
import warnings
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
    "algebra": "Álgebra: usa graph_func con polinomios (x*x, 2*x+3, x*x-4), ecuaciones lineales y cuadráticas. Incluye graph_type 'function' o 'multiple' para comparar funciones.",
    "trigonometry": "Trigonometría: usa graph_type 'parametric' para círculo (cos(t); sin(t)), graph_type 'polar' para curvas polares. Incluye type 'visual' con seno/coseno para círculo trigonométrico y triángulos.",
    "calculus": "Cálculo: usa graph_func con derivadas (2*x, 3*x*x) e integrales. graph_type 'inequality' para áreas. Incluye \\int y \\frac en formulas LaTeX.",
    "geometry": "Geometría: usa type 'visual' para triángulos, círculos y figuras geométricas. Incluye triángulo rectángulo con Pitágoras (a^2+b^2=c^2).",
    "graph_theory": "Teoría de Grafos: usa type 'visual' con visual_type='graph_theory', graph_nodes=['A','B','C',...], graph_edges=['0-1','1-2',...]. Incluye grafos dirigidos (graph_directed=true) y no dirigidos.",
    "statistics": "Estadística: usa graph_type 'function' o 'multiple' para distribuciones. Puedes incluir histogramas conceptuales con type 'visual'.",
    "arithmetic": "Aritmética: usa type 'step' para operaciones paso a paso. type 'visual' para fracciones (\\frac) y raíces (\\sqrt).",
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
         '      "graph_func": "función JS opcional. String simple (x*x) o array [x*x, 2*x+1] para múltiples curvas. Para paramétricas: cos(t); sin(t) (x(t); y(t) separado por ;)",\n'
         '      "graph_label": "etiqueta opcional. Si graph_func es array, graph_label también debe ser array",\n'
         '      "graph_type": "opcional: function (default), parametric, polar, inequality",\n'
         '      "graph_inequality": "solo si graph_type=inequality: < o > para sombrear región"\n'
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


def generate_audio(text: str, suffix: str = "") -> Path:
    filename = f"narration_{suffix}.mp3" if suffix else "narration.mp3"
    path = Config.DIRS["audio"] / filename

    if Config.ELEVENLABS_API_KEY:
        try:
            import httpx
            voice_id = Config.ELEVENLABS_VOICE_ID
            model_id = Config.ELEVENLABS_MODEL_ID
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
            payload = {"text": text.strip(), "model_id": model_id}
            headers = {
                "xi-api-key": Config.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            }
            with httpx.Client(timeout=90) as client:
                response = client.post(url, json=payload, headers=headers)
                response.raise_for_status()
            path.write_bytes(response.content)
            print(f"  Audio generado con ElevenLabs")
            return path
        except Exception as e:
            print(f"  ElevenLabs falló ({e}), usando respaldo...")
    else:
        print("  Sin API key de ElevenLabs, usando respaldo local...")

    try:
        from gtts import gTTS
        tts = gTTS(text=text, lang="es")
        tts.save(str(path))
        print(f"  Audio generado con gTTS (Google TTS)")
    except ImportError:
        print("  gTTS no instalado. Instálalo con: pip install gtts")
        print("  Mientras tanto, configura ELEVENLABS_API_KEY en .env")
        raise RuntimeError("gTTS no disponible. Instálalo o usa ElevenLabs.")
    return path


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


def generate_html(script: dict, duration: float, suffix: str = "") -> Path:
    template = (Config.DIRS["templates"] / "scene.html").read_text(encoding="utf-8")
    scenes_json = json.dumps(script["scenes"], ensure_ascii=False).replace("</", "<\\/")
    parts = template.split("{{SCENES}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{SCENES}}")
    html = parts[0] + scenes_json + parts[1]
    parts = html.split("{{DURATION}}")
    if len(parts) != 2:
        raise ValueError("Template debe contener exactamente un {{DURATION}}")
    html = parts[0] + str(duration) + parts[1]
    filename = f"scene_playback_{suffix}.html" if suffix else "scene_playback.html"
    out = Config.DIRS["scenes"] / filename
    out.write_text(html, encoding="utf-8")
    return out


def render_video(html_path: Path, duration: float, suffix: str = "") -> Path:
    dirname = f"record_{suffix}" if suffix else "record"
    record_dir = Config.DIRS["output"] / dirname
    if record_dir.exists():
        shutil.rmtree(record_dir)
    record_dir.mkdir(parents=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": Config.WIDTH, "height": Config.HEIGHT},
            record_video_dir=str(record_dir),
            device_scale_factor=1,
        )
        page = context.new_page()
        file_url = html_path.resolve().as_uri()
        page.goto(file_url)
        wait_ms = int((duration + 1.0) * 1000)
        page.wait_for_timeout(wait_ms)
        context.close()
        browser.close()

    webms = sorted(record_dir.glob("*.webm"))
    if not webms:
        raise RuntimeError("No se generó video con Playwright")
    recorded = webms[0]
    rec_name = f"recording_{suffix}.webm" if suffix else "recording.webm"
    dest = Config.DIRS["scenes"] / rec_name
    shutil.move(str(recorded), str(dest))
    shutil.rmtree(record_dir)
    return dest


def create_final_video(video_path: Path, audio_path: Path, suffix: str = "") -> Path:
    out_name = f"final_video_{suffix}.mp4" if suffix else "final_video.mp4"
    out = Config.DIRS["videos"] / out_name
    bg_music = BASE_DIR / "assets" / "mixkit-tech-house-vibes-130.mp3"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
    ]

    if bg_music.exists():
        cmd.extend(["-stream_loop", "-1", "-i", str(bg_music)])
        cmd.extend([
            "-filter_complex",
            "[2:a]volume=-20dB[a_bg];[1:a][a_bg]amix=inputs=2:duration=first[a]",
            "-map", "0:v:0", "-map", "[a]",
        ])
    else:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])

    cmd.extend([
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
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

    full_text = ". ".join(s["narration"] if "narration" in s else s["text"] for s in script["scenes"])
    print(f"Generando audio ({len(full_text)} caracteres)...")
    audio_path = generate_audio(full_text)
    print(f"  Audio: {audio_path}")

    print("Obteniendo duración...")
    duration = get_audio_duration(audio_path)
    print(f"  Duración: {duration:.2f}s")

    print("Generando HTML...")
    html_path = generate_html(script, duration)
    print(f"  HTML: {html_path}")

    print("Renderizando con Playwright...")
    t0 = time.time()
    video_path = render_video(html_path, duration)
    print(f"  Video crudo: {video_path} ({time.time()-t0:.1f}s)")

    print("Creando video final...")
    final = create_final_video(video_path, audio_path)
    mb = final.stat().st_size / 1024 / 1024
    print(f"Video final: {final} ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
