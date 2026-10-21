# Escenarios de decisión con cuotas CMF atrasadas

Se seleccionan desde `09_xgboost_prediction.py`. La interfaz gráfica utiliza el
escenario predeterminado y los presets de cada fondo. Busca modelos compatibles
con el escenario, corte, umbrales y parámetros XGBoost actuales, entrenados antes
de la fecha de predicción. Los perfiles sin modelo compatible se muestran como
pendientes sin bloquear los demás fondos. El detalle de cada tarjeta indica el
escenario, corte de noticias y archivo del modelo utilizado.

La fecha automática sigue siendo la última fecha común con cuotas CMF de todos
los fondos y noticias enriquecidas de ambas fuentes. No anticipa la fecha por
la sola existencia de noticias más recientes.

## Dos escenarios comparables

Cada fila está indexada por el **día de decisión**, incluso si ese día todavía
no tiene una cuota CMF publicada.

| Escenario | Cuota y variables financieras | Noticias |
| --- | --- | --- |
| `cmf_date_news` | Última cuota disponible según el desfase configurado | Referenciadas a la fecha de esa cuota |
| `decision_date_news` | La misma última cuota disponible | Referenciadas al día de decisión |

Ambos comparten el objetivo, el plazo de retiro y el calendario cuando sus
configuraciones operativas coinciden. El modo de noticias sigue siendo independiente:
`same_day_close` incluye el día completo; `night_partial` usa la hora configurada;
`strict_lag` solo incluye antecedentes anteriores a la fecha de referencia elegida.

Para el identificador `crecimiento_balanceado`, ambos escenarios explícitos
usan `same_day_close` por defecto. El identificador independiente
`crecimiento_balanceado_dia` usa `decision_date_news` con `night_partial` a las
21:30 por defecto.
Para una decisión del 10 de septiembre de 2026 y un plazo de un día hábil:

| Campo | `cmf_date_news` | `decision_date_news` |
| --- | --- | --- |
| Fecha de decisión | 10 de septiembre | 10 de septiembre |
| Fecha de cuota conocida, desfase 1 | 9 de septiembre | 9 de septiembre |
| Fecha de referencia de noticias | 9 de septiembre | 10 de septiembre |
| Primer día hábil de retiro | 11 de septiembre | 11 de septiembre |
| Fecha objetivo | 11 de septiembre | 11 de septiembre |

El retorno objetivo es `cuota_fecha_objetivo / ultima_cuota_conocida - 1`.
No hay que aumentar manualmente el plazo de 1 a 2: las fechas ya representan
los dos días transcurridos entre la cuota del 9 y la cuota objetivo del 11.

El plazo 4 del Balanceado mantiene su significado de **cuatro días hábiles
posteriores a la decisión**. No se convierte en cinco días de retiro: el desfase
respecto de la cuota se incorpora por separado.

## Configuración por fondo

`crecimiento_balanceado_dia` es un perfil independiente que reutiliza los archivos
CMF de `crecimiento_balanceado`. Sin `--scenario`, selecciona `decision_date_news`
con noticias hasta las 21:30 (`night_partial`), desfase de publicación de un día
calendario y horizonte de cuatro días hábiles. Su búsqueda de umbrales utiliza
`night_partial` por defecto. Los umbrales y espacios de búsqueda se configuran
por separado; sus hiperparámetros XGBoost definitivos se añadirán a
`XGB_MODEL_CONFIG` después del tuning. Mientras tanto utiliza parámetros base.
Un `--scenario` explícito tiene precedencia sobre el predeterminado del perfil.

`national_equity_dia` reutiliza los archivos CMF, series, horizonte de dos días
hábiles, umbrales, hiperparámetros XGBoost y espacios Optuna de `national_equity`,
con entradas independientes en cada configuración. Su escenario predeterminado
es `decision_date_news`, con `same_day_close` y desfase de publicación de un día
calendario: al decidir el 20 con cuota del 19, incorpora las noticias completas
del 20. Si falta la cuota del 19, conserva la última cuota disponible y referencia
las noticias al día de decisión. Se selecciona con `--fund national_equity_dia`;
un escenario explícito tiene precedencia sobre el predeterminado.

