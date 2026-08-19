"""Pruebas del detector de entradas nuevas en el ranking."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import vigilar_top  # noqa: E402


def _csv(tmp_path, nombre, filas):
    ruta = tmp_path / nombre
    lineas = ["puesto,fecha,tmin"]
    lineas += [f"{p},{f},{v}" for p, f, v in filas]
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def test_detecta_la_fecha_que_no_estaba(tmp_path):
    antes = _csv(tmp_path, "a.csv", [(1, "2026-07-21", 27.4), (2, "2025-08-11", 27.1)])
    despues = _csv(tmp_path, "b.csv", [(1, "2026-08-14", 27.9), (2, "2026-07-21", 27.4)])
    nuevas = vigilar_top.nuevas_entradas(vigilar_top.leer(antes), vigilar_top.leer(despues))
    assert nuevas == [(date(2026, 8, 14), 1, 27.9)]


def test_sin_cambios_no_hay_nuevas(tmp_path):
    filas = [(1, "2026-07-21", 27.4), (2, "2025-08-11", 27.1)]
    antes, despues = _csv(tmp_path, "a.csv", filas), _csv(tmp_path, "b.csv", filas)
    assert vigilar_top.nuevas_entradas(vigilar_top.leer(antes), vigilar_top.leer(despues)) == []


def test_la_primera_vez_no_avisa_de_todo(tmp_path, capsys, monkeypatch):
    """Sin ranking previo no se anuncian doce récords de golpe."""
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    despues = _csv(tmp_path, "b.csv", [(1, "2026-07-21", 27.4)])
    assert vigilar_top.main(["--antes", str(tmp_path / "no_existe.csv"),
                             "--despues", str(despues)]) == 0
    assert "no se avisa" in capsys.readouterr().out


def test_el_texto_distingue_el_record_absoluto():
    uno = [(date(2026, 8, 14), 1, 27.9)]
    assert "Récord absoluto" in vigilar_top.redactar(uno, "tmin")
    otro = [(date(2026, 8, 14), 4, 26.6)]
    assert "puesto 4" in vigilar_top.redactar(otro, "tmin")
    dos = uno + [(date(2026, 8, 15), 5, 26.5)]
    texto = vigilar_top.redactar(dos, "tmin")
    assert texto.startswith("Entran 2 noches nuevas") and texto.count("·") == 2


def test_escribe_las_salidas_para_actions(tmp_path, monkeypatch):
    salida = tmp_path / "out.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(salida))
    antes = _csv(tmp_path, "a.csv", [(1, "2025-08-11", 27.1)])
    despues = _csv(tmp_path, "b.csv", [(1, "2026-08-14", 27.9), (2, "2025-08-11", 27.1)])
    vigilar_top.main(["--antes", str(antes), "--despues", str(despues)])
    contenido = salida.read_text(encoding="utf-8")
    assert "nuevas=1" in contenido
    assert "texto<<FIN" in contenido and "Récord absoluto" in contenido
