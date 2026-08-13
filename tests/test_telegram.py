"""Pruebas del envío a Telegram (sin red: se sustituye requests.post)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import telegram  # noqa: E402


class RespuestaFalsa:
    def __init__(self, ok=True, status_code=200, text="{}"):
        self.ok, self.status_code, self.text = ok, status_code, text


def test_el_texto_va_solo_en_el_primer_elemento():
    media = telegram.construir_media([Path("a.png"), Path("b.png")], "document", "hola")
    assert media[0] == {"type": "document", "media": "attach://f0", "caption": "hola"}
    assert media[1] == {"type": "document", "media": "attach://f1"}


def test_envia_en_tandas_de_diez(tmp_path, monkeypatch):
    ficheros = []
    for i in range(12):
        f = tmp_path / f"{i}.png"
        f.write_bytes(b"png")
        ficheros.append(f)

    llamadas = []

    def post_falso(url, data, files, timeout):
        llamadas.append((url, data, sorted(files)))
        return RespuestaFalsa()

    monkeypatch.setattr(telegram.requests, "post", post_falso)
    telegram.enviar(ficheros, "T0K3N", "-100", texto="informe")

    assert len(llamadas) == 2                      # 10 + 2
    assert len(llamadas[0][2]) == 10 and len(llamadas[1][2]) == 2
    assert "informe" in llamadas[0][1]["media"]
    assert "caption" not in json.loads(llamadas[1][1]["media"])[0]
    assert llamadas[0][0].endswith("/botT0K3N/sendMediaGroup")


def test_un_fallo_de_telegram_se_cuenta_con_su_motivo(tmp_path, monkeypatch):
    f = tmp_path / "a.png"
    f.write_bytes(b"png")
    monkeypatch.setattr(
        telegram.requests, "post",
        lambda url, **kw: RespuestaFalsa(False, 400, '{"description":"chat not found"}'),
    )
    with pytest.raises(RuntimeError, match="chat not found"):
        telegram.enviar([f], "T", "-1")


def test_sin_credenciales_sale_con_error(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    assert telegram.main([str(tmp_path / "a.png")]) == 1
    assert "TELEGRAM_BOT_TOKEN" in capsys.readouterr().err


def test_un_fichero_que_no_existe_no_aborta_el_resto(tmp_path, monkeypatch):
    bueno = tmp_path / "bueno.png"
    bueno.write_bytes(b"png")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "T")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-1")
    enviados = []
    monkeypatch.setattr(
        telegram, "enviar",
        lambda ficheros, *a, **k: enviados.extend(ficheros),
    )
    assert telegram.main([str(bueno), str(tmp_path / "no_esta.png")]) == 0
    assert enviados == [bueno]
