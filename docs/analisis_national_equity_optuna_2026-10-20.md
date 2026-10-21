# National Equity: análisis exhaustivo del Optuna de umbrales

## Dictamen

El trial 144 muestra discriminación retrospectiva moderada y separación de
retornos entre las señales. Es un candidato experimental. La evidencia no
justifica adoptar sus umbrales como definitivos ni interpretar +7.252 puntos
porcentuales como una ventaja realizable de cartera.

Las razones principales son la concentración de resultados en pocas salidas,
sensibilidad a umbrales y etiquetas, selección sobre el mismo período evaluado,
solapamiento de retornos y una métrica que incluye el tramo de valorización
anterior a la decisión. Al aislar el tramo posterior, la diferencia compuesta
pasa a ser negativa.

## Datos y reproducción

Se leyeron los 300 trials del reporte aportado y se reconstruyó el ganador
desde su dataset guardado. Se reprodujeron accuracy, balanced accuracy, AUC,
número de salidas, diferencia compuesta y score con tolerancia absoluta de
1e-10. No se modificaron configuraciones, noticias ni modelos operativos.

```bash
MPLCONFIGDIR=/tmp/national_equity_mpl \
python scripts/analyze_national_equity_optuna.py \
  xgboost_outputs/diagnostics/national_equity_nueva_revision
```

Elegir un directorio nuevo. La ejecución terminada está en
`xgboost_outputs/diagnostics/national_equity_optuna_2026-10-20_v2/`.
Incluye hashes de los archivos de entrada, predicciones, diagnósticos, gráfico
y métricas tabuladas. No utiliza decisiones de octubre; los objetivos de los
últimos días de septiembre ya incluyen cuotas de octubre.

El modelo usa XGB base: 500 árboles, learning rate 0.03, profundidad 3,
min_child_weight 5, gamma 0.5, subsample/colsample 0.8, lambda 5, alpha 0.1,
hist, semilla 42. La reproducción usa cuatro hilos; el entrenamiento original
usa todos los disponibles. El entrenamiento tiene 192 positivos y 226
negativos: scale_pos_weight = 226/192 ≈ 1.17708.

Precaución de reproducción: CSV infiere como numéricos algunos campos CMF que
el loader original mantiene como texto. El script restaura esos tipos antes
de seleccionar columnas, evitando añadir variables que el ganador no utilizó.
El resultado conserva exactamente sus 627 variables.

## Qué predice el modelo

- Escenario: `cmf_date_news`, publicación supuesta con desfase de un día calendario.
- Noticias: día completo de la fecha de la cuota conocida.
- Objetivo: cuota de dos días hábiles después de la decisión / cuota conocida − 1.
- Clase positiva: retorno estrictamente superior a 0.004764, es decir, 0.4764 %.
- Señal mantener: probabilidad de esa clase mayor o igual a 0.2253.

La clase negativa incluye pérdidas, retornos cero y ganancias de hasta 0.4764 %.
Por tanto, los nombres heredados de las métricas «no sube/baja» o «salida
correcta» deben interpretarse respecto del objetivo, no del cero.

Un umbral de probabilidad de 0.2253 no es una tasa de acierto ni una probabilidad
calibrada garantizada. Se seleccionó para maximizar el score en junio–septiembre.

## Alineación temporal

Las comprobaciones sobre el dataset pasan: cuotas disponibles según la política
configurada, noticias alineadas a la fecha de cuota, retorno coherente con sus
cuotas y etiquetas del entrenamiento disponibles al cierre del entrenamiento.
En las 122 decisiones evaluadas, la cuota conocida es exactamente del día anterior.

Hay 418 filas entrenables. Aunque el corte solicitado es el 31/05, la última
decisión incluida en entrenamiento es el 27/05 y la última disponibilidad de
etiqueta es el 30/05. Se excluyen cuatro decisiones finales por falta de etiqueta
disponible al cierre.

La evaluación tiene 122 decisiones: 88 en lunes–viernes y 34 en fin de semana.
Solo hay 88 fechas objetivo diferentes: varias decisiones comparten salida.
No son 122 operaciones independientes.

El calendario no contiene feriados. Se validó su implementación, no su
correspondencia con las condiciones operativas reales del fondo ni con horas
históricas de publicación CMF. El dataset tampoco acredita versiones de noticias
disponibles en cada instante histórico.

