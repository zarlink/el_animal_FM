# National Equity: comparación mensual de modelos y probabilidades

## Conclusión

Entre los tres candidatos y para el criterio declarado, los hiperparámetros del
preset actual son preferibles a los trials 29 y 32. El umbral 0.35 mejora la
clasificación frente a 0.516, pero todavía no muestra una mejora económica
consistente. Se conserva como candidato experimental, no como parámetro validado.

No se justifica otro barrido sobre junio–septiembre para intentar fabricar una
mejora. Ese período ya participó en selección de objetivos, XGB y probabilidades.
El siguiente contraste debe respetar el esquema de reentrenamiento previsto y
separar selección de validación posterior.

## Qué se verificó

Se revisaron `ranking.csv` (171 combinaciones), `monthly_metrics.csv` (684 filas),
`predictions.csv` (366 filas: 122 por candidato) y `manifest.json` en
`xgboost_outputs/diagnostics/national_equity_comparacion_mensual/`.
Se reprodujeron la matriz y la diferencia compuesta del ganador desde sus
probabilidades guardadas. No se reentrenó ningún modelo ni se modificaron presets.

Los tres candidatos conservan hiperparámetros; sus pesos se vuelven a entrenar
cada mes. Las etiquetas todavía no publicadas se excluyen de cada entrenamiento.
Son cuatro modelos sucesivos por candidato, no el modelo único de mayo evaluado
durante cuatro meses. Se usan 418, 447, 480 y 509 filas entrenables.

## Cómo interpretar el ranking

El 0.592139 es el promedio mensual del score, no la balanced accuracy conjunta.
El score usa balanced accuracy con la penalización ya existente cuando la media
de mantener no supera a la de salir. El ordenamiento desempata por AUC mensual medio.

Para `preset_actual / 0.35`:

- Score mensual medio: **0.592139**.
- Balanced accuracy mensual media, sin penalizaciones: **0.598255**.
- Balanced accuracy conjunta de las 122 decisiones: **0.571121**.
- Accuracy conjunta: **0.573770**.
- AUC mensual medio: **0.576357**.
- AUC conjunta de las probabilidades de los cuatro modelos: **0.519397**.

Promediar métricas por mes y calcularlas sobre todas las filas produce resultados
distintos, especialmente cuando cambian las proporciones de clases y la escala de
probabilidades entre modelos. La AUC conjunta compara también probabilidades de
meses diferentes. No es un error aritmético.

El AUC no depende del umbral de decisión. Por eso los diez primeros renglones,
todos del mismo candidato, tienen exactamente el mismo AUC medio. Son umbrales
sobre las mismas probabilidades, no diez confirmaciones independientes.

## Comparación de candidatos

Se toma el umbral que gana por score mensual dentro de cada candidato:

| Candidato | Probabilidad | Score mensual medio | AUC mensual medio | Balanced accuracy conjunta | Mantener | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Preset actual | 0.35 | 0.5921 | 0.5764 | 57.11 % | 68 | −7.66 pp |
| Trial 32 | 0.29 | 0.5523 | 0.5145 | 53.96 % | 85 | −2.15 pp |
| Trial 29 | 0.34 | 0.5435 | 0.4705 | 53.50 % | 76 | −7.72 pp |

El preset gana por clasificación mensual, pero el trial 32/0.29 pierde menos
frente a mantener en la métrica compuesta. El ranking no optimiza esa diferencia.
No demuestra que el preset sea el mejor XGB posible: es el mejor entre estos tres
candidatos bajo este protocolo y criterio.

## Interpretación de las decisiones del ganador

| Resultado real | Salir | Mantener |
| --- | ---: | ---: |
| Retorno ≤ 0.0766 % | 30 | 28 |
| Retorno > 0.0766 % | 24 | 40 |

Hay 68 señales mantener y 54 salir. El modelo conserva 40 de 64 oportunidades
positivas (62.50 %) y clasifica correctamente 30 de 58 negativas (51.72 %).
La precisión de mantener es 58.82 %.

Clasifica correctamente 70/122 decisiones, frente a 64/122 de mantener siempre:
seis aciertos adicionales en el período seleccionado.

En esta evaluación las 54 salidas descartan 30 ventanas de pérdida y 24 ventanas
positivas. Su retorno medio sigue siendo +0.1277 %. El retorno medio en mantener
es +0.2156 %. La separación de medias es favorable, pero no basta para superar
a mantener.

El producto de ventanas da +14.7461 % para el modelo y +22.4024 % para mantener,
de donde salen −7.6563 puntos porcentuales. Las ventanas se solapan y salir
supone retorno cero: no es una cartera ejecutada.

Como comprobación adicional, usando solo el tramo fecha de decisión→objetivo,
las mismas señales dan +12.9486 % frente a +18.8660 %: diferencia −5.9174 pp.
Ese cálculo también conserva solapamientos y la hipótesis de retorno cero en salir.

## Detalle mensual del preset actual con probabilidad 0.35

