# Scraper y Pipeline de Noticias para Analisis de Volatilidad

Este proyecto descarga noticias de medios chilenos, las normaliza, consolida un corpus comun, genera candidatos para diccionarios tematicos y enriquece cada noticia con features heuristicas orientadas a analisis financiero, riesgo politico, commodities, instituciones, geopolitica y volatilidad.

El flujo actual trabaja con dos fuentes principales de noticias:

| Medio | Carpeta de salida | Estado |
| --- | --- | --- |
| BioBioChile | `biobio/` | Implementado |
| El Mostrador | `mostrador/` | Implementado |

Ademas existe un complemento separado para descargar cartolas diarias de fondos desde CMF hacia `downloads/`. Ese complemento no es requisito para crear ni enriquecer noticias, pero puede servir despues para cruzar senales noticiosas con series financieras.

---

## Menu

* [1. Objetivo](#1-objetivo)
* [2. Razonamiento de esta documentacion](#2-razonamiento-de-esta-documentacion)
* [3. Flujo principal](#3-flujo-principal)
* [4. Scripts](#4-scripts)
* [5. Instalacion](#5-instalacion)
* [6. Ejecucion recomendada](#6-ejecucion-recomendada)
* [7. Estructura esperada](#7-estructura-esperada)
* [8. Fuentes de noticias](#8-fuentes-de-noticias)
* [9. Formatos de salida](#9-formatos-de-salida)
* [10. Diccionarios y enriquecimiento](#10-diccionarios-y-enriquecimiento)
* [11. Datos generados](#11-datos-generados)
* [12. Complementos](#12-complementos)
* [13. Consideraciones metodologicas](#13-consideraciones-metodologicas)

---

## 1. Objetivo

El objetivo es transformar noticias publicadas diariamente en datos estructurados y auditables para construir variables que luego puedan relacionarse con mercado, riesgo politico, volatilidad, commodities, empresas, instituciones y fondos financieros.

El proyecto busca:

1. Descargar noticias por fecha y fuente.
2. Guardar HTML crudo para auditoria.
3. Extraer campos estructurados desde cada articulo.
4. Reparar encoding, HTML residual y ruido editorial.
5. Unificar noticias de distintas fuentes en un corpus comun.
6. Crear textos de clasificacion a partir de titulo, bajada, resumen y cuerpo.
7. Extraer candidatos de diccionario con frecuencia, TF-IDF, YAKE, entidades, embeddings y clustering.
8. Enriquecer las noticias diarias con familias tematicas, puntajes y senales de impacto potencial.
9. Preparar insumos para reglas heuristicas, modelos NLP, modelos clasicos de machine learning o modelos predictivos.

---

## 2. Razonamiento de esta documentacion

La actualizacion del README se basa en revisar los archivos Python numerados que ejecutan acciones concretas. El criterio fue separar:

| Tipo | Criterio usado | Scripts |
| --- | --- | --- |
| Pipeline principal de noticias | Produce o transforma `noticias_dia.txt`, `noticias_unificadas.txt`, `candidatos_diccionario.json` o `noticias_dia_enriquecidas.txt`. | `01` a `06` |
| Herramienta alternativa | Apoya una fuente ya existente, pero no reemplaza el flujo principal. | `07` |
| Complemento financiero | Descarga series externas para uso posterior, no procesa noticias. | `08` |

La justificacion es que el proyecto ya no termina en `05_creador_diccionario_adicional.py`. El script `06_enriquecer_noticias.py` recorre las carpetas diarias, carga diccionarios curados, puede incorporar candidatos automaticos y escribe `noticias_dia_enriquecidas.txt` sin destruir el archivo original. Por eso el README debe describir el enriquecimiento como una etapa actual, no futura.

Tambien es importante no sobredimensionar `05`: ese script no genera un clasificador final. Genera candidatos exploratorios para revision y para alimentar parcialmente `06`. El enriquecimiento usa semillas propias, archivos en `diccionarios/` y, salvo `--no-candidates`, tambien `candidatos_diccionario.json`.

---

## 3. Flujo principal

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
diccionarios/*.txt + semillas internas de 06
   ↓
06_enriquecer_noticias.py
   ↓
biobio/DD_MM_YYYY/noticias_dia_enriquecidas.txt
mostrador/DD_MM_YYYY/noticias_dia_enriquecidas.txt
features_summary/resumen_enriquecimiento_*.json
```

El pipeline tiene dos niveles:

* Corpus y diccionario: `01` a `05` construyen la base historica y candidatos.
* Features por noticia: `06` aplica diccionarios y reglas para dejar cada noticia enriquecida.

---

## 4. Scripts

| Script | Funcion | Entrada | Salida |
| --- | --- | --- | --- |
| `01_biobio_download.py` | Descarga noticias de BioBioChile por fecha o rango. | BioBioChile: sitemap, Lo Ultimo y archivos de categorias. | `biobio/DD_MM_YYYY/noticias_dia.txt`, HTML crudo y resumen de descarga. |
| `02_mostrador_download.py` | Descarga noticias de El Mostrador por fecha o rango. | El Mostrador: home, `/dia/`, `/categoria/dia/`, secciones y sitemaps. | `mostrador/DD_MM_YYYY/noticias_dia.txt`, HTML crudo y resumen de descarga. |
| `03_normalizador_noticias.py` | Repara texto, elimina ruido y recalcula metricas. | `noticias_dia.txt` por medio y fecha. | Archivo normalizado y respaldo `.bak`; opcionalmente `noticias_dia_normalizado.txt`. |
| `04_unificador_noticias_diccionario.py` | Reduce y unifica noticias en un corpus comun. | Carpetas `biobio/` y `mostrador/`. | `noticias_unificadas.txt`. |
| `05_creador_diccionario_adicional.py` | Extrae candidatos de diccionario desde el corpus. | `noticias_unificadas.txt`. | `candidatos_diccionario.json`. |
| `06_enriquecer_noticias.py` | Aplica diccionarios, candidatos y semillas para enriquecer noticias. | `noticias_dia.txt`, `diccionarios/`, `candidatos_diccionario.json`. | `noticias_dia_enriquecidas.txt` y resumen en `features_summary/`. |
| `07_download_biobio_from_google.py` | Busca noticias historicas de BioBio mediante Google y reutiliza el parser de `01`. | Google + `01_biobio_download.py`. | Actualiza/mezcla `biobio/DD_MM_YYYY/noticias_dia.txt` y genera resumen Google. |
| `08_descarga_fondos_mutuos.py` | Descarga cartola diaria CMF para fondos configurados. | CMF, con CAPTCHA manual. | Archivos por fondo en `downloads/` y resumen CMF. |

---

## 5. Instalacion

Crear y activar un entorno virtual:

```bash
python -m venv .venv
source .venv/bin/activate
```

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Dependencias relevantes:

* Scraping y parsing: `requests`, `beautifulsoup4`, `lxml`, `python-dateutil`.
* NLP y diccionarios: `spacy`, `es_core_news_lg`, `yake`, `scikit-learn`.
* Embeddings y clustering: `sentence-transformers`, `torch`, `hdbscan`.

El script `05_creador_diccionario_adicional.py` es el mas pesado: carga spaCy, embeddings y clustering. Puede usar GPU si `torch.cuda.is_available()` devuelve verdadero.

---

## 6. Ejecucion recomendada

Ejemplo para procesar 45 dias terminando el `2026-06-02`:

```bash
python 01_biobio_download.py --date 2026-06-02 --days-back 45
python 02_mostrador_download.py --date 2026-06-02 --days-back 45
python 03_normalizador_noticias.py
python 04_unificador_noticias_diccionario.py
python 05_creador_diccionario_adicional.py
python 06_enriquecer_noticias.py --date 2026-06-02 --days-back 45 --overwrite
```

Opciones utiles de los descargadores `01` y `02`:

| Opcion | Descripcion |
| --- | --- |
| `--date` | Fecha final. Acepta `DD_MM_YYYY`, `DD-MM-YYYY` o `YYYY-MM-DD`. |
| `--days-back` | Cantidad de dias hacia atras, incluyendo la fecha final. |
| `--base-dir` | Directorio base del proyecto. Por defecto, `.`. |
| `--max-articles` | Limite de noticias por dia para pruebas. `0` significa sin limite. |
| `--sleep` | Pausa entre descargas. |
| `--max-category-pages` | Maximo de paginas de archivo, categoria o seccion a revisar. |
| `--article-workers` | Numero de noticias a descargar en paralelo por dia. |

Normalizar sin sobrescribir:

```bash
python 03_normalizador_noticias.py --no-overwrite
```

Unificar solo algunos medios:

```bash
python 04_unificador_noticias_diccionario.py --media biobio mostrador --output noticias_unificadas.txt
```

Enriquecer un rango especifico:

```bash
python 06_enriquecer_noticias.py --date-from 2026-05-01 --date-to 2026-06-02 --workers 4 --overwrite
```

Enriquecer sin usar candidatos automaticos:

```bash
python 06_enriquecer_noticias.py --no-candidates
```

---

## 7. Estructura esperada

```text
el_animal_FM/
├── 01_biobio_download.py
├── 02_mostrador_download.py
├── 03_normalizador_noticias.py
├── 04_unificador_noticias_diccionario.py
├── 05_creador_diccionario_adicional.py
├── 06_enriquecer_noticias.py
├── 07_download_biobio_from_google.py
├── 08_descarga_fondos_mutuos.py
├── requirements.txt
├── README.md
├── noticias_unificadas.txt
├── candidatos_diccionario.json
├── resumen_historial_noticias.json
├── diccionarios/
│   ├── mercado_volatilidad_v1.txt
│   ├── commodities_clima_v1.txt
│   ├── empresas_chile_v1.txt
│   ├── regulatorio_tributario_v1.txt
│   ├── politico_corporativo_v1.txt
│   └── macro_indicadoresV1.txt
├── biobio/
│   ├── resumen_descarga_DD_MM_YYYY_N_dias.txt
│   ├── resumen_google_biobio_v3_DD_MM_YYYY_N_dias.txt
│   └── DD_MM_YYYY/
│       ├── noticias_dia.txt
│       ├── noticias_dia.txt.bak
│       ├── noticias_dia_enriquecidas.txt
│       └── html/
│           └── *.html
├── mostrador/
│   ├── resumen_descarga_DD_MM_YYYY_N_dias.txt
│   └── DD_MM_YYYY/
│       ├── noticias_dia.txt
│       ├── noticias_dia.txt.bak
│       ├── noticias_dia_enriquecidas.txt
│       └── html/
│           └── *.html
├── features_summary/
│   └── resumen_enriquecimiento_*.json
└── downloads/
    ├── resumen_cmf_*.json
    └── */cmf_*.txt
```

---

## 8. Fuentes de noticias

### BioBioChile

`01_biobio_download.py` usa:

* `news-sitemap.xml`.
* Sitemap mensual `static/sitemap-YYYY-MM.xml`.
* Pagina `lo-ultimo.shtml`.
* Archivos de categorias.
* API de categorias/paginacion.

Filtra principalmente URLs que:

* pertenezcan a `biobiochile.cl`;
* terminen en `.shtml`;
* contengan `/noticias/`;
* coincidan con la fecha objetivo en la ruta.

Tambien excluye rutas como BioBioTV, podcasts, programas, especiales y paginas legales. El parser actual se identifica como:

```text
biobio_raw_v3_category_archives
```

### El Mostrador

`02_mostrador_download.py` usa:

* Pagina principal.
* `/dia/`.
* `/categoria/dia/`.
* Paginacion de `/categoria/dia/page/N/`.
* Secciones editoriales.
* Sitemaps candidatos.

Acepta principalmente URLs con fecha en la ruta:

```text
/YYYY/MM/DD/
```

Excluye paginas de autor, tags, newsletter, paginas institucionales, privacidad, contacto, categorias sin noticia especifica y paginaciones internas. El parser actual se identifica como:

```text
elmostrador_raw_v2_range_sections
```

---

## 9. Formatos de salida

### Archivo diario

Cada `noticias_dia.txt` es JSON:

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

### Corpus unificado

`04_unificador_noticias_diccionario.py` genera `noticias_unificadas.txt` con:

* `metadata`: informacion general de generacion.
* `files_summary`: resumen por archivo diario.
* `articles`: noticias reducidas.

Cada articulo unificado conserva campos como `source`, `source_file`, `published_date`, `url`, `main_section`, `title`, `summary`, `body_text_clean`, `classification_text`, `parser_version`, `parse_success` y `parse_errors`.

`classification_text` combina titulo, subtitulo, bajada, resumen, resumen IA y cuerpo limpio. Es la base para `05`.

---

## 10. Diccionarios y enriquecimiento

### Candidatos automaticos

`05_creador_diccionario_adicional.py` lee `noticias_unificadas.txt` y escribe `candidatos_diccionario.json`.

El analisis incluye:

* Stopwords de spaCy y stopwords personalizadas.
* Normalizacion de frases compuestas como `banco central`, `wall street`, `tipo de cambio` y `deficit fiscal`.
* Filtros heuristicos para textos financieros, riesgo politico y geopolitica con mercado.
* N-grams, TF-IDF y keywords YAKE.
* Entidades con `es_core_news_lg`.
* Embeddings multilingues con `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`.
* Clustering con HDBSCAN.
* Muestras para auditoria manual.

Secciones principales del JSON:

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
├── mercado_volatilidad_v1.txt
├── commodities_clima_v1.txt
├── empresas_chile_v1.txt
├── regulatorio_tributario_v1.txt
├── politico_corporativo_v1.txt
└── macro_indicadoresV1.txt
```

`06_enriquecer_noticias.py` infiere la familia desde el nombre de archivo y acepta `.txt`, `.csv` y `.json`. En archivos de texto, cada linea puede ser un termino simple o un termino con peso separado por coma o punto y coma.

### Enriquecimiento diario

`06_enriquecer_noticias.py` carga:

* semillas internas (`DEFAULT_SEED_TERMS`);
* archivos de `diccionarios/`;
* candidatos de `candidatos_diccionario.json`, salvo que se use `--no-candidates`.

Luego agrega a cada articulo un bloque `features` con:

* `families`: puntajes, hits y detalles por familia tematica;
* `general_classification`: banderas como `is_economic_news`, `is_political_news`, `is_market_news`, `is_social_noise`;
* `impact`: `market_impact_candidate`, `market_impact_score`, direccion esperada, horizonte, riesgo, incertidumbre y confianza;
* `entities`: terminos relevantes detectados, como `has_banco_central`, `has_cmf`, `has_codelco`, `has_china`;
* `temporal`: fecha, hora, dia de semana y fin de semana;
* `audit`: familias activas, terminos encontrados y razon textual de clasificacion.

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

---

## 11. Datos generados

Metricas recalculadas desde los archivos actuales:

| Archivo | Metrica | Valor |
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

Resumenes existentes relevantes:

```text
biobio/resumen_descarga_11_06_2026_5_dias.txt
biobio/resumen_descarga_02_06_2026_45_dias.txt
biobio/resumen_google_biobio_v3_30_03_2026_1000_dias.txt
mostrador/resumen_descarga_11_06_2026_5_dias.txt
mostrador/resumen_descarga_02_06_2026_45_dias.txt
mostrador/resumen_descarga_09_06_2026_1000_dias.txt
features_summary/resumen_enriquecimiento_*.json
```

---

## 12. Complementos

### BioBio historico desde Google

`07_download_biobio_from_google.py` es una herramienta auxiliar para encontrar noticias historicas de BioBio cuando los mecanismos normales no cubren bien ciertas fechas. Reutiliza `01_biobio_download.py` como parser mediante `--parser-file`.

Ejemplo:

```bash
python 07_download_biobio_from_google.py --start-date 2026-04-30 --days-back 30 --max-google-pages 5
```

Puede usar proxies y rotacion de fingerprint. Sus pausas por defecto son deliberadamente largas porque consulta Google.

### Fondos mutuos CMF

`08_descarga_fondos_mutuos.py` descarga cartolas diarias de fondos en tramos de maximo 31 dias por solicitud. Requiere resolver CAPTCHA manualmente.

Ejemplos:

```bash
python 08_descarga_fondos_mutuos.py --list-funds --list-filter itau
python 08_descarga_fondos_mutuos.py --start-date 2025-04-04 --end-date 2026-06-10 --fund balanceado national_equity --skip-existing
```

Fondos configurados en el catalogo interno:

* `balanceado`
* `national_equity`
* `toesca_equity`
* `itau_ahorro_uf`
* `all`

---

## 13. Consideraciones metodologicas

El pipeline actual recolecta, estructura, limpia, unifica y enriquece noticias, pero sus puntajes no deben interpretarse como predicciones financieras definitivas.

`candidatos_diccionario.json` es una salida exploratoria. Sirve para revisar terminos y poblar o ajustar diccionarios, no para aceptar automaticamente reglas de clasificacion.

`noticias_dia_enriquecidas.txt` contiene features heuristicas utiles para analisis posterior, pero requiere validacion contra ejemplos reales y, si se usa para prediccion, contra series financieras externas.

La calidad de descarga, normalizacion y cobertura diaria sigue siendo critica: si una fuente omite fechas, extrae mal el cuerpo o introduce ruido editorial, cualquier diccionario o modelo posterior heredara ese problema.
