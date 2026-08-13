"""Genera docs/ejemplo.png con datos SINTÉTICOS.

Sirve para ver el formato del mapa de calor sin gastar peticiones de la API y
para poder probar el dibujo sin red. Los números NO son observaciones reales:
son una senoidal estacional con tendencia y ruido, más algunos huecos a
propósito para ver cómo se marcan los meses sin datos.

    python docs/generar_ejemplo.py
"""

from __future__ import annotations

import math
import random
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aemet_noches import grafico, metricas  # noqa: E402

INI, FIN = date(1990, 1, 1), date(2025, 8, 31)
HUECOS = {1996: range(1, 13), 2004: range(3, 13)}  # año: meses sin observaciones


def serie_sintetica() -> dict[date, float]:
    random.seed(7)
    minimas: dict[date, float] = {}
    dia = INI
    while dia <= FIN:
        if dia.month in HUECOS.get(dia.year, ()):
            dia += timedelta(days=1)
            continue
        estacional = 12.5 + 7.5 * math.sin(2 * math.pi * (dia.timetuple().tm_yday - 110) / 365)
        tendencia = 0.045 * (dia.year - INI.year)
        if random.random() > 0.01:  # 1 % de días sin dato, como en la vida real
            minimas[dia] = estacional + tendencia + random.gauss(0, 2.2)
        dia += timedelta(days=1)
    return minimas


if __name__ == "__main__":
    resumenes = metricas.contar(serie_sintetica())
    destino = grafico.dibujar(
        resumenes,
        Path(__file__).resolve().parent / "ejemplo.png",
        estacion="ESTACIÓN DE EJEMPLO — datos sintéticos, no son observaciones",
        tema="claro",
    )
    print(f"Generado {destino}")
