"""Lectura y normalización de la climatología diaria cacheada en disco."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

LOG = logging.getLogger(__name__)


def _num(valor) -> float | None:
    """AEMET usa coma decimal y marcas como 'Ip' para valores inapreciables."""
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    if not texto or texto in {"Ip", "Acum", "Varias"}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def cargar_dias(carpeta: Path, estacion: str | None = None) -> dict[date, float]:
    """Devuelve {fecha: temperatura mínima} con todos los tramos cacheados.

    Si un día aparece en varios tramos (solapes), gana el último leído; los
    valores de AEMET son idénticos, así que da igual cuál.
    """
    patron = f"{estacion}_*.json" if estacion else "*.json"
    ficheros = sorted(carpeta.glob(patron))
    if not ficheros:
        raise FileNotFoundError(
            f"No hay datos en {carpeta}. Ejecuta primero el comando `descargar`."
        )
    minimas: dict[date, float] = {}
    for fichero in ficheros:
        registros = json.loads(fichero.read_text(encoding="utf-8"))
        for reg in registros:
            tmin = _num(reg.get("tmin"))
            if tmin is None:
                continue
            try:
                dia = date.fromisoformat(reg["fecha"])
            except (KeyError, ValueError):
                LOG.warning("Fecha ilegible en %s: %r", fichero.name, reg.get("fecha"))
                continue
            minimas[dia] = tmin
    LOG.info("%d días con mínima leídos de %d ficheros", len(minimas), len(ficheros))
    return minimas


def nombre_estacion(carpeta: Path, estacion: str | None = None) -> str:
    """Nombre legible de la estación, tal y como lo devuelve AEMET."""
    patron = f"{estacion}_*.json" if estacion else "*.json"
    for fichero in sorted(carpeta.glob(patron)):
        registros = json.loads(fichero.read_text(encoding="utf-8"))
        for reg in registros:
            if reg.get("nombre"):
                return str(reg["nombre"]).strip()
    return estacion or "estación desconocida"
