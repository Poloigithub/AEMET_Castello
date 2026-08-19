---
tags: [proyecto, datos, clima, castelló, github]
creado: 2026-08-19
estado: en marcha
repo: https://github.com/Poloigithub/AEMET_Castello
---

# Clima de Castelló (AEMET)

Sistema que descarga los datos climáticos de la estación de AEMET de
Castelló-Almassora y genera gráficos solo, en GitHub. **No hay que tocar nada
para que funcione**: cada mes llegan los gráficos por Telegram y cada día se
vigila si cae un récord.

## Qué me llega y cuándo

| Cuándo | Qué |
|---|---|
| **Día 3 de cada mes** | Seis gráficos por Telegram: media móvil de 7 días, noches tropicales, noches tórridas, días de 35 °C, y anomalías de mínimas y de máximas |
| **Cada día, 8:40 (hora de Castelló)** | Solo si entra una temperatura nueva en el top 10 de mínimas o de máximas: la tabla por Telegram. Si no hay récord, silencio |

Todo queda además commiteado en el repo, en `resultados/`.

## Los cuatro gráficos y qué contesta cada uno

- **Mapa de recuento** — cuántas noches al año pasan de 20 °C (tropicales) o
  de 25 °C (tórridas). Filas años, columnas meses.
- **Mapa de anomalías** — si sube la temperatura. Compara cada mes con su
  normal de 1991-2020. Azul por debajo, rojo por encima. Es el bueno para
  hablar de tendencia.
- **Gráfico de líneas** — un año por línea, el pasado en gris. La versión
  publicable es la diaria con media móvil de 7 días.
- **Tabla de extremos** — los diez días más cálidos del registro, con el año
  reciente resaltado.

## Lo que hemos encontrado en los datos (agosto 2026)

- Noches tropicales: de **55 al año** en los noventa a **84** en la última
  década. Récord en 2025 con **102**.
- Noches tórridas (≥ 25 °C): **una sola** entre 1990 y 2002. **Treinta y dos**
  entre 2022 y 2025.
- Máximas: suben **+0,4 °C por década**, pero **el récord absoluto sigue
  siendo de 2009** (40,6 °C). Sube el día normal, no el pico.
- Mínimas: **once de las doce noches más cálidas de la serie son de 2018 en
  adelante**, y cinco son de una sola semana de julio de 2026.
- El mes que más se ha movido es **junio**: más de dos grados entre los
  noventa y ahora. El verano se alarga por los bordes.

> [!warning] Al publicar, decir siempre esto
> La serie **no está homogeneizada**. Los observatorios se mudan y su entorno
> se urbaniza, así que parte de la subida es clima y parte es entorno. Con
> estos datos no se pueden separar. Decirlo antes de que lo digan.

## Operación

### Los tres secretos del repo

En **Settings → Secrets and variables → Actions**:

- `AEMET_API_KEY` — la clave de AEMET. **Caduca el 21/11/2026**, hay que
  renovarla en [opendata.aemet.es](https://opendata.aemet.es/centrodedescargas/altaUsuario).
- `TELEGRAM_BOT_TOKEN` — del bot de @BotFather.
- `TELEGRAM_CHAT_ID` — mi chat.

### Lanzar algo a mano

Pestaña **Actions** del repo → elegir el workflow → *Run workflow*.

- **Mapas de calor de AEMET**: informe completo. Se puede cambiar estación,
  años, umbral, variable y firma desde el formulario.
- **Vigilancia diaria del top 10**: con `forzar_envio` manda la tabla aunque
  no haya récord, para comprobar que Telegram sigue funcionando.

### Si algo falla

| Síntoma | Causa probable |
|---|---|
| Deja de llegar todo | La clave de AEMET ha caducado |
| Llegan gráficos pero no avisos | Normal: solo avisa si hay récord |
| Falla el paso de Telegram con `chat not found` | Hay que volver a darle a Start al bot |
| Un año sale con asterisco | Le faltan días observados; el recuento se queda corto |

## Cosas que se pueden pedir sin tocar código

- Otra estación de la provincia (`estaciones --provincia CASTELLON` las lista).
- Otro umbral (30 °C, 35 °C…), cada uno va a su propia carpeta.
- Otro periodo de referencia para las anomalías (1961-1990 daría rojos más
  intensos, porque el listón sería más frío).
- Cambiar la firma del pie o los años resaltados.

## Enlaces

- Repo: https://github.com/Poloigithub/AEMET_Castello
- Rama de trabajo: `claude/heat-map-warm-nights-itnvo2` (es la rama por
  defecto, por eso los `cron` se disparan desde ahí)
- Firma de los gráficos: `poloi@eurosky.social`
