# El Animal FM: pipeline de noticias, fondos mutuos y prediccion con XGBoost

Este proyecto construye una cadena completa para transformar noticias chilenas en variables cuantitativas y cruzarlas con series de fondos mutuos descargadas desde la CMF. La primera version predictiva ya esta implementada en `09_xgboost_prediction.py`: entrena modelos XGBoost por fondo, evalua distintas modalidades temporales de uso de noticias y genera senales operativas del tipo `mantener`, `mover_o_retirar`, `entrar`, `esperar` o `salir_o_mover_defensivo`.

El flujo no parte en el modelo. Antes de llegar a XGBoost, los scripts anteriores descargan noticias, normalizan texto, unifican corpus, crean candidatos de diccionario, enriquecen cada noticia con features tematicas y descargan los datos financieros que sirven como variable objetivo.

---

## Menu

* [1. Objetivo](#1-objetivo)
* [2. Flujo completo](#2-flujo-completo)
* [3. Scripts del proyecto](#3-scripts-del-proyecto)
* [4. Instalacion](#4-instalacion)
* [5. Ejecucion recomendada de punta a punta](#5-ejecucion-recomendada-de-punta-a-punta)
* [6. Noticias: descarga, limpieza y corpus](#6-noticias-descarga-limpieza-y-corpus)
* [7. Diccionarios y enriquecimiento](#7-diccionarios-y-enriquecimiento)
* [8. Fondos mutuos CMF](#8-fondos-mutuos-cmf)
* [9. Predictor XGBoost por fondo](#9-predictor-xgboost-por-fondo)
* [10. Graficos de reportes XGBoost](#10-graficos-de-reportes-xgboost)
* [11. Estructura de archivos](#11-estructura-de-archivos)
* [12. Datos generados actualmente](#12-datos-generados-actualmente)
* [13. Consideraciones metodologicas](#13-consideraciones-metodologicas)

---

## 1. Objetivo

El objetivo es convertir informacion periodistica y financiera en datasets auditables para estimar tendencias de fondos mutuos. El sistema intenta responder una pregunta practica:

> Dada la informacion noticiosa disponible y la trayectoria reciente del fondo, conviene mantener exposicion al fondo o mover/reducir posicion durante el horizonte definido?

Para eso el proyecto hace lo siguiente:

1. Descarga noticias diarias desde BioBioChile y El Mostrador.
2. Guarda HTML crudo para auditoria.
3. Extrae campos estructurados por noticia: titulo, bajada, cuerpo, fecha, seccion, autor, enlaces, imagenes y metadatos tecnicos.
4. Normaliza encoding, HTML residual y ruido editorial.
5. Unifica las noticias en un corpus comun.
6. Extrae candidatos de diccionario usando frecuencia, TF-IDF, YAKE, entidades, embeddings y clustering.
7. Enriquece cada noticia diaria con familias tematicas, puntajes, entidades, impacto esperado y ruido social.
8. Descarga cartolas diarias de fondos mutuos desde la CMF.
9. Construye datasets por fondo, combinando features historicas del fondo y features agregadas de noticias.
10. Entrena y evalua XGBoost por fondo, horizonte y modalidad temporal.
11. Genera reportes, predicciones, importancia de variables, modelos persistidos y graficos.

---

## 2. Flujo completo

```text
01_biobio_download.py
02_mostrador_download.py
   |
   v
biobio/DD_MM_YYYY/noticias_dia.txt
mostrador/DD_MM_YYYY/noticias_dia.txt
   |
   v
03_normalizador_noticias.py
   |
   v
noticias_dia.txt normalizados + respaldos .bak
   |
   v
04_unificador_noticias_diccionario.py
   |
   v
noticias_unificadas.txt
   |
   v
05_creador_diccionario_adicional.py
   |
   v
candidatos_diccionario.json
   |
   v
diccionarios/*.txt + semillas internas de 06
   |
   v
06_enriquecer_noticias.py
   |
   v
biobio/DD_MM_YYYY/noticias_dia_enriquecidas.txt
mostrador/DD_MM_YYYY/noticias_dia_enriquecidas.txt
features_summary/resumen_enriquecimiento_*.json

08_descarga_fondos_mutuos.py
   |
   v
downloads/<codigo_fondo>_<slug_fondo>/*.txt
downloads/resumen_cmf_*.json

noticias enriquecidas + fondos CMF
   |
   v
09_xgboost_prediction.py
   |
   v
xgboost_outputs/models/*.joblib
xgboost_outputs/features/dataset_*.csv
xgboost_outputs/features/importancia_*.csv
xgboost_outputs/predictions/predicciones_*.csv
xgboost_outputs/reports/resumen_xgboost_*.json
xgboost_outputs/reports/resumen_xgboost_*.csv
   |
   v
10_graficos_xgboost.py
   |
   v
xgboost_outputs/report_charts/*.png
```

Hay tres capas conceptuales:

| Capa | Scripts | Resultado |
| --- | --- | --- |
| Corpus de noticias | `01` a `04`, mas `07` como apoyo historico | Noticias descargadas, limpias y unificadas. |
| Features noticiosas | `05` y `06` | Diccionarios, candidatos y noticias enriquecidas. |
| Prediccion financiera | `08`, `09` y `10` | Series de fondos, modelos XGBoost, senales, reportes y graficos. |

---

## 3. Scripts del proyecto

| Script | Funcion | Entrada principal | Salida principal |
| --- | --- | --- | --- |
| `01_biobio_download.py` | Descarga noticias de BioBioChile por fecha o rango. | BioBioChile: sitemaps, Lo Ultimo, categorias y APIs de paginacion. | `biobio/DD_MM_YYYY/noticias_dia.txt` y HTML crudo. |
| `02_mostrador_download.py` | Descarga noticias de El Mostrador por fecha o rango. | El Mostrador: home, `/dia/`, secciones, paginaciones y sitemaps. | `mostrador/DD_MM_YYYY/noticias_dia.txt` y HTML crudo. |
| `03_normalizador_noticias.py` | Repara texto, limpia ruido y recalcula metricas. | `noticias_dia.txt` por medio y fecha. | Archivo normalizado y respaldo `.bak`. |
| `04_unificador_noticias_diccionario.py` | Reduce y unifica noticias en un corpus comun. | Carpetas `biobio/` y `mostrador/`. | `noticias_unificadas.txt`. |
| `05_creador_diccionario_adicional.py` | Extrae candidatos de diccionario desde el corpus. | `noticias_unificadas.txt`. | `candidatos_diccionario.json`. |
| `06_enriquecer_noticias.py` | Aplica diccionarios, candidatos y reglas heuristicas. | `noticias_dia.txt`, `diccionarios/`, `candidatos_diccionario.json`. | `noticias_dia_enriquecidas.txt` y resumenes. |
| `07_download_biobio_from_google.py` | Herramienta auxiliar para recuperar BioBio historico via Google. | Google + parser de `01`. | Actualiza `biobio/DD_MM_YYYY/noticias_dia.txt`. |
| `08_descarga_fondos_mutuos.py` | Descarga cartolas diarias de fondos desde CMF. | CMF, rango de fechas, fondo y CAPTCHA manual. | `downloads/<fondo>/*.txt` y resumen CMF. |
| `09_xgboost_prediction.py` | Entrena/evalua XGBoost por fondo con noticias enriquecidas y datos CMF. | `noticias_dia_enriquecidas.txt` + `downloads/`. | Modelos, datasets, predicciones, importancia y reportes. |
| `10_graficos_xgboost.py` | Grafica reportes JSON generados por `09`. | `xgboost_outputs/reports/*.json`. | `xgboost_outputs/report_charts/*.png`. |

---

## 4. Instalacion

Crear y activar entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

Instalar dependencias base:

```bash
pip install -r requirements.txt
```

Dependencias relevantes por etapa:

| Etapa | Paquetes |
| --- | --- |
| Scraping y parsing | `requests`, `beautifulsoup4`, `lxml`, `python-dateutil` |
| NLP y diccionarios | `spacy`, `es_core_news_lg`, `yake`, `scikit-learn` |
| Embeddings y clustering | `sentence-transformers`, `torch`, `hdbscan` |
| Modelo `09` | `pandas`, `numpy`, `scikit-learn`, `xgboost`, `joblib` |
| Optimizacion opcional | `optuna` |
| Graficos `10` | `matplotlib`, `pandas`, `numpy` |

Si el entorno no tiene las dependencias del predictor:

```bash
pip install pandas numpy scikit-learn xgboost joblib matplotlib optuna
```

`05_creador_diccionario_adicional.py` es la etapa mas pesada de NLP porque usa spaCy, embeddings y clustering. `09_xgboost_prediction.py` es la etapa predictiva principal y puede crecer mucho en tiempo si se ejecuta con busquedas Optuna.

---

## 5. Ejecucion recomendada de punta a punta

Ejemplo para construir noticias, enriquecerlas, descargar fondos y entrenar modelos:

```bash
python 01_biobio_download.py --date 2026-06-26 --days-back 90
python 02_mostrador_download.py --date 2026-06-26 --days-back 90
python 03_normalizador_noticias.py
python 04_unificador_noticias_diccionario.py
python 05_creador_diccionario_adicional.py
python 06_enriquecer_noticias.py --date-to 2026-06-26 --days-back 90 --overwrite
python 08_descarga_fondos_mutuos.py --start-date 2025-04-04 --end-date 2026-06-26 --fund all --skip-existing
python 09_xgboost_prediction.py --train-start 2025-04-04 --train-end 2026-05-01 --eval-start 2026-05-02 --eval-end 2026-06-26 --fund all --single-preset-run
python 10_graficos_xgboost.py --save-only
```

Para comparar automaticamente las tres modalidades temporales de noticias en cada fondo, omitir `--single-preset-run`:

```bash
python 09_xgboost_prediction.py --train-start 2025-04-04 --train-end 2026-05-01 --eval-start 2026-05-02 --eval-end 2026-06-26 --fund all
```

---

## 6. Noticias: descarga, limpieza y corpus

### `01_biobio_download.py`

Descarga noticias de BioBioChile. El parser actual se identifica como:

```text
biobio_raw_v3_category_archives
```

Usa varias fuentes de descubrimiento:

* `news-sitemap.xml`.
* Sitemap mensual `static/sitemap-YYYY-MM.xml`.
* Pagina `lo-ultimo.shtml`.
* Archivos de categorias.
* APIs de categorias y paginacion.

Filtra URLs que pertenezcan a `biobiochile.cl`, terminen en `.shtml`, contengan `/noticias/` y coincidan con la fecha objetivo. Excluye BioBioTV, podcasts, programas, especiales y paginas institucionales.

Salida diaria:

```text
biobio/DD_MM_YYYY/noticias_dia.txt
biobio/DD_MM_YYYY/html/*.html
```

### `02_mostrador_download.py`

Descarga noticias de El Mostrador. El parser actual se identifica como:

```text
elmostrador_raw_v2_range_sections
```

Usa la pagina principal, `/dia/`, `/categoria/dia/`, paginaciones, secciones editoriales y sitemaps candidatos. Acepta principalmente URLs con fecha en la ruta:

```text
/YYYY/MM/DD/
```

Excluye paginas de autor, tags, newsletter, paginas institucionales, contacto, privacidad y paginaciones internas.

Salida diaria:

```text
mostrador/DD_MM_YYYY/noticias_dia.txt
mostrador/DD_MM_YYYY/html/*.html
```

### Formato de `noticias_dia.txt`

Cada archivo diario es JSON:

```json
{
  "metadata": {
    "source": "biobiochile",
    "target_date": "2026-06-02",
    "articles_found": 80,
    "articles_downloaded": 80,
    "parser_version": "biobio_raw_v3_category_archives"
  },
  "articles": [
    {
      "raw": {},
      "technical": {}
    }
  ]
}
```

`raw` contiene campos observables de la noticia: URL, fecha, hora, titulo, subtitulo, resumen, cuerpo, autor, seccion, indicadores de contenido, enlaces relacionados e imagenes cuando se detectan.

`technical` conserva auditoria: codigo HTTP, tipo de contenido, HTML local, version del parser, estado de parsing, errores y fuentes de descubrimiento.

### `03_normalizador_noticias.py`

Limpia y normaliza los `noticias_dia.txt`. Puede sobrescribir el archivo original dejando respaldo `.bak` o generar un archivo alternativo segun opciones.

Uso tipico:

```bash
python 03_normalizador_noticias.py
```

Sin sobrescribir:

```bash
python 03_normalizador_noticias.py --no-overwrite
```

### `04_unificador_noticias_diccionario.py`

Genera `noticias_unificadas.txt`, una version reducida y comun para entrenar diccionarios. Conserva campos como:

* `source`
* `source_file`
* `published_date`
* `url`
* `main_section`
* `title`
* `summary`
* `body_text_clean`
* `classification_text`
* `parser_version`
* `parse_success`
* `parse_errors`

`classification_text` combina titulo, subtitulo, bajada, resumen, resumen IA y cuerpo limpio. Es la base que usa `05`.

Ejemplo:

```bash
python 04_unificador_noticias_diccionario.py --media biobio mostrador --output noticias_unificadas.txt
```

### `07_download_biobio_from_google.py`

Es una herramienta auxiliar para recuperar noticias historicas de BioBio cuando los mecanismos normales no cubren bien ciertas fechas. Reutiliza el parser de `01_biobio_download.py`.

Ejemplo:

```bash
python 07_download_biobio_from_google.py --start-date 2026-04-30 --days-back 30 --max-google-pages 5
```

---

## 7. Diccionarios y enriquecimiento

### `05_creador_diccionario_adicional.py`

Lee `noticias_unificadas.txt` y genera `candidatos_diccionario.json`. Esta salida no es un clasificador final: es una fuente exploratoria para revisar terminos y fortalecer los diccionarios curados.

El analisis incluye:

* Stopwords de spaCy y stopwords personalizadas.
* Normalizacion de frases compuestas como `banco central`, `wall street`, `tipo de cambio` y `deficit fiscal`.
* Filtros heuristicos para textos financieros, riesgo politico y geopolitica con mercado.
* N-grams, TF-IDF y keywords YAKE.
* Entidades con `es_core_news_lg`.
* Embeddings multilingues con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
* Clustering con HDBSCAN.
* Muestras para auditoria manual.

Secciones principales de `candidatos_diccionario.json`:

| Seccion | Uso |
| --- | --- |
| `general` | Terminos frecuentes del corpus completo. |
| `financial_strict` | Candidatos financieros, macro, mercado, empresas o commodities. |
| `political_risk` | Candidatos politicos, fiscales, institucionales o regulatorios. |
| `geopolitical_market` | Candidatos geopoliticos con posible vinculo de mercado. |
| `entities_top` | Entidades detectadas por spaCy. |
| `clusters` | Grupos semanticos detectados. |
| `cluster_examples` | Ejemplos por cluster. |

### Diccionarios curados

La carpeta `diccionarios/` contiene terminos revisables y versionables:

```text
diccionarios/
+-- mercado_volatilidad_v1.txt
+-- commodities_clima_v1.txt
+-- empresas_chile_v1.txt
+-- regulatorio_tributario_v1.txt
+-- politico_corporativo_v1.txt
+-- macro_indicadoresV1.txt
```

`06_enriquecer_noticias.py` infiere la familia desde el nombre del archivo y acepta `.txt`, `.csv` y `.json`. En archivos de texto, cada linea puede ser un termino simple o un termino con peso separado por coma o punto y coma.

### `06_enriquecer_noticias.py`

Esta es la etapa que transforma noticias limpias en variables modelables. Carga:

* Semillas internas (`DEFAULT_SEED_TERMS`).
* Archivos de `diccionarios/`.
* Candidatos de `candidatos_diccionario.json`, salvo que se use `--no-candidates`.

Luego escribe, por cada dia y fuente:

```text
biobio/DD_MM_YYYY/noticias_dia_enriquecidas.txt
mostrador/DD_MM_YYYY/noticias_dia_enriquecidas.txt
features_summary/resumen_enriquecimiento_*.json
```

Cada articulo recibe un bloque `features` con:

| Bloque | Contenido |
| --- | --- |
| `families` | Puntajes, hits, actividad y detalles por familia tematica. |
| `general_classification` | Banderas como `is_economic_news`, `is_political_news`, `is_market_news`, `is_social_noise`. |
| `impact` | Candidato de impacto de mercado, score, direccion esperada, horizonte, riesgo, incertidumbre y confianza. |
| `entities` | Entidades relevantes: Banco Central, CMF, Codelco, China, EE.UU., etc. |
| `temporal` | Fecha, hora, dia de semana y fin de semana. |
| `audit` | Familias activas, terminos encontrados y razon textual de clasificacion. |

Familias usadas por `06`:

| Familia | Sentido |
| --- | --- |
| `macro_fiscal` | Hacienda, presupuesto, deficit, impuestos, deuda publica. |
| `mercado_financiero` | Banco Central, CMF, dolar, tasas, IPC, bolsa, bonos. |
| `energia_commodities` | Petroleo, cobre, litio, combustibles, electricidad, ENAP, Codelco. |
| `empresas_instituciones` | Empresas, bancos, CMF, Banco Central e instituciones relevantes. |
| `politico_regulatorio` | Congreso, ley, regulacion, reformas, gobierno. |
| `geopolitico_mercado` | Guerras, sanciones, aranceles, China, EE.UU., Rusia, Iran, cadenas de suministro. |
| `riesgo_alerta` | Crisis, incertidumbre, caida, emergencia, quiebra. |
| `sentimiento_positivo` | Crecimiento, alza, recuperacion, acuerdo, inversion. |
| `sentimiento_negativo` | Caida, baja, crisis, desaceleracion, perdidas. |
| `ruido_social` | Farandula, deportes, policial, musica, cine y otros ruidos no financieros. |

Ejemplos:

```bash
python 06_enriquecer_noticias.py --date-from 2026-05-01 --date-to 2026-06-26 --workers 4 --overwrite
python 06_enriquecer_noticias.py --no-candidates
```

---

## 8. Fondos mutuos CMF

`08_descarga_fondos_mutuos.py` descarga cartolas diarias desde la CMF. Es el puente entre el mundo noticioso y la variable financiera que luego usa `09`.

El script trabaja en tramos de maximo 31 dias por solicitud y requiere resolver CAPTCHA manualmente. Los archivos quedan en `downloads/`, separados por fondo.

Fondos configurados en `08`:

| Alias de descarga | Codigo CMF | Nombre |
| --- | --- | --- |
| `balanceado` | `10063` | CARTERA BALANCEADO |
| `national_equity` | `8305` | NATIONAL EQUITY |
| `toesca_equity` | `9936` | TOESCA EQUITY |
| `itau_ahorro_uf` | `10243` | AHORRO UF ITAU |
| `all` | varios | Todos los anteriores |

Ejemplos:

```bash
python 08_descarga_fondos_mutuos.py --list-funds --list-filter itau
python 08_descarga_fondos_mutuos.py --start-date 2025-04-04 --end-date 2026-06-26 --fund all --skip-existing
```

Las columnas CMF relevantes para `09` incluyen, cuando existen:

* `RUN_FM`
* `FECHA_INF`
* `SERIE`
* `VALOR_CUOTA`
* `PATRIMONIO_NETO`
* `ACTIVO_TOT`
* `CUOTAS_APORTADAS`
* `CUOTAS_RESCATADAS`
* `CUOTAS_EN_CIRCULACION`
* `NUM_PARTICIPES`
* `REM_FIJA`
* `REM_VARIABLE`
* `GASTOS_AFECTOS`
* `GASTOS_NO_AFECTOS`
* `COMISION_INVERSION`
* `COMISION_RESCATE`

---

## 9. Predictor XGBoost por fondo

`09_xgboost_prediction.py` es la primera version del predictor de tendencias de fondos mutuos. Entrena y evalua modelos XGBoost binarios por fondo, usando:

* Features de noticias enriquecidas generadas por `06`.
* Series de fondos descargadas desde CMF con `08`.
* Features tecnicas del fondo: retornos, lags, volatilidad, momentum, medias moviles, drawdown, flujos y calendario.
* Targets futuros definidos por horizonte y umbral de retorno.
* Presets por fondo para modalidad, probabilidad minima, umbral de target e hiperparametros XGBoost.

### Entradas requeridas

`09` espera que existan:

```text
biobio/DD_MM_YYYY/noticias_dia_enriquecidas.txt
mostrador/DD_MM_YYYY/noticias_dia_enriquecidas.txt
downloads/<carpeta_fondo>/*.txt
```

La constante interna `NEWS_FILE_NAME` apunta a:

```text
noticias_dia_enriquecidas.txt
```

Por eso no basta con descargar noticias: hay que correr `06` antes de entrenar.

### Fondos modelados por `09`

`09` usa una configuracion propia, alineada con las descargas CMF:

| Fondo en `09` | RUN_FM | Carpeta esperada | Etiqueta | Horizonte |
| --- | --- | --- | --- | --- |
| `crecimiento_balanceado` | `10063` | `10063_crecimiento_balanceado` | Crecimiento Balanceado | 4 dias habiles |
| `ahorro_uf_itau` | `10243` | `10243_ahorro_uf_itau` | Ahorro UF Itau | 1 dia habil |
| `national_equity` | `8305` | `8305_national_equity` | National Equity | 2 dias habiles |
| `toesca_equity` | `9936` | `9936_toesca_equity` | Toesca Equity | 2 dias habiles |

El horizonte define cuantos dias hacia adelante se mide el retorno objetivo:

```text
future_return_h = future_valor_cuota / valor_cuota - 1
target_up = future_return_h > target_threshold
```

Si `target_up = 1`, el modelo interpreta que el fondo supera el umbral definido para su horizonte. La senal operacional queda como `mantener`. Si `target_up = 0`, la senal queda como `mover_o_retirar`.

### Series CMF

Cada fondo puede tener varias series. `09` elige la primera disponible segun `preferred_series`; si no encuentra una preferida, usa la serie con mayor patrimonio promedio.

Preferencias actuales:

| Fondo | Series preferidas |
| --- | --- |
| `crecimiento_balanceado` | `SIMPLE`, `APV`, `IT` |
| `ahorro_uf_itau` | `SIMPLE`, `APV`, `F4`, `F5`, `IT` |
| `national_equity` | `F1`, `SIMPLE`, `APV`, `IT` |
| `toesca_equity` | `F1`, `SIMPLE`, `APV`, `IT` |

### Features de noticias

`09` convierte cada `noticias_dia_enriquecidas.txt` en una matriz diaria. Por cada articulo, extrae variables numericas desde:

* Conteo total de noticias y conteo por fuente.
* Banderas del `raw`: seccion economia, mercado, nacional, internacional, opinion, agencia, etc.
* Metricas del texto: palabras, caracteres, parrafos, citas, relacionados e imagenes.
* `features.families`: score, hit count y activacion por familia.
* `features.general_classification`.
* `features.impact`.
* `features.entities`.
* `features.temporal`.
* `features.audit`, omitiendo campos textuales extensos.

Luego agrega esas variables por dia:

* Las columnas terminadas en `_mean` se promedian.
* El resto se suma.

Sobre la matriz diaria agrega rezagos y ventanas:

| Feature temporal | Descripcion |
| --- | --- |
| `_lag1` | Valor del dia anterior. |
| `_roll3_lag1` | Suma movil de 3 dias, rezagada un dia. |
| `_roll7_lag1` | Suma movil de 7 dias, rezagada un dia. |
| `news_weekend_pressure_roll3_lag1` | Presion de noticias de fin de semana en ventana 3. |
| `news_weekend_pressure_roll7_lag1` | Presion de noticias de fin de semana en ventana 7. |
| `_same_day` | Solo en modo `same_day_close`. |
| `_today_until_decision` | Solo en modo `night_partial`. |

### Modalidades de decision

El predictor compara o ejecuta tres formas de usar la informacion noticiosa:

| Modalidad | Uso de noticias | Lectura practica |
| --- | --- | --- |
| `strict_lag` | Solo noticias hasta el dia anterior. | Modo conservador para evitar mirar informacion del mismo dia. |
| `night_partial` | Rezagos + noticias del mismo dia publicadas hasta `decision_time`. | Simula decision nocturna con noticias disponibles hasta, por defecto, `21:30`. |
| `same_day_close` | Rezagos + todas las noticias del mismo dia. | Modo de cierre o retrospectivo; util para comparar, menos estricto temporalmente. |

Por defecto, si no se usa `--single-preset-run`, `09` prueba automaticamente las tres modalidades para cada fondo seleccionado y escribe un resumen comparativo.

### Features propias del fondo

`09` transforma la serie CMF en variables tecnicas:

* `return_1d` y `log_return_1d`.
* Lags de retorno en ventanas 1, 2, 3, 5, 10 y 20.
* Medias y desviaciones moviles de retorno en ventanas 3, 5, 10 y 20.
* Momentum en ventanas 3, 5, 10 y 20.
* Medias moviles de valor cuota en ventanas 5, 10 y 20.
* `valor_cuota_vs_ma20`.
* `ma5_vs_ma20`.
* `drawdown_20`.
* Flujos netos de cuotas si existen `CUOTAS_APORTADAS` y `CUOTAS_RESCATADAS`.
* Retorno de patrimonio si existe `PATRIMONIO_NETO`.
* Cambio de participes si existe `NUM_PARTICIPES`.
* Variables de calendario: dia de semana, dia de mes, mes, inicio/fin de mes y fin de semana.

Cuando `strict_return_lag` esta activo, se excluyen algunas variables del mismo dia para reducir riesgo de leakage:

```text
return_1d
log_return_1d
patrimonio_return_1d
participes_change_1d
```

### Presets actuales por fondo

`FUND_MODEL_CONFIG` define modalidad, hora de decision, umbral de probabilidad y umbral de target para cada fondo:

| Fondo | Modalidad preset | Hora | Probabilidad minima | Target threshold |
| --- | --- | --- | --- | --- |
| `crecimiento_balanceado` | `night_partial` | `21:30` | `0.367` | `0.00053` |
| `ahorro_uf_itau` | `night_partial` | `21:30` | `0.61` | `0.0000` |
| `national_equity` | `same_day_close` | N/A | `0.516` | `0.000766` |
| `toesca_equity` | `night_partial` | `21:30` | `0.35` | `0.00030` |

`XGB_MODEL_CONFIG` tambien define hiperparametros por fondo: `n_estimators`, `learning_rate`, `max_depth`, `min_child_weight`, `gamma`, `subsample`, `colsample_bytree`, `reg_lambda` y `reg_alpha`.

Si se quiere ignorar esos presets:

```bash
python 09_xgboost_prediction.py --train-start 2025-04-04 --train-end 2026-05-01 --eval-start 2026-05-02 --eval-end 2026-06-26 --fund all --single-preset-run --no-fund-presets --decision-mode strict_lag
```

Si se quieren ignorar solo los hiperparametros por fondo y volver a `base_xgb_params`:

```bash
python 09_xgboost_prediction.py --train-start 2025-04-04 --train-end 2026-05-01 --eval-start 2026-05-02 --eval-end 2026-06-26 --fund all --single-preset-run --no-fund-xgb-config
```

### Comandos principales de `09`

Comparar las tres modalidades por fondo:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund all
```

Ejecutar solo el preset por fondo:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund all \
  --single-preset-run
```

Ejecutar un solo fondo:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund national_equity \
  --single-preset-run
```

Forzar una modalidad y umbrales sin editar el codigo:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund all \
  --single-preset-run \
  --override-decision-mode strict_lag \
  --override-probability-threshold 0.55 \
  --override-target-threshold 0.0005
```

Buscar automaticamente `target_threshold`, `probability_threshold` y `decision_mode` con Optuna:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund all \
  --optuna-threshold-search \
  --optuna-trials 80
```

Afinar hiperparametros XGBoost con Optuna usando los presets ya fijados:

```bash
python 09_xgboost_prediction.py \
  --train-start 2025-04-04 \
  --train-end 2026-05-01 \
  --eval-start 2026-05-02 \
  --eval-end 2026-06-26 \
  --fund national_equity \
  --optuna-xgb-search \
  --optuna-xgb-trials 250 \
  --optuna-xgb-score strategy_return
```

### Argumentos CLI relevantes

| Argumento | Descripcion |
| --- | --- |
| `--train-start` | Inicio del periodo de entrenamiento. |
| `--train-end` | Termino del periodo de entrenamiento. Idealmente menor que `eval-start`. |
| `--eval-start` | Inicio del periodo de evaluacion/practica. |
| `--eval-end` | Termino del periodo de evaluacion/practica. |
| `--fund` | Uno o mas fondos: `crecimiento_balanceado`, `ahorro_uf_itau`, `national_equity`, `toesca_equity`, `all`. |
| `--single-preset-run` | Ejecuta una sola configuracion por fondo, usando presets. |
| `--no-fund-presets` | Desactiva `FUND_MODEL_CONFIG` y usa parametros globales. |
| `--no-fund-xgb-config` | Desactiva `XGB_MODEL_CONFIG`. |
| `--decision-mode` | Modalidad global si no se usan presets: `strict_lag`, `night_partial`, `same_day_close`. |
| `--decision-time` | Hora de corte para `night_partial`, por ejemplo `21:30`. |
| `--target-threshold` | Umbral minimo de retorno futuro para marcar `target_up = 1`. |
| `--probability-threshold` | Probabilidad minima del modelo para convertir probabilidad en senal positiva. |
| `--strict-return-lag` | Evita usar algunas variables financieras del mismo dia. |
| `--override-*` | Overrides selectivos sin editar presets en codigo. |
| `--tune` / `--tune-iter` | Tuning interno simple de hiperparametros. |
| `--optuna-threshold-search` | Busca umbrales y modalidad con Optuna. |
| `--optuna-xgb-search` | Busca hiperparametros XGBoost con Optuna. |

### Salidas de `09`

`09` crea automaticamente:

```text
xgboost_outputs/
+-- models/
|   +-- xgb_*.joblib
+-- predictions/
|   +-- predicciones_*.csv
+-- features/
|   +-- dataset_*.csv
|   +-- importancia_*.csv
+-- reports/
    +-- resumen_xgboost_*.json
    +-- resumen_xgboost_*.csv
```

Archivos principales:

| Salida | Contenido |
| --- | --- |
| `models/xgb_*.joblib` | Modelo XGBoost entrenado, columnas usadas, thresholds, serie seleccionada y configuracion. |
| `features/dataset_*.csv` | Dataset final por fondo y experimento: features del fondo + features de noticias + target. |
| `features/importancia_*.csv` | Importancia de variables segun `model.feature_importances_`. |
| `predictions/predicciones_*.csv` | Predicciones por fecha de evaluacion, probabilidades, decisiones y semaforo. |
| `reports/resumen_xgboost_*.json` | Reporte estructurado por experimento. |
| `reports/resumen_xgboost_*.csv` | Version plana del resumen para Excel/pandas. |

### Columnas importantes en predicciones

`predicciones_*.csv` contiene columnas como:

| Columna | Significado |
| --- | --- |
| `valor_cuota` | Valor cuota actual del fondo. |
| `future_exit_date` | Fecha futura usada para calcular el retorno objetivo. |
| `future_valor_cuota` | Valor cuota futuro. |
| `future_return_h` | Retorno futuro en el horizonte del fondo. |
| `target_up` | Resultado real: 1 si supera `target_threshold`, 0 si no. |
| `pred_prob_up` | Probabilidad estimada por XGBoost. |
| `pred_up` | Prediccion binaria tras aplicar `probability_threshold`. |
| `decision` | `mantener` o `mover_o_retirar`. |
| `captured_return_if_follow_signal` | Retorno capturado si se mantiene solo cuando el modelo predice subida. |
| `semaforo` | `verde`, `amarillo` o `rojo`. |
| `decision_if_out` | Decision si actualmente no se esta dentro: `entrar` o `esperar`. |
| `decision_if_in` | Decision si actualmente se esta dentro: `mantener`, `mantener_con_alerta` o `salir_o_mover_defensivo`. |

### Semaforo operativo

El semaforo no reentrena el modelo ni cambia `pred_up`. Es una capa adicional para lectura operativa.

Condiciones usadas:

* `pred_up == 1`
* `pred_prob_up >= probability_threshold`
* `momentum_10 > 0`
* `valor_cuota_vs_ma20 > 0`
* `drawdown_20 > -0.04`

Regla:

| Semaforo | Lectura |
| --- | --- |
| `verde` | Cumple prediccion, probabilidad y condiciones tecnicas minimas. |
| `amarillo` | Condiciones mixtas; puede justificar mantener con alerta si ya se esta dentro. |
| `rojo` | Esperar fuera o evaluar salida/mover a defensivo. |

### Metricas del reporte

Cada experimento guarda metricas de clasificacion y de estrategia:

| Metrica | Significado |
| --- | --- |
| `accuracy` | Proporcion total de aciertos. |
| `balanced_accuracy` | Accuracy balanceada entre clases. |
| `precision_up` | Precision cuando el modelo predice mantener. |
| `recall_up` | Cobertura de dias que realmente suben. |
| `f1_up` | Balance entre precision y recall de la clase positiva. |
| `roc_auc` | Separacion probabilistica si hay ambas clases. |
| `buy_hold_return_compounded` | Retorno acumulado manteniendo siempre. |
| `strategy_return_compounded` | Retorno acumulado siguiendo la senal del modelo. |
| `strategy_improvement_vs_buy_hold` | Diferencia entre estrategia y buy & hold. |
| `avg_future_return_when_pred_up` | Retorno futuro promedio cuando predice mantener. |
| `avg_future_return_when_pred_down` | Retorno futuro promedio cuando predice mover/retiro. |
| `signals_up_mantener` | Cantidad de senales mantener. |
| `signals_down_mover_o_retirar` | Cantidad de senales mover/retiro. |

La matriz de confusion se interpreta asi:

| Real / Prediccion | Predice mover/retiro | Predice mantener |
| --- | --- | --- |
| Real no sube o baja | Salida correcta (`TN`) | Mantener incorrecto (`FP`) |
| Real sube | Salida incorrecta / oportunidad perdida (`FN`) | Mantener correcto (`TP`) |

---

## 10. Graficos de reportes XGBoost

`10_graficos_xgboost.py` lee los JSON generados por `09` desde:

```text
xgboost_outputs/reports/
```

Y genera dashboards PNG en:

```text
xgboost_outputs/report_charts/
```

Cada grafico resume:

1. Retorno acumulado Buy & Hold vs estrategia.
2. Mejora de la estrategia frente a Buy & Hold.
3. Metricas de clasificacion principales.
4. Retorno futuro promedio segun senal.
5. Matriz de confusion interpretada por fondo.

Uso:

```bash
python 10_graficos_xgboost.py
python 10_graficos_xgboost.py --save-only
python 10_graficos_xgboost.py --show
python 10_graficos_xgboost.py --report-dir xgboost_outputs/reports --pattern "resumen_xgboost*.json"
```

---

## 11. Estructura de archivos

```text
el_animal_FM/
+-- 01_biobio_download.py
+-- 02_mostrador_download.py
+-- 03_normalizador_noticias.py
+-- 04_unificador_noticias_diccionario.py
+-- 05_creador_diccionario_adicional.py
+-- 06_enriquecer_noticias.py
+-- 07_download_biobio_from_google.py
+-- 08_descarga_fondos_mutuos.py
+-- 09_xgboost_prediction.py
+-- 10_graficos_xgboost.py
+-- requirements.txt
+-- README.md
+-- noticias_unificadas.txt
+-- candidatos_diccionario.json
+-- resumen_historial_noticias.json
+-- diccionarios/
|   +-- mercado_volatilidad_v1.txt
|   +-- commodities_clima_v1.txt
|   +-- empresas_chile_v1.txt
|   +-- regulatorio_tributario_v1.txt
|   +-- politico_corporativo_v1.txt
|   +-- macro_indicadoresV1.txt
+-- biobio/
|   +-- resumen_descarga_*.txt
|   +-- resumen_google_biobio_*.txt
|   +-- DD_MM_YYYY/
|       +-- noticias_dia.txt
|       +-- noticias_dia.txt.bak
|       +-- noticias_dia_enriquecidas.txt
|       +-- html/
|           +-- *.html
+-- mostrador/
|   +-- resumen_descarga_*.txt
|   +-- DD_MM_YYYY/
|       +-- noticias_dia.txt
|       +-- noticias_dia.txt.bak
|       +-- noticias_dia_enriquecidas.txt
|       +-- html/
|           +-- *.html
+-- features_summary/
|   +-- resumen_enriquecimiento_*.json
+-- downloads/
|   +-- resumen_cmf_*.json
|   +-- <codigo_fondo>_<slug_fondo>/
|       +-- *.txt
+-- xgboost_outputs/
    +-- models/
    +-- predictions/
    +-- features/
    +-- reports/
    +-- report_charts/
```

---

## 12. Datos generados actualmente

Metricas historicas ya presentes en el proyecto:

| Archivo o carpeta | Metrica | Valor |
| --- | --- | --- |
| `noticias_unificadas.txt` | Archivos diarios procesados | 90 |
| `noticias_unificadas.txt` | Noticias unificadas | 4.736 |
| `candidatos_diccionario.json` | Articulos totales | 4.736 |
| `candidatos_diccionario.json` | Textos utiles para analisis general | 3.757 |
| `candidatos_diccionario.json` | Textos financieros estrictos | 819 |
| `candidatos_diccionario.json` | Textos de riesgo politico | 477 |
| `candidatos_diccionario.json` | Textos geopoliticos con contexto de mercado | 333 |
| `biobio/*/noticias_dia_enriquecidas.txt` | Archivos enriquecidos existentes | 411 |
| `mostrador/*/noticias_dia_enriquecidas.txt` | Archivos enriquecidos existentes | 320 |
| `xgboost_outputs/` | Archivos predictivos generados | 2.070 |

Resumenes existentes relevantes:

```text
biobio/resumen_descarga_*.txt
biobio/resumen_google_biobio_*.txt
mostrador/resumen_descarga_*.txt
features_summary/resumen_enriquecimiento_*.json
downloads/resumen_cmf_*.json
xgboost_outputs/reports/resumen_xgboost_*.json
xgboost_outputs/reports/resumen_xgboost_*.csv
```

---

## 13. Consideraciones metodologicas

Este proyecto ya contiene una primera version funcional del predictor, pero los resultados deben leerse como senales experimentales, no como recomendacion financiera automatica.

Puntos criticos:

* La calidad de descarga importa. Fechas faltantes, cuerpos mal extraidos o ruido editorial afectan diccionarios, features y modelo.
* `candidatos_diccionario.json` es exploratorio. No debe aceptarse automaticamente como verdad semantica.
* Las features de `06` son heuristicas. Sirven para modelar, auditar y comparar, pero requieren revision contra ejemplos reales.
* La separacion temporal entre entrenamiento y evaluacion es importante. Idealmente `train_end < eval_start`.
* `same_day_close` puede ser util para benchmark, pero puede ser menos realista operacionalmente si se usa informacion que no estaba disponible al momento de decidir.
* `night_partial` depende de que las noticias tengan hora de publicacion parseable.
* El modelo XGBoost aprende correlaciones del periodo disponible. Con pocos datos o cambios de regimen, las metricas pueden variar fuertemente.
* `strategy_return_compounded` asume seguir mecanicamente la senal y no incorpora costos, restricciones, impuestos, ventanas reales de rescate/suscripcion ni fricciones operativas.
* El semaforo es una capa de lectura operativa, no una garantia de resultado.

La forma recomendada de avanzar es mantener reportes por periodo, comparar modalidades, revisar importancias de variables, auditar predicciones puntuales y ampliar el historial antes de interpretar estabilidad del modelo.
