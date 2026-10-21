# Auditoría temporal y comparación sin noticias — 20/10/2026

Hay inconsistencias temporales en las noticias que deben resolverse antes de
seleccionar hiperparámetros o interpretar el aporte del bloque noticioso.
El modelo financiero supera al completo en AUC en los cinco cortes examinados,
pero tampoco demuestra una mejora estable frente a mantener.

## Ejecución reproducible

```bash
python scripts/audit_prediction_news.py \
  --output xgboost_outputs/diagnostics/news_audit_2026-10-20
```

El directorio debe ser nuevo para evitar sobrescribir resultados. Los resultados
de esta ejecución ya existen; para repetir, elegir otro nombre de salida.
El script no guarda modelos operativos ni modifica configuraciones de fondos.

Perfil `crecimiento_balanceado_dia`, serie SIMPLE, escenario `decision_date_news`,
`night_partial` a las 21:30, desfase 1, horizonte 4, calendario lunes a viernes
sin feriados configurados. Objetivo 0.00053 y probabilidad 0.367, provisionales.
Entrenamiento creciente desde 04/04/2025, cierre al final del mes anterior,
evaluación mensual junio–octubre hasta el 18/10. Los objetivos conocidos terminan
el 11/10: hay 133 observaciones evaluables en total.

Ambos modelos usan las mismas filas, etiquetas, umbrales y parámetros XGB base,
con semilla 42 y ponderación de clases calculada en cada entrenamiento. No hay
Optuna ni tuning. El modelo completo tiene 574 variables noticiosas y 53
financieras/de calendario. La ablación elimina exactamente las columnas producidas
por el constructor de noticias: no usa prefijos, pues algunas se llaman
`body_length...` o `is_economy_section...`.

## Alineación de cuotas y objetivos

Las verificaciones sobre las 562 filas del dataset pasan:

- Cuota supuestamente disponible en o antes de la decisión.
- Referencia de noticias igual al día de decisión.
- Objetivo posterior a la decisión y retorno igual al cociente de cuotas menos uno.
- Etiquetas y fechas futuras excluidas de las variables del modelo.
- En cada corte, solo se entrena con etiquetas disponibles al cierre del entrenamiento.

En 560 filas la cuota tiene un día calendario de antigüedad, en una tiene dos
y en otra tres. `strict_return_lag=False` permite usar el retorno de esa cuota
ya conocida; no supone usar la cuota aún no publicada del día de decisión.
Otros indicadores conservan desplazamientos históricos adicionales del código.

Pasaron las 14 pruebas existentes de escenarios, incluida la invariancia de las
variables ante cambiar una cuota aún no publicada. Se añadió y pasó una prueba
del corte de noticias: incluye exactamente las 21:30:00, excluye 21:30:01 y
horas desconocidas. El agregado de días anteriores incluye el día completo.

Estas comprobaciones validan la política implementada, no la hora real de
publicación CMF. Los feriados siguen sin configurar y los archivos actuales no
permiten reconstruir revisiones históricas de cuotas o artículos.

## Inconsistencias encontradas en noticias

Se revisaron los archivos del 25/03/2025 al 18/10/2026, incluido el margen
histórico utilizado por el constructor:

| Fuente | Artículos | Fecha distinta de carpeta | Fecha posterior a carpeta | Hora desconocida |
| --- | ---: | ---: | ---: | ---: |
| BioBio | 28.998 | 1.201 | 1.083 | 7 |
| El Mostrador | 14.567 | 120 | 59 | 20 |

Son incidencias en archivos, no necesariamente artículos únicos. El constructor
actual agrupa por fecha de carpeta y solo verifica la hora para el corte parcial;
no comprueba que la fecha de publicación corresponda a esa carpeta.

**BioBio:** en las 1.083 incidencias con fecha posterior, la fecha de la URL
coincide con la publicación declarada. Por ejemplo, `06_04_2025` contiene una
noticia con publicación `2025-06-04T17:08:42-04:00` y URL con `/2025/06/04/`.
Así, contenido de junio entra como información de abril. Es evidencia concreta
de contaminación temporal por asignación a carpeta, compatible con inversión de
día/mes. El punto exacto que originó las carpetas históricas queda pendiente;
no se corrigieron ni movieron archivos durante esta auditoría.