La última fecha objetivo es el 02/10 y su disponibilidad supuesta es el 03/10.
Esto precisa la reserva de octubre propuesta antes: los primeros días de octubre
ya intervienen como etiquetas de decisiones de septiembre. Un corte conservador
posterior a ese solapamiento comienza el 04/10; ese período todavía requeriría
historia suficiente y no debería reutilizarse para seleccionar más parámetros.

## Clasificación y retornos por señal

| Resultado real | Señal salir | Señal mantener | Total |
| --- | ---: | ---: | ---: |
| Retorno ≤ 0.4764 % | 21 | 50 | 71 |
| Retorno > 0.4764 % | 10 | 41 | 51 |
| Total | 31 | 91 | 122 |

Accuracy 50.82 %, balanced accuracy 54.98 %, precision positiva 45.05 %,
recall positivo 80.39 %, F1 57.75 % y AUC 0.6211.

Mantener siempre tiene accuracy 41.80 %. Predecir siempre la clase negativa
alcanza 58.20 %, pero pierde todas las oportunidades de la clase positiva y
su métrica de estrategia queda en cero. Accuracy por sí sola no resuelve el
objetivo económico.

Las señales mantener capturan 41/51 oportunidades superiores al objetivo y
descartan 10. Entre las 31 salidas, 21 están por debajo del objetivo; de esas
31, solo 18 tienen pérdida efectiva y 13 tienen retorno positivo. El modelo
señala salir en 18 de las 58 ventanas negativas: quedan 40 pérdidas dentro de
las señales mantener.

| Grupo | Media | Mediana | Mínimo | Máximo |
| --- | ---: | ---: | ---: | ---: |
| Mantener, 91 filas | +0.2976 % | +0.2767 % | −3.5788 % | +5.6184 % |
| Salir, 31 filas | −0.1782 % | −0.2199 % | −2.5860 % | +2.1252 % |

La separación media es +0.4758 puntos porcentuales. Es una señal favorable
descriptiva, con errores relevantes en ambas direcciones.

## Qué significa el score

El código usa:

`score = mejora_compuesta + 0.5 × retorno_estrategia + 0.5 × (media_mantener − media_salir)`

Para el ganador no se activan las penalizaciones por pocas señales o separación
invertida. Sus contribuciones son:

| Término | Contribución |
| --- | ---: |
| Diferencia frente a mantener | 0.07251954 |
| Mitad del retorno compuesto de estrategia | 0.14827201 |
| Mitad de la separación de medias | 0.00237882 |
| Total | 0.22317037 |

El nombre `risk_adjusted` no implica Sharpe, control de volatilidad ni máximo
drawdown. Ninguno de esos términos aparece en la fórmula.

197/300 trials tienen score positivo, pero solo 85/300 superan a mantener en
la métrica compuesta. Un score positivo no prueba mejora. En este ganador sí
hay diferencia positiva y también es el trial con mayor diferencia compuesta.

## Rentabilidad reportada y limitación de ejecución

El producto de ventanas da 22.4024 % para mantener y 29.6544 % para la estrategia:
diferencia +7.2520 puntos porcentuales. Cada ventana va desde la cuota conocida
hasta su fecha objetivo y puede solaparse con varias otras. No constituye una
serie de retornos diarios de una cartera.

Además, al predecir salir el código sustituye por cero todo ese retorno. Esto
incluye el tramo anterior a la decisión y el plazo mientras se tramitaría el
retiro. No modela una salida efectiva, permanencia en efectivo, reentrada,
costos ni capital ya comprometido por decisiones anteriores.

Se reconstruyó como diagnóstico la cuota del día de decisión a partir de los
valores históricos guardados. Es una etiqueta retrospectiva: no se añadió como
variable del modelo. Se cumple:

`1 + retorno_total = (1 + retorno_cuota_conocida_a_decisión) × (1 + retorno_decisión_a_objetivo)`

| Señal | Media cuota conocida → decisión | Media decisión → objetivo |
| --- | ---: | ---: |
| Mantener | +0.12125 % | +0.17567 % |
| Salir | −0.25037 % | +0.07202 % |

Las salidas se concentran en ventanas con un tramo previo negativo. Después
de la decisión, su media ya es positiva. Conservando las mismas 91/31 señales
y usando únicamente el tramo posterior, la métrica da 18.8660 % para mantener
y 16.4294 % para la estrategia: **−2.4366 puntos porcentuales**.

