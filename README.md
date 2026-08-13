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

Opciones útiles:

| Opción | Para qué |
|---|---|
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
3. Pestaña **Actions → Mapa de calor de noches tropicales → Run workflow**.
   Puedes cambiar estación, años y umbral desde el propio formulario.

Al terminar tendrás en el repo `resultados/mapa_calor_claro.png`,
`resultados/mapa_calor_oscuro.png`, `resultados/noches_tropicales.csv` y
`resultados/resumen.txt`, más los mismos ficheros como artefacto descargable
del run. La descarga de AEMET se cachea entre ejecuciones, así que la segunda
vez tarda segundos.

El workflow también está programado el día 3 de cada mes, pero **GitHub solo
lanza los `cron` desde la rama por defecto**: hasta que esta rama no se
fusione, solo funcionará el botón de *Run workflow*.

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
