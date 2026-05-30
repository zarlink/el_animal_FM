# Scraper de Noticias para Análisis de Volatilidad

Este repositorio tiene por objetivo descargar noticias diarias desde medios digitales, inicialmente **Radio Bío Bío / BioBioChile** y posteriormente **El Mostrador**, para construir una base de datos estructurada que permita realizar análisis de volatilidad de mercado.

La finalidad del proyecto es transformar noticias publicadas diariamente en datos estructurados que, en una etapa posterior, puedan ser usados como entrada para modelos de machine learning, tales como **XGBoost**, **TFT** u otros algoritmos de análisis predictivo.

---

## 1. Objetivo general del proyecto

El objetivo principal es recolectar noticias diarias, extraer información relevante desde cada artículo y almacenarla en un formato estructurado que permita, posteriormente, analizar su posible relación con la volatilidad de instrumentos financieros, fondos mutuos o mercados específicos.

En esta primera etapa, el foco está puesto en:

1. Descargar noticias desde BioBioChile.
2. Extraer información estructurada desde cada noticia.
3. Guardar los datos en archivos organizados por fecha.
4. Preparar la información para una futura etapa de clasificación.
5. Construir una base histórica que permita correlacionar noticias con variables financieras.

---

## 2. Fuente inicial: BioBioChile

La primera fuente trabajada es **BioBioChile**, medio digital chileno que publica noticias en distintas secciones, tales como:

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

El scraper busca obtener noticias diarias desde distintas categorías, excluyendo contenidos que no correspondan a noticias tradicionales, como podcasts o contenido audiovisual puro.

---

## 3. Estructura general de descarga

Las noticias descargadas se guardan dentro de una carpeta organizada por medio y fecha.

Ejemplo:

```text
biobio/
└── 30_05_2026/
    ├── noticias_dia.txt
    └── html/
        ├── noticia_1.html
        ├── noticia_2.html
        └── ...
```

Donde:

* `biobio/` corresponde al medio de origen.
* `30_05_2026/` corresponde a la fecha de publicación de las noticias.
* `noticias_dia.txt` contiene la información estructurada de las noticias descargadas.
* `html/` contiene una copia del HTML crudo de cada noticia, útil para auditoría, depuración y mejora del parser.

---

## 4. Formato de salida

El archivo principal de salida es:

```text
noticias_dia.txt
```

Aunque tiene extensión `.txt`, el contenido se almacena en formato **JSON**, manteniendo una estructura ordenada para cada noticia.

Cada noticia se divide principalmente en dos bloques:

```json
{
  "raw": {},
  "technical": {}
}
```

---

## 5. Bloque `raw`

El bloque `raw` contiene la información directamente extraída desde la noticia.

Su objetivo es conservar los datos observables del artículo sin aplicar todavía una clasificación financiera, económica o de sentimiento.

Ejemplo general:

```json
{
  "raw": {
    "source": "biobiochile",
    "source_type": "news_site",
    "url": "https://www.biobiochile.cl/...",
    "canonical_url": "",
    "article_id": "",
    "slug": "palabras-separadas-por-guion",
    "scraped_at": "2026-05-30T16:43:12.424553-04:00",
    "published_at_raw": "2026-05-30T09:01:34-04:00",
    "published_at": "2026-05-30T09:01:34-04:00",
    "published_date": "2026-05-30",
    "published_time": "09:01:34",
    "timezone": "America/Santiago"
  }
}
```

---

## 6. Identificación de la noticia

Los campos de identificación permiten reconocer la fuente, URL, fecha y metadatos básicos del artículo.

| Campo              | Descripción                                                                           |
| ------------------ | ------------------------------------------------------------------------------------- |
| `source`           | Medio desde el cual se obtuvo la noticia.                                             |
| `source_type`      | Tipo de fuente, por ejemplo `news_site`.                                              |
| `url`              | URL original desde la cual se descargó la noticia.                                    |
| `canonical_url`    | URL canónica del artículo, si se encuentra disponible.                                |
| `article_id`       | Identificador interno de la noticia, si existe.                                       |
| `slug`             | Fragmento final de la URL, generalmente compuesto por palabras separadas por guiones. |
| `scraped_at`       | Fecha y hora en que el scraper descargó la noticia.                                   |
| `published_at_raw` | Fecha de publicación original obtenida desde el sitio.                                |
| `published_at`     | Fecha de publicación normalizada.                                                     |
| `published_date`   | Fecha de publicación en formato `YYYY-MM-DD`.                                         |
| `published_time`   | Hora de publicación.                                                                  |
| `timezone`         | Zona horaria asociada a la noticia.                                                   |

