# Contexto para retomar el reentrenamiento de Crecimiento Balanceado

Actualizado: 19 de octubre de 2026.

## Punto actual de la conversación

Después de crear este contexto se realizaron dos búsquedas del perfil
independiente y una comparación mensual con entrenamiento creciente. El registro
detallado, con métricas y conclusiones, está en la sección «Avances de exploración
para retomar la conversación» de
[`prediction_scenarios.md`](prediction_scenarios.md). Leerla antes de continuar:
actualiza los siguientes pasos exploratorios descritos más abajo.

La búsqueda con entrenamiento hasta mayo eligió objetivo `0.000458` y
probabilidad `0.2168`, manteniendo 131/133 veces y mejorando solo +0.2235 pp la
métrica compuesta. Al fijar esos umbrales y reentrenar mensualmente de junio a
octubre, ninguno de los dos escenarios superó a mantener en ningún mes.
El cerrado generó 7 salidas, todas descartando retornos superiores al objetivo;
el reciente generó 15, de las cuales 12 descartaban retornos superiores al
objetivo. No se adoptaron estos umbrales como configuración definitiva.

La propuesta más reciente es diagnosticar alineación y aporte de noticias
frente a variables financieras y comparar con un modelo solo financiero antes
de seguir afinando Optuna. Ese diagnóstico aún no se ejecutó. No se trabajó UI.

## Lectura de `prediction_scenarios.md` incorporada a la conversación

Se leyó el documento completo a petición del usuario. Aclara que escenario y
modo de noticias son dos decisiones distintas: el escenario elige la fecha de
referencia; el modo determina si se usa el día completo, un corte horario o
solo antecedentes anteriores. Compartir escenario no significa compartir
umbrales ni modelo entre identificadores de fondos.

También establece que la cuota objetivo debe existir en la fecha exacta de
salida: no se sustituye por otra fecha. Las etiquetas no disponibles al corte
de entrenamiento se excluyen, también en el tuning interno. Las filas sin
objetivo se conservan para predicción, pero se excluyen de métricas y ajuste.
Los modelos incluyen una huella de escenario, horizonte, calendario, desfase y
corte; la predicción en vivo debe cargar una configuración compatible.

Al leerlo se encontraron dos frases antiguas ambiguas: «los dos perfiles usan
same_day_close» y «sin --scenario se conserva legacy». Se corrigieron para
distinguir los dos escenarios del identificador original del nuevo perfil
`crecimiento_balanceado_dia`, cuyo predeterminado es `decision_date_news` con
`night_partial` a las 21:30. No se cambió código ni se lanzó entrenamiento
como parte de esta actualización documental.

## Objetivo y decisiones del usuario

Después de varios meses se actualizó el diccionario de palabras utilizado para
procesar noticias. Por eso hay que volver a entrenar los fondos con las nuevas
variables. El usuario indica que ya reentrenó Crecimiento Balanceado para el
escenario de día completo cerrado; en esta sesión no se verificaron los
artefactos ni los resultados de ese reentrenamiento.

Ahora se busca explorar un segundo perfil del mismo fondo:
`crecimiento_balanceado_dia`. Debe tener identidad, umbrales, parámetros y
modelos propios, aunque utilice la misma serie CMF del fondo original.
El usuario pidió no enfocarse todavía en la interfaz gráfica.

El problema operativo es que las noticias pueden estar actualizadas mientras
la última cuota CMF conocida corresponde a un día anterior. Por ejemplo, el
lunes 19/10 a las 21:30 podría estar disponible solamente la cuota del viernes.
Se quiere incorporar las noticias posteriores a esa cuota sin usar cuotas aún
no disponibles ni confundir la fecha de cuota con la fecha de decisión.

## Dos escenarios existentes

Cada fila de los escenarios nuevos está indexada por fecha de decisión.

| Escenario | Cuota | Noticias de referencia |
| --- | --- | --- |
| `cmf_date_news` | Última cuota supuestamente disponible | Fecha de esa cuota |
| `decision_date_news` | La misma última cuota disponible | Fecha de decisión |

La intención del perfil cerrado es usar noticias del día de cuota completo
(`cmf_date_news` + `same_day_close`). La intención de `_dia` es incorporar
noticias recientes hasta las 21:30 (`decision_date_news` + `night_partial`).

Los cuatro días hábiles de retiro se cuentan después de la decisión. El retorno
objetivo se calcula como cuota de salida / última cuota conocida - 1. El desfase
de la cuota se incorpora mediante las fechas; no hay que aumentar manualmente
el horizonte a cinco. El intervalo total puede ser mayor y no equivale siempre
a cinco días calendario.

