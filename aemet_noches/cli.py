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


def _referencia(texto: str) -> tuple[int, int]:
    """Acepta '1991-2020'."""
    try:
        ini, fin = (int(x) for x in texto.split("-"))
    except ValueError:
        raise argparse.ArgumentTypeError("Formato esperado: 1991-2020") from None
    if fin <= ini:
        raise argparse.ArgumentTypeError("El año final debe ser posterior al inicial")
    return ini, fin


def cmd_anomalias(args):
    valores = datos.cargar_dias(args.carpeta, args.estacion, campo=args.variable)
    serie = metricas.medias_por_mes(
        valores,
        desde_anyo=args.desde.year if args.desde else None,
        hasta_anyo=args.hasta.year if args.hasta else None,
    )
    normal = metricas.normales(serie, args.referencia)
    anomalia = metricas.anomalias(serie, normal)
    metricas.guardar_csv_anomalias(serie, anomalia, normal, args.csv)

    que = "máxima" if args.variable == "tmax" else "mínima"
    ini, fin = args.referencia
    print(f"Anomalía de la {que} media mensual respecto a {ini}-{fin}\n")
    print(f"{'Año':<6}{'Media':>8}{'Anomalía':>10}{'Récord':>9}")
    for r, a in zip(serie, anomalia):
        validas = [v for v in a if v is not None]
        media = f"{r.media_anual:.1f}" if r.media_anual is not None else "—"
        anom = f"{sum(validas) / len(validas):+.2f}" if len(validas) == 12 else "parcial"
        rec = f"{r.extremo:.1f}" if r.extremo is not None else "—"
        print(f"{r.anyo:<6}{media:>8}{anom:>10}{rec:>9}")
    print(f"\nCSV guardado en {args.csv}")

    nombre = args.nombre or datos.nombre_estacion(args.carpeta, args.estacion)
    plantilla = args.png.stem
    if "{tema}" not in plantilla and len(args.temas) > 1:
        plantilla += "_{tema}"  # varios temas necesitan nombres distintos
    for tema in args.temas:
        png = args.png.with_name(plantilla.replace("{tema}", tema) + args.png.suffix)
        ruta = grafico.dibujar_anomalias(
            serie, anomalia, png, estacion=nombre, variable=args.variable,
            referencia=args.referencia, tema=tema, credito=args.credito,
        )
        print(f"Mapa guardado en {ruta}")


def cmd_calcular(args):
    minimas = datos.cargar_dias(args.carpeta, args.estacion, campo=args.variable)
    resumenes = metricas.contar(
        minimas,
        umbral=args.umbral,
        estricto=args.estricto,
        desde_anyo=args.desde.year if args.desde else None,
        hasta_anyo=args.hasta.year if args.hasta else None,
    )
    metricas.guardar_csv(resumenes, args.csv)
    signo = ">" if args.estricto else "≥"
    que = "máxima" if args.variable == "tmax" else "mínima"
    print(f"Días con {que} {signo} {args.umbral:g} °C\n")
    print(f"{'Año':<6}{'Días':>7}{'Cobertura':>11}")
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
        variable=args.variable,
        tema=args.tema,
        credito=args.credito,
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

    def opcion_variable(sp):
        sp.add_argument(
            "--variable", choices=("tmin", "tmax"), default="tmin",
            help="temperatura mínima (por defecto) o máxima del día",
        )

    def opciones_umbral(sp):
        opcion_variable(sp)
        sp.add_argument("--umbral", type=float, default=20.0, help="grados (por defecto 20)")
        sp.add_argument(
            "--estricto", action="store_true",
            help="cuenta > umbral en vez de >= umbral",
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
    sp.add_argument("--credito", help="firma al pie, p. ej. 'Gráfico: fulano@servidor'")
    sp.set_defaults(func=cmd_mapa)

    sp = subs.add_parser(
        "anomalias",
        help="mapa de anomalías: cuánto se desvía cada mes de su normal climática",
    )
    comunes(sp)
    opcion_variable(sp)
    sp.add_argument(
        "--referencia", type=_referencia, default=(1991, 2020),
        help="periodo normal de referencia (por defecto 1991-2020)",
    )
    sp.add_argument("--csv", type=Path, default=CARPETA_SALIDA / "anomalias.csv")
    sp.add_argument(
        "--png", type=Path, default=CARPETA_SALIDA / "anomalias_{tema}.png",
        help="ruta del PNG; '{tema}' se sustituye por claro/oscuro",
    )
    sp.add_argument("--temas", nargs="+", choices=sorted(grafico.TEMAS), default=["claro"])
    sp.add_argument("--nombre")
    sp.add_argument("--credito")
    sp.set_defaults(func=cmd_anomalias)

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
    sp.add_argument("--credito")
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
