"""Compara dos rankings y dice qué fechas han entrado nuevas.

    python scripts/vigilar_top.py --antes viejo.csv --despues nuevo.csv

Escribe en la salida estándar un resumen legible y, si está definida la
variable GITHUB_OUTPUT, deja ahí `nuevas` (cuántas) y `texto` (el aviso ya
redactado) para que el workflow decida si envía algo.

Si el fichero «antes» no existe todavía, no hay nada con qué comparar: se
considera que no hay novedades, para no anunciar como récord toda la
clasificación la primera vez que esto se ejecuta.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aemet_noches.metricas import fecha_larga  # noqa: E402


def leer(ruta: Path) -> dict[date, tuple[int, float]]:
    """{fecha: (puesto, valor)} a partir del CSV del ranking."""
    if not ruta or not ruta.exists():
        return {}
    salida = {}
    with ruta.open(encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            valor = next(v for k, v in fila.items() if k not in ("puesto", "fecha"))
            salida[date.fromisoformat(fila["fecha"])] = (int(fila["puesto"]), float(valor))
    return salida


def nuevas_entradas(antes: dict, despues: dict) -> list[tuple[date, int, float]]:
    """Fechas presentes ahora que antes no estaban, de mejor a peor puesto."""
    nuevas = [(dia, p, v) for dia, (p, v) in despues.items() if dia not in antes]
    return sorted(nuevas, key=lambda x: (x[1], x[0]))


def redactar(nuevas: list[tuple[date, int, float]], variable: str) -> str:
    que = "noche" if variable == "tmin" else "día"
    cual = "mínima" if variable == "tmin" else "máxima"
    if len(nuevas) == 1:
        dia, puesto, valor = nuevas[0]
        grados = f"{valor:.1f}".replace(".", ",")
        cabeza = "🔴 Récord absoluto" if puesto == 1 else f"Nueva entrada (puesto {puesto})"
        return (
            f"{cabeza} en el top 10: {cual} de {grados} °C "
            f"el {fecha_larga(dia)}."
        )
    lineas = [f"Entran {len(nuevas)} {que}s nuevas en el top 10:"]
    for dia, puesto, valor in nuevas:
        grados = f"{valor:.1f}".replace(".", ",")
        lineas.append(f"· {grados} °C el {fecha_larga(dia)} (puesto {puesto})")
    return "\n".join(lineas)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="¿Ha entrado algo nuevo en el ranking?")
    p.add_argument("--antes", type=Path, help="CSV anterior (puede no existir)")
    p.add_argument("--despues", type=Path, required=True, help="CSV recién calculado")
    p.add_argument("--variable", default="tmin", choices=("tmin", "tmax"))
    args = p.parse_args(argv)

    antes = leer(args.antes)
    despues = leer(args.despues)
    if not antes:
        print("No hay ranking anterior con el que comparar: no se avisa de nada.")
        nuevas = []
    else:
        nuevas = nuevas_entradas(antes, despues)

    texto = redactar(nuevas, args.variable) if nuevas else ""
    print(texto or "Sin novedades en el top 10.")

    if salida := os.environ.get("GITHUB_OUTPUT"):
        with open(salida, "a", encoding="utf-8") as f:
            f.write(f"nuevas={len(nuevas)}\n")
            # Delimitador para texto de varias líneas, como pide Actions.
            f.write(f"texto<<FIN\n{texto}\nFIN\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
