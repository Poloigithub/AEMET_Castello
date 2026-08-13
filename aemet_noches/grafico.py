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
    que = "máxima" if variable == "tmax" else "mínima"
    umbral_txt = f"{umbral:g}".replace(".", ",")
    disponible = ancho - izq - 0.2
    titulo = fig.text(
        izq / ancho, 1 - 0.32 / alto,
        f"{nombre_del_fenomeno(umbral, estricto, variable)} en {estacion}",
        fontsize=11, color=t["tinta"], va="top", ha="left", weight="bold",
    )
    subtitulo = fig.text(
        izq / ancho, 1 - 0.55 / alto,
        f"Días con temperatura {que} {signo} {umbral_txt} °C, por mes y año  ·  "
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
