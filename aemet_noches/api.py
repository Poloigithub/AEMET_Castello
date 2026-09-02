"""Cliente mínimo de AEMET OpenData.

La API funciona en dos pasos: se pide un recurso con la api_key y AEMET
responde con un JSON que contiene una URL temporal (`datos`) de la que hay
que descargar el contenido real.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://opendata.aemet.es/opendata"
LOG = logging.getLogger(__name__)


class ErrorAemet(RuntimeError):
    pass


class SinDatos(Exception):
    """AEMET responde 404 cuando no hay datos para ese rango/estación."""


@dataclass
class ClienteAemet:
    api_key: str
    espera: float = 1.5  # segundos entre peticiones, para no chocar con el límite
    reintentos: int = 4
    timeout: int = 60

    def _get(self, url: str, con_clave: bool) -> requests.Response:
        cabeceras = {"api_key": self.api_key} if con_clave else {}
        espera = self.espera
        ultimo_error: Exception | None = None
        for intento in range(1, self.reintentos + 1):
            try:
                r = requests.get(url, headers=cabeceras, timeout=self.timeout)
            except requests.RequestException as exc:  # red inestable
                ultimo_error = exc
                LOG.warning("Fallo de red (%s), reintento %d", exc, intento)
                time.sleep(espera)
                espera *= 2
                continue
            if r.status_code == 429:
                LOG.warning("Límite de peticiones alcanzado, esperando %.0fs", espera * 4)
                time.sleep(espera * 4)
                espera *= 2
                continue
            return r
        raise ErrorAemet(f"No se pudo contactar con AEMET: {ultimo_error}")

    @staticmethod
    def _json(r: requests.Response):
        # AEMET sirve algunos ficheros en ISO-8859-15 sin declararlo bien.
        if not r.encoding:
            r.encoding = "ISO-8859-15"
        try:
            return json.loads(r.text)
        except json.JSONDecodeError as exc:
            raise ErrorAemet(f"Respuesta no JSON de AEMET: {r.text[:200]!r}") from exc

    def recurso(self, ruta: str):
        """Pide `ruta` y devuelve ya el contenido del enlace `datos`."""
        sobre = self._json(self._get(BASE + ruta, con_clave=True))
        estado = sobre.get("estado")
        if estado == 404:
            raise SinDatos(sobre.get("descripcion", "sin datos"))
        if estado != 200 or "datos" not in sobre:
            raise ErrorAemet(f"AEMET respondió {estado}: {sobre.get('descripcion')}")
        time.sleep(self.espera)
        return self._json(self._get(sobre["datos"], con_clave=False))

    # -- endpoints concretos -------------------------------------------------

    def inventario_estaciones(self):
        return self.recurso("/api/valores/climatologicos/inventarioestaciones/todasestaciones")

    def climatologia_diaria(self, estacion: str, ini: date, fin: date):
        ruta = (
            "/api/valores/climatologicos/diarios/datos"
            f"/fechaini/{ini:%Y-%m-%d}T00:00:00UTC"
            f"/fechafin/{fin:%Y-%m-%d}T23:59:59UTC"
            f"/estacion/{estacion}"
        )
        return self.recurso(ruta)


def tramos(ini: date, fin: date, meses: int = 6):
    """Parte el rango en tramos: AEMET limita el intervalo por petición."""
    actual = ini
    while actual <= fin:
        # avanza `meses` meses menos un día
        y, m = actual.year, actual.month + meses
        y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
        try:
            siguiente = date(y, m, actual.day)
        except ValueError:  # p. ej. 31 de un mes de 30
            siguiente = date(y, m, 1)
        tope = min(siguiente - timedelta(days=1), fin)
        yield actual, tope
        actual = tope + timedelta(days=1)


def pedir_tramo(
    cliente: ClienteAemet,
    estacion: str,
    desde: date,
    hasta: date,
    minimo_dias: int = 8,
):
    """Pide un tramo y, si AEMET lo rechaza, lo parte por la mitad.

    La API devuelve 400 con mensajes desconcertantes ("la fecha final no
    puede ser mayor que la inicial") ante rangos que aceptó el día anterior.
    No hay forma de saber desde fuera si es un límite no documentado o un
    fallo pasajero, así que se prueba con la mitad antes de rendirse. Por
    debajo de `minimo_dias` se deja de insistir: ahí el problema es otro y
    conviene que se vea.
    """
    try:
        return cliente.climatologia_diaria(estacion, desde, hasta)
    except SinDatos:
        return []
    except ErrorAemet:
        if (hasta - desde).days <= minimo_dias:
            raise
        medio = desde + (hasta - desde) / 2
        LOG.warning("AEMET rechazó %s → %s; se parte en dos", desde, hasta)
        izquierda = pedir_tramo(cliente, estacion, desde, medio, minimo_dias)
        derecha = pedir_tramo(
            cliente, estacion, medio + timedelta(days=1), hasta, minimo_dias
        )
        return izquierda + derecha


def descargar_serie(
    cliente: ClienteAemet,
    estacion: str,
    ini: date,
    fin: date,
    carpeta: Path,
    meses_por_lote: int = 6,
    forzar: bool = False,
    hoy: date | None = None,
) -> int:
    """Descarga la climatología diaria por tramos y la cachea en disco.

    Devuelve el número de tramos descargados (los ya cacheados no cuentan).

    El tramo que llega hasta hoy se vuelve a pedir siempre: está incompleto
    por definición, y darlo por bueno dejaría la serie congelada en el día en
    que se cacheó por primera vez.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    hoy = hoy or date.today()
    nuevos = 0
    for desde, hasta in tramos(ini, fin, meses_por_lote):
        destino = carpeta / f"{estacion}_{desde:%Y%m%d}_{hasta:%Y%m%d}.json"
        if destino.exists() and not forzar and hasta < hoy:
            LOG.debug("Ya estaba: %s", destino.name)
            continue
        # A AEMET no se le pide nunca hasta hoy: la petición lleva la hora
        # 23:59 y eso es futuro hasta la medianoche, lo que la API rechaza con
        # un 400 desconcertante ("la fecha final no puede ser mayor que la
        # inicial"). Como además publica con días de retraso, pedir hasta ayer
        # no pierde ni un dato.
        pedir_hasta = min(hasta, hoy - timedelta(days=1))
        if desde > pedir_hasta:
            LOG.debug("Tramo aún sin días publicables: %s", destino.name)
            continue
        LOG.info("Descargando %s → %s", desde, pedir_hasta)
        datos = pedir_tramo(cliente, estacion, desde, pedir_hasta)
        # El tramo en curso cambia de nombre cada día (acaba en «hoy»), así que
        # se barren las versiones anteriores del mismo tramo antes de escribir:
        # si no, la caché acumularía un fichero por día con los mismos datos.
        for viejo in carpeta.glob(f"{estacion}_{desde:%Y%m%d}_*.json"):
            if viejo != destino:
                viejo.unlink()
        destino.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        nuevos += 1
        time.sleep(cliente.espera)
    return nuevos