---

## 7. Clasificación editorial observable

Estos campos describen cómo BioBioChile clasifica editorialmente la noticia.

```json
{
  "main_section": "bbcl-investiga",
  "subsection": "",
  "breadcrumb_raw": "",
  "article_type_editorial": "noticia",
  "is_opinion": false,
  "is_investigation": true,
  "is_economy_section": false,
  "is_national_section": false,
  "is_international_section": false,
  "region_section": ""
}
```

| Campo                      | Descripción                                                                              |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| `main_section`             | Sección principal de la noticia.                                                         |
| `subsection`               | Subsección, si existe.                                                                   |
| `breadcrumb_raw`           | Ruta editorial o breadcrumb visible en la página.                                        |
| `article_type_editorial`   | Tipo editorial del contenido, por ejemplo `noticia`, `opinion`, `reportaje` o `agencia`. |
| `is_opinion`               | Indica si la noticia corresponde a opinión.                                              |
| `is_investigation`         | Indica si corresponde a contenido investigativo.                                         |
| `is_economy_section`       | Indica si pertenece a una sección económica.                                             |
| `is_national_section`      | Indica si pertenece a una sección nacional.                                              |
| `is_international_section` | Indica si pertenece a una sección internacional.                                         |
| `region_section`           | Región asociada a la noticia, si corresponde.                                            |

---

## 8. Título, subtítulo y resumen

Estos campos permiten obtener la información textual inicial de cada noticia.

```json
{
  "title": "Título de la noticia",
  "subtitle": "Subtítulo de la noticia",
  "lead": "Texto inicial o bajada",
  "ai_summary": "Resumen generado por IA",
  "has_ai_summary": true,
  "summary_source": "bio_bio_ai_reviewed_by_author"
}
```

| Campo            | Descripción                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `title`          | Título principal de la noticia.                                  |
| `subtitle`       | Subtítulo o descripción breve.                                   |
| `lead`           | Bajada o primer texto relevante detectado.                       |
| `ai_summary`     | Resumen generado por IA, cuando está disponible.                 |
| `has_ai_summary` | Indica si la noticia contiene resumen IA.                        |
| `summary_source` | Fuente del resumen, por ejemplo `bio_bio_ai_reviewed_by_author`. |

---

## 9. Autoría y atribución

El scraper también intenta extraer información del autor o autora de la noticia.

```json
{
  "author_name": "Nombre de Autor",
  "author_url": "",
  "author_role": "Periodista de Investigación en BioBioChile.",
  "author_image_url": "https://www.biobiochile.cl/assets/authors/1112.jpg",
  "source_attribution": "",
  "is_agency_content": false,
  "is_staff_writer": true,
  "is_external_columnist": false
}
```

| Campo                   | Descripción                                      |
| ----------------------- | ------------------------------------------------ |
| `author_name`           | Nombre del autor o autora.                       |
| `author_url`            | URL del perfil del autor, si existe.             |
| `author_role`           | Rol o cargo del autor.                           |
| `author_image_url`      | Imagen del autor, si está disponible.            |
| `source_attribution`    | Atribución externa, agencia o fuente secundaria. |
| `is_agency_content`     | Indica si el contenido proviene de agencia.      |
| `is_staff_writer`       | Indica si corresponde a un periodista del medio. |
| `is_external_columnist` | Indica si corresponde a columnista externo.      |

---

## 10. Cuerpo de la noticia

El cuerpo de la noticia se almacena en distintos niveles para facilitar análisis posteriores.

```json
{
  "body_text_raw": "Texto completo de la noticia...",
  "body_text_clean": "Texto limpio de la noticia...",
  "paragraphs": [],
  "paragraph_count": 51,
  "body_length_chars": 9703,
  "body_length_words": 1696,
  "internal_subheadings": [],
  "quote_count": 10
}
```

