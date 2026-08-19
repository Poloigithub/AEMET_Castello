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


def cmd_lineas(args):
    valores = datos.cargar_dias(args.carpeta, args.estacion, campo=args.variable)
    desde = args.desde.year if args.desde else None
    hasta = args.hasta.year if args.hasta else None
    diaria = args.resolucion == "diaria"

    if diaria:
        series = metricas.series_diarias(valores, desde, hasta)
        anyos = sorted(series)
    else:
        serie = metricas.medias_por_mes(valores, desde, hasta)
        anyos = [r.anyo for r in serie]
    if not anyos:
        sys.exit("No hay datos para ese rango.")

    normal = None
    try:
        normal = (
            metricas.normal_diaria(series, args.referencia) if diaria
            else metricas.normales(serie, args.referencia)
        )
    except ValueError as exc:  # sin referencia suficiente se dibuja igual, sin línea
        print(f"Aviso: no se dibuja la normal. {exc}")

    destacar = args.destacar or anyos[-2:]
    faltan = [a for a in destacar if a not in anyos]
    if faltan:
        sys.exit(f"No hay datos de {', '.join(str(a) for a in faltan)} en la serie.")

    if diaria and args.suavizado > 1:
        series = {a: metricas.suavizar(v, args.suavizado) for a, v in series.items()}
        if normal:
            normal = metricas.suavizar(normal, args.suavizado)

    nombre = args.nombre or datos.nombre_estacion(args.carpeta, args.estacion)
    plantilla = args.png.stem
    if "{tema}" not in plantilla and len(args.temas) > 1:
        plantilla += "_{tema}"
    for tema in args.temas:
        png = args.png.with_name(plantilla.replace("{tema}", tema) + args.png.suffix)
        comunes = dict(
            estacion=nombre, destacar=destacar, variable=args.variable,
            normal=normal, referencia=args.referencia, tema=tema, credito=args.credito,
        )
        if diaria:
            ruta = grafico.dibujar_lineas_diarias(
                series, png, suavizado=args.suavizado, **comunes
            )
        else:
            ruta = grafico.dibujar_lineas(serie, png, **comunes)
        print(f"Gráfico guardado en {ruta}")


def cmd_lluvia(args):
    lluvia = datos.cargar_dias(args.carpeta, args.estacion, campo="prec")
    serie = metricas.resumir_lluvia(
        lluvia,
        umbral_lluvia=args.umbral_lluvia,
        desde_anyo=args.desde.year if args.desde else None,
        hasta_anyo=args.hasta.year if args.hasta else None,
    )
    if not serie:
        sys.exit("No hay datos de precipitación para ese rango.")
    metricas.guardar_csv_lluvia(serie, args.csv)

    print(f"Lluvia en {args.estacion}  (día de lluvia = {args.umbral_lluvia:g} mm o más)\n")
    print(f"{'Año':<6}{'Total':>8}{'Días':>6}{'Racha seca':>12}{'Top 5':>8}")
    for r in serie:
        aviso = " *" if r.cobertura < 0.9 else ""
        torr = f"{r.torrencialidad:.0%}" if r.torrencialidad is not None else "—"
        print(f"{r.anyo:<6}{r.total:>7.0f}{'mm':>1}{r.dias_de_lluvia:>6}"
              f"{r.racha_seca:>9} d{torr:>8}{aviso}")
    print("\n* años con menos del 90 % de días observados.")
    print(f"\nCSV guardado en {args.csv}")

    nombre = args.nombre or datos.nombre_estacion(args.carpeta, args.estacion)
    plantilla = args.png.stem
    if "{tema}" not in plantilla and len(args.temas) > 1:
        plantilla += "_{tema}"
    for tema in args.temas:
        png = args.png.with_name(plantilla.replace("{tema}", tema) + args.png.suffix)
        ruta = grafico.dibujar_lluvia(
            serie, png, estacion=nombre, tema=tema, credito=args.credito,
        )
        print(f"Mapa guardado en {ruta}")
    if args.png_rachas:
        plantilla = args.png_rachas.stem
        if "{tema}" not in plantilla and len(args.temas) > 1:
            plantilla += "_{tema}"
        for tema in args.temas:
            png = args.png_rachas.with_name(
                plantilla.replace("{tema}", tema) + args.png_rachas.suffix)
            ruta = grafico.dibujar_tabla_rachas(
                serie, png, estacion=nombre, umbral_lluvia=args.umbral_lluvia,
                tema=tema, credito=args.credito,
            )
            print(f"Tabla de rachas guardada en {ruta}")


def cmd_ultimo(args):
    """El último día del que AEMET ya ha publicado dato, y cuánto se retrasa."""
    valores = datos.cargar_dias(args.carpeta, args.estacion, campo=args.variable)
    if not valores:
        sys.exit("No hay datos descargados.")
    ultimo = max(valores)
    desfase = (date.today() - ultimo).days
    if args.formato == "iso":
        print(ultimo.isoformat())
        return
    dias = "día" if desfase == 1 else "días"
    print(f"{metricas.fecha_larga(ultimo)} ({desfase} {dias} de desfase)")