`toesca_equity_dia` copia las configuraciones de `toesca_equity` en entradas
independientes y reutiliza sus archivos CMF, series y horizonte de dos días
hábiles. Su escenario predeterminado es `decision_date_news`, con desfase 1.
Conserva el corte original `night_partial` a las 21:30: al decidir el 20 con
cuota del 19, incorpora noticias del 20 hasta esa hora. Se selecciona con
`--fund toesca_equity_dia`; un escenario explícito reemplaza el predeterminado.
Los demás fondos conservan `legacy` como escenario predeterminado.

`prediction_config.py` contiene `FUND_SCENARIO_CONFIG`. Cada fondo puede tener
overrides independientes para los dos escenarios. Crecimiento Balanceado incluye
ambos perfiles con plazo 4 y desfase 1. Se pueden añadir, por ejemplo,
`probability_threshold`, `target_threshold`, `strict_return_lag`, `tune`,
`tune_iter` o `xgb_params` a cada perfil. Los parámetros no especificados heredan
el preset general del fondo; los overrides CLI tienen precedencia.

`quote_lag_days` es un desfase supuesto de **publicación en días calendario**.
Una cuota fechada el 9 se considera disponible desde el 10 con desfase 1.
Si falta esa observación, se utiliza la última observación anterior disponible.
No se conoce retrospectivamente la hora real de publicación: esta política debe
ajustarse si la disponibilidad real difiere.

El calendario utiliza `BUSINESS_WEEKMASK` (lunes a viernes por defecto) y
`BUSINESS_HOLIDAYS`. La lista de feriados empieza vacía: se deben configurar
las fechas aplicables a la operación; no se descarga un calendario chileno ni se
interpretan ausencias de cuotas como feriados.

La fecha objetivo es exacta. Si falta su cuota, el objetivo queda desconocido;
no se reemplaza por otra fecha ni por cero.

## Ejecución

Entrenar y evaluar ambos escenarios del Balanceado:

```bash
python 09_xgboost_prediction.py --fund crecimiento_balanceado --scenario both \
  --train-start 2025-04-04 --train-end 2026-06-30 \
  --eval-start 2026-07-01 --eval-end 2026-09-30
```

Con `both` se ejecuta un perfil por escenario, sin multiplicarlo automáticamente
por las tres modalidades anteriores. Para ejecutar uno, usar
`--scenario cmf_date_news` o `--scenario decision_date_news`.

Para modificar temporalmente el plazo o el desfase:

```bash
python 09_xgboost_prediction.py --fund crecimiento_balanceado \
  --scenario both --withdrawal-days 1 --quote-lag-days 1 \
  --train-start 2025-04-04 --train-end 2026-06-30 \
  --eval-start 2026-07-01 --eval-end 2026-09-30
```

`--business-holidays YYYY-MM-DD ...` reemplaza la lista configurada. Un ejemplo
de corte parcial es `--override-decision-mode night_partial --decision-time 23:59`.

Los dos escenarios también funcionan con `--optuna-threshold-search` y
`--optuna-xgb-search`: `both` crea estudios y archivos separados. Las fechas de
evaluación de Optuna sirven para seleccionar configuración, por lo que una
validación externa debe utilizar otro período posterior reservado.

`--predict-live-only` carga modelos guardados con la misma configuración y usa
filas por día de decisión, aunque todavía no exista la cuota de ese día.
Se deben repetir el escenario, los parámetros y las fechas de entrenamiento
con que se generó el modelo.