| Campo                  | Descripción                                         |
| ---------------------- | --------------------------------------------------- |
| `body_text_raw`        | Texto completo extraído desde la noticia.           |
| `body_text_clean`      | Texto limpio, normalizado y sin exceso de espacios. |
| `paragraphs`           | Lista de párrafos detectados.                       |
| `paragraph_count`      | Número de párrafos extraídos.                       |
| `body_length_chars`    | Cantidad de caracteres del cuerpo limpio.           |
| `body_length_words`    | Cantidad aproximada de palabras.                    |
| `internal_subheadings` | Subtítulos internos de la noticia.                  |
| `quote_count`          | Conteo aproximado de citas o comillas relevantes.   |

---

## 11. Multimedia e imágenes

El scraper intenta extraer información asociada a imágenes, videos o audio.

```json
{
  "main_image_url": "https://media.biobiochile.cl/...",
  "main_image_alt": "Texto alternativo",
  "image_caption": "",
  "image_credit": "",
  "has_image": true,
  "image_count": 23,
  "has_video": false,
  "video_url": "",
  "has_audio": false,
  "media_type": "text"
}
```

| Campo            | Descripción                                                      |
| ---------------- | ---------------------------------------------------------------- |
| `main_image_url` | URL de la imagen principal.                                      |
| `main_image_alt` | Texto alternativo de la imagen.                                  |
| `image_caption`  | Pie de foto, si existe.                                          |
| `image_credit`   | Crédito de imagen, si se detecta.                                |
| `has_image`      | Indica si la noticia contiene imágenes.                          |
| `image_count`    | Número de imágenes detectadas.                                   |
| `has_video`      | Indica si la noticia contiene video.                             |
| `video_url`      | URL del video, si existe.                                        |
| `has_audio`      | Indica si contiene audio.                                        |
| `media_type`     | Tipo de contenido detectado: `text`, `video`, `audio` o `mixed`. |

---

## 12. Noticias relacionadas y enlaces internos

El scraper también intenta extraer enlaces relacionados, noticias sugeridas y links internos.

```json
{
  "read_also_links": [],
  "read_also_titles": [],
  "read_also_dates": [],
  "related_links": [],
  "related_titles": [],
  "related_count": 0
}
```

| Campo              | Descripción                                            |
| ------------------ | ------------------------------------------------------ |
| `read_also_links`  | URLs de noticias marcadas como “Lee también”.          |
| `read_also_titles` | Títulos de noticias relacionadas.                      |
| `read_also_dates`  | Fechas de noticias relacionadas, si están disponibles. |
| `related_links`    | Otros enlaces relacionados detectados.                 |
| `related_titles`   | Títulos de otros enlaces relacionados.                 |
| `related_count`    | Cantidad total de enlaces relacionados.                |

---

## 13. Redes sociales y distribución

También se intentan capturar enlaces de distribución social.

```json
{
  "share_facebook_url": "",
  "share_x_url": "",
  "share_whatsapp_url": "",
  "visible_views_raw": "",
  "views_count": null
}
```

| Campo                | Descripción                                                |
| -------------------- | ---------------------------------------------------------- |
| `share_facebook_url` | URL para compartir en Facebook.                            |
| `share_x_url`        | URL para compartir en X / Twitter.                         |
| `share_whatsapp_url` | URL para compartir por WhatsApp.                           |
| `visible_views_raw`  | Texto visible asociado a visitas, si existe.               |
| `views_count`        | Número de visitas, si se puede extraer de forma confiable. |

---

## 14. Bloque `technical`

El bloque `technical` contiene información sobre el proceso de descarga, auditoría y parsing.

```json
{
  "technical": {
    "http_status": 200,
    "content_type": "text/html",
    "downloaded_from_sitemap": false,
    "downloaded_from_feed": true,
    "html_raw_path": "/ruta/local/noticia.html",
    "parser_version": "biobio_raw_v3_category_archives",
    "parse_success": true,
    "parse_errors": [],
    "template_noise_detected": true,
    "robots_allowed_checked": "not_checked",
    "discovery_sources": []
  }
}
```

