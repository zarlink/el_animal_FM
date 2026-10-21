# National Equity: análisis de Optuna XGB con umbrales actuales

## Conclusión

El trial 29 mejora la clasificación frente a los hiperparámetros actuales
reentrenados en el mismo escenario, pero su comportamiento es casi siempre salir.
No justifica promover sus parámetros a producción: descarta la mayoría de las
oportunidades positivas y no supera a mantener en la métrica compuesta.

El problema principal que este experimento deja expuesto es la combinación de
modelo, probabilidades y umbral 0.516. El espacio XGB explorado produce entre
cero y quince señales mantener de 122 decisiones. Antes de ampliar ese espacio
hay que evaluar el umbral sobre candidatos XGB fijos, con separación temporal
entre selección y validación.

## Trabajo realizado y reproducción

Se revisaron los 300 trials. Se cargó el modelo guardado del trial 29 y se
reconstruyeron los trials 32 y 165. Se reprodujeron score, AUC, accuracy,
balanced accuracy y métricas compuestas con tolerancia absoluta de 1e-10.
Se reentrenaron además XGB base y los parámetros de `XGB_MODEL_CONFIG` actuales,
siempre con las mismas filas, variables y umbrales. No se cambiaron presets
ni se guardaron nuevos modelos operativos.

```bash
PYTHONPATH=src python scripts/analyze_national_equity_xgb.py \
  xgboost_outputs/diagnostics/national_equity_xgb_nueva_revision
```

La ejecución terminada está en
`xgboost_outputs/diagnostics/national_equity_xgb_2026-10-20/`.
El directorio de salida debe ser nuevo. Contiene hashes de los archivos de
entrada, comparaciones, predicciones por decisión, sensibilidad y resumen JSON.

## Qué se mantuvo fijo

- Decisión con última cuota publicada supuestamente un día después de su fecha
  y noticias completas de esa fecha: `cmf_date_news`, `same_day_close`.
- Horizonte de dos días hábiles posteriores a la decisión, sin feriados configurados.
- Objetivo: retorno superior a **0.0766 %**, no 0.766 % ni 0.4764 %.
- Probabilidad mínima para mantener: **0.516**.
- 418 filas de entrenamiento: 234 positivas y 184 negativas.
- 122 filas de evaluación: 64 positivas y 58 negativas.
- 627 variables: 574 de noticias y 53 financieras/de calendario.

El `scale_pos_weight` de 184/234 = 0.7863247863 se deriva de esas clases. No es
un hiperparámetro libre elegido por Optuna.

La búsqueda explícita de XGB se ejecuta aunque `tune=False`: este último controla
el tuning clásico. El mensaje `Usa XGB_MODEL_CONFIG: True` tampoco implica partir
de un modelo anterior ni garantiza incluir sus parámetros exactos en los trials.
Optuna entrena desde cero los parámetros sugeridos dentro de `XGB_SEARCH_SPACE`.

El nombre del modelo termina en `target0p0008` por redondeo del nombre a cuatro
decimales; su metadata y el entrenamiento conservan el objetivo exacto 0.000766.

## Matriz de confusión del trial 29

| Resultado real | Predice salir | Predice mantener | Total |
| --- | ---: | ---: | ---: |
| Retorno ≤ 0.0766 % | 55 | 3 | 58 |
| Retorno > 0.0766 % | 53 | 11 | 64 |
| Total | 108 | 14 | 122 |

La precisión del 78.57 % corresponde a 11 aciertos entre 14 señales mantener.
El recall del 17.19 % corresponde a 11 de las 64 oportunidades positivas.
Se pierden 53 de esas oportunidades, el 82.81 %.

La especificidad es 55/58 = 94.83 %. Balanced accuracy es la media de esa
especificidad y el recall: (94.83 % + 17.19 %)/2 = 56.01 %.
El modelo obtiene esa cifra con muy pocas señales mantener y alta cobertura de
la clase negativa, sin equilibrar la frecuencia de sus señales.

Hay 66 decisiones clasificadas correctamente, frente a 64 de mantener siempre:
solo dos aciertos adicionales, aunque distribuidos de forma distinta entre clases.
La balanced accuracy del baseline constante es 50 %.