Con `--scenario legacy` se selecciona el flujo anterior basado en las fechas
de cuotas. Sin `--scenario`, se usa el escenario predeterminado del fondo:
`decision_date_news` para `crecimiento_balanceado_dia`, `national_equity_dia`
y `toesca_equity_dia`,
y `legacy` para los demás.
Los resultados de legacy no son intercambiables con los de los nuevos escenarios.

## Prevención de información futura y trazabilidad

- Las variables financieras se calculan sobre la serie histórica y se unen
  por la fecha supuesta de disponibilidad, nunca por una cuota aún no publicada.
- La fecha futura y su cuota se usan como etiquetas, no como variables del modelo.
- El entrenamiento excluye etiquetas cuya cuota objetivo todavía no se habría
  publicado al término del rango de entrenamiento. El tuning interno aplica
  esa misma separación en su propio corte temporal.
- Las filas sin objetivo conocido se conservan para predicción y se excluyen de
  entrenamiento y métricas, incluidas las búsquedas de Optuna.
- Modelos, datasets y reportes identifican escenario, horizonte y una huella de
  calendario, desfase y corte. Una configuración incompatible no se carga como
  si correspondiera al modelo solicitado.
- Los CSV incluyen `decision_date`, `quote_date`, `quote_available_date`,
  `news_reference_date`, `withdrawal_start_date`, `future_exit_date` y
  `target_available_date`.

Los retornos objetivo parten de la cuota conocida, que puede corresponder a un
período ya transcurrido. Las métricas compuestas heredadas agregan ventanas que
pueden solaparse: no representan una simulación de ejecución de retiros ni una
rentabilidad realizable de cartera.

## Avances de exploración para retomar la conversación

Registro de la sesión del 19/10/2026. El contexto completo está en
[`contexto_reentrenamiento_crecimiento_balanceado.md`](contexto_reentrenamiento_crecimiento_balanceado.md).
Estos resultados son experimentales; no se adoptaron nuevos umbrales ni se
agregaron hiperparámetros definitivos de `_dia` a `XGB_MODEL_CONFIG`.

### Búsquedas de umbrales del perfil independiente

Se ejecutaron 300 trials por búsqueda, con escenario `decision_date_news`,
modo `night_partial` a las 21:30, desfase 1, horizonte 4 y score `risk_adjusted`.
El inicio de entrenamiento fue 04/04/2025 y el fin solicitado de evaluación,
18/10/2026.

| Entrenamiento hasta | Evaluación desde | Mejor objetivo | Probabilidad | Train / eval | Score | Mantener / salir | Diferencia compuesta vs. mantener |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 30/08/2026 | 01/09/2026 | 0.003078 | 0.2001 | 507 / 41 | -0.012445 | 17 / 24 | -4.8546 pp |
| 31/05/2026 | 01/06/2026 | 0.000458 | 0.2168 | 416 / 133 | 0.166552 | 131 / 2 | +0.2235 pp |

La primera búsqueda exploró objetivo `[0, 0.01]` y probabilidad `[0.20, 0.80]`.
Ningún trial superó a mantener según la métrica compuesta; el mejor quedó en
el límite inferior de probabilidad. AUC del ganador: 0.378571.

La segunda exploró objetivo `[0, 0.004]` y probabilidad `[0.05, 0.40]`.
Hubo 42 trials empatados en el mejor score. Su matriz fue TN=1, FP=43, FN=1,
TP=88; accuracy 0.669173, balanced accuracy 0.505746 y AUC 0.393514.
La mejora dependía de solo dos salidas, con retorno objetivo promedio
-0.0008407032. El trial 112 tuvo la mayor mejora compuesta (+0.4132 pp), pero
con una sola salida. El score ganador se explica principalmente por su término
de retorno absoluto, no por una gran mejora frente a mantener.