`quote_lag_days=1` significa un día calendario supuesto de publicación. No
representa una comprobación histórica de la hora real de publicación CMF.
Se usa la última observación disponible si falta la cuota esperada.
El calendario usa lunes a viernes y actualmente no tiene feriados configurados.

Las noticias de días anteriores ya están representadas por acumulados de 3 y
7 días y variables de fin de semana. No se implementó una ventana adicional que
acumule exactamente desde la última cuota hasta el instante de decisión.
No asumir que esa ventana exacta existe.

## Estado implementado del perfil independiente

Archivo principal:
`src/el_animal_fm/prediction/application/config/prediction_config.py`.

`crecimiento_balanceado_dia` figura en:

- `FUND_CONFIG`: mismo `run_fm="10063"`, carpeta
  `10063_crecimiento_balanceado` y preferencia de series `SIMPLE`, `APV`, `IT`.
  Incluye `default_scenario="decision_date_news"`.
- `FUND_SCENARIO_CONFIG`: `decision_date_news`, `night_partial`, hora `21:30`,
  desfase 1, horizonte 4.
- `FUND_MODEL_CONFIG`: umbral de probabilidad `0.367`, objetivo `0.00053`,
  `strict_return_lag=False`, `tune=False`, `tune_iter=15`. Estos valores son
  provisionales para el perfil nuevo, no un resultado validado de su búsqueda.
- `THRESHOLD_SEARCH_SPACE`: objetivo entre `0.0035` y `0.0055`, probabilidad
  entre `0.33` y `0.45`, modos `['night_partial']`.
- `XGB_SEARCH_SPACE`: espacio propio, inicialmente con los mismos rangos del
  fondo original.

Todavía NO tiene entrada en `XGB_MODEL_CONFIG`. Se agregará después de explorar
y seleccionar sus hiperparámetros. Mientras tanto usa parámetros base y no
hereda automáticamente los hiperparámetros del perfil original.

El identificador completo es `crecimiento_balanceado_dia`, no `crecimiento_dia`.
Los archivos por fondo utilizan ese identificador y quedan separados del
perfil original. La carpeta de entrada CMF se comparte intencionalmente.
La etiqueta visual aún es la misma que la del fondo original; no se trabajó UI.

Cambios realizados en esta sesión:

- `config/runtime_config.py`: resuelve el escenario predeterminado del fondo
  cuando no hay un escenario explícito. CLI explícito tiene precedencia.
- `application/pipeline.py`: conserva la resolución por fondo y evita que el
  perfil `_dia` ejecute las tres modalidades legacy por omitir `--scenario`.
  Las etiquetas de reportes se generan según los escenarios efectivos.
- `cli/xgboost_prediction.py`: documenta el escenario predeterminado y permite
  parámetros operativos sin `--scenario` cuando los fondos seleccionados tienen
  un escenario operativo predeterminado.
- `prediction_config.py`: escenario predeterminado de `_dia` y corrección de
  sus modos Optuna a `night_partial`.
- `docs/prediction_scenarios.md`: documenta el comportamiento nuevo.
- `tests/test_prediction_scenarios.py`: comprobación del perfil predeterminado,
  overrides y separación de configuración.

Los demás fondos conservan `legacy` como escenario predeterminado, incluido
`crecimiento_balanceado`. Para ejecutar el perfil cerrado mediante el escenario
nuevo debe indicarse `--scenario cmf_date_news`. No se cambió su valor
predeterminado ni se asumió que la configuración actual reproduce por sí sola
el modelo cerrado que el usuario ya había reentrenado.

Ya había cambios del usuario en `optuna_threshold_search.py`: los modos
explícitos de CLI tienen precedencia sobre el espacio por fondo. Se conservaron.
Así, `--optuna-modes night_partial` permite imponer el modo. Un modo explícito
distinto también puede reemplazar el predeterminado: no hay un bloqueo rígido.

## Corrida exploratoria analizada

Se ejecutó ANTES de registrar el perfil independiente, bajo el identificador
original pero usando el segundo escenario:

```bash
python 09_xgboost_prediction.py \
  --fund crecimiento_balanceado \
  --scenario decision_date_news \
  --quote-lag-days 1 \
  --withdrawal-days 4 \
  --override-decision-mode night_partial \
  --decision-time 21:30 \
  --train-start 2025-04-04 --train-end 2026-09-11 \
  --eval-start 2026-09-12 --eval-end 2026-10-18 \
  --optuna-threshold-search --optuna-trials 300 \
  --optuna-modes night_partial \
  --optuna-target-min 0.0 --optuna-target-max 0.01 \
  --optuna-prob-min 0.20 --optuna-prob-max 0.80 \
  --optuna-score risk_adjusted
```

