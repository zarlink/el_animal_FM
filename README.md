# Scraper y Pipeline de Noticias para Análisis de Volatilidad

Este repositorio descarga noticias desde medios digitales chilenos, normaliza el texto, consolida el corpus y genera candidatos de diccionario para clasificar noticias según su posible relación con mercados, riesgo político, indicadores macroeconómicos, empresas, commodities y volatilidad.

Actualmente el flujo considera dos fuentes principales:

| Medio | Carpeta de salida | Estado |
| --- | --- | --- |
| BioBioChile | `biobio/` | Implementado |
| El Mostrador | `mostrador/` | Implementado |

La finalidad del proyecto es transformar noticias publicadas diariamente en datos estructurados que puedan ser usados posteriormente como entrada para clasificadores heurísticos, modelos NLP, modelos clásicos de machine learning o modelos predictivos asociados a volatilidad de instrumentos financieros.

---

## Menú

* [1. Objetivo general](#1-objetivo-general)
* [2. Flujo del pipeline](#2-flujo-del-pipeline)
* [3. Scripts principales](#3-scripts-principales)
* [4. Instalación y dependencias](#4-instalación-y-dependencias)
* [5. Ejecución recomendada](#5-ejecución-recomendada)
* [6. Estructura del repositorio](#6-estructura-del-repositorio)
* [7. Fuente 1: BioBioChile](#7-fuente-1-biobiochile)
* [8. Fuente 2: El Mostrador](#8-fuente-2-el-mostrador)
* [9. Formato de salida diario](#9-formato-de-salida-diario)
* [10. Normalización de noticias](#10-normalización-de-noticias)
* [11. Unificación del corpus](#11-unificación-del-corpus)
* [12. Creación de candidatos de diccionario](#12-creación-de-candidatos-de-diccionario)
* [13. Diccionarios temáticos](#13-diccionarios-temáticos)
* [14. Estado actual de datos generados](#14-estado-actual-de-datos-generados)
* [15. Exclusiones actuales](#15-exclusiones-actuales)
* [16. Uso futuro de los datos](#16-uso-futuro-de-los-datos)
* [17. Etapas futuras](#17-etapas-futuras)
* [18. Consideración metodológica](#18-consideración-metodológica)

---

## 1. Objetivo general

El objetivo principal es construir una base histórica de noticias chilenas e internacionales publicadas por medios locales, con suficiente estructura y limpieza para analizar su posible relación con variables financieras.

El proyecto busca:

1. Descargar noticias por fecha y por medio.
2. Guardar HTML crudo para auditoría posterior.
3. Extraer campos estructurados desde cada artículo.
4. Reparar problemas de encoding, HTML residual y ruido editorial.
5. Unificar noticias de distintas fuentes en un solo corpus.
6. Construir textos de clasificación a partir de título, bajada, resumen y cuerpo.
7. Extraer candidatos de diccionario mediante frecuencia, TF-IDF, YAKE, entidades, embeddings y clustering.
8. Preparar insumos para clasificadores financieros y modelos predictivos.

---

## 2. Flujo del pipeline

El flujo actual del proyecto es:

```text
01_biobio_download.py
02_mostrador_download.py
   ↓
biobio/DD_MM_YYYY/noticias_dia.txt
mostrador/DD_MM_YYYY/noticias_dia.txt
   ↓
03_normalizador_noticias.py
   ↓
noticias_dia.txt normalizados + respaldos .bak
   ↓
04_unificador_noticias_diccionario.py
   ↓
noticias_unificadas.txt
   ↓
05_creador_diccionario_adicional.py
   ↓
candidatos_diccionario.json
   ↓
diccionarios/*.txt
```

Los scripts `01` y `02` generan datos por fuente y fecha. El script `03` repara y limpia los textos. El script `04` reduce y consolida los registros en un único archivo. El script `05` analiza el corpus y produce candidatos para diccionarios temáticos.

---

## 3. Scripts principales

| Script | Función | Entrada | Salida |
| --- | --- | --- | --- |
| `01_biobio_download.py` | Descarga noticias de BioBioChile por rango de días. | BioBioChile. | `biobio/DD_MM_YYYY/noticias_dia.txt`, HTML crudo y resumen de descarga. |
| `02_mostrador_download.py` | Descarga noticias de El Mostrador por rango de días. | El Mostrador. | `mostrador/DD_MM_YYYY/noticias_dia.txt`, HTML crudo y resumen de descarga. |
| `03_normalizador_noticias.py` | Repara textos, elimina ruido y recalcula métricas del cuerpo. | `noticias_dia.txt` por medio y fecha. | Archivos normalizados y respaldo `.bak`. |
| `04_unificador_noticias_diccionario.py` | Unifica noticias normalizadas en un corpus reducido. | Carpetas `biobio/` y `mostrador/`. | `noticias_unificadas.txt`. |
| `05_creador_diccionario_adicional.py` | Analiza el corpus y genera candidatos para diccionarios. | `noticias_unificadas.txt`. | `candidatos_diccionario.json`. |
| `cmf_download_10063_CB.py` | Descarga información CMF asociada a fondos o series financieras. | CMF. | Archivos en `downloads/`. |

---

## 4. Instalación y dependencias

Crear y activar un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

El archivo `requirements.txt` incluye dependencias de scraping, limpieza, NLP y clustering, entre ellas:

* `requests`
* `beautifulsoup4`
* `lxml`
* `python-dateutil`
* `spacy`
* `es_core_news_lg`
* `scikit-learn`
* `sentence-transformers`
* `hdbscan`
* `yake`

El script `05_creador_diccionario_adicional.py` requiere más recursos que los scrapers, porque carga spaCy, modelos de embeddings y ejecuta clustering.

---

## 5. Ejecución recomendada

Ejemplo para descargar y procesar un rango de 45 días terminando el `2026-06-02`:

```bash
python 01_biobio_download.py --date 2026-06-02 --days-back 45
python 02_mostrador_download.py --date 2026-06-02 --days-back 45
python 03_normalizador_noticias.py
python 04_unificador_noticias_diccionario.py
python 05_creador_diccionario_adicional.py
```

Opciones útiles de los descargadores:

| Opción | Descripción |
| --- | --- |
| `--date` | Fecha final del rango. Acepta `DD_MM_YYYY`, `DD-MM-YYYY` o `YYYY-MM-DD`. |
| `--days-back` | Cantidad total de días hacia atrás, incluyendo la fecha final. |
| `--base-dir` | Directorio base del proyecto. Por defecto, `.`. |
| `--max-articles` | Límite de noticias por día para pruebas. `0` significa sin límite. |
| `--sleep` | Pausa entre descargas. |
| `--max-category-pages` | Máximo de páginas de archivo o categoría a revisar. |
| `--article-workers` | Número de noticias a descargar en paralelo por día. |

El normalizador permite evitar sobrescritura:

```bash
python 03_normalizador_noticias.py --no-overwrite
```

El unificador permite cambiar medios o salida:

```bash
python 04_unificador_noticias_diccionario.py --media biobio mostrador --output noticias_unificadas.txt
```

---

## 6. Estructura del repositorio

Estructura principal esperada:

```text
el_animal_FM/
├── 01_biobio_download.py
├── 02_mostrador_download.py
├── 03_normalizador_noticias.py
├── 04_unificador_noticias_diccionario.py
├── 05_creador_diccionario_adicional.py
├── cmf_download_10063_CB.py
├── requirements.txt
├── README.md
├── noticias_unificadas.txt
├── candidatos_diccionario.json
├── diccionarios/
│   ├── mercado_volatilidad_v1.txt
│   ├── commodities_clima_v1.txt
│   ├── empresas_chile_v1.txt
│   ├── regulatorio_tributario_v1.txt
│   ├── politico_corporativo_v1.txt
│   └── macro_indicadoresV1.txt
├── biobio/
│   ├── resumen_descarga_DD_MM_YYYY_N_dias.txt
│   └── DD_MM_YYYY/
│       ├── noticias_dia.txt
│       ├── noticias_dia.txt.bak
│       └── html/
│           └── *.html
├── mostrador/
│   ├── resumen_descarga_DD_MM_YYYY_N_dias.txt
│   └── DD_MM_YYYY/
│       ├── noticias_dia.txt
│       ├── noticias_dia.txt.bak
│       └── html/
│           └── *.html
└── downloads/
    └── *.txt
```

Las carpetas `biobio/` y `mostrador/` contienen datos descargados por fecha. El archivo `noticias_unificadas.txt` es el corpus consolidado. El archivo `candidatos_diccionario.json` contiene salidas del análisis automático. La carpeta `diccionarios/` guarda diccionarios temáticos curados o en proceso de curaduría.

---

## 7. Fuente 1: BioBioChile

BioBioChile se descarga con `01_biobio_download.py`.

La estrategia de descubrimiento combina:

* `news-sitemap.xml`.
* Página `lo-ultimo.shtml`.
* Archivos de categorías.
* Paginación por categorías.

El scraper privilegia URLs de noticias escritas que:

* pertenezcan a `biobiochile.cl`;
* terminen en `.shtml`;
* contengan `/noticias/`;
* coincidan con la fecha objetivo en la ruta.

Categorías base consideradas:

* Nacional.
* Internacional.
* Economía.
* Deportes.
* Sociedad.
* Espectáculos y TV.
* Opinión.
* BBCL Investiga.

El parser actual se identifica como:

```text
biobio_raw_v3_category_archives
```

---

## 8. Fuente 2: El Mostrador

El Mostrador se descarga con `02_mostrador_download.py`.

La estrategia de descubrimiento combina:

* Página principal.
* `/dia/`.
* `/categoria/dia/`.
* Paginación de `/categoria/dia/page/N/`.
* Secciones editoriales.
* Sitemaps candidatos.

El scraper acepta principalmente URLs que contienen una fecha en el patrón:

```text
/YYYY/MM/DD/
```

Secciones base consideradas:

* País.
* Mundo.
* Sin editar.
* Mercados.
* Actualidad económica.
* Opinión.
* Columnas.
* Cartas.
* Editorial.
* TV.
* Multimedia.
* Cultura.
* Agenda País.
* Agenda.
* Braga.
* Deportes.

El parser actual se identifica como:

```text
elmostrador_raw_v2_range_sections
```

---

## 9. Formato de salida diario

Cada `noticias_dia.txt` es un JSON con metadatos y artículos:

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

El bloque `raw` contiene información observable de la noticia:

* URL original y URL canónica.
* Fecha y hora de publicación.
* Título, subtítulo, bajada, resumen y cuerpo.
* Autoría.
* Sección editorial.
* Indicadores de tipo de contenido.
* Enlaces relacionados.
* Imágenes, video o audio cuando se detectan.

El bloque `technical` contiene información de auditoría:

* Código HTTP.
* Tipo de contenido.
* Ruta local del HTML.
* Versión del parser.
* Estado de parsing.
* Errores o advertencias.
* Fuentes de descubrimiento.

---

## 10. Normalización de noticias

El script `03_normalizador_noticias.py` procesa los archivos `noticias_dia.txt` de `biobio/` y `mostrador/`.

La normalización realiza:

* Reparación de mojibake, por ejemplo `dÃ©ficit` a `déficit`.
* Decodificación de entidades HTML.
* Eliminación de HTML residual.
* Eliminación de ruido editorial y boilerplate.
* Limpieza de listas de textos relacionados.
* Reconstrucción de párrafos.
* Recalculo de `paragraph_count`.
* Recalculo de `body_length_chars`.
* Recalculo de `body_length_words`.
* Marcado de metadatos con `text_normalized` y `text_normalizer_version`.

Por defecto sobrescribe el archivo original y crea un respaldo `.bak` si no existe. Con `--no-overwrite`, genera un archivo `noticias_dia_normalizado.txt`.

Esta etapa no convierte todo a ASCII. El objetivo es conservar texto en UTF-8 correctamente legible, manteniendo acentos y caracteres propios del español cuando correspondan.

---

## 11. Unificación del corpus

El script `04_unificador_noticias_diccionario.py` recorre las carpetas de medios, busca directorios con formato `DD_MM_YYYY` y carga cada `noticias_dia.txt`.

La salida principal es:

```text
noticias_unificadas.txt
```

Este archivo contiene:

* `metadata`: información general de generación.
* `files_summary`: resumen por archivo diario procesado.
* `articles`: noticias reducidas y listas para análisis.

Cada artículo unificado conserva campos como:

* `source`
* `source_file`
* `published_date`
* `published_time`
* `url`
* `canonical_url`
* `main_section`
* `subsection`
* `title`
* `subtitle`
* `lead`
* `summary`
* `ai_summary`
* `body_text_clean`
* `classification_text`
* `classification_text_length`
* `parser_version`
* `parse_success`
* `parse_errors`

El campo `classification_text` combina título, subtítulo, bajada, resumen y cuerpo limpio. Es el texto base para extracción de palabras clave y construcción de diccionarios.

---

## 12. Creación de candidatos de diccionario

El script `05_creador_diccionario_adicional.py` lee:

```text
noticias_unificadas.txt
```

y escribe:

```text
candidatos_diccionario.json
```

El análisis incluye:

* Limpieza adicional de texto.
* Stopwords de spaCy y stopwords personalizadas.
* Normalización de frases compuestas, como `banco central`, `wall street`, `tipo de cambio` o `déficit fiscal`.
* Clasificación heurística preliminar por familias.
* Extracción de n-grams.
* Extracción TF-IDF.
* Extracción de keywords con YAKE.
* Extracción de entidades con `es_core_news_lg`.
* Embeddings multilingües con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
* Clustering con HDBSCAN.
* Muestras por familia temática para revisión manual.

Familias principales generadas:

| Familia | Descripción |
| --- | --- |
| `general` | Términos frecuentes del corpus completo. |
| `financial_strict` | Noticias con señales financieras, macro, mercado, empresas o commodities. |
| `political_risk` | Noticias con señales de riesgo político, institucional, fiscal o regulatorio. |
| `geopolitical_market` | Noticias geopolíticas con posible vínculo de mercado. |
| `entities_top` | Entidades detectadas por spaCy. |
| `clusters` | Grupos semánticos detectados por embeddings y HDBSCAN. |
| `cluster_examples` | Ejemplos por cluster para auditoría. |

---

## 13. Diccionarios temáticos

La carpeta `diccionarios/` contiene archivos destinados a consolidar términos curados a partir de `candidatos_diccionario.json`.

Archivos actuales:

```text
diccionarios/
├── mercado_volatilidad_v1.txt
├── commodities_clima_v1.txt
├── empresas_chile_v1.txt
├── regulatorio_tributario_v1.txt
├── politico_corporativo_v1.txt
└── macro_indicadoresV1.txt
```

Estos archivos representan categorías reutilizables para una etapa posterior de clasificación. La idea es revisar los candidatos automáticos, seleccionar términos útiles y poblar estos diccionarios con versiones trazables.

---

## 14. Estado actual de datos generados

El corpus unificado actual registra:

| Archivo | Métrica | Valor |
| --- | --- | --- |
| `noticias_unificadas.txt` | Archivos diarios procesados | 90 |
| `noticias_unificadas.txt` | Noticias unificadas | 4.736 |
| `candidatos_diccionario.json` | Artículos totales | 4.736 |
| `candidatos_diccionario.json` | Textos útiles para análisis general | 3.757 |
| `candidatos_diccionario.json` | Textos financieros estrictos | 819 |
| `candidatos_diccionario.json` | Textos de riesgo político | 477 |
| `candidatos_diccionario.json` | Textos geopolíticos con contexto de mercado | 333 |

También existen resúmenes de descarga por rango:

```text
biobio/resumen_descarga_02_06_2026_45_dias.txt
mostrador/resumen_descarga_02_06_2026_45_dias.txt
```

---

## 15. Exclusiones actuales

El scraper busca excluir contenidos que puedan contaminar la base principal de noticias escritas.

En BioBioChile se excluyen, entre otros:

* Podcasts.
* BioBioTV.
* Programas.
* Especiales no noticiosos.
* Páginas legales.
* Contenido que no esté bajo `/noticias/`.

En El Mostrador se excluyen páginas que no correspondan a noticias individuales:

* Páginas de autor.
* Tags.
* Newsletter.
* Páginas institucionales.
* Páginas de privacidad o contacto.
* Paginaciones internas.
* Categorías sin noticia específica.

Además, el análisis de diccionarios excluye o reduce peso de contenidos como deportes, cultura, multimedia, opinión, cartas y editoriales cuando no son útiles para el diccionario financiero.

---

## 16. Uso futuro de los datos

Los datos generados pueden alimentar una capa posterior de clasificación, con variables como:

* Si la noticia es económica, financiera, política, regulatoria, geopolítica o social.
* Si tiene impacto potencial en mercado.
* Qué familia temática domina.
* Qué empresas, instituciones, países o sectores aparecen.
* Qué instrumentos financieros podrían verse afectados.
* Qué horizonte temporal podría tener el impacto.
* Si el evento se asocia a volatilidad, riesgo fiscal, commodities, tasas, moneda, crédito o renta variable.

Estas variables podrán correlacionarse con series financieras, fondos mutuos, valores cuota, índices o métricas de volatilidad.

---

## 17. Etapas futuras

Las etapas pendientes más relevantes son:

1. Poblar y versionar los archivos de `diccionarios/` a partir de `candidatos_diccionario.json`.
2. Crear un clasificador que use los diccionarios temáticos para etiquetar noticias nuevas.
3. Diseñar reglas de scoring para intensidad, dirección e impacto esperado.
4. Integrar series financieras descargadas desde CMF u otras fuentes.
5. Generar variables agregadas por día, medio, familia temática y sector.
6. Evaluar modelos clásicos de clasificación o regresión.
7. Probar modelos NLP y embeddings para clasificación supervisada.
8. Evaluar modelos predictivos como XGBoost o TFT.
9. Agregar pruebas y validaciones automáticas de calidad del corpus.
10. Medir cobertura diaria por fuente y detectar brechas de descarga.

---

## 18. Consideración metodológica

El pipeline actual recolecta, estructura, limpia y analiza noticias, pero todavía no debe interpretarse como un clasificador financiero definitivo.

`candidatos_diccionario.json` es una salida exploratoria y debe ser revisada antes de convertirse en reglas de clasificación. Los diccionarios temáticos deben construirse con curaduría manual, control de versiones y validación contra ejemplos reales.

La calidad de las etapas de descarga, normalización y unificación es crítica, porque cualquier modelo posterior dependerá directamente de la cobertura, consistencia y limpieza del corpus.
