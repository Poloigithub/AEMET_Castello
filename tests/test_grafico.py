"""Comprobación de humo del dibujo: que salga un PNG y no reviente."""

from datetime import date, timedelta

import pytest

from aemet_noches import grafico, metricas


def _resumenes():
    minimas = {}
    dia = date(2018, 1, 1)
    while dia <= date(2020, 12, 31):
        if not (dia.year == 2019 and dia.month == 7):  # hueco a propósito
            minimas[dia] = 21.0 if dia.month in (7, 8) else 12.0
        dia += timedelta(days=1)
    return metricas.contar(minimas)


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_png(tmp_path, tema):
    destino = grafico.dibujar(
        _resumenes(), tmp_path / f"{tema}.png", estacion="PRUEBA", tema=tema, dpi=80
    )
    assert destino.exists() and destino.stat().st_size > 1000


def test_credito_al_pie(tmp_path):
    con = grafico.dibujar(
        _resumenes(), tmp_path / "con.png", estacion="PRUEBA",
        credito="Gráfico: fulano@servidor", dpi=80,
    )
    sin = grafico.dibujar(_resumenes(), tmp_path / "sin.png", estacion="PRUEBA", dpi=80)
    assert con.read_bytes() != sin.read_bytes()


def test_titulo_largo_no_desborda(tmp_path):
    grafico.dibujar(
        _resumenes(),
        tmp_path / "largo.png",
        estacion="NOMBRE ABSURDAMENTE LARGO " * 6,
        tema="claro",
        dpi=80,
    )


def test_el_titulo_cambia_con_el_umbral():
    assert grafico.nombre_del_fenomeno(20) == "Noches tropicales"
    assert grafico.nombre_del_fenomeno(25) == "Noches tórridas"
    assert grafico.nombre_del_fenomeno(25, estricto=True) == "Noches con mínima > 25 °C"
    assert grafico.nombre_del_fenomeno(22.5) == "Noches con mínima ≥ 22,5 °C"


def test_sin_anyos_da_error(tmp_path):
    with pytest.raises(ValueError):
        grafico.dibujar([], tmp_path / "x.png", estacion="PRUEBA")


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_la_tabla_de_extremos(tmp_path, tema):
    from datetime import date

    ranking = [(date(2026, 7, 21), 27.4), (date(2025, 8, 11), 27.1),
               (date(2023, 7, 20), 26.5), (date(2023, 7, 31), 26.5)]
    destino = grafico.dibujar_tabla_extremos(
        ranking, tmp_path / f"t_{tema}.png", estacion="PRUEBA", tema=tema,
        top=3, dpi=80,
    )
    assert destino.exists() and destino.stat().st_size > 1000


def test_la_tabla_vacia_da_error(tmp_path):
    with pytest.raises(ValueError):
        grafico.dibujar_tabla_extremos([], tmp_path / "x.png", estacion="PRUEBA")
