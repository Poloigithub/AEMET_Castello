"""Pruebas del recuento (no tocan la red)."""

from datetime import date, timedelta

from aemet_noches import metricas
from aemet_noches.datos import _num


def test_num_admite_coma_y_marcas():
    assert _num("21,4") == 21.4
    assert _num("-1,2") == -1.2
    assert _num("Ip") is None
    assert _num("") is None
    assert _num(None) is None


def test_cuenta_por_mes_y_umbral():
    minimas = {
        date(2020, 7, 1): 20.0,   # justo en el umbral
        date(2020, 7, 2): 20.1,
        date(2020, 7, 3): 19.9,
        date(2020, 8, 1): 24.3,
    }
    (r,) = metricas.contar(minimas)
    assert r.por_mes[6] == 2   # julio: el 20,0 cuenta con >=
    assert r.por_mes[7] == 1
    assert r.total == 3

    (estricto,) = metricas.contar(minimas, estricto=True)
    assert estricto.por_mes[6] == 1  # el 20,0 ya no cuenta
    assert estricto.total == 2


def test_cobertura_detecta_anyos_incompletos():
    completo = {date(2021, 1, 1) + timedelta(days=i): 10.0 for i in range(365)}
    parcial = {date(2022, 1, 1) + timedelta(days=i): 10.0 for i in range(100)}
    a, b = metricas.contar({**completo, **parcial})
    assert a.anyo == 2021 and a.cobertura == 1.0
    assert b.anyo == 2022 and round(b.cobertura, 3) == round(100 / 365, 3)


def test_anyos_sin_datos_aparecen_vacios():
    minimas = {date(2000, 8, 5): 22.0, date(2003, 8, 5): 22.0}
    resumenes = metricas.contar(minimas)
    assert [r.anyo for r in resumenes] == [2000, 2001, 2002, 2003]
    assert resumenes[1].total == 0 and resumenes[1].dias_con_dato == 0


def test_csv_ida_y_vuelta(tmp_path):
    minimas = {date(2019, 9, 3): 21.0, date(2019, 9, 4): 18.0}
    resumenes = metricas.contar(minimas)
    destino = tmp_path / "r.csv"
    metricas.guardar_csv(resumenes, destino)
    leidos = metricas.leer_csv(destino)
    assert leidos[0].por_mes == resumenes[0].por_mes
    assert leidos[0].dias_con_dato_mes == resumenes[0].dias_con_dato_mes
