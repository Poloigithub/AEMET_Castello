"""Pruebas del cálculo de anomalías (no tocan la red)."""

from datetime import date, timedelta

import pytest

from aemet_noches import grafico, metricas


def _serie_constante(ini=1991, fin=2021, valor=25.0):
    """Un valor fijo todos los días: la anomalía tiene que salir cero."""
    v = {}
    dia = date(ini, 1, 1)
    while dia <= date(fin, 12, 31):
        v[dia] = valor
        dia += timedelta(days=1)
    return v


def test_media_mensual_y_extremo():
    v = _serie_constante(1991, 2021)
    v[date(2021, 7, 15)] = 41.2
    serie = metricas.medias_por_mes(v)
    assert serie[0].anyo == 1991
    assert serie[0].medias[0] == pytest.approx(25.0)
    assert serie[-1].extremo == pytest.approx(41.2)


def test_anomalia_cero_si_no_cambia_nada():
    serie = metricas.medias_por_mes(_serie_constante())
    normal = metricas.normales(serie)
    anom = metricas.anomalias(serie, normal)
    assert all(abs(v) < 1e-9 for fila in anom for v in fila)


def test_mes_incompleto_no_produce_media():
    v = _serie_constante(1991, 2021)
    for dia in [date(2021, 8, d) for d in range(1, 20)]:  # agosto se queda a 12 días
        del v[dia]
    serie = metricas.medias_por_mes(v)
    ultimo = serie[-1]
    assert ultimo.medias[7] is None          # agosto fuera
    assert ultimo.medias[6] == pytest.approx(25.0)  # julio sigue
    assert ultimo.media_anual is None        # el año ya no tiene media comparable


def test_referencia_corta_avisa_en_vez_de_mentir():
    serie = metricas.medias_por_mes(_serie_constante(2015, 2021))
    with pytest.raises(ValueError, match="periodo de referencia"):
        metricas.normales(serie, (1991, 2020))


def test_anomalia_positiva_cuando_sube():
    v = _serie_constante(1991, 2020)
    dia = date(2021, 1, 1)
    while dia <= date(2021, 12, 31):
        v[dia] = 27.0  # dos grados por encima
        dia += timedelta(days=1)
    serie = metricas.medias_por_mes(v)
    anom = metricas.anomalias(serie, metricas.normales(serie))
    assert all(x == pytest.approx(2.0) for x in anom[-1])


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_el_mapa_de_anomalias(tmp_path, tema):
    v = _serie_constante(1991, 2021)
    serie = metricas.medias_por_mes(v)
    anom = metricas.anomalias(serie, metricas.normales(serie))
    destino = grafico.dibujar_anomalias(
        serie, anom, tmp_path / f"{tema}.png", estacion="PRUEBA", tema=tema, dpi=80
    )
    assert destino.exists() and destino.stat().st_size > 1000


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_el_grafico_de_lineas(tmp_path, tema):
    serie = metricas.medias_por_mes(_serie_constante(1991, 2021))
    destino = grafico.dibujar_lineas(
        serie, tmp_path / f"l_{tema}.png", estacion="PRUEBA",
        destacar=[2020, 2021], normal=metricas.normales(serie), tema=tema, dpi=80,
    )
    assert destino.exists() and destino.stat().st_size > 1000


def test_lineas_sin_normal_y_con_un_ano_que_no_esta(tmp_path):
    serie = metricas.medias_por_mes(_serie_constante(2019, 2021))
    destino = grafico.dibujar_lineas(
        serie, tmp_path / "l.png", estacion="PRUEBA",
        destacar=[2021, 1999], normal=None, dpi=80,   # 1999 no existe: se ignora
    )
    assert destino.exists()


def test_serie_diaria_alinea_los_anos_y_tira_el_29_de_febrero():
    v = _serie_constante(2019, 2020)
    v[date(2020, 2, 29)] = 99.0          # bisiesto: no debe aparecer
    v[date(2020, 3, 1)] = 30.0
    series = metricas.series_diarias(v)
    assert set(series) == {2019, 2020}
    assert all(len(x) == 365 for x in series.values())
    assert 99.0 not in series[2020]
    i = metricas.indice_del_dia(date(2020, 3, 1))
    assert i == metricas.indice_del_dia(date(2019, 3, 1))  # mismo hueco en ambos
    assert series[2020][i] == 30.0


def test_suavizar_promedia_y_respeta_los_bordes():
    assert metricas.suavizar([1.0, 2.0, 3.0], 1) == [1.0, 2.0, 3.0]
    assert metricas.suavizar([0.0, 3.0, 0.0], 3) == pytest.approx([1.5, 1.0, 1.5])
    assert metricas.suavizar([1.0, None, 3.0], 3) == pytest.approx([1.0, 2.0, 3.0])


def test_normal_diaria_usa_la_ventana_y_avisa_si_falta_referencia():
    series = metricas.series_diarias(_serie_constante(1991, 2020))
    normal = metricas.normal_diaria(series)
    assert len(normal) == 365 and all(abs(v - 25.0) < 1e-9 for v in normal)
    with pytest.raises(ValueError, match="periodo de referencia"):
        metricas.normal_diaria(metricas.series_diarias(_serie_constante(2018, 2020)))


@pytest.mark.parametrize("tema", sorted(grafico.TEMAS))
def test_dibuja_lineas_diarias(tmp_path, tema):
    series = metricas.series_diarias(_serie_constante(1991, 2021))
    destino = grafico.dibujar_lineas_diarias(
        series, tmp_path / f"d_{tema}.png", estacion="PRUEBA", destacar=[2020, 2021],
        normal=metricas.normal_diaria(series), tema=tema, suavizado=7, dpi=80,
    )
    assert destino.exists() and destino.stat().st_size > 1000
