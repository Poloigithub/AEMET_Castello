"""Dice qué clave de AEMET hay puesta, sin enseñarla.

Las claves de AEMET son JWT, y su carga útil lleva las fechas de emisión y
caducidad. Eso basta para distinguir una clave de otra en un log público sin
revelar nada: las fechas no son secretas y el token nunca se imprime.

Existe porque hace falta saber si el secreto AEMET_API_KEY tiene la clave
vieja o la nueva cuando algo empieza a fallar justo después de cambiarla.
"""

from __future__ import annotations

import base64
import datetime as dt
import json
import os
import sys


def fecha(marca) -> str:
    try:
        return f"{dt.datetime.fromtimestamp(int(marca), dt.timezone.utc):%Y-%m-%d %H:%M UTC}"
    except (TypeError, ValueError, OSError):
        return f"(ilegible: {marca!r})"


def main() -> int:
    clave = os.environ.get("AEMET_API_KEY")
    if not clave:
        print("No hay AEMET_API_KEY en el entorno.")
        return 1

    partes = clave.split(".")
    if len(partes) != 3:
        print("La clave no tiene forma de JWT; no se le pueden leer las fechas.")
        return 1

    relleno = partes[1] + "=" * (-len(partes[1]) % 4)
    try:
        carga = json.loads(base64.urlsafe_b64decode(relleno))
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"No se pudo leer la carga del JWT: {exc}")
        return 1

    # Solo estos dos campos. El resto de la carga lleva el correo del titular
    # y el identificador de la clave, y este log es público.
    print(f"Emitida:  {fecha(carga.get('iat'))}")
    print(f"Caduca:   {fecha(carga.get('exp'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
