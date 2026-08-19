"""Envía imágenes a un chat de Telegram con la API de bots.

Uso:
    TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... \
        python scripts/telegram.py --texto "Informe de agosto" fichero1.png fichero2.png

Por defecto van como **documento**, no como foto: Telegram recomprime las fotos
y estos gráficos llevan texto de 5 pt que se convierte en papilla. Con
`--como foto` se envían como imagen si prefieres la vista previa en el chat.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import requests

API = "https://api.telegram.org"
MAXIMO_POR_GRUPO = 10  # límite de la API para sendMediaGroup


def construir_media(ficheros: list[Path], como: str, texto: str | None) -> list[dict]:
    """El array `media` que espera la API, con el texto en el primer elemento."""
    media = []
    for i, fichero in enumerate(ficheros):
        item = {"type": como, "media": f"attach://f{i}"}
        if i == 0 and texto:
            item["caption"] = texto
        media.append(item)
    return media


def enviar_texto(texto: str, token: str, chat: str, timeout: int = 60) -> None:
    """Un aviso sin imagen, para cuando algo se ha roto y no hay nada que enseñar."""
    respuesta = requests.post(
        f"{API}/bot{token}/sendMessage",
        data={"chat_id": chat, "text": texto, "disable_web_page_preview": "true"},
        timeout=timeout,
    )
    if not respuesta.ok:
        raise RuntimeError(
            f"Telegram devolvió {respuesta.status_code}: {respuesta.text[:300]}"
        )
    print("Aviso de texto enviado a Telegram.")


def enviar(
    ficheros: list[Path],
    token: str,
    chat: str,
    texto: str | None = None,
    como: str = "document",
    timeout: int = 120,
) -> None:
    if not ficheros:
        raise ValueError("No hay ficheros que enviar")
    for tanda in range(0, len(ficheros), MAXIMO_POR_GRUPO):
        lote = ficheros[tanda : tanda + MAXIMO_POR_GRUPO]
        # El texto solo en el primer envío, para no repetirlo en cada tanda.
        media = construir_media(lote, como, texto if tanda == 0 else None)
        abiertos = [f.open("rb") for f in lote]
        try:
            respuesta = requests.post(
                f"{API}/bot{token}/sendMediaGroup",
                data={"chat_id": chat, "media": json.dumps(media)},
                files={f"f{i}": (f.name, abierto) for i, (f, abierto) in
                       enumerate(zip(lote, abiertos))},
                timeout=timeout,
            )
        finally:
            for abierto in abiertos:
                abierto.close()
        if not respuesta.ok:
            # El cuerpo de Telegram explica el fallo mucho mejor que el código.
            raise RuntimeError(
                f"Telegram devolvió {respuesta.status_code}: {respuesta.text[:300]}"
            )
        print(f"Enviados {len(lote)} ficheros a Telegram.")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Envía ficheros a un chat de Telegram")
    p.add_argument("ficheros", nargs="*", type=Path)
    p.add_argument("--texto", help="texto que acompaña al primer fichero")
    p.add_argument("--como", choices=("document", "foto"), default="document")
    args = p.parse_args(argv)

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        print(
            "Faltan TELEGRAM_BOT_TOKEN o TELEGRAM_CHAT_ID. Créalos como secretos "
            "del repositorio; el token te lo da @BotFather.",
            file=sys.stderr,
        )
        return 1

    if not args.ficheros:  # aviso de texto, sin adjuntos
        if not args.texto:
            print("Nada que enviar: ni ficheros ni texto.", file=sys.stderr)
            return 1
        enviar_texto(args.texto, token, chat)
        return 0

    existentes = [f for f in args.ficheros if f.exists()]
    if faltan := [f for f in args.ficheros if not f.exists()]:
        print(f"Aviso: no existen {', '.join(str(f) for f in faltan)}", file=sys.stderr)
    if not existentes:
        print("No hay ningún fichero que enviar.", file=sys.stderr)
        return 1

    enviar(
        existentes, token, chat, texto=args.texto,
        como="photo" if args.como == "foto" else "document",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
