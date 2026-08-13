"""Pruebas del troceado de fechas (no tocan la red)."""

from datetime import date, timedelta

from aemet_noches.api import tramos


def test_tramos_cubren_el_rango_sin_huecos_ni_solapes():
    ini, fin = date(1990, 1, 1), date(1995, 3, 17)
    lista = list(tramos(ini, fin, meses=6))
    assert lista[0][0] == ini
    assert lista[-1][1] == fin
    for (_, hasta), (desde, _) in zip(lista, lista[1:]):
        assert desde == hasta + timedelta(days=1)


def test_tramos_respetan_el_tamano_pedido():
    lista = list(tramos(date(2020, 1, 1), date(2020, 12, 31), meses=6))
    assert lista == [
        (date(2020, 1, 1), date(2020, 6, 30)),
        (date(2020, 7, 1), date(2020, 12, 31)),
    ]


def test_tramo_unico_si_el_rango_es_corto():
    assert list(tramos(date(2024, 5, 1), date(2024, 5, 10), meses=6)) == [
        (date(2024, 5, 1), date(2024, 5, 10))
    ]


def test_dia_31_no_rompe_el_salto_de_mes():
    lista = list(tramos(date(2021, 8, 31), date(2022, 3, 1), meses=6))
    assert lista[0][0] == date(2021, 8, 31)
    assert lista[-1][1] == date(2022, 3, 1)
