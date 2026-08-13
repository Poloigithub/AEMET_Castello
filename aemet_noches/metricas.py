"""Recuento de noches tropicales por año y mes.

Definición: una *noche tropical* es un día cuya temperatura mínima no baja de
20 °C (criterio OMM/AEMET, comparación `>=`). Con `estricto=True` se usa `>`,
que es lo que literalmente significa "superior a 20". La diferencia son los
días con mínima exactamente 20,0.
"""

from __future__ import annotations

import calendar
import csv
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MESES = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]


@dataclass
class ResumenAnual:
    anyo: int
    por_mes: list[int] = field(default_factory=lambda: [0] * 12)
    dias_con_dato_mes: list[int] = field(default_factory=lambda: [0] * 12)

    @property
    def total(self) -> int:
        return sum(self.por_mes)

    @property
    def dias_con_dato(self) -> int:
        return sum(self.dias_con_dato_mes)

    @property
    def dias_del_anyo(self) -> int:
        return 366 if calendar.isleap(self.anyo) else 365

    @property
    def cobertura(self) -> float:
        return self.dias_con_dato / self.dias_del_anyo

    def dias_del_mes(self, mes: int) -> int:
        return calendar.monthrange(self.anyo, mes)[1]


def contar(
    minimas: dict[date, float],
    umbral: float = 20.0,
    estricto: bool = False,
    desde_anyo: int | None = None,
    hasta_anyo: int | None = None,
    recortar: bool = True,
) -> list[ResumenAnual]:
    """Agrupa las mínimas diarias en recuentos por año y mes.

    Con `recortar` se descartan los años sin ninguna observación al principio
    y al final de la serie (los huecos interiores se conservan: son parte de
    la historia de la estación y en el mapa salen rayados).
    """
    if not minimas:
        return []
    anyos = {d.year for d in minimas}
    ini = desde_anyo if desde_anyo is not None else min(anyos)
    fin = hasta_anyo if hasta_anyo is not None else max(anyos)
    resumenes = {a: ResumenAnual(a) for a in range(ini, fin + 1)}

    for dia, tmin in minimas.items():
        resumen = resumenes.get(dia.year)
        if resumen is None:
            continue
        resumen.dias_con_dato_mes[dia.month - 1] += 1
        if (tmin > umbral) if estricto else (tmin >= umbral):
            resumen.por_mes[dia.month - 1] += 1

    serie = [resumenes[a] for a in sorted(resumenes)]
    if recortar:
        while serie and serie[0].dias_con_dato == 0:
            serie.pop(0)
        while serie and serie[-1].dias_con_dato == 0:
            serie.pop()
    return serie


@dataclass
class ResumenTermico:
    """Medias mensuales de una temperatura (máxima o mínima) en un año."""

    anyo: int
    medias: list[float | None] = field(default_factory=lambda: [None] * 12)
    dias_con_dato_mes: list[int] = field(default_factory=lambda: [0] * 12)
    extremo: float | None = None  # el valor más alto observado en el año

    def dias_del_mes(self, mes: int) -> int:
        return calendar.monthrange(self.anyo, mes)[1]

    def cobertura_mes(self, mes: int) -> float:
        return self.dias_con_dato_mes[mes - 1] / self.dias_del_mes(mes)

    @property
    def media_anual(self) -> float | None:
        validas = [m for m in self.medias if m is not None]
        return sum(validas) / len(validas) if len(validas) == 12 else None


