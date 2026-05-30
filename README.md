# Scraper de Noticias para Análisis de Volatilidad

Este repositorio tiene por objetivo descargar noticias diarias desde medios digitales chilenos, inicialmente **Radio Bío Bío / BioBioChile** y **El Mostrador**, para construir una base de datos estructurada que permita realizar análisis de volatilidad de mercado.

La finalidad del proyecto es transformar noticias publicadas diariamente en datos estructurados que, en una etapa posterior, puedan ser utilizados como entrada para modelos de machine learning, tales como **XGBoost**, **TFT**, modelos clásicos de clasificación o aproximaciones de NLP.

---

## Menú

* [1. Objetivo general del proyecto](#1-objetivo-general-del-proyecto)
* [2. Medios considerados](#2-medios-considerados)
* [3. Estructura general del repositorio](#3-estructura-general-del-repositorio)
* [4. Flujo general del scraper](#4-flujo-general-del-scraper)
* [5. Fuente 1: BioBioChile](#5-fuente-1-biobiochile)

  * [5.1 Estrategia de descubrimiento](#51-estrategia-de-descubrimiento)
  * [5.2 Estructura de salida de BioBioChile](#52-estructura-de-salida-de-biobiochile)
  * [5.3 Campos principales extraídos desde BioBioChile](#53-campos-principales-extraídos-desde-biobiochile)
* [6. Fuente 2: El Mostrador](#6-fuente-2-el-mostrador)

  * [6.1 Estrategia de descubrimiento](#61-estrategia-de-descubrimiento)
  * [6.2 Secciones consideradas](#62-secciones-consideradas)
  * [6.3 Estructura de salida de El Mostrador](#63-estructura-de-salida-de-el-mostrador)
  * [6.4 Campos principales extraídos desde El Mostrador](#64-campos-principales-extraídos-desde-el-mostrador)
* [7. Bloque `raw`](#7-bloque-raw)
* [8. Bloque `technical`](#8-bloque-technical)
* [9. Organización de carpetas](#9-organización-de-carpetas)
* [10. Exclusiones actuales](#10-exclusiones-actuales)
* [11. Uso futuro de los datos](#11-uso-futuro-de-los-datos)
* [12. Etapas futuras del proyecto](#12-etapas-futuras-del-proyecto)
* [13. Consideración metodológica](#13-consideración-metodológica)

---

## 1. Objetivo general del proyecto

El objetivo principal es recolectar noticias diarias, extraer información relevante desde cada artículo y almacenarla en un formato estructurado que permita, posteriormente, analizar su posible relación con la volatilidad de instrumentos financieros, fondos mutuos o mercados específicos.

En esta primera etapa, el foco está puesto en:

1. Descargar noticias desde medios digitales.
2. Extraer información estructurada desde cada noticia.
3. Guardar los datos en archivos organizados por fecha y por medio.
4. Preparar la información para una futura etapa de clasificación.
5. Construir una base histórica que permita correlacionar noticias con variables financieras.
6. Generar insumos para modelos predictivos o explicativos de volatilidad.

---

## 2. Medios considerados

Actualmente el proyecto contempla dos fuentes principales:

| Medio        | Carpeta de salida | Estado        |
| ------------ | ----------------- | ------------- |
| BioBioChile  | `biobio/`         | En desarrollo |
| El Mostrador | `mostrador/`      | En desarrollo |

Ambos scrapers comparten una lógica común:

* Descubrir noticias del día.
* Filtrar URLs válidas.
* Descargar el HTML de cada noticia.
* Extraer campos estructurados.
* Guardar el HTML crudo.
* Generar un archivo diario con la información procesada.
* Registrar información técnica del proceso.

---

## 3. Estructura general del repositorio

Una estructura esperada del proyecto puede ser la siguiente:

```text
el_animal_FM/
├── biobio/
│   └── 30_05_2026/
│       ├── noticias_dia.txt
│       └── html/
│           ├── noticia_1.html
│           ├── noticia_2.html
│           └── ...
│
├── mostrador/
│   └── 30_05_2026/
│       ├── noticias_dia.txt
│       └── html/
│           ├── noticia_1.html
│           ├── noticia_2.html
│           └── ...
│
├── scripts/
│   ├── biobio_scraper.py
│   └── mostrador_scraper.py
│
├── requirements.txt
└── README.md
```

Donde:

* `biobio/` contiene las noticias descargadas desde BioBioChile.
* `mostrador/` contiene las noticias descargadas desde El Mostrador.
* Cada carpeta diaria se identifica con formato `DD_MM_YYYY`.
* `noticias_dia.txt` contiene la información estructurada.
* `html/` almacena el HTML crudo de cada noticia.

---

## 4. Flujo general del scraper

El flujo general del proyecto es el siguiente:

```text
Scraper
   ↓
Descubre URLs del día
   ↓
Filtra URLs válidas
   ↓
Descarga HTML de cada noticia
   ↓
Extrae datos raw
   ↓
Registra datos technical
   ↓
Guarda noticias_dia.txt
   ↓
Guarda HTML crudo
```

La información se guarda en formato JSON dentro de archivos `.txt`, lo que permite inspección manual y posterior procesamiento automático.

---

## 5. Fuente 1: BioBioChile

BioBioChile es la primera fuente trabajada en el proyecto.

El scraper busca obtener noticias diarias desde distintas categorías, excluyendo contenidos que no correspondan al flujo principal de noticias escritas, tales como podcasts o contenido audiovisual puro.

Entre las secciones relevantes se encuentran:

* Nacional.
* Internacional.
* Economía.
* Opinión.
* BBCL Investiga.
* Servicios / BBCL Contigo.
* Deportes.
* Tendencias.
* Artes y cultura.
* Espectáculos y TV.

---

## 5.1 Estrategia de descubrimiento

La estrategia actual de BioBioChile considera archivos de categorías, por ejemplo:

```text
https://www.biobiochile.cl/lista/categorias/nacional
```

La lógica consiste en:

1. Recorrer categorías de noticias.
2. Detectar tarjetas o enlaces de artículos.
3. Filtrar URLs que correspondan a noticias estándar.
4. Excluir podcasts, BioBioTV y contenido no noticioso.
5. Deduplicar noticias repetidas entre categorías.
6. Descargar cada noticia.
7. Extraer campos `raw` y `technical`.
8. Guardar la información estructurada.

El scraper busca privilegiar rutas de noticias escritas, generalmente bajo URLs que contienen:

```text
/noticias/
```

y que terminan en:

```text
.shtml
```

---

## 5.2 Estructura de salida de BioBioChile

Cada noticia de BioBioChile se almacena con la siguiente estructura general:

```json
{
  "raw": {
    "source": "biobiochile",
    "source_type": "news_site",
    "url": "https://www.biobiochile.cl/...",
    "canonical_url": "",
    "article_id": "",
    "slug": "",
    "scraped_at": "",
    "published_at_raw": "",
    "published_at": "",
    "published_date": "",
    "published_time": "",
    "timezone": "America/Santiago"
  },
  "technical": {
    "http_status": 200,
    "content_type": "text/html",
    "downloaded_from_sitemap": false,
    "downloaded_from_feed": true,
    "html_raw_path": "",
    "parser_version": "",
    "parse_success": true,
    "parse_errors": [],
    "template_noise_detected": false,
    "robots_allowed_checked": "not_checked",
    "discovery_sources": []
  }
}
```

---

## 5.3 Campos principales extraídos desde BioBioChile

El scraper de BioBioChile intenta extraer:

### Identificación

| Campo              | Descripción                       |
| ------------------ | --------------------------------- |
| `source`           | Medio de origen.                  |
| `source_type`      | Tipo de fuente.                   |
| `url`              | URL original de la noticia.       |
| `canonical_url`    | URL canónica.                     |
| `article_id`       | Identificador interno, si existe. |
| `slug`             | Fragmento final de la URL.        |
| `scraped_at`       | Fecha y hora de descarga.         |
| `published_at_raw` | Fecha original detectada.         |
| `published_at`     | Fecha normalizada.                |
| `published_date`   | Fecha en formato `YYYY-MM-DD`.    |
| `published_time`   | Hora de publicación.              |
| `timezone`         | Zona horaria.                     |

### Clasificación editorial observable

| Campo                      | Descripción                     |
| -------------------------- | ------------------------------- |
| `main_section`             | Sección principal.              |
| `subsection`               | Subsección.                     |
| `breadcrumb_raw`           | Breadcrumb visible.             |
| `article_type_editorial`   | Tipo de contenido.              |
| `is_opinion`               | Si corresponde a opinión.       |
| `is_investigation`         | Si corresponde a investigación. |
| `is_economy_section`       | Si pertenece a economía.        |
| `is_national_section`      | Si pertenece a nacional.        |
| `is_international_section` | Si pertenece a internacional.   |
| `region_section`           | Región asociada, si existe.     |

### Texto principal

| Campo                  | Descripción                             |
| ---------------------- | --------------------------------------- |
| `title`                | Título de la noticia.                   |
| `subtitle`             | Subtítulo o bajada.                     |
| `lead`                 | Primer texto relevante detectado.       |
| `ai_summary`           | Resumen generado por IA, cuando existe. |
| `has_ai_summary`       | Indica si existe resumen IA.            |
| `summary_source`       | Fuente del resumen.                     |
| `body_text_raw`        | Texto completo extraído.                |
| `body_text_clean`      | Texto limpio y normalizado.             |
| `paragraphs`           | Lista de párrafos.                      |
| `paragraph_count`      | Cantidad de párrafos.                   |
| `body_length_chars`    | Largo en caracteres.                    |
| `body_length_words`    | Largo en palabras.                      |
| `internal_subheadings` | Subtítulos internos.                    |
| `quote_count`          | Conteo aproximado de citas.             |

### Autoría

| Campo                   | Descripción                            |
| ----------------------- | -------------------------------------- |
| `author_name`           | Nombre del autor.                      |
| `author_url`            | URL del autor, si existe.              |
| `author_role`           | Rol o cargo.                           |
| `author_image_url`      | Imagen del autor.                      |
| `source_attribution`    | Fuente externa o agencia.              |
| `is_agency_content`     | Si proviene de agencia.                |
| `is_staff_writer`       | Si corresponde a periodista del medio. |
| `is_external_columnist` | Si corresponde a columnista externo.   |

### Multimedia y enlaces

| Campo                | Descripción                      |
| -------------------- | -------------------------------- |
| `main_image_url`     | Imagen principal.                |
| `main_image_alt`     | Texto alternativo de imagen.     |
| `image_caption`      | Pie de foto.                     |
| `image_credit`       | Crédito de imagen.               |
| `has_image`          | Si contiene imagen.              |
| `image_count`        | Número de imágenes detectadas.   |
| `has_video`          | Si contiene video.               |
| `video_url`          | URL del video.                   |
| `has_audio`          | Si contiene audio.               |
| `media_type`         | Tipo de contenido.               |
| `read_also_links`    | Enlaces “Lee también”.           |
| `related_links`      | Enlaces relacionados.            |
| `share_facebook_url` | Link para compartir en Facebook. |
| `share_x_url`        | Link para compartir en X.        |
| `share_whatsapp_url` | Link para compartir en WhatsApp. |

---

## 6. Fuente 2: El Mostrador

El Mostrador es la segunda fuente considerada en el proyecto.

A diferencia de BioBioChile, El Mostrador presenta una estructura más cercana a WordPress, con páginas como:

```text
https://www.elmostrador.cl/dia/
https://www.elmostrador.cl/categoria/dia/
```

Además, el scraper contempla distintas secciones editoriales, tales como:

* País.
* Mundo.
* Mercados.
* Actualidad económica.
* Opinión.
* Columnas.
* Cartas.
* Editorial.
* Multimedia.
* Cultura.
* Agenda País.
* Braga.
* Deportes.

---

## 6.1 Estrategia de descubrimiento

La estrategia de El Mostrador se basa en varias fuentes de descubrimiento:

1. Página `/dia/`.
2. Página `/categoria/dia/`.
3. Paginación de `/categoria/dia/page/N/`.
4. Archivos de secciones.
5. Sitemaps candidatos.
6. Página principal.

El scraper intenta detectar noticias del día revisando URLs que contienen una fecha en el patrón:

```text
/YYYY/MM/DD/
```

Ejemplo:

```text
https://www.elmostrador.cl/noticias/pais/2026/05/30/...
```

A diferencia de BioBioChile, El Mostrador no depende de archivos `.shtml`, sino de rutas fechadas.

---

## 6.2 Secciones consideradas

El scraper de El Mostrador contiene una lista base de secciones que se consultan para descubrir noticias.

Ejemplos:

```text
https://www.elmostrador.cl/
https://www.elmostrador.cl/noticias/pais/
https://www.elmostrador.cl/noticias/mundo/
https://www.elmostrador.cl/mercados/
https://www.elmostrador.cl/mercados/actualidad-economica/
https://www.elmostrador.cl/noticias/opinion/
https://www.elmostrador.cl/categoria/columnas/
https://www.elmostrador.cl/categoria/cartas/
https://www.elmostrador.cl/categoria/editorial/
https://www.elmostrador.cl/noticias/multimedia/
https://www.elmostrador.cl/cultura/
https://www.elmostrador.cl/agenda-pais/
https://www.elmostrador.cl/braga/
https://www.elmostrador.cl/noticias/deportes/
```

Estas rutas permiten ampliar la cobertura más allá de la página principal del día.

---

## 6.3 Estructura de salida de El Mostrador

Cada noticia de El Mostrador se almacena con una estructura similar a BioBioChile, pero con campos adicionales asociados a su estructura editorial.

```json
{
  "raw": {
    "source": "elmostrador",
    "source_type": "news_site",
    "url": "",
    "canonical_url": "",
    "article_id": "",
    "slug": "",
    "scraped_at": "",
    "published_at_raw": "",
    "published_at": "",
    "published_date": "",
    "published_time": "",
    "timezone": "America/Santiago",

    "main_section": "",
    "subsection": "",
    "breadcrumb_raw": "",
    "article_type_editorial": "",
    "site_vertical": "",
    "program_or_series": "",

    "is_opinion": false,
    "is_column": false,
    "is_letter_to_editor": false,
    "is_editorial": false,
    "is_market_section": false,
    "is_economy_section": false,
    "is_country_section": false,
    "is_world_section": false,
    "is_multimedia": false,
    "is_regional": false,
    "is_agenda_pais": false,
    "is_culture": false,
    "is_deportes": false,
    "region_section": ""
  },
  "technical": {
    "http_status": 200,
    "content_type": "text/html",
    "downloaded_from_sitemap": false,
    "downloaded_from_feed": false,
    "downloaded_from_dia_page": false,
    "downloaded_from_categoria_dia": false,
    "html_raw_path": "",
    "parser_version": "elmostrador_raw_v2_range_sections",
    "parse_success": true,
    "parse_errors": [],
    "template_noise_detected": false,
    "robots_allowed_checked": "not_checked",
    "discovery_sources": []
  }
}
```

---

## 6.4 Campos principales extraídos desde El Mostrador

El scraper de El Mostrador intenta extraer información más amplia debido a la estructura editorial del sitio.

### Identificación

| Campo              | Descripción                                  |
| ------------------ | -------------------------------------------- |
| `source`           | Medio de origen, en este caso `elmostrador`. |
| `source_type`      | Tipo de fuente.                              |
| `url`              | URL original de la noticia.                  |
| `canonical_url`    | URL canónica.                                |
| `article_id`       | Identificador interno, si se detecta.        |
| `slug`             | Fragmento final de la URL.                   |
| `scraped_at`       | Fecha y hora de descarga.                    |
| `published_at_raw` | Fecha original detectada.                    |
| `published_at`     | Fecha normalizada.                           |
| `published_date`   | Fecha en formato `YYYY-MM-DD`.               |
| `published_time`   | Hora de publicación.                         |
| `timezone`         | Zona horaria.                                |

### Clasificación editorial observable

| Campo                    | Descripción                                |
| ------------------------ | ------------------------------------------ |
| `main_section`           | Sección principal.                         |
| `subsection`             | Subsección.                                |
| `breadcrumb_raw`         | Breadcrumb visible.                        |
| `article_type_editorial` | Tipo de contenido.                         |
| `site_vertical`          | Vertical editorial del sitio.              |
| `program_or_series`      | Programa o serie asociada, si corresponde. |
| `is_opinion`             | Si corresponde a opinión.                  |
| `is_column`              | Si corresponde a columna.                  |
| `is_letter_to_editor`    | Si corresponde a carta al director.        |
| `is_editorial`           | Si corresponde a editorial.                |
| `is_market_section`      | Si pertenece a mercados.                   |
| `is_economy_section`     | Si pertenece a economía o mercados.        |
| `is_country_section`     | Si pertenece a país.                       |
| `is_world_section`       | Si pertenece a mundo.                      |
| `is_multimedia`          | Si corresponde a multimedia.               |
| `is_regional`            | Si corresponde a contenido regional.       |
| `is_agenda_pais`         | Si pertenece a Agenda País.                |
| `is_culture`             | Si pertenece a cultura.                    |
| `is_deportes`            | Si pertenece a deportes.                   |
| `region_section`         | Región asociada, si existe.                |

### Texto principal

| Campo                   | Descripción                          |
| ----------------------- | ------------------------------------ |
| `title`                 | Título principal.                    |
| `subtitle`              | Subtítulo o descripción breve.       |
| `lead`                  | Primer párrafo o bajada relevante.   |
| `summary`               | Resumen general.                     |
| `ai_summary`            | Síntesis generada con IA, si existe. |
| `has_ai_summary`        | Indica si existe resumen IA.         |
| `summary_source`        | Fuente del resumen.                  |
| `title_length_chars`    | Largo del título.                    |
| `subtitle_length_chars` | Largo del subtítulo.                 |
| `summary_length_chars`  | Largo del resumen.                   |
| `body_text_raw`         | Texto completo extraído.             |
| `body_text_clean`       | Texto limpio.                        |
| `paragraphs`            | Lista de párrafos.                   |
| `paragraph_count`       | Número de párrafos.                  |
| `body_length_chars`     | Largo en caracteres.                 |
| `body_length_words`     | Largo aproximado en palabras.        |
| `internal_subheadings`  | Subtítulos internos.                 |
| `quote_count`           | Conteo aproximado de citas.          |
| `has_quotes`            | Indica si existen citas.             |

### Autoría y atribución

| Campo                   | Descripción                                    |
| ----------------------- | ---------------------------------------------- |
| `author_name`           | Nombre del autor.                              |
| `author_url`            | URL del autor.                                 |
| `author_role`           | Rol o cargo del autor.                         |
| `author_bio`            | Biografía breve, si se detecta.                |
| `author_type`           | Tipo de autor.                                 |
| `source_attribution`    | Fuente o agencia externa.                      |
| `is_staff_writer`       | Si corresponde a periodista o autor del medio. |
| `is_newsroom`           | Si corresponde a mesa de noticias.             |
| `is_external_columnist` | Si corresponde a columnista externo.           |
| `is_agency_content`     | Si proviene de agencia.                        |
| `agency_name`           | Nombre de la agencia detectada.                |
| `desk_or_team`          | Equipo o mesa asociada.                        |

### Enlaces, documentos y contenido relacionado

| Campo                     | Descripción                                      |
| ------------------------- | ------------------------------------------------ |
| `external_links_in_body`  | Links externos dentro del cuerpo.                |
| `internal_links_in_body`  | Links internos dentro del cuerpo.                |
| `document_links`          | Links a documentos, PDF, Excel u otros archivos. |
| `has_document_link`       | Indica si existen documentos vinculados.         |
| `mentioned_documents_raw` | Texto asociado a documentos mencionados.         |
| `also_interesting_links`  | Links de “También te puede interesar”.           |
| `also_interesting_titles` | Títulos asociados.                               |
| `also_interesting_count`  | Cantidad de enlaces detectados.                  |
| `featured_links`          | Links destacados.                                |
| `featured_titles`         | Títulos destacados.                              |
| `featured_count`          | Cantidad de destacados.                          |
| `same_day_links`          | Noticias del mismo día.                          |
| `same_day_titles`         | Títulos del mismo día.                           |
| `same_day_count`          | Cantidad de noticias del día asociadas.          |
| `related_links`           | Otros enlaces relacionados.                      |
| `related_titles`          | Títulos relacionados.                            |
| `related_count`           | Cantidad total de relacionados.                  |

### Multimedia y canales

| Campo                  | Descripción                             |
| ---------------------- | --------------------------------------- |
| `main_image_url`       | Imagen principal.                       |
| `main_image_alt`       | Texto alternativo.                      |
| `image_caption`        | Pie de foto.                            |
| `image_credit`         | Crédito de imagen.                      |
| `has_image`            | Si contiene imagen.                     |
| `image_count`          | Número de imágenes.                     |
| `has_video`            | Si contiene video.                      |
| `video_url`            | URL del video.                          |
| `has_audio`            | Si contiene audio.                      |
| `audio_url`            | URL de audio.                           |
| `has_embedded_youtube` | Si contiene embed de YouTube.           |
| `has_embedded_spotify` | Si contiene embed de Spotify.           |
| `media_type`           | Tipo de medio detectado.                |
| `share_facebook_url`   | Link para compartir en Facebook.        |
| `share_x_url`          | Link para compartir en X.               |
| `share_whatsapp_url`   | Link para compartir por WhatsApp.       |
| `google_news_url`      | Link de Google News, si existe.         |
| `whatsapp_channel_url` | Canal de WhatsApp, si existe.           |
| `youtube_url`          | Canal o embed de YouTube.               |
| `spotify_url`          | Link de Spotify.                        |
| `visible_views_raw`    | Texto visible de visitas.               |
| `views_count`          | Número de visitas, si se puede extraer. |

### Discovery

El Mostrador incorpora un bloque adicional dentro de `raw` llamado `discovery`, que permite auditar cómo fue descubierta la noticia.

```json
{
  "discovery": {
    "discovered_from_dia_page": false,
    "discovered_from_categoria_dia": false,
    "discovered_from_home": false,
    "discovered_from_section": "",
    "listing_position": null,
    "listing_page_number": null,
    "listing_title": "",
    "listing_excerpt": "",
    "listing_author": "",
    "listing_date_raw": "",
    "listing_category": ""
  }
}
```

Este bloque permite conocer:

* Si la noticia fue descubierta desde `/dia/`.
* Si apareció en `/categoria/dia/`.
* Si fue encontrada desde una sección.
* En qué página de listado apareció.
* Qué título o extracto tenía en el listado.
* Qué categoría visible tenía al momento del descubrimiento.

---

## 7. Bloque `raw`

El bloque `raw` contiene información directamente extraída desde la noticia.

No corresponde todavía a una interpretación económica, financiera o de sentimiento.

Su finalidad es conservar la mayor cantidad posible de información observable:

* Fecha.
* Título.
* Subtítulo.
* Autoría.
* Sección.
* Cuerpo.
* Resumen IA.
* Enlaces.
* Multimedia.
* Relacionados.
* Fuente de descubrimiento.

En una etapa posterior, estos datos serán utilizados para generar variables clasificadas, tales como:

* Noticia económica o no económica.
* Impacto positivo, negativo, neutro o mixto.
* Intensidad de impacto.
* Horizonte esperado de impacto.
* Sector económico afectado.
* Relación con mercado financiero.

---

## 8. Bloque `technical`

El bloque `technical` contiene información sobre el proceso de descarga, auditoría y parsing.

Ejemplo:

```json
{
  "technical": {
    "http_status": 200,
    "content_type": "text/html",
    "downloaded_from_sitemap": false,
    "downloaded_from_feed": true,
    "downloaded_from_dia_page": false,
    "downloaded_from_categoria_dia": false,
    "html_raw_path": "/ruta/local/noticia.html",
    "parser_version": "elmostrador_raw_v2_range_sections",
    "parse_success": true,
    "parse_errors": [],
    "template_noise_detected": false,
    "robots_allowed_checked": "not_checked",
    "discovery_sources": []
  }
}
```

| Campo                           | Descripción                                        |
| ------------------------------- | -------------------------------------------------- |
| `http_status`                   | Código HTTP obtenido al descargar la noticia.      |
| `content_type`                  | Tipo de contenido devuelto por el servidor.        |
| `downloaded_from_sitemap`       | Indica si fue descubierta desde sitemap.           |
| `downloaded_from_feed`          | Indica si fue descubierta desde feed o listado.    |
| `downloaded_from_dia_page`      | Indica si fue descubierta desde `/dia/`.           |
| `downloaded_from_categoria_dia` | Indica si fue descubierta desde `/categoria/dia/`. |
| `html_raw_path`                 | Ruta local del HTML original.                      |
| `parser_version`                | Versión del parser utilizado.                      |
| `parse_success`                 | Indica si la extracción fue exitosa.               |
| `parse_errors`                  | Lista de errores o advertencias.                   |
| `template_noise_detected`       | Indica si se detectaron residuos de plantilla.     |
| `robots_allowed_checked`        | Estado de revisión de reglas `robots.txt`.         |
| `discovery_sources`             | Fuentes desde donde se descubrió la noticia.       |

---

## 9. Organización de carpetas

La salida se organiza por medio y fecha.

### BioBioChile

```text
biobio/
└── 30_05_2026/
    ├── noticias_dia.txt
    └── html/
        ├── noticia_1.html
        ├── noticia_2.html
        └── ...
```

### El Mostrador

```text
mostrador/
└── 30_05_2026/
    ├── noticias_dia.txt
    └── html/
        ├── noticia_1.html
        ├── noticia_2.html
        └── ...
```

Además, para descargas por rango, pueden generarse archivos de resumen general:

```text
biobio/resumen_descarga_30_05_2026_30_dias.txt
mostrador/resumen_descarga_30_05_2026_30_dias.txt
```

---

## 10. Exclusiones actuales

El scraper busca excluir contenidos que puedan contaminar la base principal de noticias escritas.

### BioBioChile

Actualmente se excluyen o deben excluirse:

* Podcasts.
* BioBioTV.
* Programas audiovisuales.
* URLs bajo `/podcasts/`.
* URLs bajo `/biobiotv/`.

### El Mostrador

En El Mostrador, las exclusiones están orientadas a evitar páginas que no son noticias individuales:

* Páginas de autor.
* Tags.
* Newsletter.
* Páginas institucionales.
* Páginas de privacidad.
* Páginas de contacto.
* Paginaciones internas.
* Páginas de categorías sin noticia específica.

El criterio principal para El Mostrador es aceptar solo URLs que contengan una fecha en el patrón:

```text
/YYYY/MM/DD/
```

---

## 11. Uso futuro de los datos

Los datos obtenidos por los scrapers serán utilizados posteriormente para construir variables de entrada para modelos de análisis de volatilidad.

En una siguiente etapa se agregará una capa de clasificación que permitirá estimar, entre otros aspectos:

* Si la noticia es económica o no económica.
* Si tiene impacto potencial en mercados.
* Si el impacto esperado es positivo, negativo, neutro o mixto.
* Qué sector económico podría verse afectado.
* Qué instituciones, empresas o países aparecen mencionados.
* Si el impacto esperado es inmediato, breve o extendido.
* Qué relación puede tener la noticia con fondos mutuos, acciones o instrumentos financieros.

---

## 12. Etapas futuras del proyecto

Las siguientes etapas previstas son:

1. Mejorar la cobertura por día y por categoría.
2. Validar que se descarguen todas las noticias de una fecha determinada.
3. Agregar auditoría por categoría y por fuente de descubrimiento.
4. Mejorar la limpieza del cuerpo de las noticias.
5. Corregir problemas de encoding o mojibake.
6. Crear un clasificador heurístico inicial.
7. Etiquetar noticias para entrenamiento supervisado.
8. Probar modelos clásicos como árboles, SVM o regresión logística.
9. Incorporar modelos NLP, embeddings o modelos tipo Transformer.
10. Correlacionar noticias con valores cuota de fondos mutuos.
11. Generar variables agregadas por día.
12. Evaluar modelos predictivos como XGBoost y TFT.

---

## 13. Consideración metodológica

En esta etapa no se asignan todavía etiquetas financieras ni de sentimiento.

El scraper solo busca recolectar y estructurar información observable.

La clasificación económica, el análisis de impacto, la detección de entidades y la relación con volatilidad serán abordadas en una etapa posterior mediante:

* Reglas heurísticas.
* Diccionarios financieros.
* Modelos clásicos de machine learning.
* NLP.
* Embeddings.
* Clasificadores supervisados.
* Modelos predictivos con variables temporales.

La calidad de esta primera etapa es fundamental, porque los modelos posteriores dependerán directamente de la calidad, cobertura y consistencia de los datos recolectados.