## Resultado económico de las señales

Las ventanas mantener tienen retorno medio +0.5698 %; las ventanas salir,
+0.1257 %. El grupo descartado todavía tiene retorno positivo en promedio.

Las 108 salidas descartan 53 ventanas positivas. Las 14 señales mantener
incluyen tres pérdidas grandes: 01/06 −3.5788 %, 02/06 −2.7198 % y 29/09
−2.3081 %. Las dos de junio se solapan. En el grupo mantener, los once aciertos
promedian +1.5076 % y las tres pérdidas −2.8689 %.

Una precisión alta por conteo no garantiza que se capturen suficientes ganancias
ni que los errores tengan poca magnitud.

La métrica compuesta de estrategia es +8.0032 %, frente a +22.4024 % de mantener:
diferencia −14.3992 puntos porcentuales. Son productos de ventanas solapadas,
con retorno cero supuesto en salir, no rentabilidad realizable de cartera.

## Comparación bajo condiciones iguales

Los hiperparámetros actuales se reentrenaron con los mismos datos del experimento.
Esta tabla no evalúa un modelo legacy guardado ni implica sustituirlo automáticamente.

| Configuración | Balanced accuracy | AUC | Mantener | Retorno compuesto diagnóstico | Diferencia vs. mantener |
| --- | ---: | ---: | ---: | ---: | ---: |
| Preset XGB actual, reentrenado | 51.40 % | 0.5439 | 6 | −0.74 % | −23.14 pp |
| XGB base | 49.76 % | 0.5625 | 6 | −5.03 % | −27.43 pp |
| Trial 29 | 56.01 % | 0.5665 | 14 | +8.00 % | −14.40 pp |
| Trial 32 | 56.01 % | 0.6034 | 14 | +14.69 % | −7.71 pp |
| Trial 165 | 55.39 % | 0.5908 | 9 | +15.86 % | −6.55 pp |
| Mantener siempre | 50.00 % | 0.5000 | 122 | +22.40 % | 0 pp |

El trial 29 mejora al preset actual en este escenario y con el punto de corte
fijo. Eso no basta para adoptarlo: sigue por debajo de mantener y la selección
reutiliza el período evaluado.

No corresponde comparar directamente su AUC 0.5665 con el 0.6211 de la búsqueda
anterior de umbrales: aquella clasificaba retorno >0.4764 %, esta >0.0766 %.
Son etiquetas distintas, aunque las ventanas de retornos sean las mismas.

## Por qué empatan 29 y 32

Ambos producen exactamente la misma matriz: TN=55, FP=3, FN=53, TP=11. Por eso
empatan en accuracy, precisión, recall, F1 y balanced accuracy. La fórmula de
selección no usa magnitud de retornos ni AUC como desempate.

Las señales mantener coinciden en nueve fechas. Cada modelo tiene cinco señales
mantener exclusivas: diez decisiones difieren. Los distintos retornos de esas
fechas explican la diferencia de 6.69 pp entre sus métricas compuestas.

El trial 29 queda primero por ser el empate más temprano. El código ordena solo
por score de forma estable; no seleccionó 29 por superar económicamente a 32.
No es un error aritmético de Optuna. El objetivo deja el desempate sin resolver.

El trial 165 tiene la mejor métrica económica de toda la búsqueda, aun negativa.
El trial 44 tiene el mayor AUC (0.6474), pero diferencia compuesta −24.52 pp.
Ordenamiento, decisiones al umbral fijo y magnitud económica son criterios distintos.

## Lectura de los 300 trials

Todos terminaron sin `failed_reason`. Ninguno supera a mantener.
La diferencia compuesta mediana es −20.22 pp; el rango va de −29.73 a −6.55 pp.
La mediana de señales mantener es seis; el rango es cero a quince.

El score toma balanced accuracy y resta `0.02 + abs(media_salir - media_mantener)`
si la media de mantener no supera a la de salir. Se penalizaron 115 trials.
Los trials 29 y 32 no reciben penalización porque ambos separan esas medias en
el sentido exigido. La fórmula no exige que las salidas tengan retorno negativo
ni que la estrategia supere a mantener.