**El Mostrador:** en las 59 incidencias con fecha posterior, la URL coincide con
la carpeta. Hay un problema distinto en la fecha extraída: por ejemplo, en
`04_01_2026`, `published_at_raw="4 enero, 2026"` se guardó como
`published_at="2026-04-09T00:00:00-04:00"`, aunque la URL indica enero 4.
`parse_spanish_date` intenta primero `dateutil.parse(..., fuzzy=True)` y solo
después su expresión explícita para meses españoles. Esa prioridad permite una
interpretación incorrecta antes de llegar al parser español. Además, `00:00`
puede ser una hora por defecto para textos sin hora: no equivale a publicación
verificada antes de las 21:30.

Las 1.142 fechas declaradas posteriores no deben interpretarse todas como
artículos realmente futuros: los dos casos anteriores tienen orígenes distintos.
Los detalles están en `news_date_mismatches.csv` y los conteos diarios en
`news_timestamp_audit.csv`, dentro del directorio de resultados.

## Comparación mensual

| Mes | Filas | AUC completo | AUC financiero | Salidas completo | Salidas financiero |
| --- | ---: | ---: | ---: | ---: | ---: |
| Junio | 30 | 0.216 | 0.494 | 8 | 11 |
| Julio | 31 | 0.438 | 0.504 | 0 | 4 |
| Agosto | 31 | 0.488 | 0.625 | 15 | 18 |
| Septiembre | 30 | 0.521 | 0.549 | 26 | 14 |
| Octubre, 1–11 | 11 | 0.286 | 0.571 | 0 | 8 |

Sobre 133 observaciones, el completo acierta 56 (42.11 %), el financiero 70
(52.63 %) y mantener siempre 89 (66.92 %). El financiero supera al completo en
AUC en cada corte, pero solo presenta diferencia compuesta positiva frente a
mantener en julio; el completo no presenta diferencia positiva en ningún mes.
No se suman las diferencias compuestas: las ventanas se solapan y estas métricas
no representan rentabilidad ejecutable.

El Brier promedio ponderado es 0.380 para el completo, 0.332 para el financiero
y 0.223 para una probabilidad constante igual a la prevalencia del entrenamiento
de cada corte. Menor es mejor. La ponderación de clases de XGB puede afectar la
calibración; estos valores describen las probabilidades usadas, no identifican
por sí solos el origen del problema.

Las noticias sí se utilizan: entre 229 y 266 columnas noticiosas participan en
divisiones de árboles, y concentran aproximadamente 86–87 % de la importancia
normalizada reportada por XGBoost. Esto no prueba utilidad predictiva; la suma
también depende del tamaño del grupo y de sus correlaciones. Al permutar juntas
las noticias entre filas de evaluación, el AUC promedio aumenta en los cinco
cortes (10 permutaciones por corte). Es un diagnóstico de inestabilidad, no una
prueba causal: se rompen relaciones temporales y financieras entre variables.

## Qué hacer con estos resultados

No promover umbrales ni ajustar XGB usando esta comparación como validación final.
Junio–octubre ya se utilizó para explorar configuraciones, y ahora además se
confirmó contaminación temporal en una parte de las noticias.

El siguiente trabajo es corregir la asignación temporal de BioBio y el parser
español de El Mostrador, definir cómo tratar fechas/horas desconocidas y regenerar
las noticias derivadas afectadas. Después se debe repetir exactamente esta
comparación sobre los datos corregidos y reservar un período posterior para
selección y validación separadas. La ablación actual es evidencia de que conviene
revisar los datos antes de dedicar más búsquedas a hiperparámetros, no evidencia
definitiva de que las noticias nunca aporten.

Artefactos: `manifest.json`, `metrics.csv`, `predictions.csv`, `importance.csv`,
`features.csv`, `dataset.csv`, `news_timestamp_audit.csv`, `news_date_mismatches.csv`
en `xgboost_outputs/diagnostics/news_audit_2026-10-20/`.
