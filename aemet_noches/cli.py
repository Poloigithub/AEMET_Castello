"""Interfaz de línea de comandos."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date
from pathlib import Path

from . import api, datos, grafico, metricas

ESTACION_POR_DEFECTO = "8500A"  # Castelló de la Plana / Almassora
CARPETA_DATOS = Path("datos/crudos")
CARPETA_SALIDA = Path("salida")


def _fecha(texto: str) -> date:
    """Acepta 1990 o 1990-05-01."""
    if len(texto) == 4 and texto.isdigit():
        return date(int(texto), 1, 1)
    return date.fromisoformat(texto)


def _api_key(args) -> str:
    clave = args.api_key or os.environ.get("AEMET_API_KEY")
    fichero = Path(".aemet_api_key")
    if not clave and fichero.exists():
        clave = fichero.read_text(encoding="utf-8").strip()
    if not clave:
        sys.exit(
            "Falta la clave de AEMET. Pásala con --api-key, ponla en la variable\n"
            "de entorno AEMET_API_KEY o guárdala en el fichero .aemet_api_key.\n"
            "Se pide gratis en https://opendata.aemet.es/centrodedescargas/altaUsuario"
        )
    return clave


def cmd_estaciones(args):
    cliente = api.ClienteAemet(_api_key(args))
    filtro = (args.provincia or "").upper()
    for est in cliente.inventario_estaciones():
        if filtro and filtro not in est.get("provincia", "").upper():
            continue
        print(
            f"{est['indicativo']:<8} {est['nombre']:<40} "
            f"{est.get('provincia',''):<18} {est.get('altitud','')} m"
        )


def cmd_descargar(args):
    cliente = api.ClienteAemet(_api_key(args), espera=args.espera)
    nuevos = api.descargar_serie(
        cliente,
        args.estacion,
        args.desde,
        args.hasta,
        args.carpeta,
        meses_por_lote=args.meses_por_lote,
        forzar=args.forzar,
    )
    print(f"Tramos nuevos descargados: {nuevos}. Caché en {args.carpeta}")


def cmd_calcular(args):
    minimas = datos.cargar_dias(args.carpeta, args.estacion)
    resumenes = metricas.contar(
        minimas,
        umbral=args.umbral,
        estricto=args.estricto,
        desde_anyo=args.desde.year if args.desde else None,
        hasta_anyo=args.hasta.year if args.hasta else None,
    )
    metricas.guardar_csv(resumenes, args.csv)
    signo = ">" if args.estricto else "≥"
    print(f"Noches con mínima {signo} {args.umbral:g} °C\n")
    print(f"{'Año':<6}{'Noches':>7}{'Cobertura':>11}")
    for r in resumenes:
        aviso = "  (año incompleto)" if r.cobertura < 0.9 else ""
        print(f"{r.anyo:<6}{r.total:>7}{r.cobertura:>10.0%}{aviso}")
    print(f"\nCSV guardado en {args.csv}")
    return resumenes


def cmd_mapa(args):
    resumenes = metricas.leer_csv(args.csv)
    nombre = args.nombre or datos.nombre_estacion(args.carpeta, args.estacion)
    ruta = grafico.dibujar(
        resumenes,
        args.png,
        estacion=nombre,
        umbral=args.umbral,
        estricto=args.estricto,
        tema=args.tema,
    )
    print(f"Mapa de calor guardado en {ruta}")


def cmd_todo(args):
    cmd_descargar(args)
    cmd_calcular(args)
    cmd_mapa(args)


def construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="aemet_noches",
        description="Noches tropicales (mínima ≥ 20 °C) a partir de AEMET OpenData.",
    )
    p.add_argument("--api-key", help="clave de AEMET OpenData")
    p.add_argument("-v", "--verboso", action="store_true")
    subs = p.add_subparsers(dest="comando", required=True)

    def comunes(sp, con_fechas=True):
        sp.add_argument("--estacion", default=ESTACION_POR_DEFECTO)
        sp.add_argument("--carpeta", type=Path, default=CARPETA_DATOS)
        if con_fechas:
            sp.add_argument("--desde", type=_fecha, default=date(1990, 1, 1))
            sp.add_argument("--hasta", type=_fecha, default=date.today())

    def opciones_umbral(sp):
        sp.add_argument("--umbral", type=float, default=20.0, help="grados (por defecto 20)")
        sp.add_argument(
            "--estricto", action="store_true",
            help="cuenta mínima > umbral en vez de >= umbral",
        )

    sp = subs.add_parser("estaciones", help="lista estaciones de AEMET")
    sp.add_argument("--provincia", default="CASTELLON")
    sp.set_defaults(func=cmd_estaciones)

    sp = subs.add_parser("descargar", help="descarga y cachea la climatología diaria")
    comunes(sp)
    sp.add_argument("--meses-por-lote", type=int, default=6)
    sp.add_argument("--espera", type=float, default=1.5, help="segundos entre peticiones")
    sp.add_argument("--forzar", action="store_true", help="reescribe tramos ya cacheados")
    sp.set_defaults(func=cmd_descargar)

    sp = subs.add_parser("calcular", help="cuenta noches tropicales por año y mes")
    comunes(sp)
    opciones_umbral(sp)
    sp.add_argument("--csv", type=Path, default=CARPETA_SALIDA / "noches_tropicales.csv")
    sp.set_defaults(func=cmd_calcular)

    sp = subs.add_parser("mapa", help="dibuja el mapa de calor")
    comunes(sp, con_fechas=False)
    opciones_umbral(sp)
    sp.add_argument("--csv", type=Path, default=CARPETA_SALIDA / "noches_tropicales.csv")
    sp.add_argument("--png", type=Path, default=CARPETA_SALIDA / "mapa_calor.png")
    sp.add_argument("--tema", choices=sorted(grafico.TEMAS), default="claro")
    sp.add_argument("--nombre", help="nombre de la estación para el título")
    sp.set_defaults(func=cmd_mapa)

    sp = subs.add_parser("todo", help="descargar + calcular + mapa de una tacada")
    comunes(sp)
    opciones_umbral(sp)
    sp.add_argument("--meses-por-lote", type=int, default=6)
    sp.add_argument("--espera", type=float, default=1.5)
    sp.add_argument("--forzar", action="store_true")
    sp.add_argument("--csv", type=Path, default=CARPETA_SALIDA / "noches_tropicales.csv")
    sp.add_argument("--png", type=Path, default=CARPETA_SALIDA / "mapa_calor.png")
    sp.add_argument("--tema", choices=sorted(grafico.TEMAS), default="claro")
    sp.add_argument("--nombre")
    sp.set_defaults(func=cmd_todo)

    return p


def main(argv=None):
    args = construir_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verboso else logging.INFO,
        format="%(message)s",
    )
    try:
        args.func(args)
    except (FileNotFoundError, api.ErrorAemet, ValueError) as exc:
        sys.exit(str(exc))
    except KeyboardInterrupt:
        sys.exit("\nInterrumpido. Lo descargado se queda cacheado.")


if __name__ == "__main__":
    main()