def cmd_extremos(args):
    valores = datos.cargar_dias(args.carpeta, args.estacion, campo=args.variable)
    if args.desde or args.hasta:
        ini = args.desde.year if args.desde else -9999
        fin = args.hasta.year if args.hasta else 9999
        valores = {d: v for d, v in valores.items() if ini <= d.year <= fin}
    ranking = metricas.extremos(valores, top=args.top, mayores=not args.menores)
    if not ranking:
        sys.exit("No hay datos para ese rango.")

    que = "noches" if args.variable == "tmin" else "días"
    cual = "mínima" if args.variable == "tmin" else "máxima"
    orden = "más baja" if args.menores else "más alta"
    nombre = args.nombre or datos.nombre_estacion(args.carpeta, args.estacion)
    anyos = sorted({d.year for d in valores})
    print(
        f"Las {args.top} {que} de {cual} {orden} en {nombre}, "
        f"{anyos[0]}–{anyos[-1]}\n"
    )
    puesto, anterior = 0, None
    for i, (dia, valor) in enumerate(ranking, start=1):
        if valor != anterior:
            puesto, anterior = i, valor
            marca = f"{puesto:>3}."
        else:
            marca = "    "  # empate: se deja el hueco en blanco
        grados = f"{valor:.1f}".replace(".", ",")
        print(f"{marca}  {grados:>5} °C   {metricas.fecha_larga(dia)}")
    if len(ranking) > args.top:
        print(f"\n(Son {len(ranking)} y no {args.top} por empate en el último puesto.)")
    ultimo = max(valores)
    desfase = (date.today() - ultimo).days
    print(f"\nÚltimo día con datos: {metricas.fecha_larga(ultimo)} "
          f"({desfase} {'día' if desfase == 1 else 'días'} de desfase).")

    if args.csv:
        metricas.guardar_csv_extremos(ranking, args.csv, columna=args.variable)
        print(f"\nCSV guardado en {args.csv}")
    if args.png:
        plantilla = args.png.stem
        if "{tema}" not in plantilla and len(args.temas) > 1:
            plantilla += "_{tema}"
        for tema in args.temas:
            png = args.png.with_name(plantilla.replace("{tema}", tema) + args.png.suffix)
            ruta = grafico.dibujar_tabla_extremos(
                ranking, png, estacion=nombre, variable=args.variable,
                top=args.top, resaltar=args.resaltar, tema=tema,
                credito=args.credito,
            )
            print(f"Tabla guardada en {ruta}")


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
    que = {"tmax": "máxima", "prec": "precipitación"}.get(args.variable, "mínima")
    unidad = "mm" if args.variable == "prec" else "°C"
    print(f"Días con {que} {signo} {args.umbral:g} {unidad}\n")
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
            "--variable", choices=("tmin", "tmax", "prec"), default="tmin",
            help="mínima (por defecto), máxima o precipitación del día",
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

    sp = subs.add_parser(
        "lluvia",
        help="totales, días de lluvia, rachas secas y torrencialidad",
    )
    comunes(sp)
    sp.add_argument("--umbral-lluvia", type=float, default=1.0, metavar="MM",
                    help="mm a partir de los cuales el día cuenta como lluvioso")
    sp.add_argument("--csv", type=Path, default=CARPETA_SALIDA / "lluvia.csv")
    sp.add_argument("--png", type=Path, default=CARPETA_SALIDA / "lluvia_{tema}.png")
    sp.add_argument("--png-rachas", type=Path,
                    default=CARPETA_SALIDA / "rachas_secas_{tema}.png",
                    help="tabla año a año de la racha sin llover más larga")
    sp.add_argument("--temas", nargs="+", choices=sorted(grafico.TEMAS), default=["claro"])
    sp.add_argument("--nombre")
    sp.add_argument("--credito")
    sp.set_defaults(func=cmd_lluvia)

    sp = subs.add_parser(
        "ultimo",
        help="último día con datos publicados y cuántos días lleva de retraso",
    )
    comunes(sp, con_fechas=False)
    opcion_variable(sp)
    sp.add_argument("--formato", choices=("humano", "iso"), default="humano")
    sp.set_defaults(func=cmd_ultimo)

    sp = subs.add_parser(
        "extremos",
        help="ranking de los días más cálidos (o más fríos) de toda la serie",
    )
    comunes(sp)
    opcion_variable(sp)
    sp.add_argument("--top", type=int, default=10, help="cuántos días (por defecto 10)")
    sp.add_argument(
        "--menores", action="store_true",
        help="los valores más bajos en vez de los más altos",
    )
    sp.add_argument("--csv", type=Path, help="guarda el ranking en un CSV")
    sp.add_argument("--png", type=Path, help="dibuja la tabla como imagen")
    sp.add_argument(
        "--resaltar", type=int, nargs="+", metavar="AÑO",
        help="años a resaltar en la tabla (por defecto, el más reciente)",
    )
    sp.add_argument("--temas", nargs="+", choices=sorted(grafico.TEMAS), default=["claro"])
    sp.add_argument("--nombre")
    sp.add_argument("--credito")
    sp.set_defaults(func=cmd_extremos)

    sp = subs.add_parser(
        "lineas",
        help="una línea por año: el pasado en gris y los años que elijas en color",
    )
    comunes(sp)
    opcion_variable(sp)
    sp.add_argument(
        "--destacar", type=int, nargs="+", metavar="AÑO",
        help="años a resaltar (por defecto, el último de la serie)",
    )
    sp.add_argument(
        "--resolucion", choices=("diaria", "mensual"), default="diaria",
        help="un punto por día (por defecto) o la media de cada mes",
    )
    sp.add_argument(
        "--suavizado", type=int, default=1, metavar="DÍAS",
        help="media móvil centrada para la resolución diaria (1 = sin suavizar)",
    )
    sp.add_argument("--referencia", type=_referencia, default=(1991, 2020))
    sp.add_argument("--png", type=Path, default=CARPETA_SALIDA / "lineas_{tema}.png")
    sp.add_argument("--temas", nargs="+", choices=sorted(grafico.TEMAS), default=["claro"])
    sp.add_argument("--nombre")
    sp.add_argument("--credito")
    sp.set_defaults(func=cmd_lineas)

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