Este cálculo posterior sigue solapando ventanas y supone retorno cero en las
salidas: tampoco es una simulación ejecutable. Sí demuestra que +7.2520 pp no
se mantiene al cambiar el punto de partida a la fecha de decisión. El objetivo
puede ser útil para pronosticar el valor de rescate respecto de la última cuota;
su interpretación como beneficio de ejecutar una salida requiere otra evaluación.

## Distribución mensual sin reentrenar

Se segmentaron las predicciones del único modelo entrenado hasta mayo. No se
hicieron cuatro entrenamientos mensuales.

| Mes | Filas | AUC | Salidas | Media de retorno en salidas | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: | ---: | ---: |
| Junio | 30 | 0.3801 | 6 | +0.2566 % | −1.7089 pp |
| Julio | 31 | 0.7325 | 13 | +0.2014 % | −2.8283 pp |
| Agosto | 31 | 0.7875 | 8 | −0.8141 % | +7.5475 pp |
| Septiembre | 30 | 0.5550 | 4 | −0.7923 % | +2.8604 pp |

La mejora aparece en la segunda mitad. Julio muestra que un AUC alto puede
convivir con una mala decisión económica al umbral elegido. Septiembre muestra
que pocas salidas favorables pueden mejorar la métrica con clasificación débil.
No sumar las diferencias compuestas mensuales.

## Concentración y solapamiento

Las tres salidas con mayor contribución corresponden al 24/09 (−2.5860 %),
11/08 (−2.5077 %) y 10/08 (−2.4739 %). Las dos de agosto se solapan: no son
dos episodios de mercado independientes.

Al reemplazar retrospectivamente las mejores señales salir por mantener,
sin cambiar las demás decisiones:

| Salidas favorables reemplazadas | Diferencia compuesta restante |
| --- | ---: |
| Ninguna | +7.2520 pp |
| La mejor | +3.8991 pp |
| Las tres mejores | −2.3143 pp |
| Las cinco mejores | −6.5510 pp |

Esto mide concentración, no demuestra por sí solo que el modelo sea inútil:
estrategias de protección pueden depender de evitar pocos eventos grandes.
Aquí exige evidencia adicional porque los eventos se seleccionaron entre 300 trials.

Como prueba complementaria se tomaron ventanas sin solapamiento entre cuota
inicial y objetivo mediante selección cronológica voraz. La muestra iniciada
en la primera fila conserva 35 ventanas y 10 salidas; su diferencia es −3.1620 pp.
Desplazar el inicio entre cero y seis filas produce diferencias de −3.16 a
−3.30 pp. Son subconjuntos muy relacionados que convergen hacia las mismas
ventanas, no siete validaciones independientes ni una simulación operativa.

Separar decisiones de lunes–viernes y de fin de semana produce +10.4949 pp
y −3.4686 pp, respectivamente, también con ventanas solapadas. No son resultados
aditivos ni justifican eliminar fines de semana tras ver el resultado.

## Estabilidad de la búsqueda

Todos los 300 trials terminaron sin `failed_reason`. 85 (28.33 %) superan a
mantener y 215 no lo hacen. La diferencia mediana es −3.0498 pp, percentil 75
+0.5536 pp y percentil 95 +4.2249 pp. El ganador es único en score.

Los 20 mejores exploran objetivo 0.004612–0.005685 y probabilidad 0.2002–0.2437.
La concentración es orientativa: TPE adapta dónde prueba, por lo que esa
densidad no es una estimación de probabilidad de éxito.

Los 300 trials representan solo 60 patrones distintos de etiquetas combinando
train/evaluación y 51 patrones de entrenamiento. Los diez mejores solo contienen
tres patrones combinados. Los empates de los trials 168/182/186/191 corresponden
a problemas equivalentes y señales iguales; no son confirmaciones independientes.

En el ganador, cualquier objetivo en aproximadamente
`[0.0047483959263296, 0.0047665920800672)` produce las mismas etiquetas de
entrenamiento. La sexta cifra decimal del ganador no expresa precisión económica.

Con el modelo ganador fijo:

| Probabilidad | Salidas | Diferencia vs. mantener |
| --- | ---: | ---: |
| 0.2000 | 25 | +3.4773 pp |
| 0.2100 | 27 | +3.2870 pp |
| 0.2200 | 30 | +6.7032 pp |
| 0.2253 | 31 | +7.2520 pp |
| 0.2300 | 32 | +6.9892 pp |
| 0.2400 | 42 | +0.2460 pp |
| 0.2500 | 44 | −0.7174 pp |
| 0.3000 | 60 | −10.5226 pp |
| 0.5000 | 108 | −22.7593 pp |

