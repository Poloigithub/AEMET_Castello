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