Los reportes de estas búsquedas están en `xgboost_outputs/reports/`, con prefijos
`optuna_threshold_trials_crecimiento_balanceado_dia_2025-04-04_2026-08-30_eval_2026-09-01_2026-10-18_`
y `optuna_threshold_trials_crecimiento_balanceado_dia_2025-04-04_2026-05-31_eval_2026-06-01_2026-10-18_`,
ambos terminados en `decision_date_news_f611946e83ec.csv`.

### Comparación mensual con entrenamiento creciente

El usuario ejecutó `bash multiples_escenarios.bash`. Se fijaron objetivo
`0.000458` y probabilidad `0.2168`, sin Optuna, sin tuning y con
`--no-fund-xgb-config --single-preset-run`. Se compararon, bajo el mismo
identificador `crecimiento_balanceado_dia`:

- `cmf_date_news` con `same_day_close`: noticias del día de cuota completo.
- `decision_date_news` con `night_partial` a las 21:30: noticias recientes.

Se entrenó siempre desde 04/04/2025, cerrando el entrenamiento al final del
mes anterior y evaluando el mes siguiente. Los cortes fueron junio, julio,
agosto, septiembre y octubre hasta el 18. Octubre solo tuvo etiquetas hasta
el 11; sus siete filas restantes quedaron para predicción live.

| Mes evaluado | Filas | Salidas cerrado / reciente | Diferencia vs. mantener cerrado / reciente | AUC cerrado / reciente |
| --- | --- | --- | --- | --- |
| Junio | 30 | 1 / 0 | -1.3198 / 0 pp | 0.2727 / 0.1875 |
| Julio | 31 | 0 / 0 | 0 / 0 pp | 0.4333 / 0.4333 |
| Agosto | 31 | 1 / 2 | -0.8644 / -1.9756 pp | 0.3393 / 0.5714 |
| Septiembre | 30 | 5 / 13 | -2.5978 / -3.8882 pp | 0.3333 / 0.5069 |
| Octubre, 1–11 | 11 | 0 / 0 | 0 / 0 pp | 0.3929 / 0.0714 |

Agregado de las matrices de las 133 observaciones:

| Resultado | Cerrado | Reciente |
| --- | --- | --- |
| TN / FP / FN / TP | 0 / 44 / 7 / 82 | 3 / 41 / 12 / 77 |
| Salidas | 7 | 15 |
| Accuracy | 61.65 % | 60.15 % |

Mantener siempre acertaba 89/133 (66.92 %). Ningún escenario superó a mantener
en ningún corte mensual. Las siete salidas del cerrado descartaron retornos
superiores al objetivo; en el reciente ocurrió con doce de quince salidas.
Una etiqueta negativa significa retorno menor o igual a 0.0458 %, no
necesariamente una pérdida. No sumar las diferencias compuestas mensuales ni
interpretarlas como rentabilidad de una cartera.

### Conclusiones y próximo paso acordado como propuesta

- La pequeña mejora de la búsqueda con un modelo entrenado hasta mayo no se
  sostuvo al reentrenar mensualmente. Los umbrales no muestran estabilidad bajo
  ese esquema; esto no prueba que todo reentrenamiento mensual sea perjudicial.
- El perfil reciente no ha demostrado una ventaja consistente. El corte de
  septiembre genera muchas más salidas sin mejora económica de la métrica.
- Los umbrales se seleccionaron usando junio–octubre. Los cortes son un
  diagnóstico retrospectivo, no una prueba independiente de la selección.
- Se usaron umbrales elegidos para el escenario reciente y parámetros XGBoost
  base en ambos escenarios. No es una evaluación del modelo cerrado propio ya
  reentrenado por el usuario ni de la mejor configuración posible de cada uno.
- Antes de más Optuna, se propuso revisar alineación temporal, importancia y
  utilización efectiva de variables de noticias frente a financieras, y
  comparar con un modelo exclusivamente financiero. Ese análisis NO se ha
  realizado todavía y el usuario aún no solicitó implementarlo.
