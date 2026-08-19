#!/usr/bin/env bash
# Genera el juego completo de gráficos de una estación: los tres recuentos
# habituales, las anomalías de mínima y máxima, y las líneas diarias.
# Espera los datos ya descargados en datos/crudos/.
#
#   ESTACION=8500A DESDE=1990 CREDITO="Gráfico: ..." ./scripts/generar_lote.sh
set -euo pipefail

ESTACION="${ESTACION:-8500A}"
DESDE="${DESDE:-1990}"
CREDITO="${CREDITO:-}"
SUAVIZADO="${SUAVIZADO:-7}"
TEMAS=(claro oscuro)

comunes=(--estacion "$ESTACION" --desde "$DESDE")
if [ -n "$CREDITO" ]; then pintar=(--credito "$CREDITO"); else pintar=(); fi
if [ -n "${HASTA:-}" ]; then comunes+=(--hasta "$HASTA"); fi

contar() {  # variable umbral
  local variable=$1 umbral=$2 slug destino
  case "$variable" in
    tmax) slug="tmax${umbral}" ;;
    prec) slug="lluvia${umbral}" ;;
    *)    slug="min${umbral}" ;;
  esac
  destino="resultados/$slug"
  mkdir -p "$destino"
  echo "→ $destino"
  python -m aemet_noches calcular "${comunes[@]}" \
    --variable "$variable" --umbral "$umbral" \
    --csv "$destino/datos.csv" | tee "$destino/resumen.txt"
  for tema in "${TEMAS[@]}"; do
    python -m aemet_noches mapa --estacion "$ESTACION" \
      --variable "$variable" --umbral "$umbral" "${pintar[@]}" \
      --csv "$destino/datos.csv" --png "$destino/mapa_$tema.png" --tema "$tema"
  done
}

series() {  # variable
  local variable=$1 anom="resultados/anomalias_$1" lin="resultados/lineas_$1"
  mkdir -p "$anom" "$lin"
  echo "→ $anom y $lin"
  python -m aemet_noches anomalias "${comunes[@]}" --variable "$variable" "${pintar[@]}" \
    --temas "${TEMAS[@]}" --csv "$anom/datos.csv" --png "$anom/mapa_{tema}.png" \
    | tee "$anom/resumen.txt"
  local dibujo=("${comunes[@]}" --variable "$variable" "${pintar[@]}" --temas "${TEMAS[@]}")
  if [ -n "${DESTACAR:-}" ]; then dibujo+=(--destacar $DESTACAR); fi
  python -m aemet_noches lineas "${dibujo[@]}" --resolucion mensual \
    --png "$lin/mensual_{tema}.png"
  python -m aemet_noches lineas "${dibujo[@]}" --resolucion diaria \
    --png "$lin/diaria_{tema}.png"
  python -m aemet_noches lineas "${dibujo[@]}" --resolucion diaria \
    --suavizado "$SUAVIZADO" --png "$lin/diaria_suave_{tema}.png"
}

lluvia() {
  local destino="resultados/lluvia"
  mkdir -p "$destino"
  python -m aemet_noches lluvia "${comunes[@]}" "${pintar[@]}" --temas "${TEMAS[@]}" \
    --csv "$destino/datos.csv" --png "$destino/mapa_{tema}.png" \
    | tee "$destino/resumen.txt"
}

ranking() {  # variable
  local destino="resultados/rankings"
  mkdir -p "$destino"
  python -m aemet_noches extremos "${comunes[@]}" --variable "$1" --top 10 \
    "${pintar[@]}" --temas "${TEMAS[@]}" \
    --csv "$destino/top10_$1.csv" --png "$destino/top10_$1_{tema}.png" \
    | tee "$destino/top10_$1.txt"
}

contar tmin 20   # noches tropicales
contar tmin 25   # noches tórridas
contar tmax 35   # días de calor
series tmin
series tmax
ranking tmin     # las noches más cálidas de la serie
ranking tmax     # y los días más calurosos
contar prec 1    # días de lluvia
lluvia           # totales, rachas secas y torrencialidad
python scripts/generar_web.py
