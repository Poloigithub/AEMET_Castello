"""Mapa de calor de noches tropicales: años (filas) × meses (columnas)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from .metricas import MESES, ResumenAnual, ResumenTermico  # noqa: E402

# Rampa secuencial de un solo tono (naranja), clara → oscura.
# Derivada del naranja categórico #eb6834 manteniendo el perfil de luminosidad
# de la rampa azul de referencia: L monótona en OKLCH y dentro de gamut sRGB.
RAMPA = [
    "#fdd6c8", "#fcc1ab", "#fbab8e", "#f89470", "#f57c4f", "#ef642b",
    "#db571e", "#c54e1a", "#af4416", "#9a3b12", "#86320e", "#722a0a", "#5f2107",
]

# Escala divergente para anomalías: dos tonos opuestos y gris neutro en el cero.
# Los brazos se dan del centro hacia fuera; en tema oscuro el extremo es el
# claro, para que el cero se funda con el fondo y la desviación destaque.
AZUL = {150: "#b7d3f6", 250: "#86b6ef", 350: "#5598e7", 450: "#2a78d6",
        550: "#1c5cab", 650: "#104281"}
ROJO = {150: "#fcbfb9", 250: "#f89189", 350: "#ef605b", 450: "#da2731",
        550: "#ac1a23", 650: "#7f1017"}

TEMAS = {
    "claro": {
        "fondo": "#fcfcfb",
        "tinta": "#0b0b0b",
        "tinta_2": "#52514e",
        "apagado": "#898781",
        "vacio": "#f0efec",       # celda con datos pero cero noches
        "sin_datos": "#e1e0d9",   # celda sin observaciones
        "rampa": RAMPA[:12],      # clara → oscura
        "gris": "#f0efec",        # cero de la escala divergente
        "brazos": [150, 250, 350, 450, 550, 650],   # del centro hacia fuera
    },
    "oscuro": {
        "fondo": "#1a1a19",
        "tinta": "#ffffff",
        "tinta_2": "#c3c2b7",
        "apagado": "#898781",
        "vacio": "#2c2c2a",
        "sin_datos": "#383835",
        "rampa": list(reversed(RAMPA[2:])),  # oscura → clara sobre fondo oscuro
        "gris": "#383835",
        "brazos": [550, 450, 350, 250, 150],
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


def nombre_del_fenomeno(
    umbral: float, estricto: bool = False, variable: str = "tmin"
) -> str:
    """Los umbrales con nombre propio en climatología; el resto, descriptivo."""
    if variable == "tmin" and not estricto and umbral == 20:
        return "Noches tropicales"
    if variable == "tmin" and not estricto and umbral == 25:
        return "Noches tórridas"
    signo = ">" if estricto else "≥"
    if variable == "prec":
        return f"Días de lluvia ({signo} {umbral:g} mm)".replace(".", ",")
    if variable == "tmax":
        return f"Días con máxima {signo} {umbral:g} °C".replace(".", ",")
    return f"Noches con mínima {signo} {umbral:g} °C".replace(".", ",")


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
    variable: str = "tmin",
    tema: str = "claro",
    credito: str | None = None,
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
    que = {"tmax": "máxima", "prec": "precipitación"}.get(variable, "mínima")
    unidad = "mm" if variable == "prec" else "°C"
    umbral_txt = f"{umbral:g}".replace(".", ",")
    disponible = ancho - izq - 0.2
    titulo = fig.text(
        izq / ancho, 1 - 0.32 / alto,
        f"{nombre_del_fenomeno(umbral, estricto, variable)} en {estacion}",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    subtitulo = fig.text(
        izq / ancho, 1 - 0.55 / alto,
        f"Días con {que} {signo} {umbral_txt} {unidad}, por mes y año  ·  "
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
    if credito:
        notas.insert(0, credito)
    if incompletos:
        rango = f"{min(incompletos)}–{max(incompletos)}" if len(incompletos) > 3 else \
            ", ".join(str(a) for a in incompletos)
        notas.append(
            f"* Años con menos del {cobertura_minima:.0%} de días observados "
            f"({len(incompletos)}: {rango}); su recuento se queda corto."
        )
    # El bloque crece hacia abajo, así que se sube el ancla según cuántas líneas haya.
    fig.text(
        izq / ancho, (0.14 + 0.08 * len(notas)) / alto, "\n".join(notas),
        fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino


def _escala_divergente(t: dict) -> LinearSegmentedColormap:
    """Azul ↔ rojo con gris neutro en el cero, según el tema."""
    brazos = t["brazos"]
    frio = [AZUL[p] for p in reversed(brazos)]
    calor = [ROJO[p] for p in brazos]
    return LinearSegmentedColormap.from_list("anomalias", frio + [t["gris"]] + calor)


def dibujar_anomalias(
    serie: list[ResumenTermico],
    anomalia: list[list[float | None]],
    destino: Path,
    estacion: str,
    variable: str = "tmax",
    referencia: tuple[int, int] = (1991, 2020),
    tema: str = "claro",
    credito: str | None = None,
    dpi: int = 200,
) -> Path:
    """Mapa de anomalías: cuánto se desvía cada mes de su normal climática."""
    if not serie:
        raise ValueError("No hay años que dibujar")
    t = TEMAS[tema]
    mapa = _escala_divergente(t)

    n = len(serie)
    valores = [v for fila in anomalia for v in fila if v is not None]
    if not valores:
        raise ValueError("No hay ningún mes con datos suficientes para la anomalía")
    # Límite simétrico: el cero tiene que quedar en el centro de la escala.
    limite = max(0.5, max(abs(v) for v in valores))
    limite = round(limite + 0.24, 1)

    ancho_celda, alto_celda = 0.46, 0.21
    izq, der = 0.72, 1.45
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

    hueco = 0.045
    hay_huecos = False

    for fila, (r, fila_anom) in enumerate(zip(serie, anomalia)):
        for mes in range(12):
            x, y = mes + hueco, fila + hueco
            w, h = 1 - 2 * hueco, 1 - 2 * hueco
            valor = fila_anom[mes]
            if valor is None:
                hay_huecos = True
                ax.add_patch(
                    Rectangle(
                        (x, y), w, h,
                        facecolor=t["fondo"], edgecolor=t["sin_datos"],
                        linewidth=0.6, hatch="///////",
                    )
                )
                continue
            color = mapa(0.5 + 0.5 * valor / limite)
            ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor="none"))
            etiqueta = f"{valor:+.1f}".replace(".", ",").replace("-", "−")
            ax.text(
                mes + 0.5, fila + 0.5, etiqueta,
                ha="center", va="center", fontsize=4.6,
                color=_tinta_sobre(matplotlib.colors.to_hex(color), t),
            )

        ax.text(
            -0.25, fila + 0.5, str(r.anyo), ha="right", va="center",
            fontsize=5.6, color=t["tinta_2"],
        )
        # Dos columnas en tinta a la derecha: media del año y récord absoluto.
        media = r.media_anual
        ax.text(
            12.3, fila + 0.5,
            "—" if media is None else f"{media:.1f}".replace(".", ","),
            ha="left", va="center", fontsize=5.6,
            color=t["tinta"] if media is not None else t["apagado"],
        )
        ax.text(
            13.5, fila + 0.5,
            "—" if r.extremo is None else f"{r.extremo:.1f}".replace(".", ","),
            ha="left", va="center", fontsize=5.6,
            color=t["tinta"] if r.extremo is not None else t["apagado"],
        )

    for mes, nombre in enumerate(MESES):
        ax.text(
            mes + 0.5, -0.35, nombre, ha="center", va="bottom",
            fontsize=5.6, color=t["apagado"],
        )
    ax.text(12.3, -0.35, "Media", ha="left", va="bottom", fontsize=5.6, color=t["apagado"])
    ax.text(13.5, -0.35, "Récord", ha="left", va="bottom", fontsize=5.6, color=t["apagado"])

    # --- títulos y leyenda --------------------------------------------------
    que = "máxima" if variable == "tmax" else "mínima"
    disponible = ancho - izq - 0.2
    titulo = fig.text(
        izq / ancho, 1 - 0.32 / alto,
        f"¿Sube la temperatura {que} en {estacion}?",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    subtitulo = fig.text(
        izq / ancho, 1 - 0.55 / alto,
        f"Desviación de la {que} media de cada mes respecto a su normal de "
        f"{referencia[0]}–{referencia[1]}, en °C  ·  {serie[0].anyo}–{serie[-1].anyo}",
        fontsize=7, color=t["tinta_2"], va="top", ha="left",
    )
    _ajustar_a_lo_ancho(fig, titulo, disponible, minimo=7)
    _ajustar_a_lo_ancho(fig, subtitulo, disponible, minimo=5.5)

    tira_izq, tira_ancho, tira_y = izq + 0.55, 1.30, 0.92
    leyenda = fig.add_axes(
        [tira_izq / ancho, 1 - tira_y / alto, tira_ancho / ancho, 0.08 / alto]
    )
    leyenda.imshow([[i / 255 for i in range(256)]], aspect="auto", cmap=mapa, vmin=0, vmax=1)
    leyenda.set_xticks([])
    leyenda.set_yticks([])
    for lado in leyenda.spines.values():
        lado.set_visible(False)
    lim_txt = f"{limite:.1f}".replace(".", ",")
    fig.text(
        (tira_izq - 0.07) / ancho, 1 - (tira_y - 0.005) / alto, f"−{lim_txt} °C",
        fontsize=5.6, color=t["apagado"], va="top", ha="right",
    )
    fig.text(
        (tira_izq + tira_ancho + 0.07) / ancho, 1 - (tira_y - 0.005) / alto,
        f"+{lim_txt} °C",
        fontsize=5.6, color=t["apagado"], va="top", ha="left",
    )

    notas = [
        f"Fuente: AEMET OpenData, valores climatológicos diarios. «Media» es la "
        f"{que} media del año y «Récord», la {que} más alta registrada.",
    ]
    if credito:
        notas.insert(0, credito)
    if hay_huecos:
        notas.append(
            "Las celdas rayadas son meses con menos del 90 % de días observados: "
            "una media a medias no es comparable, así que se deja en blanco."
        )
    fig.text(
        izq / ancho, (0.14 + 0.08 * len(notas)) / alto, "\n".join(notas),
        fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino


# Colores para los años destacados: naranja y violeta de la paleta categórica.
# Validados como par (ΔE 37,6 en visión normal, 29,5 en protanopia), y ninguno
# de los dos se lee como "año frío", que es lo que pasaría con el azul.
DESTACADOS = {
    "claro": ["#eb6834", "#4a3aa7", "#1baf7a"],
    "oscuro": ["#d95926", "#9085e9", "#199e70"],
}




def _dibujar_series(
    series: dict[int, list[float | None]],
    x: list[float],
    ticks: tuple[list[float], list[str]],
    destino: Path,
    estacion: str,
    destacar: list[int],
    variable: str,
    normal: list[float] | None,
    referencia: tuple[int, int],
    tema: str,
    credito: str | None,
    detalle: str,
    marcador: bool,
    grosor_fondo: float,
    alpha_fondo: float,
    nota_extra: str | None = None,
    dpi: int = 200,
) -> Path:
    """Núcleo común de los gráficos de líneas (uno por año)."""
    if not series:
        raise ValueError("No hay años que dibujar")
    t = TEMAS[tema]
    colores = DESTACADOS[tema]
    anyos = sorted(series)

    ancho, alto = 7.2, 4.6
    fig = plt.figure(figsize=(ancho, alto), dpi=dpi, facecolor=t["fondo"])
    ax = fig.add_axes([0.62 / ancho, 0.80 / alto, 5.75 / ancho, 3.10 / alto])
    ax.set_facecolor(t["fondo"])

    def trazo(valores):
        return [(x[i], v) for i, v in enumerate(valores) if v is not None]

    fondo = [a for a in anyos if a not in destacar]
    for anyo in fondo:
        p = trazo(series[anyo])
        if len(p) > 1:
            ax.plot([a for a, _ in p], [b for _, b in p], color=t["sin_datos"],
                    linewidth=grosor_fondo, alpha=alpha_fondo, zorder=1,
                    solid_capstyle="round")

    if normal:
        p = trazo(normal)
        ax.plot([a for a, _ in p], [b for _, b in p], color=t["tinta_2"],
                linewidth=1.1, linestyle=(0, (4, 2)), zorder=2)

    dibujados = []
    for i, anyo in enumerate(destacar):
        if anyo not in series:
            continue
        p = trazo(series[anyo])
        if not p:
            continue
        color = colores[i % len(colores)]
        ax.plot(
            [a for a, _ in p], [b for _, b in p], color=color, linewidth=1.6,
            marker="o" if marcador else None, markersize=3.2,
            markeredgecolor=t["fondo"], markeredgewidth=0.6,
            zorder=4, solid_capstyle="round",
        )
        dibujados.append((anyo, color, p[-1]))

    for anyo, _, (px, py) in dibujados:
        ax.annotate(
            str(anyo), xy=(px, py), xytext=(5, 0), textcoords="offset points",
            va="center", ha="left", fontsize=6.5, color=t["tinta"], zorder=5,
            bbox=dict(facecolor=t["fondo"], edgecolor="none", pad=0.8),
        )

    posiciones, etiquetas_x = ticks
    ax.set_xticks(posiciones)
    ax.set_xticklabels(etiquetas_x, fontsize=6.5, color=t["apagado"])
    ax.tick_params(axis="both", length=0, pad=4)
    for etiqueta in ax.get_yticklabels():
        etiqueta.set_fontsize(6.5)
        etiqueta.set_color(t["apagado"])
    # La unidad, una sola vez arriba, en vez de repetirla en cada marca.
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:g}".replace(".", ","))
    ax.text(
        -0.012, 1.012, "°C", transform=ax.transAxes, ha="right", va="bottom",
        fontsize=6.5, color=t["apagado"],
    )
    ax.grid(axis="y", color=t["sin_datos"], linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(t["sin_datos"])
    ax.spines["bottom"].set_linewidth(0.8)
    margen = (x[-1] - x[0]) * 0.03
    ax.set_xlim(x[0] - margen, x[-1] + margen)

    manijas = [plt.Line2D([], [], color=t["sin_datos"], linewidth=1.0)]
    etiquetas = [f"Cada año de {anyos[0]} a {max(fondo)}" if fondo else "—"]
    if normal:
        manijas.append(
            plt.Line2D([], [], color=t["tinta_2"], linewidth=1.1, linestyle=(0, (4, 2)))
        )
        etiquetas.append(f"Normal {referencia[0]}–{referencia[1]}")
    for anyo, color, _ in dibujados:
        manijas.append(plt.Line2D([], [], color=color, linewidth=1.9))
        etiquetas.append(str(anyo))
    leyenda = ax.legend(
        manijas, etiquetas, loc="upper left", bbox_to_anchor=(0, 1.10),
        ncol=len(manijas), frameon=False, fontsize=6.3,
        handlelength=1.6, columnspacing=1.4, handletextpad=0.5,
    )
    for texto in leyenda.get_texts():
        texto.set_color(t["tinta_2"])

    que = "máxima" if variable == "tmax" else "mínima"
    titulo = fig.text(
        0.62 / ancho, 1 - 0.30 / alto,
        f"Temperatura {que} {detalle} en {estacion}",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    _ajustar_a_lo_ancho(fig, titulo, ancho - 0.9, minimo=7)

    notas = ["Fuente: AEMET OpenData, valores climatológicos diarios."]
    if nota_extra:
        notas[0] += " " + nota_extra
    if credito:
        notas.insert(0, credito)
    fig.text(
        0.62 / ancho, (0.14 + 0.08 * len(notas)) / alto, "\n".join(notas),
        fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino


def dibujar_lineas(
    serie: list[ResumenTermico],
    destino: Path,
    estacion: str,
    destacar: list[int],
    variable: str = "tmax",
    normal: list[float] | None = None,
    referencia: tuple[int, int] = (1991, 2020),
    tema: str = "claro",
    credito: str | None = None,
    dpi: int = 200,
) -> Path:
    """Un punto por mes: doce medias mensuales, un año por línea."""
    return _dibujar_series(
        {r.anyo: r.medias for r in serie},
        x=list(range(12)),
        ticks=(list(range(12)), MESES),
        destino=destino, estacion=estacion, destacar=destacar, variable=variable,
        normal=normal, referencia=referencia, tema=tema, credito=credito,
        detalle="media de cada mes", marcador=True,
        grosor_fondo=0.7, alpha_fondo=1.0,
        nota_extra="Se omiten los meses con menos del 90 % de días observados.",
        dpi=dpi,
    )


def dibujar_lineas_diarias(
    series: dict[int, list[float | None]],
    destino: Path,
    estacion: str,
    destacar: list[int],
    variable: str = "tmax",
    normal: list[float] | None = None,
    referencia: tuple[int, int] = (1991, 2020),
    tema: str = "claro",
    credito: str | None = None,
    suavizado: int = 1,
    dpi: int = 200,
) -> Path:
    """Un punto por día del año: 365 valores, un año por línea."""
    from .metricas import INICIO_DE_MES

    nota = "El 29 de febrero se descarta para que todos los años tengan 365 días."
    if suavizado > 1:
        nota = f"Media móvil centrada de {suavizado} días. " + nota
    centros = [
        (INICIO_DE_MES[m] + INICIO_DE_MES[m + 1] - 1) / 2 if m < 11
        else (INICIO_DE_MES[11] + 365) / 2
        for m in range(12)
    ]
    return _dibujar_series(
        series,
        x=list(range(365)),
        ticks=(centros, MESES),
        destino=destino, estacion=estacion, destacar=destacar, variable=variable,
        normal=normal, referencia=referencia, tema=tema, credito=credito,
        detalle="de cada día", marcador=False,
        grosor_fondo=0.35, alpha_fondo=0.5,
        nota_extra=nota, dpi=dpi,
    )


def dibujar_tabla_extremos(
    ranking: list[tuple[object, float]],
    destino: Path,
    estacion: str,
    variable: str = "tmin",
    top: int = 10,
    resaltar: list[int] | None = None,
    tema: str = "claro",
    credito: str | None = None,
    dpi: int = 200,
) -> Path:
    """La clasificación como tabla, resaltando las filas de los años elegidos.

    Sin barras ni puntos: en un top los valores se apiñan en un palmo y
    cualquier codificación de longitud exagera diferencias de una décima.
    Aquí la cifra es el dato, y el color solo marca de qué año es cada fila.
    """
    from .metricas import fecha_larga

    if not ranking:
        raise ValueError("No hay nada que listar")
    t = TEMAS[tema]
    n = len(ranking)
    if resaltar is None:  # por defecto, el año más reciente que aparezca
        resaltar = [max(d.year for d, _ in ranking)]
    resaltar = set(resaltar)
    wash = RAMPA[0] if tema == "claro" else "#4a1a06"

    alto_fila = 0.30
    izq, der = 0.55, 0.50
    arriba, abajo = 1.00, 0.85
    ancho = 4.75
    alto = arriba + n * alto_fila + abajo

    fig = plt.figure(figsize=(ancho, alto), dpi=dpi, facecolor=t["fondo"])
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    ax.set_xlim(0, ancho)
    ax.set_ylim(0, alto)

    x_puesto, x_grados, x_fecha = izq + 0.28, izq + 1.40, izq + 1.60
    y0 = abajo + n * alto_fila

    puesto, anterior = 0, None
    for i, (dia, valor) in enumerate(ranking, start=1):
        y = y0 - i * alto_fila + alto_fila / 2
        marcado = dia.year in resaltar
        if marcado:
            ax.add_patch(
                Rectangle(
                    (izq - 0.14, y - alto_fila / 2 + 0.02),
                    ancho - izq - der + 0.28, alto_fila - 0.04,
                    facecolor=wash, edgecolor="none", zorder=1,
                )
            )
        if valor != anterior:
            puesto, anterior = i, valor
            ax.text(
                x_puesto, y, str(puesto), ha="right", va="center", zorder=2,
                fontsize=7, color=t["apagado"],
            )
        ax.text(
            x_grados, y, f"{valor:.1f}".replace(".", ",") + " °C",
            ha="right", va="center", fontsize=9, weight="bold", zorder=2,
            color=t["tinta"],
        )
        ax.text(
            x_fecha, y, fecha_larga(dia), ha="left", va="center", zorder=2,
            fontsize=7.8, color=t["tinta"] if marcado else t["tinta_2"],
        )

    que = "noches" if variable == "tmin" else "días"
    cual = "mínimas" if variable == "tmin" else "máximas"
    titulo = fig.text(
        izq / ancho, 1 - 0.30 / alto,
        f"Las {n} {que} más cálidas en {estacion}",
        fontsize=11.5, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    _ajustar_a_lo_ancho(fig, titulo, ancho - izq - 0.3, minimo=7)
    anyos = ", ".join(str(a) for a in sorted(resaltar))
    subtitulo = fig.text(
        izq / ancho, 1 - 0.56 / alto,
        f"Las {cual} más altas del registro · en color, las de {anyos}",
        fontsize=7.5, color=t["tinta_2"], va="top", ha="left",
    )
    _ajustar_a_lo_ancho(fig, subtitulo, ancho - izq - 0.3, minimo=5.8)

    notas = ["Fuente: AEMET OpenData, valores climatológicos diarios."]
    if n > top:
        notas.insert(
            0,
            f"Son {n} y no {top}: hay empate en el último puesto y dejar fuera "
            "una fecha idéntica sería arbitrario.",
        )
    if credito:
        notas.insert(0, credito)
    fig.text(
        izq / ancho, (0.14 + 0.09 * len(notas)) / alto, "\n".join(notas),
        fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6,
    )

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino


# Rampa secuencial azul para la lluvia: es el tono secuencial por defecto de
# la paleta y, además, nadie lee el azul como "calor".
RAMPA_LLUVIA = [
    "#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b",
]


def dibujar_lluvia(
    serie,
    destino: Path,
    estacion: str,
    tema: str = "claro",
    credito: str | None = None,
    cobertura_minima: float = 0.9,
    dpi: int = 200,
) -> Path:
    """Mapa de precipitación mensual en mm, con el total del año a la derecha."""
    if not serie:
        raise ValueError("No hay años que dibujar")
    t = TEMAS[tema]
    pasos = RAMPA_LLUVIA[:12] if tema == "claro" else list(reversed(RAMPA_LLUVIA[2:]))
    mapa = LinearSegmentedColormap.from_list("lluvia", pasos)

    n = len(serie)
    maximo = max((max(r.por_mes) for r in serie), default=0) or 1

    ancho_celda, alto_celda = 0.42, 0.21
    izq, der = 0.72, 1.05
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

    hueco = 0.045
    incompletos = []
    for fila, r in enumerate(serie):
        for mes in range(12):
            x, y = mes + hueco, fila + hueco
            w, h = 1 - 2 * hueco, 1 - 2 * hueco
            mm = r.por_mes[mes]
            color = t["vacio"] if mm < 0.05 else mapa(0.12 + 0.88 * mm / maximo)
            ax.add_patch(Rectangle((x, y), w, h, facecolor=color, edgecolor="none"))
            if mm >= 0.5:
                ax.text(
                    mes + 0.5, fila + 0.5, f"{mm:.0f}",
                    ha="center", va="center", fontsize=5.0,
                    color=_tinta_sobre(matplotlib.colors.to_hex(color), t),
                )
        etiqueta = str(r.anyo)
        if r.cobertura < cobertura_minima:
            etiqueta += " *"
            incompletos.append(r.anyo)
        ax.text(-0.25, fila + 0.5, etiqueta, ha="right", va="center",
                fontsize=5.6, color=t["tinta_2"])
        ax.text(12.25, fila + 0.5, f"{r.total:.0f}", ha="left", va="center",
                fontsize=5.6, color=t["tinta"] if r.total else t["apagado"])

    for mes, nombre in enumerate(MESES):
        ax.text(mes + 0.5, -0.35, nombre, ha="center", va="bottom",
                fontsize=5.6, color=t["apagado"])
    ax.text(12.25, -0.35, "Año", ha="left", va="bottom", fontsize=5.6, color=t["apagado"])

    titulo = fig.text(
        izq / ancho, 1 - 0.32 / alto, f"Lluvia mensual en {estacion}",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    _ajustar_a_lo_ancho(fig, titulo, ancho - izq - 0.2, minimo=7)
    fig.text(
        izq / ancho, 1 - 0.55 / alto,
        f"Precipitación acumulada, en milímetros  ·  {serie[0].anyo}–{serie[-1].anyo}",
        fontsize=7, color=t["tinta_2"], va="top", ha="left",
    )

    tira_izq, tira_ancho, tira_y = izq + 0.55, 1.30, 0.92
    leyenda = fig.add_axes(
        [tira_izq / ancho, 1 - tira_y / alto, tira_ancho / ancho, 0.08 / alto]
    )
    leyenda.imshow([[0.12 + 0.88 * i / 255 for i in range(256)]],
                   aspect="auto", cmap=mapa, vmin=0, vmax=1)
    leyenda.set_xticks([])
    leyenda.set_yticks([])
    for lado in leyenda.spines.values():
        lado.set_visible(False)
    fig.text((tira_izq - 0.07) / ancho, 1 - (tira_y - 0.005) / alto, "0 mm",
             fontsize=5.6, color=t["apagado"], va="top", ha="right")
    fig.text((tira_izq + tira_ancho + 0.07) / ancho, 1 - (tira_y - 0.005) / alto,
             f"{maximo:.0f} mm en el mes",
             fontsize=5.6, color=t["apagado"], va="top", ha="left")

    notas = ["Fuente: AEMET OpenData, valores climatológicos diarios."]
    if credito:
        notas.insert(0, credito)
    if incompletos:
        notas.append(
            f"* {len(incompletos)} año(s) con menos del {cobertura_minima:.0%} de "
            "días observados; su total se queda corto."
        )
    fig.text(izq / ancho, (0.14 + 0.08 * len(notas)) / alto, "\n".join(notas),
             fontsize=5.6, color=t["apagado"], va="top", ha="left", linespacing=1.6)

    destino.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(destino, facecolor=t["fondo"])
    plt.close(fig)
    return destino
