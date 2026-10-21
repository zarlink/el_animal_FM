# Revisión y reparación del archivo completo de noticias

Se revisaron todas las carpetas locales de BioBio y El Mostrador, sin limitar el
análisis a las fechas del experimento XGB. Se corrigieron ubicaciones, fechas,
identidades por URL y referencias a HTML. No se ejecutó entrenamiento ni se
regeneraron las clasificaciones completas de noticias.

## Resultado

| Fuente y etapa | Registros antes | URLs únicas después | Copias adicionales retiradas | Registros originalmente en fecha incorrecta |
| --- | ---: | ---: | ---: | ---: |
| BioBio original | 29.853 | 28.877 | 976 | 1.382 |
| BioBio enriquecida | 28.998 | 28.209 | 789 | 1.201 |
| El Mostrador original | 14.856 | 14.843 | 13 | 28 |
| El Mostrador enriquecida | 14.625 | 14.615 | 10 | 26 |

Después de la reparación, cada una de esas cuatro colecciones tiene cero URLs
repetidas, cero artículos en carpetas distintas de su publicación resuelta y cero
campos temporales pendientes de corregir. Una noticia original y su representación
enriquecida son etapas distintas, no un duplicado que deba eliminarse.

Se inspeccionaron las cabeceras de los 44.687 HTML iniciales. Quedaron 43.704
HTML activos, sin duplicados ni ubicaciones incorrectas. Los HTML duplicados se
archivaron, conservando su contenido. Las referencias `technical.html_raw_path`
se actualizaron para apuntar al archivo conservado.

## Evidencia y criterios

Se utiliza la fecha de publicación original completa cuando se puede interpretar
de forma determinista. Los meses españoles se analizan explícitamente; no se
permite que un parser rellene componentes con el día de ejecución. Las fechas
con zona horaria se convierten a America/Santiago antes de escoger carpeta.
La fecha de la URL es un respaldo cuando no existe publicación interpretable.
No se sustituye una publicación válida por la fecha de la URL: hay artículos
publicados antes del día que indica su URL.

La identidad utiliza URL canónica, normalizando http/https, alias www, barra
final, fragmentos y parámetros de seguimiento. Se conservan otros parámetros.
Entre copias se prefiere una extracción exitosa, luego contenido más completo
y finalmente la extracción más reciente. Los originales anteriores permanecen
en los respaldos.

La comprobación contra `article:published_time`, `datePublished` de meta o JSON-LD
confirmó la fecha de 28.865 HTML de BioBio y 14.826 de El Mostrador. No hubo
contradicciones con los artículos conservados. Otros 13 HTML no tienen esos
metadatos reconocibles; su ubicación se contrastó con la identidad y publicación
del registro, sin inventar información adicional.

Se recuperaron 10 URLs de El Mostrador dañadas por limpieza editorial, en ambas
etapas (20 registros corregidos). El limpiador eliminaba palabras como
`destacados` o `publicidad` también dentro de URLs y rutas. La recuperación usa
una correspondencia exacta entre la URL canónica del HTML y el resultado del
antiguo limpiador, no títulos ni aproximaciones.

## Prevención en el procesamiento habitual

- El parser de El Mostrador interpreta fechas españolas antes de cualquier
  interpretación ambigua. Una fecha sin hora no se convierte en medianoche.
- El descubrimiento de BioBio prioriza la fecha explícita de la URL de su API
  frente a campos numéricos ambiguos.
- La limpieza editorial respeta URLs y rutas absolutas.
- La normalización valida fecha/carpeta y deduplica el archivo. El proceso por
  lotes detecta URLs repetidas entre días antes de escribir.
- El enriquecimiento valida los archivos y deduplica antes de generar variables.
  Reemplaza el derivado completo; nunca agrega una segunda copia al existente.
- Una huella del original permite detectar cambios aunque el enriquecido ya
  exista. Los derivados antiguos sin huella se reconstruyen una vez; luego se
  omiten si su original sigue igual. Cambiar el diccionario sin cambiar el
  original conserva la opción explícita de sobrescribir de la interfaz.
- La descarga comprueba la fecha efectiva antes de guardar y verifica URLs
  repetidas en otros días. Los artículos de fecha incompatible se registran en
  `noticias_rechazadas_fecha.json`, fuera de los archivos consumidos por modelos.

Una noticia mal ubicada o una duplicación entre días provoca un error que indica
ejecutar la reconciliación, en vez de propagarse silenciosamente al enriquecido.

## Diferencias entre etapas que siguen pendientes

| Fuente | Originales sin enriquecer | Enriquecidos con versión distinta del original |
| --- | ---: | ---: |
| BioBio | 668 | 4.262 |
| El Mostrador | 228 | 3.075 |

No hay enriquecidos sin original ni diferencias de fecha entre las etapas.
La comparación de versiones usa todo el bloque `raw`; puede detectar diferencias
de texto o de otros campos, no implica que todas las clasificaciones hayan cambiado.
El siguiente enriquecimiento reconstruirá los derivados desde los originales
actuales. Esta revisión no ejecutó esa regeneración completa.

Hay 16 artículos sin HTML local disponible (9 BioBio y 7 El Mostrador). Se
conservaron y marcaron como `missing_or_unverified`, con la referencia inexistente
vacía; el detalle está en `html_issues.csv`. No se descargaron reemplazos.
Hay 340 originales sin hora verificable. Se conservan sin hora y quedan excluidos
del corte parcial del mismo día; pueden participar en agregados de días previos.

Los datasets y modelos XGB anteriores no se regeneraron. Antes de volver a
comparar modelos hay que reconstruir sus entradas con el archivo corregido y
los enriquecidos actualizados.

## Informes, respaldos y reproducción

- `news_integrity_reports/repair_2026-10-20/`: conteos antes/después, incidencias
  por artículo, cambios y respaldos. Se modificaron 838 JSON en la primera pasada.
- `news_integrity_reports/url_recovery_2026-10-20/`: recuperación de URLs y
  respaldo de los JSON correspondientes.
- `news_integrity_reports/verification_2026-10-20/`: verificación completa de
  artículos/HTML y comparación entre etapas (`layer_consistency.csv`).
- `news_integrity_reports/final_json_verification_2026-10-20/`: comprobación final
  de estabilidad después de ordenar los registros por URL.

La revisión completa de HTML no propuso movimientos adicionales, y la última
revisión de JSON propuso cero cambios: repetir la reconciliación conserva el resultado.

Los JSON originales se respaldaron con gzip. Los HTML se conservaron fuera de
las carpetas activas; cuando hubo una reubicación se usaron enlaces físicos para
mantener el respaldo sin duplicar su espacio. Las copias `.bak` históricas se
conservaron y no son entradas activas de normalización/enriquecimiento.

Para una nueva revisión completa, elegir un directorio de informe que no exista:

```bash
python scripts/reconcile_news.py --output news_integrity_reports/nueva_revision
```

El modo anterior solo revisa y muestra los cambios propuestos. Para aplicar una
reconciliación, agregar `--apply`; se crea un respaldo antes de escribir.

Validación de código: 59 pruebas pasaron con
`PYTHONPATH=src python -m unittest discover -s tests -q`, incluidos casos de fechas
españolas, zonas horarias, URLs con seguimiento, cambio del original, repetición
del enriquecimiento y reconciliación con respaldo y reubicación de HTML.