No existe una contradicción entre ganar esta búsqueda y perder frente al baseline:
se optimizó una métrica de clasificación con una condición de separación, no la
rentabilidad de ejecutar decisiones.

## Comportamiento temporal del ganador

Se segmenta un único modelo entrenado hasta mayo; no hay reentrenamiento mensual.

| Mes | AUC | Balanced accuracy | Mantener | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: | ---: |
| Junio | 0.4072 | 48.19 % | 4 | −14.88 pp |
| Julio | 0.7395 | 61.76 % | 4 | −6.35 pp |
| Agosto | 0.7689 | 55.88 % | 2 | −7.61 pp |
| Septiembre | 0.4027 | 58.60 % | 4 | +13.60 pp |

En septiembre, mantener tiene métrica −12.78 % y el modelo +0.83 %.
Su pequeña exposición ayuda en ese mes negativo; pierde gran parte de las
subidas de los tres meses anteriores. Ese resultado mensual no demuestra por
sí solo identificación del régimen bajista: una regla casi siempre en efectivo
también puede evitar buena parte de una caída.

La clasificación por ranking varía mucho por mes. No sumar diferencias compuestas
mensuales ni interpretarlas como operaciones independientes.

## Generalización y probabilidades

El trial 29 clasifica correctamente las 418 filas de entrenamiento: accuracy,
balanced accuracy y AUC de 1.0. En evaluación baja a 54.10 %, 56.01 % y 0.5665.
El preset actual también clasifica perfectamente su entrenamiento y generaliza
débilmente en este período. Es evidencia de una brecha importante compatible
con sobreajuste y/o cambio de distribución, sin identificar una causa única.

Respecto de XGB base, el ganador aumenta árboles de 500 a 900, profundidad de
3 a 4, learning rate de 0.03 a 0.0503 y reduce lambda de 5 a 1.03. Está en el
techo del rango de árboles y cerca del piso de lambda. Esto no justifica abrir
el espacio a todavía más capacidad cuando el entrenamiento ya es perfecto.

La probabilidad positiva promedio del ganador es 32.57 %, mientras la frecuencia
positiva observada es 52.46 %. Solo 14 probabilidades alcanzan 0.516.
Su Brier es 0.2932 y logloss 0.8224; una probabilidad constante igual a la
prevalencia del entrenamiento obtiene 0.2506 y 0.6944. Menor es mejor.
La ponderación de clases y el cambio temporal pueden contribuir al desacople,
pero no se atribuye causalmente a un solo parámetro.

Un bootstrap circular condicional al ganador, con 3.000 remuestras, produce:

| Bloque | Intervalo AUC 95 % | Intervalo balanced accuracy 95 % |
| --- | --- | --- |
| 7 días | 0.4274–0.7067 | 0.4975–0.6194 |
| 14 días | 0.4122–0.7211 | 0.5036–0.6154 |

Los intervalos son amplios y dependen del tamaño de bloque. No se repite la
búsqueda de 300 trials en cada remuestra, por lo que no corrigen el sesgo de selección.

## Diagnóstico del umbral: mismo objetivo y modelos fijos

Se evaluaron probabilidades ya producidas por los modelos, sin cambiar el objetivo
0.000766, reentrenar por cada umbral ni volver a ejecutar Optuna.

Con el trial 29, bajar el umbral a 0.28 produce 76 señales mantener y balanced
accuracy 56.79 %, pero la diferencia compuesta sigue ligeramente negativa:
−0.12 pp. Su mejor score de la cuadrícula se encuentra en 0.32 (57.27 %), con
diferencia −0.54 pp. Recalibrar la regla no garantiza mejora económica.

El trial 32 muestra un candidato más interesante:

| Probabilidad, trial 32 | Mantener | Balanced accuracy | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: |
| 0.516 | 14 | 56.01 % | −7.71 pp |
| 0.280 | 67 | 62.90 % | +9.70 pp |

En 0.28, su matriz es TN=34, FP=24, FN=21, TP=43. La precisión baja a 64.18 %,
pero captura 67.19 % de la clase positiva. Conserva muchas más oportunidades.
El preset XGB actual también presenta un candidato retrospectivo en probabilidad
0.12, con 85 señales mantener y diferencia +5.11 pp.