Mejor trial: 80. Serie SIMPLE, 520 filas train, 30 eval, 627 variables.
Objetivo `0.000002`, probabilidad `0.2477`, score `0.04918734475682182`.

| Métrica | Valor |
| --- | --- |
| Accuracy | 0.766667 |
| Balanced accuracy | 0.549689 |
| Precision up | 0.785714 |
| Recall up | 0.956522 |
| F1 up | 0.862745 |
| ROC AUC | 0.372671 |
| Mantener / salir | 28 / 2 |
| Retorno compuesto de mantener, métrica heredada | 0.109219 |
| Retorno compuesto de estrategia, métrica heredada | 0.105042 |
| Diferencia | -0.004177 |

Matriz: TN=1, FP=6, FN=1, TP=22. Había 23 positivos de 30:
mantener siempre también acertaba 76.67 %. Detectó solo 1 de 7 negativos.
Las dos señales de salida tenían retorno objetivo promedio positivo de
0.0018939163. No hubo mejora demostrada frente a mantener.

Se comprobaron 300 trials y 24 empatados en el mejor score. Los mejores
umbrales producen métricas repetidas, no evidencia de precisión especial del
umbral `0.2477`. No se adoptaron estos valores como preset definitivo.

`risk_adjusted`, en `application/xgboost/xgb_evaluation.py`, calcula:

```text
mejora_vs_buy_hold + 0.5 * retorno_estrategia
                  + 0.5 * (retorno_medio_up - retorno_medio_down)
```

Además aplica penalizaciones por pocas señales y falta de separación de
retornos. No mide explícitamente volatilidad ni drawdown. Un score positivo no
implica superar buy & hold.

Las métricas compuestas multiplican retornos de ventanas solapadas. NO son una
simulación de cartera ni rentabilidades realizables. El retorno objetivo parte
de una cuota previa a la decisión e incluye un tramo ya transcurrido.

El período eval fue usado para seleccionar los 300 trials: no es una prueba
independiente. Hay pocas observaciones y ventanas correlacionadas; se necesita
validación temporal adicional antes de adoptar parámetros.

El CSV del mejor dataset tenía 562 filas al inspeccionarlo (el texto inicial
del usuario decía 560 filas de la serie). Las últimas filas carecían de objetivo;
la última decisión etiquetada era 11/10/2026, aunque el rango llegaba al 18/10.
El dataset incluye decisiones de fines de semana.

Artefactos de esa exploración, relativos a la raíz:

```text
xgboost_outputs/features/optuna_dataset_crecimiento_balanceado_decision_date_news_h4_a8cbe2eeb3e7_night_partial_target0p000002_2025-04-04_2026-10-18.csv
xgboost_outputs/reports/optuna_threshold_trials_crecimiento_balanceado_2025-04-04_2026-09-11_eval_2026-09-12_2026-10-18_decision_date_news_f611946e83ec.csv
xgboost_outputs/reports/optuna_threshold_best_ALL_2025-04-04_2026-09-11_eval_2026-09-12_2026-10-18_decision_date_news_f611946e83ec.json
```

## Validación realizada y pendientes

Se ejecutó correctamente:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p test_prediction_scenarios.py
```

Resultado: 14 pruebas aprobadas. `git diff --check` también pasó. No se ejecutó
un reentrenamiento real del nuevo perfil sobre los datos del usuario después
de los cambios, ni una nueva búsqueda Optuna de 300 trials.

Siguientes pasos:

1. Explorar umbrales bajo `--fund crecimiento_balanceado_dia`. Ya no es
   obligatorio indicar `--scenario decision_date_news`; se puede hacer para
   dejar el experimento explícito. Elegir conscientemente los rangos: los
   presets actuales son más estrechos que los de la corrida anterior.
2. Validar estabilidad en cortes temporales adicionales y reservar un período
   sin usar para selección. Revisar calendario y disponibilidad CMF reales.
3. Con umbrales seleccionados, explorar XGBoost y agregar su entrada propia a
   `XGB_MODEL_CONFIG`.
4. Reentrenar y guardar el modelo independiente; repetir configuración y fechas
   al cargarlo para predicción en vivo.
5. Si se quiere medir utilidad operativa, implementar una simulación de una
   sola cartera con fechas de ejecución; no interpretar los retornos compuestos
   heredados como rentabilidad real.

El workspace contiene cambios y archivos previos del usuario. No se hicieron
commits, no se revirtieron sus cambios y no se trabajó la interfaz gráfica.
Antes de continuar, leer este documento y contrastarlo con el código actual:
puede haber nuevos cambios después de esta sesión.
