"""Prueba qué rangos acepta el endpoint de climatologías diarias de AEMET.

Existe para dejar de suponer. El fallo que motiva esto es un 400 con el
mensaje "La fecha final no puede ser mayor que la fecha inicial" sobre un
rango en el que la fecha final es obviamente posterior a la inicial, así que
el mensaje no dice nada útil y hay que averiguar el patrón desde fuera.

Cada prueba es una sola petición, sin reintentos ni troceado, con una espera
generosa entre ellas para que un límite de peticiones no contamine el
resultado. Se imprime una tabla de qué pasa con cada rango.

Uso:
    python scripts/probar_rangos.py --estacion 8500A
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

# Se invoca como `python scripts/probar_rangos.py`, así que sys.path apunta a
# scripts/ y no a la raíz del repo, donde vive el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aemet_noches.api import BASE, ClienteAemet  # noqa: E402


def probar(cliente: ClienteAemet, estacion: str, ini: date, fin: date):
    """Una petición cruda. Devuelve (ok, descripción de lo que respondió)."""
    ruta = (
        "/api/valores/climatologicos/diarios/datos"
        f"/fechaini/{ini:%Y-%m-%d}T00:00:00UTC"
        f"/fechafin/{fin:%Y-%m-%d}T23:59:59UTC"
        f"/estacion/{estacion}"
    )
    try:
        sobre = cliente._json(cliente._get(BASE + ruta, con_clave=True))
    except Exception as exc:  # noqa: BLE001 — aquí interesa cualquier fallo
        return False, f"excepción: {exc}"
    estado = sobre.get("estado")
    if estado == 200 and "datos" in sobre:
        datos = cliente._json(cliente._get(sobre["datos"], con_clave=False))
        return True, f"{len(datos)} días"
    return False, f"{estado}: {sobre.get('descripcion', '')}"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--estacion", default="8500A")
    p.add_argument("--espera", type=float, default=10.0,
                   help="segundos entre pruebas, para descartar el límite de peticiones")
    args = p.parse_args()

    clave = os.environ.get("AEMET_API_KEY")
    if not clave:
        raise SystemExit("Falta AEMET_API_KEY")
    cliente = ClienteAemet(api_key=clave, reintentos=1)

    hoy = date.today()
    ayer = hoy - timedelta(days=1)

    casos: list[tuple[str, date, date]] = [
        # El caso que destapó todo: este mismo día se sirvió bien a las 11:57
        # y se rechazó a las 12:15. Si tras un rato de calma vuelve a ir, lo
        # que había era una penalización por pedir demasiado.
        ("el que va y viene", hoy - timedelta(days=30), hoy - timedelta(days=30)),
        # Longitud creciente desde un mismo arranque reciente: si hay un tope
        # de días por petición, aquí se ve dónde está.
        ("reciente, 1 día", ayer, ayer),
        ("reciente, 8 días", ayer - timedelta(days=7), ayer),
        ("reciente, 16 días", ayer - timedelta(days=15), ayer),
        ("reciente, 32 días", ayer - timedelta(days=31), ayer),
        ("reciente, 64 días", ayer - timedelta(days=63), ayer),
        # El rango exacto que falla en la vigilancia diaria.
        ("el que falla", date(hoy.year, 7, 1), ayer),
        # Controles en el pasado: estos tramos ya se descargaron bien en su
        # día. Si ahora fallan, lo que ha cambiado es la API, no las fechas.
        ("pasado, 6 meses", date(2025, 1, 1), date(2025, 6, 30)),
        ("pasado, 64 días", date(2025, 7, 1), date(2025, 9, 2)),
        ("pasado, 1 día", date(2025, 7, 1), date(2025, 7, 1)),
    ]

    print(f"{'prueba':<20} {'rango':<26} resultado")
    print("-" * 78)
    for nombre, ini, fin in casos:
        ok, detalle = probar(cliente, args.estacion, ini, fin)
        marca = "OK  " if ok else "FALLA"
        print(f"{nombre:<20} {ini} → {fin}   {marca} {detalle}", flush=True)
        time.sleep(args.espera)


if __name__ == "__main__":
    main()