- No se deben promover `0.000458 / 0.2168` como parámetros definitivos con la
  evidencia actual. Sigue pendiente seleccionar y validar hiperparámetros
  propios de `crecimiento_balanceado_dia`.

### Revisión realizada el 20/10/2026

Se realizó la auditoría temporal y comparación mensual completo/solo financiero
con objetivo `0.00053` y probabilidad `0.367`, ambos provisionales. El financiero
obtuvo mayor AUC en los cinco meses, sin demostrar una mejora estable frente a
mantener. Se encontraron noticias de BioBio asignadas a carpetas anteriores a
su publicación y fechas mal interpretadas en El Mostrador. La comparación queda
condicionada por esos problemas; se deben corregir los datos antes del tuning.
Detalles, límites y reproducción en
[`auditoria_temporal_noticias_2026-10-20.md`](auditoria_temporal_noticias_2026-10-20.md).

Después se revisó y reparó el archivo completo de ambas fuentes: fechas/carpetas,
duplicados por URL, URLs dañadas y referencias HTML. La verificación final no
detecta duplicados ni ubicaciones incorrectas. Falta actualizar los enriquecidos
que difieren del original y reconstruir las entradas XGB antes de repetir la
comparación. Ver
[`revision_integridad_noticias_2026-10-20.md`](revision_integridad_noticias_2026-10-20.md).

## Semáforo operativo (regla actualizada el 21/10/2026)

El color combina una señal del modelo con tres filtros técnicos:
`momentum_10 > 0`, `valor_cuota_vs_ma20 > 0` y `drawdown_20 > -0.04`.
El modelo es favorable si `pred_up == 1` y
`pred_prob_up >= probability_threshold`. Si alguna comprobación falla, se
considera desfavorable. En el flujo normal, `pred_up` se deriva de esa misma
comparación de probabilidad: ambas comprobaciones cuentan como una sola señal
para asignar el color, evitando duplicar su peso.

La clase positiva representa superar el retorno objetivo configurado; una señal
desfavorable no implica necesariamente que se pronostique una pérdida.

- Verde: modelo favorable y los tres filtros técnicos favorables.
- Rojo: fallan los tres filtros técnicos, o el modelo es desfavorable y fallan
  al menos dos filtros técnicos.
- Amarillo: todas las demás combinaciones.

La tabla cubre todas las combinaciones de respaldo del modelo y filtros técnicos:

| Filtros técnicos favorables | Modelo favorable | Modelo desfavorable |
| --- | --- | --- |
| 3 | Verde | Amarillo |
| 2 | Amarillo | Amarillo |
| 1 | Amarillo | Rojo |
| 0 | Rojo | Rojo |

Por ejemplo, un modelo favorable con momentum negativo, cuota bajo su media y
caída desde el máximo igual o peor que −4 % ahora genera rojo. Antes podía
quedar amarillo por los dos puntos derivados de la misma señal del modelo.
Los límites técnicos son estrictos: momentum cero, cuota igual a su media o
`drawdown_20 == -0.04` no cumplen sus respectivos filtros.

`entry_score` conserva la suma histórica de cinco condiciones por compatibilidad
con los CSV y la interfaz; ya no determina el color. Las decisiones asociadas
se detallan a continuación:

| Color | Si se está fuera (`decision_if_out`) | Si se está dentro (`decision_if_in`) |
| --- | --- | --- |
| Verde | `entrar` | `mantener` |
| Amarillo | `esperar` | `mantener_con_alerta` |
| Rojo | `esperar` | `salir_o_mover_defensivo` |

La implementación está en `build_entry_semaforo`, dentro de
[`prediction_output.py`](../src/el_animal_fm/prediction/application/signals/prediction_output.py).

La regla se aplica al generar nuevas predicciones, sin reentrenar el modelo ni
reescribir CSV anteriores. Es una política operativa pendiente de validación
temporal, no una conclusión de rentabilidad de los análisis anteriores.