Estos puntos se identificaron mirando el mismo junio–septiembre ya explorado.
No se deben adoptar como nuevos umbrales definitivos. Confirman que la combinación
modelo/umbral merece una evaluación conjunta y que mantener 0.516 fijo puede
descartar modelos útiles a otro punto de corte.

El buscador actual `--optuna-threshold-search` entrena XGB base. No afina automáticamente
el umbral del trial 32 ni el del modelo guardado: para esa tarea hay que mantener
sus hiperparámetros o sus probabilidades fijos explícitamente.

## Noticias y medición posterior a decidir

El ganador utiliza 247 variables noticiosas y 42 financieras en divisiones.
Las noticias concentran 85.98 % de importancia normalizada; ese porcentaje no
es causal y depende de cuántas variables hay en cada grupo.

Una ablación financiera con parámetros del trial 29 obtiene AUC 0.4399 y
diferencia −9.74 pp, frente a AUC 0.5665 y −14.40 pp del completo. El mejor
ranking del completo tampoco implica mejor resultado económico al punto de corte.
Esta ablación no optimiza el modelo financiero por separado.

La limitación de retornos solapados y tramo ya transcurrido continúa vigente.
Con señales 0.516 fijas y retirando de cada retorno el tramo cuota conocida→decisión,
el trial 29 queda en −7.32 pp frente al baseline posterior y el 32 en −6.15 pp.
El candidato retrospectivo 32/0.28 conserva +8.30 pp en ese diagnóstico posterior.
Todos esos productos siguen solapando ventanas y suponiendo retorno cero en salir;
ninguno constituye una simulación del retiro con su plazo real.

La evaluación termina en decisiones del 30/09, cuyos objetivos alcanzan el 02/10,
disponibles supuestamente el 03/10. No se evaluaron decisiones de octubre.
La validación posterior debe purgar ese solapamiento y mantenerse fuera de más selección.

## Qué conservar y qué probar después

No sustituir todavía los parámetros actuales por el trial 29. Mantener el escenario
de noticias/cuota del día anterior y el objetivo 0.000766 durante la siguiente
comparación. Tratar preset actual, 29 y 32 como candidatos, estudiar su umbral de
probabilidad con selección temporal y congelar la combinación antes de una prueba
posterior reservada. No mezclar todavía con el futuro perfil `_dia`.

La evaluación debe distinguir clasificación, retorno posterior a decidir y ejecución
con plazo real de retiro. Una nueva búsqueda más grande usando otra vez el mismo
período no demostraría que el modelo generaliza.

Archivos: `summary.json`, `model_comparison.csv`, `monthly.csv`, `predictions.csv`,
`probability_sensitivity.csv`, `tied_trials_disagreements.csv`, `calibration.csv`,
`importance.csv` en el directorio de diagnóstico indicado arriba.

## Comando para la comparación mensual de candidatos

`scripts/compare_national_equity_candidates.py` conserva los hiperparámetros del
preset actual y de los trials 29 y 32 y el objetivo 0.000766. Reentrena desde
04/04/2025 con cierre al final del mes anterior a cada evaluación, excluyendo
las etiquetas aún no publicadas en ese cierre. Calcula 57 umbrales de probabilidad
por candidato, incluyendo la referencia 0.516, a partir de las mismas predicciones.
No reentrena por cada probabilidad. El ranking usa el promedio mensual del score
de balanced accuracy con penalización existente y desempata por AUC mensual medio.

```bash
python scripts/compare_national_equity_candidates.py \
  --train-start 2025-04-04 \
  --eval-start 2026-06-01 \
  --eval-end 2026-09-30 \
  --prob-min 0.05 --prob-max 0.60 --prob-step 0.01 \
  --output xgboost_outputs/diagnostics/national_equity_comparacion_mensual
```

El directorio de salida debe ser nuevo. Guarda `ranking.csv`,
`monthly_metrics.csv`, `predictions.csv`, `manifest.json` y un candidato
experimental en JSON. No modifica presets ni guarda modelos operativos.
Es diagnóstico retrospectivo: los hiperparámetros candidatos ya se seleccionaron
usando junio–septiembre. Se validaron las entradas reales sin entrenar y pasaron
tres pruebas de grilla, particiones mensuales y purga de etiquetas.
