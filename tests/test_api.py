"""Pruebas del troceado de fechas (no tocan la red)."""

import pytest

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
    # El semestre cerrado se pide una sola vez; el abierto, en las dos tiradas.
    # Se distinguen por el día en que empiezan, no por el final: desde que no
    # se pide "hasta hoy", todos los tramos acaban en el pasado.
    cerrado = [p for p in pedidos if p[0] == date(2026, 1, 1)]
    abierto = [p for p in pedidos if p[0] == date(2026, 7, 1)]
    assert len(cerrado) == 1
    assert len(abierto) == 2


def test_no_se_acumulan_versiones_del_tramo_en_curso(tmp_path):
    """El tramo abierto cambia de nombre cada día: solo debe quedar el último."""
    from aemet_noches.api import descargar_serie

    pedidos: list = []
    for dia in (date(2026, 8, 18), date(2026, 8, 19), date(2026, 8, 20)):
        descargar_serie(
            _cliente_falso(pedidos), "8500A", date(2026, 7, 1), dia,
            tmp_path, meses_por_lote=6, hoy=dia,
        )
    ficheros = sorted(p.name for p in tmp_path.glob("*.json"))
    assert ficheros == ["8500A_20260701_20260820.json"]


def test_nunca_se_pide_a_aemet_hasta_hoy(tmp_path):
    """La hora 23:59 de hoy es futuro y AEMET responde 400 a eso."""
    from aemet_noches.api import descargar_serie

    hoy = date(2026, 9, 2)
    pedidos: list = []
    descargar_serie(
        _cliente_falso(pedidos), "8500A", date(2026, 1, 1), hoy,
        tmp_path, meses_por_lote=6, hoy=hoy,
    )
    assert all(fin < hoy for _, fin in pedidos), pedidos
    assert max(fin for _, fin in pedidos) == date(2026, 9, 1)   # hasta ayer


def test_un_tramo_que_empieza_hoy_no_se_pide(tmp_path):
    """Sin días publicables no hay nada que pedir, y menos un rango invertido."""
    from aemet_noches.api import descargar_serie

    hoy = date(2026, 7, 1)
    pedidos: list = []
    descargar_serie(
        _cliente_falso(pedidos), "8500A", date(2026, 7, 1), hoy,
        tmp_path, meses_por_lote=6, hoy=hoy,
    )
    assert pedidos == []


def test_un_tramo_rechazado_se_parte_en_dos():
    """AEMET rechaza rangos largos de forma caprichosa; se prueba con la mitad."""
    from aemet_noches.api import ErrorAemet, pedir_tramo

    pedidos: list = []

    class Quisquilloso:
        espera = 0

        def climatologia_diaria(self, estacion, ini, fin):
            pedidos.append((ini, fin))
            if (fin - ini).days > 40:
                raise ErrorAemet("AEMET respondió 400: la fecha final...")
            return [{"fecha": ini.isoformat(), "tmin": "10,0"}]

    datos = pedir_tramo(Quisquilloso(), "8500A", date(2026, 7, 1), date(2026, 9, 1))
    assert len(datos) == 2                       # las dos mitades han entrado
    assert pedidos[0] == (date(2026, 7, 1), date(2026, 9, 1))   # primero entero
    assert all((f - i).days <= 40 for i, f in pedidos[1:])      # luego troceado


def test_si_ni_partiendo_funciona_el_error_sale_a_la_luz():
    from aemet_noches.api import ErrorAemet, pedir_tramo

    class Roto:
        espera = 0

        def climatologia_diaria(self, estacion, ini, fin):
            raise ErrorAemet("AEMET respondió 401: clave inválida")

    with pytest.raises(ErrorAemet, match="401"):
        pedir_tramo(Roto(), "8500A", date(2026, 7, 1), date(2026, 9, 1))