| Campo                     | Descripción                                            |
| ------------------------- | ------------------------------------------------------ |
| `http_status`             | Código HTTP obtenido al descargar la noticia.          |
| `content_type`            | Tipo de contenido devuelto por el servidor.            |
| `downloaded_from_sitemap` | Indica si la noticia fue descubierta desde un sitemap. |
| `downloaded_from_feed`    | Indica si fue descubierta desde un feed o listado.     |
| `html_raw_path`           | Ruta local donde se guardó el HTML original.           |
| `parser_version`          | Versión del parser utilizado.                          |
| `parse_success`           | Indica si la extracción fue exitosa.                   |
| `parse_errors`            | Lista de errores o advertencias detectadas.            |
| `template_noise_detected` | Indica si se detectaron residuos de plantilla.         |
| `robots_allowed_checked`  | Estado de revisión de reglas `robots.txt`.             |
| `discovery_sources`       | Fuentes desde donde se descubrió la noticia.           |

---

## 15. Estrategia actual de descubrimiento

La versión actual del scraper trabaja con archivos de categorías de BioBioChile.

Ejemplo de ruta:

```text
https://www.biobiochile.cl/lista/categorias/nacional
```

La estrategia consiste en:

1. Recorrer categorías de noticias.
2. Detectar tarjetas o enlaces de artículos.
3. Filtrar URLs que correspondan a noticias estándar.
4. Excluir podcasts y contenido audiovisual no noticioso.
5. Deduplicar noticias repetidas entre categorías.
6. Descargar cada noticia.
7. Extraer campos `raw` y `technical`.
8. Guardar la información estructurada en `noticias_dia.txt`.

---

## 16. Exclusiones actuales

Por ahora, se excluyen contenidos que no correspondan al flujo principal de noticias escritas.

Ejemplos de contenidos excluidos:

* Podcasts.
* BioBioTV.
* Programas audiovisuales.
* URLs bajo `/podcasts/`.
* URLs bajo `/biobiotv/`.

La razón de esta exclusión es mantener una base homogénea para el análisis posterior de noticias escritas.

---

## 17. Uso futuro de los datos

Los datos obtenidos por el scraper serán utilizados posteriormente para construir variables de entrada para modelos de análisis de volatilidad.

En una siguiente etapa se agregará una capa de clasificación que permitirá estimar, entre otros aspectos:

* Si la noticia es económica o no económica.
* Si tiene impacto potencial en mercados.
* Si el impacto esperado es positivo, negativo, neutro o mixto.
* Qué sector económico podría verse afectado.
* Qué instituciones, empresas o países aparecen mencionados.
* Si el impacto esperado es inmediato, breve o extendido.
* Qué relación puede tener la noticia con fondos mutuos, acciones o instrumentos financieros.

---

## 18. Etapas futuras del proyecto

Las siguientes etapas previstas son:

1. Mejorar la cobertura por día y por categoría.
2. Validar que se descarguen todas las noticias de una fecha determinada.
3. Agregar auditoría por categoría.
4. Mejorar la limpieza del cuerpo de las noticias.
5. Crear un clasificador heurístico inicial.
6. Etiquetar noticias para entrenamiento supervisado.
7. Probar modelos clásicos como árboles, SVM o regresión logística.
8. Incorporar modelos NLP o embeddings.
9. Correlacionar noticias con valores cuota de fondos mutuos.
10. Evaluar modelos predictivos como XGBoost y TFT.

---

## 19. Estado actual

Actualmente el scraper permite:

* Descargar noticias desde BioBioChile.
* Organizar las noticias por fecha.
* Guardar HTML crudo de respaldo.
* Extraer metadatos principales.
* Extraer cuerpo, título, autor, sección y resumen IA.
* Registrar información técnica del proceso.
* Excluir contenidos no deseados como podcasts y BioBioTV.
* Preparar la información para una futura etapa de clasificación.

---

## 20. Consideración metodológica

En esta etapa no se asignan todavía etiquetas financieras ni de sentimiento. El scraper solo busca recolectar y estructurar información observable.

La clasificación económica, el análisis de impacto y la relación con volatilidad serán abordados en una etapa posterior mediante reglas heurísticas, modelos NLP o algoritmos supervisados.
