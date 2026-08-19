"""Genera index.html a partir de lo que haya en resultados/.

La página se sirve con GitHub Pages desde la raíz del repo, así que apunta a
las imágenes que ya están en `resultados/` en vez de duplicarlas.

    python scripts/generar_web.py

Todo el contenido sale de los CSV: si un producto no está generado, su
sección no aparece, en vez de dejar una imagen rota.
"""

from __future__ import annotations

import csv
import html
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aemet_noches.metricas import MESES, fecha_larga  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
RESULTADOS = RAIZ / "resultados"

MESES_LARGOS = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def leer_csv(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def numero(texto: str, por_defecto=None):
    try:
        return float(texto)
    except (TypeError, ValueError):
        return por_defecto


def tendencia(pares: list[tuple[int, float]]) -> float | None:
    """Pendiente de la recta de mínimos cuadrados, por década."""
    if len(pares) < 5:
        return None
    n = len(pares)
    mx = sum(x for x, _ in pares) / n
    my = sum(y for _, y in pares) / n
    denominador = sum((x - mx) ** 2 for x, _ in pares)
    if denominador == 0:
        return None
    return sum((x - mx) * (y - my) for x, y in pares) / denominador * 10


# --- piezas de la página --------------------------------------------------

def tarjeta(valor: str, titulo: str, pie: str = "") -> str:
    pie_html = (
        f'<p class="mt-1 text-xs text-slate-500 dark:text-slate-400">{html.escape(pie)}</p>'
        if pie else ""
    )
    return f'''      <div class="rounded-xl border border-slate-200 bg-white p-5 dark:border-slate-800 dark:bg-slate-900">
        <p class="text-3xl font-semibold tracking-tight text-slate-900 dark:text-white">{valor}</p>
        <p class="mt-1 text-sm font-medium text-slate-600 dark:text-slate-300">{html.escape(titulo)}</p>
        {pie_html}
      </div>'''


def figura(base: str, titulo: str, texto: str, csv_rel: str | None = None) -> str:
    """Una sección con su gráfico, que cambia de tema con el del navegador."""
    claro, oscuro = f"{base}_claro.png", f"{base}_oscuro.png"
    if not (RAIZ / claro).exists():
        return ""
    enlace = (
        f'<a class="underline decoration-slate-300 underline-offset-4 hover:decoration-slate-500 '
        f'dark:decoration-slate-600" href="{csv_rel}">datos en CSV</a>'
        if csv_rel and (RAIZ / csv_rel).exists() else ""
    )
    return f'''    <section class="mt-14">
      <h2 class="text-xl font-semibold tracking-tight text-slate-900 dark:text-white">{html.escape(titulo)}</h2>
      <p class="mt-2 max-w-2xl text-sm leading-relaxed text-slate-600 dark:text-slate-300">{texto}</p>
      <figure class="mt-5 overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
        <picture>
          <source srcset="{oscuro}" media="(prefers-color-scheme: dark)">
          <img src="{claro}" alt="{html.escape(titulo)}" class="w-full" loading="lazy">
        </picture>
      </figure>
      <p class="mt-2 text-xs text-slate-500 dark:text-slate-400">{enlace}</p>
    </section>'''


def construir() -> str:
    hoy = date.today()
    tarjetas: list[str] = []

    # --- noches tropicales ---
    trop = leer_csv(RESULTADOS / "min20" / "datos.csv")
    completos = [f for f in trop if numero(f["cobertura"], 0) >= 0.99]
    if completos:
        ultimo = completos[-1]
        pares = [(int(f["anyo"]), float(f["total"])) for f in completos]
        pendiente = tendencia(pares)
        mejor = max(completos, key=lambda f: int(f["total"]))
        tarjetas.append(tarjeta(
            ultimo["total"], f"noches tropicales en {ultimo['anyo']}",
            f"máximo de la serie: {mejor['total']} en {mejor['anyo']}"))
        if pendiente:
            tarjetas.append(tarjeta(
                f"{pendiente:+.0f}".replace("-", "−"), "noches más por década",
                f"{pares[0][0]}–{pares[-1][0]}, mínima ≥ 20 °C"))

    # --- tórridas ---
    torr = leer_csv(RESULTADOS / "min25" / "datos.csv")
    ct = [f for f in torr if numero(f["cobertura"], 0) >= 0.99]
    if ct:
        viejas = sum(int(f["total"]) for f in ct if int(f["anyo"]) <= 2002)
        nuevas = sum(int(f["total"]) for f in ct if int(f["anyo"]) >= 2022)
        tarjetas.append(tarjeta(
            str(nuevas), "noches tórridas desde 2022",
            f"solo {viejas} entre 1990 y 2002 · mínima ≥ 25 °C"))

    # --- récord de mínima ---
    top = leer_csv(RESULTADOS / "rankings" / "top10_tmin.csv")
    if top:
        primera = top[0]
        dia = date.fromisoformat(primera["fecha"])
        grados = f"{float(primera['tmin']):.1f}".replace(".", ",")
        tarjetas.append(tarjeta(
            f"{grados} °C", "la noche más cálida registrada", fecha_larga(dia)))

    # --- lluvia ---
    lluvia = leer_csv(RESULTADOS / "lluvia" / "datos.csv")
    cl = [f for f in lluvia if numero(f["cobertura"], 0) >= 0.99]
    if cl:
        racha = max(cl, key=lambda f: int(f["racha_seca"]))
        tarjetas.append(tarjeta(
            f'{racha["racha_seca"]} días', "la racha seca más larga",
            f'acabó el {fecha_larga(date.fromisoformat(racha["racha_seca_fin"]))}'
            if racha["racha_seca_fin"] else ""))
        torrencial = sum(numero(f["torrencialidad"], 0) for f in cl) / len(cl)
        tarjetas.append(tarjeta(
            f"{torrencial:.0%}", "de la lluvia, en 5 días",
            "media de los años completos"))

    secciones = "\n".join(filter(None, [
        figura("resultados/lineas_tmax/diaria_suave", "El año en curso frente a todos los demás",
               "Cada línea gris es un año desde 1990. En color, los dos últimos. "
               "Media móvil de siete días para que se lean las olas de calor sin el "
               "temblor del día a día.",
               "resultados/anomalias_tmax/datos.csv"),
        figura("resultados/anomalias_tmax/mapa", "¿Sube la temperatura máxima?",
               "Desviación de cada mes respecto a su normal de 1991-2020. Azul por "
               "debajo de lo normal, rojo por encima. El cero no es «el clima de "
               "antes»: son treinta años que ya llevaban calentamiento dentro.",
               "resultados/anomalias_tmax/datos.csv"),
        figura("resultados/min20/mapa", "Noches tropicales",
               "Noches en que la temperatura mínima no bajó de 20 °C, mes a mes. "
               "El verano no se ha vuelto solo más intenso: se ha alargado por los "
               "bordes, sobre todo por junio.",
               "resultados/min20/datos.csv"),
        figura("resultados/min25/mapa", "Noches tórridas",
               "El mismo mapa con el listón en 25 °C. Entre 1990 y 2002 hubo una "
               "sola noche así; en los últimos años son decenas.",
               "resultados/min25/datos.csv"),
        figura("resultados/rankings/top10_tmin", "Las noches más cálidas del registro",
               "Once de las doce más cálidas desde 1990 son de 2018 en adelante.",
               "resultados/rankings/top10_tmin.csv"),
        figura("resultados/lluvia/mapa", "Lluvia mensual",
               "Precipitación acumulada por mes. En clima mediterráneo el total "
               "anual dice menos que el reparto: unos pocos días concentran buena "
               "parte del agua del año.",
               "resultados/lluvia/datos.csv"),
    ]))

    return f'''<!doctype html>
<html lang="es" class="scroll-smooth">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clima de Castelló · datos de AEMET</title>
<meta name="description" content="Noches tropicales, anomalías de temperatura y lluvia en Castelló-Almassora desde 1990, con datos de AEMET.">
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-900 antialiased dark:bg-slate-950 dark:text-slate-100">
  <main class="mx-auto max-w-4xl px-6 py-16">

    <header>
      <p class="text-sm font-medium uppercase tracking-widest text-slate-500 dark:text-slate-400">Castelló de la Plana · Almassora</p>
      <h1 class="mt-3 text-4xl font-bold tracking-tight sm:text-5xl">Treinta y seis años de clima, contados con los datos de AEMET</h1>
      <p class="mt-5 max-w-2xl text-lg leading-relaxed text-slate-600 dark:text-slate-300">
        La estación 8500A lleva midiendo desde 1990. Esto es lo que dicen sus datos
        sobre cómo han cambiado las noches, los días y la lluvia en este trozo de costa.
      </p>
      <p class="mt-4 text-sm text-slate-500 dark:text-slate-400">
        Actualizado el {hoy.day} de {MESES_LARGOS[hoy.month - 1]} de {hoy.year} ·
        se regenera solo cada mes ·
        <a class="underline underline-offset-4" href="https://github.com/Poloigithub/AEMET_Castello">código y datos</a>
      </p>
    </header>

    <div class="mt-12 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
{chr(10).join(tarjetas)}
    </div>

{secciones}

    <footer class="mt-20 border-t border-slate-200 pt-8 text-sm leading-relaxed text-slate-500 dark:border-slate-800 dark:text-slate-400">
      <p>
        <strong class="font-medium text-slate-700 dark:text-slate-200">Fuente:</strong>
        AEMET OpenData, valores climatológicos diarios de la estación 8500A.
        Los gráficos y los CSV se generan solos desde
        <a class="underline underline-offset-4" href="https://github.com/Poloigithub/AEMET_Castello">este repositorio</a>.
      </p>
      <p class="mt-3">
        <strong class="font-medium text-slate-700 dark:text-slate-200">Una cautela:</strong>
        la serie no está homogeneizada. Los observatorios se mudan, cambian de
        instrumental y su entorno se urbaniza, así que parte de la subida es clima
        y parte es entorno. Con estos datos no se pueden separar.
      </p>
      <p class="mt-6 text-xs">Gráficos: poloi@eurosky.social</p>
    </footer>

  </main>
</body>
</html>
'''


if __name__ == "__main__":
    destino = RAIZ / "index.html"
    destino.write_text(construir(), encoding="utf-8")
    (RAIZ / ".nojekyll").touch()  # que Pages sirva las carpetas tal cual
    print(f"Web generada en {destino}")