Hay un entorno favorable alrededor de 0.22–0.23 para este modelo, pero no
estabilidad amplia. Se hizo además una cuadrícula retrospectiva de cinco
objetivos y tres probabilidades, manteniendo XGB base. Con probabilidad 0.2253,
objetivo 0.0046 cambia dos etiquetas de entrenamiento y da −1.4183 pp; objetivo
0.0049 también cambia dos y da −1.4750 pp; objetivo 0.0045 cambia seis y da
−7.6010 pp. La combinación concreta depende de pocas etiquetas.

Esta cuadrícula es diagnóstico sobre el mismo período. No se promueve otro
ganador ni se presenta como nueva validación.

## Incertidumbre y calibración

Un bootstrap circular por bloques, con 4.000 remuestras para bloques de siete
y catorce días, da los siguientes intervalos percentiles descriptivos del 95 %:

| Bloque | AUC | Contribución logarítmica neta de salidas |
| --- | --- | --- |
| 7 días | 0.4838–0.7607 | −0.0951 a +0.2216 |
| 14 días | 0.4662–0.7759 | −0.0887 a +0.1980 |

Los intervalos contienen 0.5 en AUC y cero en contribución. Se remuestrea el
ganador ya seleccionado: no se repite Optuna en cada remuestra ni se corrige
la selección múltiple. No son evidencia de significancia del proceso completo,
ni los porcentajes de remuestras negativas constituyen p-valores.

El Brier es 0.2495 y logloss 0.7055. Usando una probabilidad constante igual a
la prevalencia del entrenamiento, son 0.2450 y 0.6831: el modelo no mejora esas
dos medidas de calidad probabilística frente a ese baseline. Esto puede
coexistir con AUC superior a 0.5: ordenar casos y calibrar probabilidades son
propiedades diferentes. La ponderación de clases también afecta su calibración.
Los intervalos de probabilidad extremos tienen muy pocas observaciones; no
permiten conclusiones firmes sobre calibración por tramo.

## Noticias frente a variables financieras

El modelo completo tiene 574 variables noticiosas y 53 financieras/de calendario.
Utiliza 292 variables noticiosas y 47 financieras en divisiones de árboles.
Las noticias suman 86.92 % de la importancia normalizada; este porcentaje no
es un aporte causal y depende del tamaño del grupo y de correlaciones.

Se entrenó una ablación financiera con las mismas filas, parámetros XGB base
y umbrales del ganador completo:

| Modelo | AUC | Salidas | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: |
| Completo | 0.6211 | 31 | +7.2520 pp |
| Solo financiero/calendario | 0.5109 | 44 | −5.0998 pp |

El bloque noticioso merece seguir investigándose en National Equity. Esta
comparación favorece una configuración seleccionada para el modelo completo:
no se optimizó el financiero por separado ni se evaluó en un período externo.
No demuestra valor incremental futuro de las noticias.

## Decisión de trabajo

Conservar `0.004764 / 0.2253` como candidato congelado para contrastes, sin
promoverlo al preset definitivo. Primero definir una evaluación compatible con
el instante de decisión y el plazo real de retiro, distinguiendo pronóstico del
valor de rescate de rentabilidad de ejecutar señales. Después comprobar
estabilidad con cortes temporales purgados y con un período posterior reservado.

Si se ajusta XGB usando junio–septiembre, ese período sigue siendo selección.
La comprobación externa debe permanecer fuera del tuning y del ajuste posterior
del umbral de probabilidad. Con la evidencia actual, más búsqueda puede elevar
el score retrospectivo sin resolver las limitaciones que explican este resultado.

Gráfico: `diagnostic.png`. Tablas: `monthly.csv`, `local_grid.csv`,
`fixed_model_probability_sensitivity.csv`, `concentration.csv`,
`nonoverlapping_windows.csv`, `calendar_slices.csv`, `calibration.csv`,
`importance.csv`, `financial_comparison_predictions.csv`,
`trials_with_label_signatures.csv`. Datos por decisión:
`winner_predictions.csv`, `exits_ranked.csv`. Resumen numérico: `summary.json`.