def medias_por_mes(
    valores: dict[date, float],
    desde_anyo: int | None = None,
    hasta_anyo: int | None = None,
    cobertura_minima: float = 0.9,
) -> list[ResumenTermico]:
    """Media mensual de la temperatura, mes a mes y año a año.

    Un mes al que le falten más de `1 - cobertura_minima` de los días se deja
    en None: una media sobre medio mes no es comparable con la de un mes
    entero, y en un gráfico de anomalías eso se convierte en señal falsa.
    """
    if not valores:
        return []
    anyos = {d.year for d in valores}
    ini = desde_anyo if desde_anyo is not None else min(anyos)
    fin = hasta_anyo if hasta_anyo is not None else max(anyos)

    acumulado: dict[tuple[int, int], list[float]] = {}
    for dia, valor in valores.items():
        if ini <= dia.year <= fin:
            acumulado.setdefault((dia.year, dia.month), []).append(valor)

    serie = []
    for anyo in range(ini, fin + 1):
        r = ResumenTermico(anyo)
        for mes in range(1, 13):
            datos_mes = acumulado.get((anyo, mes), [])
            r.dias_con_dato_mes[mes - 1] = len(datos_mes)
            if datos_mes and r.cobertura_mes(mes) >= cobertura_minima:
                r.medias[mes - 1] = sum(datos_mes) / len(datos_mes)
        todos = [v for mes in range(1, 13) for v in acumulado.get((anyo, mes), [])]
        r.extremo = max(todos) if todos else None
        serie.append(r)

    while serie and not any(serie[0].dias_con_dato_mes):
        serie.pop(0)
    while serie and not any(serie[-1].dias_con_dato_mes):
        serie.pop()
    return serie


def normales(
    serie: list[ResumenTermico],
    referencia: tuple[int, int] = (1991, 2020),
    minimo_anyos: int = 15,
) -> list[float]:
    """Media de cada mes en el periodo de referencia (la 'normal climática')."""
    ini, fin = referencia
    salida = []
    for mes in range(12):
        muestras = [
            r.medias[mes] for r in serie
            if ini <= r.anyo <= fin and r.medias[mes] is not None
        ]
        if len(muestras) < minimo_anyos:
            raise ValueError(
                f"El periodo de referencia {ini}-{fin} solo tiene {len(muestras)} "
                f"años válidos para el mes {mes + 1} (hacen falta {minimo_anyos}). "
                "Usa --referencia con un periodo que cubra tus datos."
            )
        salida.append(sum(muestras) / len(muestras))
    return salida


def anomalias(serie: list[ResumenTermico], normal: list[float]) -> list[list[float | None]]:
    """Desviación de cada mes respecto a su normal, en grados."""
    return [
        [None if m is None else m - normal[i] for i, m in enumerate(r.medias)]
        for r in serie
    ]


def guardar_csv_anomalias(
    serie: list[ResumenTermico],
    anomalia: list[list[float | None]],
    normal: list[float],
    destino: Path,
) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    coma = lambda v: "" if v is None else f"{v:.2f}"  # noqa: E731
    with destino.open("w", newline="", encoding="utf-8") as f:
        e = csv.writer(f)
        e.writerow(
            ["anyo"]
            + [f"media_{m.lower()}" for m in MESES]
            + [f"anomalia_{m.lower()}" for m in MESES]
            + ["media_anual", "extremo_anual"]
            + [f"dias_con_dato_{m.lower()}" for m in MESES]
        )
        for r, a in zip(serie, anomalia):
            e.writerow(
                [r.anyo]
                + [coma(v) for v in r.medias]
                + [coma(v) for v in a]
                + [coma(r.media_anual), coma(r.extremo)]
                + r.dias_con_dato_mes
            )
        e.writerow(["normal"] + [coma(v) for v in normal] + [""] * 12 + ["", ""] + [""] * 12)


def guardar_csv(resumenes: list[ResumenAnual], destino: Path) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.writer(f)
        escritor.writerow(
            ["anyo", "total"]
            + [m.lower() for m in MESES]
            + ["dias_con_dato", "dias_del_anyo", "cobertura"]
            + [f"dias_con_dato_{m.lower()}" for m in MESES]
        )
        for r in resumenes:
            escritor.writerow(
                [r.anyo, r.total]
                + r.por_mes
                + [r.dias_con_dato, r.dias_del_anyo, f"{r.cobertura:.3f}"]
                + r.dias_con_dato_mes
            )


def leer_csv(origen: Path) -> list[ResumenAnual]:
    resumenes = []
    with origen.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            r = ResumenAnual(int(fila["anyo"]))
            r.por_mes = [int(fila[m.lower()]) for m in MESES]
            r.dias_con_dato_mes = [int(fila[f"dias_con_dato_{m.lower()}"]) for m in MESES]
            resumenes.append(r)
    return resumenes
