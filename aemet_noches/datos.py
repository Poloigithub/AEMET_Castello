"""Lectura y normalización de la climatología diaria cacheada en disco."""

from __future__ import annotations

import json
import logging
import re
from datetime import date
from pathlib import Path

LOG = logging.getLogger(__name__)

# AEMET devuelve los nombres en mayúsculas ("CASTELLÓ - ALMASSORA").
CONECTORES = {
    "a", "al", "da", "das", "de", "del", "do", "dos", "e", "el", "en",
    "i", "la", "las", "les", "lo", "los", "o", "y",
}
# Topónimos cuya grafía oficial no sigue la regla general.
EXCEPCIONES = {"vila-real": "Vila-real"}


def _capitalizar(palabra: str) -> str:
    """Primera letra en mayúscula, también tras guion, barra, punto o apóstrofo."""
    return re.sub(
        r"(^|[-/'’.])(\w)",
        lambda m: m.group(1) + m.group(2).upper(),
        palabra.lower(),
    )


def formatear_nombre(bruto: str) -> str:
    """'CASTELLÓ - ALMASSORA' → 'Castelló - Almassora'.

    Los conectores van en minúscula salvo que abran el nombre, así que
    'CASTELLÓ DE LA PLANA' sale como 'Castelló de la Plana'. Para nombres
    raros siempre queda la opción de pasar `--nombre` a mano.
    """
    palabras = bruto.split()
    salida = []
    for i, palabra in enumerate(palabras):
        clave = palabra.lower()
        if clave in EXCEPCIONES:
            salida.append(EXCEPCIONES[clave])
        elif i > 0 and clave in CONECTORES:
            salida.append(clave)
        else:
            salida.append(_capitalizar(palabra))
    return " ".join(salida)


def _num(valor, ip_es_cero: bool = False) -> float | None:
    """AEMET usa coma decimal y marcas como 'Ip' para valores inapreciables.

    En precipitación, `Ip` («inapreciable») significa que llovió menos de lo
    que el pluviómetro sabe medir: es un día **con** dato y con 0,0 mm, no un
    día perdido. Tratarlo como hueco descartaría cientos de días de lluvia
    débil y falsearía las rachas secas. `Acum` es distinto: la cantidad se
    sumó a otro día, así que ese día no tiene medida propia.
    """
    if valor is None:
        return None
    texto = str(valor).strip().replace(",", ".")
    if not texto:
        return None
    if texto == "Ip":
        return 0.0 if ip_es_cero else None
    if texto in {"Acum", "Varias"}:
        return None
    try:
        return float(texto)
    except ValueError:
        return None


def cargar_dias(
    carpeta: Path, estacion: str | None = None, campo: str = "tmin"
) -> dict[date, float]:
    """Devuelve {fecha: valor} para el campo pedido ('tmin', 'tmax' o 'prec').

    Si un día aparece en varios tramos (solapes), gana el último leído; los
    valores de AEMET son idénticos, así que da igual cuál.
    """
    patron = f"{estacion}_*.json" if estacion else "*.json"
    ficheros = sorted(carpeta.glob(patron))
    if not ficheros:
        raise FileNotFoundError(
            f"No hay datos en {carpeta}. Ejecuta primero el comando `descargar`."
        )
    valores: dict[date, float] = {}
    for fichero in ficheros:
        registros = json.loads(fichero.read_text(encoding="utf-8"))
        for reg in registros:
            valor = _num(reg.get(campo), ip_es_cero=(campo == "prec"))
            if valor is None:
                continue
            try:
                dia = date.fromisoformat(reg["fecha"])
            except (KeyError, ValueError):
                LOG.warning("Fecha ilegible en %s: %r", fichero.name, reg.get("fecha"))
                continue
            valores[dia] = valor
    LOG.info("%d días con %s leídos de %d ficheros", len(valores), campo, len(ficheros))
    return valores


def nombre_estacion(carpeta: Path, estacion: str | None = None) -> str:
    """Nombre de la estación según AEMET, con las mayúsculas ya arregladas."""
    patron = f"{estacion}_*.json" if estacion else "*.json"
    for fichero in sorted(carpeta.glob(patron)):
        registros = json.loads(fichero.read_text(encoding="utf-8"))
        for reg in registros:
            if reg.get("nombre"):
                return formatear_nombre(str(reg["nombre"]).strip())
    return estacion or "estación desconocida"