| Mes | AUC | Balanced accuracy | Mantener / salir | Diferencia compuesta vs. mantener |
| --- | ---: | ---: | ---: | ---: |
| Junio | 0.4525 | 47.29 % | 6 / 24 | −11.21 pp |
| Julio | 0.6681 | 72.27 % | 12 / 19 | −1.41 pp |
| Agosto | 0.7731 | 69.75 % | 20 / 11 | +5.88 pp |
| Septiembre | 0.4118 | 50.00 % | 30 / 0 | 0 pp |

Solo agosto mejora la métrica compuesta. Septiembre empata porque mantiene
siempre, no porque aporte protección: reproduce el retorno del baseline, −12.78 %.
Julio clasifica bastante bien y aun así descarta suficiente retorno para quedar
ligeramente por debajo de mantener. No sumar diferencias compuestas mensuales.

El score de septiembre es 0.475536, aunque su balanced accuracy sea 0.5. Al
mantener siempre en un mes con media negativa, la fórmula compara esa media con
cero asignado al grupo vacío salir y aplica la penalización. Es el comportamiento
del score existente, no una estimación de retorno de salidas realmente observadas.

## Variación de probabilidades entre reentrenamientos

| Mes | Probabilidad media | Probabilidad mínima | Frecuencia positiva observada |
| --- | ---: | ---: | ---: |
| Junio | 0.2085 | 0.0090 | 56.67 % |
| Julio | 0.3066 | 0.0119 | 54.84 % |
| Agosto | 0.3949 | 0.0657 | 54.84 % |
| Septiembre | 0.7056 | 0.3820 | 43.33 % |

En septiembre la probabilidad mínima supera 0.35, de modo que todas las filas
producen mantener. El modelo está más optimista cuando la frecuencia positiva
observada es menor. Es un indicio de inestabilidad de calibración y/o de distribución,
sin identificar una causa única.

Un punto de corte fijo requiere que las probabilidades de los modelos sucesivos
conserven una interpretación razonablemente estable. Estos resultados ponen esa
condición en duda. Cualquier calibración futura debe aprenderse con datos pasados
separados o predicciones temporales fuera de muestra, nunca con las etiquetas del
mes que se pretende anticipar.

## Comparación con 0.516 y con el candidato anterior

Con reentrenamiento mensual y los mismos hiperparámetros actuales:

| Probabilidad | Score mensual medio | Balanced accuracy conjunta | Mantener | Diferencia vs. mantener |
| --- | ---: | ---: | ---: | ---: |
| 0.516 | 0.4867 | 47.52 % | 41 | −27.81 pp |
| 0.350 | 0.5921 | 57.11 % | 68 | −7.66 pp |

0.35 es claramente mejor dentro de este diagnóstico. Eso no convierte la mejora
relativa a una configuración débil en evidencia de ventaja frente a mantener.

El candidato trial 32/0.28 tenía balanced accuracy 62.90 % y diferencia +9.70 pp
con un único entrenamiento hasta mayo. Al reentrenarlo mensualmente pasa a
53.88 % y −0.39 pp. No sostuvo aquella ventaja bajo el nuevo esquema.
Esto no demuestra que el reentrenamiento mensual sea malo en general: muestra
que el resultado dependía del origen de entrenamiento y debe validarse con la
rutina que se utilizará realmente.

## ¿Hay umbrales que superen a mantener?

Hay 13 de 171 combinaciones con diferencia positiva, todas pequeñas:

- Trial 32/0.07: +0.7756 pp, 118 mantener y cuatro salir.
- Trial 29/0.15: +0.5070 pp, 105 mantener y diecisiete salir.
- Preset actual/0.11–0.13: +0.3714 pp, 99 mantener y veintitrés salir.

Los tres umbrales 0.11–0.13 producen las mismas decisiones, no tres evidencias
distintas. El mayor resultado económico depende de cuatro salidas. Elegir ahora
esas combinaciones sería otra selección usando el mismo período; no prueba una
ventaja estable.

El entorno 0.34–0.38 del ganador conserva scores mensuales relativamente próximos,
pero todas esas configuraciones siguen por debajo de mantener. La estabilidad
parcial de clasificación no implica estabilidad económica.

## Decisión de trabajo

Conservar los hiperparámetros actuales como referencia principal entre los tres
candidatos, y mantener fijo el objetivo 0.000766. Registrar 0.35 como probabilidad
experimental para la comparación posterior, con 0.516 como control. No promover
0.35 como definitivo ni adoptar los trials 29/32 con la evidencia actual.

Antes de repetir Optuna o construir conclusiones sobre `_dia`, fijar la rutina de
entrenamiento que se desea utilizar, revisar la estabilidad de probabilidades y
congelar la política para una comprobación posterior suficientemente amplia.
Los candidatos y sus umbrales ya fueron seleccionados con junio–septiembre.

La última etiqueta de septiembre llega al 02/10, disponible supuestamente el 03/10.
La comparación posterior debe purgar ese solapamiento y no volver a usarse para
retocar parámetros. Las métricas operativas deben respetar el plazo real de retiro.
