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


def _cliente_falso(registro):
    class Falso:
        espera = 0

        def climatologia_diaria(self, estacion, ini, fin):
            registro.append((ini, fin))
            return [{"fecha": ini.isoformat(), "tmin": "10,0"}]

    return Falso()


def test_el_tramo_en_curso_se_vuelve_a_pedir(tmp_path):
    """Un tramo que llega a hoy está incompleto: cachearlo congelaría la serie."""
    from aemet_noches.api import descargar_serie

    hoy = date(2026, 8, 19)
    pedidos: list = []
    for _ in range(2):  # dos ejecuciones seguidas
        descargar_serie(
            _cliente_falso(pedidos), "8500A", date(2026, 1, 1), hoy,
            tmp_path, meses_por_lote=6, hoy=hoy,
        )
    # El primer semestre (cerrado) se pide una vez; el que llega a hoy, las dos.
    cerrados = [p for p in pedidos if p[1] < hoy]
    en_curso = [p for p in pedidos if p[1] >= hoy]
    assert len(cerrados) == 1
    assert len(en_curso) == 2
