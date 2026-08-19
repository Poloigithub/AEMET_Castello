# Noches tropicales en Castelló

Cuenta, año a año, cuántas noches la temperatura **mínima** no bajó de 20 °C
(«noches tropicales») usando los valores climatológicos diarios de
[AEMET OpenData](https://opendata.aemet.es/), y dibuja un mapa de calor de
años × meses.

![ejemplo del mapa](docs/ejemplo.png)

> La imagen de arriba está generada con **datos sintéticos**, solo para enseñar
> el formato de salida. Los datos reales los descargas tú con tu clave de AEMET
> (ver más abajo); en el entorno donde se escribió esto el dominio
> `opendata.aemet.es` estaba bloqueado por la política de red.

## Puesta en marcha

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Necesitas una clave de la API, que es **gratuita e inmediata**: la pides en
<https://opendata.aemet.es/centrodedescargas/altaUsuario> y te llega por correo.
Luego, cualquiera de estas tres opciones vale:

```bash
export AEMET_API_KEY="eyJhbGciOi..."      # variable de entorno
echo "eyJhbGciOi..." > .aemet_api_key      # fichero local (está en .gitignore)
python -m aemet_noches --api-key "eyJ..." …
```

## Uso

De una tacada, para la estación de Castelló:

```bash
python -m aemet_noches todo --estacion 8500A --desde 1990
```

O paso a paso:

```bash
# 1. ¿qué estaciones hay en la provincia?
python -m aemet_noches estaciones --provincia CASTELLON

# 2. descargar la climatología diaria (se cachea en datos/crudos/)
python -m aemet_noches descargar --estacion 8500A --desde 1990 --hasta 2025-12-31

# 3. contar noches tropicales por año y mes → salida/noches_tropicales.csv
python -m aemet_noches calcular --estacion 8500A

# 4. dibujar el mapa de calor → salida/mapa_calor.png
python -m aemet_noches mapa --estacion 8500A --tema claro
```

### ¿Están subiendo las temperaturas?

Contar días por encima de un umbral depende mucho de dónde pongas el umbral y
descarta la mayoría de los datos. Para ver la tendencia hay un segundo mapa,
el de **anomalías**: cuánto se desvía la temperatura media de cada mes
respecto a lo normal en esa estación para ese mes.

```bash
python -m aemet_noches anomalias --variable tmax --temas claro oscuro
```

Usa todos los días, quita el ciclo estacional (comparar julio con enero no
dice nada) y no depende de ningún listón elegido a dedo. La referencia por
defecto es **1991–2020**, la normal climática de la OMM; se cambia con
`--referencia 1961-1990`. La escala es divergente, con gris en el cero: azul
por debajo de lo normal, rojo por encima. A la derecha, la media del año y el
récord absoluto.

Y para ver la misma subida como curvas, un gráfico de líneas con un año por
línea: el pasado en gris y los años que elijas en color, sobre la normal.

```bash
python -m aemet_noches lineas --variable tmax --destacar 2025 2026
```

Por defecto va **día a día** (365 puntos por año). En crudo el ruido diario se
come la señal: con dos años encima, las líneas se cruzan todo el rato y no se
puede decir cuál va por arriba. Para eso está `--suavizado 7`, que aplica una
media móvil centrada y deja ver las olas de calor sin el temblor. Y con
`--resolucion mensual` se reduce a doce puntos por año, que es lo más limpio
para leer la tendencia aunque pierdas el detalle de cada episodio.

También puedes contar días de calor con el mapa de siempre:
`python -m aemet_noches todo --variable tmax --umbral 35`.

Opciones útiles:

| Opción | Para qué |
|---|---|
| `--variable tmax` | trabajar con la máxima del día en vez de la mínima |
| `--umbral 25` | otro listón, p. ej. «noches tórridas» (mínima ≥ 25 °C) |
| `--estricto` | cuenta `> 20` en vez de `>= 20` (ver más abajo) |
| `--tema oscuro` | paleta para fondo oscuro |
| `--nombre "Castelló"` | nombre a mostrar en el título |
| `--espera 3` | más segundos entre peticiones si AEMET te corta por ritmo |
| `--meses-por-lote 3` | tramos más cortos si la API rechaza el rango |

La descarga se cachea por tramos en `datos/crudos/`: si se corta a medias, la
vuelves a lanzar y sigue por donde iba. Con `--forzar` reescribe lo ya bajado.

## Ejecutarlo en GitHub (sin instalar nada)

Hay un workflow que hace todo en los servidores de GitHub y deja el resultado
commiteado en `resultados/`. Requiere un paso manual, una sola vez:

1. Ve a **Settings → Secrets and variables → Actions → New repository secret**.
2. Nombre: `AEMET_API_KEY`. Valor: tu clave de AEMET.
3. Pestaña **Actions → Mapas de calor de AEMET → Run workflow**. Desde el
   formulario se cambian estación, años, variable (`tmin`/`tmax`), umbral y
   firma.

Cada tirada deja en el repo dos carpetas, y así una no pisa a la otra:

- `resultados/min20/` — el conteo, con su `datos.csv`, `resumen.txt` y los
  mapas en claro y oscuro. El nombre sale del umbral: `min25`, `tmax35`…
- `resultados/anomalias_tmax/` — el mapa de anomalías de esa variable.

Lo mismo va como artefacto descargable del run. La descarga de AEMET se cachea
entre ejecuciones, así que a partir de la segunda vez tarda segundos.

### Recibirlo por Telegram

Si añades dos secretos más, cada tirada te manda los gráficos a un chat:

1. Habla con [@BotFather](https://t.me/BotFather), `/newbot`, y guarda el token
   como secreto `TELEGRAM_BOT_TOKEN`.
2. Escríbele algo a tu bot (si no, no puede contestarte) y saca tu chat con
   `curl "https://api.telegram.org/bot<TOKEN>/getUpdates"`. El número de
   `chat.id` va en el secreto `TELEGRAM_CHAT_ID`. Para un grupo, mete el bot en
   el grupo y usa el id negativo que aparezca ahí.

Sin esos secretos el paso no falla: avisa y sigue. Las imágenes van como
**documento**, no como foto, porque Telegram recomprime las fotos y estos
gráficos llevan texto de 5 pt que se volvería ilegible.

La tirada mensual ejecuta `scripts/generar_lote.sh`, que genera el juego
completo (noches tropicales, tórridas, días de 35, anomalías de mínima y
máxima, y las líneas), y envía los seis gráficos principales.

### Vigilancia diaria del top 10

Un segundo workflow (`vigilancia.yml`) corre **todos los días**: actualiza los
datos, recalcula la clasificación de mínimas y **solo si entra una fecha nueva
en el top 10** manda la tabla por Telegram y guarda el ranking actualizado en
el repo. Si no hay novedad no envía nada ni commitea: el silencio es el caso
normal.

Dos cosas que conviene saber:

- **AEMET publica los valores climatológicos diarios con unos días de
  retraso**, porque pasan por validación. El aviso llega cuando el dato es
  firme, no la misma noche del récord.
- La primera vez que corre, si no hay un ranking anterior con el que comparar,
  no avisa de nada: crea la base y calla. Si no, anunciaría doce récords de
  golpe.

Con `forzar_envio` se manda la tabla aunque no haya novedades, para comprobar
que el circuito funciona.

El workflow mensual está programado **el día 3 de cada mes**. GitHub solo lanza los
`cron` desde la rama por defecto del repositorio, así que si algún día mueves
esto a otra rama, la tirada mensual se queda muda hasta que la fusiones.

## Detalles que importan

**La definición.** Lo estándar (OMM, y lo que usa AEMET en sus informes) es
*mínima ≥ 20,0 °C*, y es lo que hace el programa por defecto. «Superior a 20»
en sentido literal sería `> 20`, que deja fuera los días de mínima exactamente
20,0; para eso está `--estricto`. La diferencia suele ser de pocas noches al
año, pero conviene decir cuál usas cuando enseñes el gráfico.

**La noche se cuenta en el día en que AEMET registra la mínima**, que es la del
día climatológico completo. Una noche a caballo entre dos días cuenta una vez,
no dos.

**Los huecos son la trampa principal.** Si a un año le faltan observaciones, su
recuento sale corto y en el gráfico parecería un año fresco. Por eso el CSV
lleva `dias_con_dato` y `cobertura`, los meses sin observaciones salen rayados
en el mapa y los años con menos del 90 % de días observados van marcados con
asterisco. Míralo antes de sacar conclusiones de una tendencia.

**La estación.** `8500A` es *Castelló de la Plana / Almassora*, la de serie más
larga de la zona. Ojo: los observatorios se mudan, cambian de instrumental y de
entorno urbano, y esas cosas dejan escalones en la serie. Esto cuenta lo que
midió el termómetro, no es una serie homogeneizada.

## Qué genera

- `salida/anomalias.csv` — media mensual, anomalía, media anual y récord del
  año, más la fila `normal` con la referencia usada.
- `salida/noches_tropicales.csv` — una fila por año: total, desglose de los doce
  meses, días con dato y cobertura (más el desglose mensual de días con dato).
- `salida/mapa_calor.png` — el mapa de calor: filas = años, columnas = meses,
  color = noches tropicales de ese mes, y el total del año en la columna de la
  derecha (en negro, porque es otra escala y no debe compartir el color).

## Pruebas

```bash
pip install pytest && python -m pytest tests -q
```

No tocan la red: comprueban el recuento, el manejo de la coma decimal y las
marcas de AEMET (`Ip`), la cobertura y el troceado de fechas.
