"""Mapa de calor de noches tropicales: años (filas) × meses (columnas)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from .metricas import MESES, ResumenAnual  # noqa: E402

# Rampa secuencial de un solo tono (naranja), clara → oscura.
# Derivada del naranja categórico #eb6834 manteniendo el perfil de luminosidad
# de la rampa azul de referencia: L monótona en OKLCH y dentro de gamut sRGB.
RAMPA = [
    "#fdd6c8", "#fcc1ab", "#fbab8e", "#f89470", "#f57c4f", "#ef642b",
    "#db571e", "#c54e1a", "#af4416", "#9a3b12", "#86320e", "#722a0a", "#5f2107",
]

TEMAS = {
    "claro": {
        "fondo": "#fcfcfb",
        "tinta": "#0b0b0b",
        "tinta_2": "#52514e",
        "apagado": "#898781",
        "vacio": "#f0efec",       # celda con datos pero cero noches
        "sin_datos": "#e1e0d9",   # celda sin observaciones
        "rampa": RAMPA[:12],      # clara → oscura
    },
    "oscuro": {
        "fondo": "#1a1a19",
        "tinta": "#ffffff",
        "tinta_2": "#c3c2b7",
        "apagado": "#898781",
        "vacio": "#2c2c2a",
        "sin_datos": "#383835",
        "rampa": list(reversed(RAMPA[2:])),  # oscura → clara sobre fondo oscuro
    },
}


def _luminancia(hexv: str) -> float:
    def canal(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hexv[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def _tinta_sobre(fondo: str, tema: dict) -> str:
    """El texto de la celda va en blanco o en tinta oscura, el que más contraste."""
    oscura = "#0b0b0b"
    return oscura if _contraste(fondo, oscura) >= _contraste(fondo, "#ffffff") else "#ffffff"


def _ajustar_a_lo_ancho(fig, texto, ancho_max_pulg: float, minimo: float = 6.5) -> None:
    """Reduce el cuerpo del texto hasta que quepa en el ancho disponible."""
    fig.canvas.draw()
    while texto.get_fontsize() > minimo:
        caja = texto.get_window_extent(fig.canvas.get_renderer())
        if caja.width / fig.dpi <= ancho_max_pulg:
            return
        texto.set_fontsize(texto.get_fontsize() - 0.5)
    caja = texto.get_window_extent(fig.canvas.get_renderer())
    if caja.width / fig.dpi > ancho_max_pulg:  # aún no cabe: recorta
        contenido = texto.get_text()
        proporcion = ancho_max_pulg * fig.dpi / caja.width
        corte = max(8, int(len(contenido) * proporcion) - 1)
        texto.set_text(contenido[:corte].rstrip() + "…")


def dibujar(
    resumenes: list[ResumenAnual],
    destino: Path,
    estacion: str,
    umbral: float = 20.0,
    estricto: bool = False,
    tema: str = "claro",
    cobertura_minima: float = 0.9,
    dpi: int = 200,
) -> Path:
    if not resumenes:
        raise ValueError("No hay años que dibujar")
    t = TEMAS[tema]
    mapa = LinearSegmentedColormap.from_list("noches", t["rampa"])

    n = len(resumenes)
    maximo = max((max(r.por_mes) for r in resumenes), default=0) or 1

    # Geometría en pulgadas: celda 0,42 × 0,20 in, más márgenes fijos.
    ancho_celda, alto_celda = 0.42, 0.21
    izq, der = 0.72, 0.92
    arriba, abajo = 1.35, 0.85
    ancho = izq + 12 * ancho_celda + der
    alto = arriba + n * alto_celda + abajo

    fig = plt.figure(figsize=(ancho, alto), dpi=dpi, facecolor=t["fondo"])
    ax = fig.add_axes(
        [izq / ancho, abajo / alto, (12 * ancho_celda) / ancho, (n * alto_celda) / alto]
    )
    ax.set_facecolor(t["fondo"])
    ax.set_xlim(0, 12)
    ax.set_ylim(n, 0)
    for lado in ax.spines.values():
        lado.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])

    hueco = 0.045  # separación entre celdas (~2 px al dpi de salida)
    incompletos = []

    for fila, r in enumerate(resumenes):
        for mes in range(12):
            x, y = mes + hueco, fila + hueco
            w, h = 1 - 2 * hueco, 1 - 2 * hueco
            valor = r.por_mes[mes]
            con_dato = r.dias_con_dato_mes[mes] > 0
            if not con_dato:
                ax.add_patch(
                    Rectangle(
                        (x, y), w, h,
                        facecolor=t["fondo"], edgecolor=t["sin_datos"],
                        linewidth=0.6, hatch="///////", linestyle="-",
                    )
                )
                continue
            color = t["vacio"] if valor == 0 else mapa(0.12 + 0.88 * valor / maximo)
            ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor="none"))
            if valor:
                hexc = matplotlib.colors.to_hex(color)
                ax.text(
                    mes + 0.5, fila + 0.5, str(valor),
                    ha="center", va="center", fontsize=5.2,
                    color=_tinta_sobre(hexc, t),
                )

        etiqueta = str(r.anyo)
        if r.cobertura < cobertura_minima:
            etiqueta += " *"
            incompletos.append(r.anyo)
        ax.text(
            -0.25, fila + 0.5, etiqueta, ha="right", va="center",
            fontsize=5.6, color=t["tinta_2"],
        )
        # Total anual: en tinta, nunca coloreado (es otra escala).
        total = str(r.total) if r.dias_con_dato else "—"
        ax.text(
            12.25, fila + 0.5, total, ha="left", va="center",
            fontsize=5.6, color=t["tinta"] if r.total else t["apagado"],
        )

    for mes, nombre in enumerate(MESES):
        ax.text(
            mes + 0.5, -0.35, nombre, ha="center", va="bottom",
            fontsize=5.6, color=t["apagado"],
        )
    ax.text(
        12.25, -0.35, "Año", ha="left", va="bottom",
        fontsize=5.6, color=t["apagado"],
    )

    # --- títulos y leyenda --------------------------------------------------
    signo = ">" if estricto else "≥"
    umbral_txt = f"{umbral:g}".replace(".", ",")
    disponible = ancho - izq - 0.2
    titulo = fig.text(
        izq / ancho, 1 - 0.32 / alto,
        f"Noches tropicales en {estacion}",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    subtitulo = fig.text(
        izq / ancho, 1 - 0.55 / alto,
        f"Días con temperatura mínima {signo} {umbral_txt} °C, por mes y año  ·  "
        f"{resumenes[0].anyo}–{resumenes[-1].anyo}",
        fontsize=7, color=t["tinta_2"], va="top", ha="left",
    )
    _ajustar_a_lo_ancho(fig, titulo, disponible, minimo=7)
    _ajustar_a_lo_ancho(fig, subtitulo, disponible, minimo=5.5)

    # Leyenda de la rampa: tira de gradiente con los extremos etiquetados al lado.
    tira_izq, tira_ancho, tira_y = izq + 0.14, 1.30, 0.92
    leyenda = fig.add_axes(
        [tira_izq / ancho, 1 - tira_y / alto, tira_ancho / ancho, 0.08 / alto]
    )
    leyenda.imshow(
        [[0.12 + 0.88 * i / 255 for i in range(256)]],
        aspect="auto", cmap=mapa, vmin=0, vmax=1,
    )
    leyenda.set_xticks([])
    leyenda.set_yticks([])
    for lado in leyenda.spines.values():
        lado.set_visible(False)
    fig.text(
        (tira_izq - 0.07) / ancho, 1 - (tira_y - 0.005) / alto, "1",
        fontsize=5.6, color=t["apagado"], va="top", ha="right",
    )
    fig.text(
        (tira_izq + tira_ancho + 0.07) / ancho, 1 - (tira_y - 0.005) / alto,
        f"{maximo} noches en el mes",
        fontsize=5.6, color=t["apagado"], va="top", ha="left",
    )

    notas = [
        "Fuente: AEMET OpenData, valores climatológicos diarios. "
        "Las celdas rayadas son meses sin observaciones.",
    ]
    if incompletos:
        rango = f"{min(incompletos)}–{max(incompletos)}" if len(incompletos) > 3 else \
            ", ".join(str(a) for a in incompletos)
        notas.append(
            f"* Años con menos del {cobertura_minima:.0%} de días observados "
            f"({len(incompletos)}: {rango}); su recuento se queda corto."
        )
    fig.text(
        izq / ancho, 0.30 / alto, "\n".join(notas),
        fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino
