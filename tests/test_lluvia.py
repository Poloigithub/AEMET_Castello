"""Pruebas de las métricas de lluvia (sin red)."""

from datetime import date, timedelta

import pytest

from aemet_noches import grafico, metricas
from aemet_noches.datos import _num


def _anyo_seco(anyo=2020, lluvias=None):
    """Un año entero a cero salvo los días que se indiquen."""
    dias = {}
    d = date(anyo, 1, 1)
    while d <= date(anyo, 12, 31):
        dias[d] = 0.0
        d += timedelta(days=1)
    dias.update(lluvias or {})
    return dias


def test_ip_cuenta_como_cero_solo_en_precipitacion():
    assert _num("Ip") is None                    # en temperatura, dato perdido
    assert _num("Ip", ip_es_cero=True) == 0.0    # en lluvia, llovió pero no se mide
    assert _num("Acum", ip_es_cero=True) is None  # eso sí es un hueco de verdad


def test_totales_y_dias_de_lluvia():
    v = _anyo_seco(lluvias={date(2020, 4, 1): 12.0, date(2020, 4, 2): 0.4,
                            date(2020, 9, 9): 30.0})
    (r,) = metricas.resumir_lluvia(v)
    assert r.total == pytest.approx(42.4)
    assert r.dias_de_lluvia == 2          # el de 0,4 mm no llega al milímetro
    assert r.por_mes[3] == pytest.approx(12.4)


def test_la_racha_seca_se_apunta_donde_termina():
    v = _anyo_seco(lluvias={date(2020, 1, 1): 5.0, date(2020, 3, 1): 5.0})
    (r,) = metricas.resumir_lluvia(v)
    assert r.racha_seca == 59             # del 2 de enero al 29 de febrero
    assert r.racha_seca_fin == date(2020, 3, 1)


def test_la_racha_seca_puede_cruzar_el_ano():
    v = _anyo_seco(2020, {date(2020, 12, 1): 5.0})
    v.update(_anyo_seco(2021, {date(2021, 2, 10): 5.0}))
    a, b = metricas.resumir_lluvia(v)
    # La racha que empieza en diciembre y muere en febrero se apunta en 2021,
    # que es el año en que por fin llueve y se puede contar.
    assert b.racha_seca == 70             # del 2 de diciembre al 9 de febrero
    assert b.racha_seca_fin == date(2021, 2, 10)
    assert a.racha_seca_fin == date(2020, 12, 1)


def test_torrencialidad():
    seis = {date(2020, 5, d): 10.0 for d in range(1, 7)}
    (r,) = metricas.resumir_lluvia(_anyo_seco(lluvias=seis))
    assert r.total == pytest.approx(60.0)
    assert r.torrencialidad == pytest.approx(50 / 60)   # los 5 mayores de 6
    assert metricas.resumir_lluvia(_anyo_seco())[0].torrencialidad is None


def test_csv_de_lluvia(tmp_path):
    import csv as _csv

    v = _anyo_seco(lluvias={date(2020, 4, 1): 12.0})
    destino = tmp_path / "l.csv"
    metricas.guardar_csv_lluvia(metricas.resumir_lluvia(v), destino)
    (fila,) = list(_csv.DictReader(destino.open(encoding="utf-8")))
    assert fila["anyo"] == "2020" and fila["total_mm"] == "12.0"
    assert fila["dias_de_lluvia"] == "1"


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_el_mapa_de_lluvia(tmp_path, tema):
    v = _anyo_seco(lluvias={date(2020, 4, 1): 12.0, date(2020, 10, 3): 80.0})
    serie = metricas.resumir_lluvia(v)
    destino = grafico.dibujar_lluvia(
        serie, tmp_path / f"{tema}.png", estacion="PRUEBA", tema=tema, dpi=80
    )
    assert destino.exists() and destino.stat().st_size > 1000


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_la_tabla_de_rachas(tmp_path, tema):
    v = _anyo_seco(2019, {date(2019, 6, 1): 20.0})
    v.update(_anyo_seco(2020, {date(2020, 3, 1): 20.0, date(2020, 9, 1): 8.0}))
    serie = metricas.resumir_lluvia(v)
    destino = grafico.dibujar_tabla_rachas(
        serie, tmp_path / f"r_{tema}.png", estacion="PRUEBA", tema=tema, dpi=80
    )
    assert destino.exists() and destino.stat().st_size > 1000


def test_la_tabla_de_rachas_vacia_da_error(tmp_path):
    with pytest.raises(ValueError):
        grafico.dibujar_tabla_rachas([], tmp_path / "x.png", estacion="PRUEBA")
