"""Pruebas del troceado de fechas y del trato con AEMET (no tocan la red)."""

import json

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


def _cliente_con_sobres(sobres, monkeypatch):
    """Devuelve un ClienteAemet que consume `sobres` en vez de llamar a la red."""
    from aemet_noches import api

    pendientes = list(sobres)
    esperas: list[float] = []

    def falso_get(self, url, con_clave):
        class R:
            encoding = "utf-8"
            text = json.dumps(pendientes.pop(0))
        return R()

    monkeypatch.setattr(api.ClienteAemet, "_get", falso_get)
    monkeypatch.setattr(api.time, "sleep", esperas.append)
    return api.ClienteAemet(api_key="x", espera=0.1), esperas


def test_el_400_enganoso_de_fechas_se_trata_como_freno(monkeypatch):
    """AEMET frena con un 400 que habla de fechas: hay que esperar y reintentar."""
    freno = {"estado": 400, "descripcion": "La fecha final no puede ser mayor que la fecha inicial"}
    bueno = {"estado": 200, "datos": "https://ejemplo/datos"}
    cliente, esperas = _cliente_con_sobres(
        [freno, freno, bueno, [{"fecha": "2026-07-01"}]], monkeypatch
    )

    datos = cliente.recurso("/loquesea")

    assert datos == [{"fecha": "2026-07-01"}]
    # Dos frenos, dos esperas largas, y la segunda mayor que la primera.
    largas = [e for e in esperas if e >= 5]
    assert len(largas) == 2 and largas[1] > largas[0]


def test_un_error_de_verdad_no_se_reintenta(monkeypatch):
    """Solo se insiste ante un freno; un 401 de clave caducada falla ya."""
    from aemet_noches.api import ErrorAemet

    cliente, _ = _cliente_con_sobres(
        [{"estado": 401, "descripcion": "API key caducada"}], monkeypatch
    )
    with pytest.raises(ErrorAemet, match="401"):
        cliente.recurso("/loquesea")


def test_si_falla_todo_el_tramo_no_se_disfraza_de_dato_perdido(tmp_path):
    """Una caída de AEMET no puede pasar por 'no había datos'."""
    from aemet_noches.api import ErrorAemet, descargar_serie

    class Caido:
        espera = 0

        def climatologia_diaria(self, estacion, ini, fin):
            raise ErrorAemet("AEMET respondió 500")

    with pytest.raises(ErrorAemet):
        descargar_serie(
            Caido(), "8500A", date(2026, 7, 1), date(2026, 9, 2),
            tmp_path, meses_por_lote=6, hoy=date(2026, 9, 2),
        )
