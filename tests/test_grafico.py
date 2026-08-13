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


def test_titulo_largo_no_desborda(tmp_path):
    grafico.dibujar(
        _resumenes(),
        tmp_path / "largo.png",
        estacion="NOMBRE ABSURDAMENTE LARGO " * 6,
        tema="claro",
        dpi=80,
    )


def test_sin_anyos_da_error(tmp_path):
    with pytest.raises(ValueError):
        grafico.dibujar([], tmp_path / "x.png", estacion="PRUEBA")
