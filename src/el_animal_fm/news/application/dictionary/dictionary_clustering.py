from __future__ import annotations

from collections import defaultdict
import hashlib
import logging
from pathlib import Path

from huggingface_hub import try_to_load_from_cache
from el_animal_fm.news.application.dictionary import dictionary_config as config
from el_animal_fm.news.application.dictionary.dictionary_cache import DictionaryCache, dependencies, fingerprint

from el_animal_fm.news.application.dictionary.dictionary_progress import log_stage

import hdbscan
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from el_animal_fm.news.application.dictionary.dictionary_classifier import should_use_for_financial_dictionary
from el_animal_fm.news.application.dictionary.dictionary_text import build_embedding_text


MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
logger = logging.getLogger("creador_diccionario")


def _model_revision():
    path = try_to_load_from_cache(MODEL_NAME, "config.json")
    if isinstance(path, str):
        # Snapshot directories use the resolved commit hash, not the mutable 'main'.
        return Path(path).parent.name
    return None


def build_embedding_clusters(
    articles: list[dict], *, cache: DictionaryCache | None = None,
) -> tuple[np.ndarray, dict[str, list[dict]]]:
    embedding_articles = []
    embedding_texts = []

    text_signature = dependencies("dictionary_text", values=list(config.PHRASE_NORMALIZATIONS.items()))
    with log_stage("Preparación de textos para embeddings"):
        for article in articles:
            if not should_use_for_financial_dictionary(article):
                continue

            key = fingerprint([text_signature, article])
            text = cache.get("embedding_text", key) if cache is not None else None
            if text is None:
                text = build_embedding_text(article)
                if cache is not None:
                    cache.put("embedding_text", key, text)

            if text and len(text.split()) >= 5:
                embedding_articles.append(article)
                embedding_texts.append(text)

    if embedding_texts:
        device = "cuda" if torch.cuda.is_available() else "cpu"

        def embedding_key():
            revision = _model_revision()
            if revision is None:
                return None
            signature = dependencies(
                "dictionary_clustering", values={"model": MODEL_NAME, "revision": revision, "device": device},
                packages=("sentence-transformers", "transformers", "torch", "numpy", "huggingface-hub"),
            )
            return fingerprint([signature, embedding_texts])

        key = embedding_key()
        saved = cache.get("embeddings", key) if cache is not None and key is not None else None
        if saved is not None:
            logger.info("CACHÉ | REUTILIZADO | embeddings")
            embeddings = np.asarray(saved["values"], dtype=saved["dtype"])
        else:
            with log_stage("Carga del modelo de embeddings"):
                model = SentenceTransformer(MODEL_NAME)
            with log_stage("Cálculo de embeddings", len(embedding_texts)):
                embeddings = model.encode(
                    embedding_texts, show_progress_bar=True, normalize_embeddings=True,
                    batch_size=128 if device == "cuda" else 64,
                )
            key = embedding_key()
            if cache is not None and key is not None:
                cache.put("embeddings", key, {"dtype": str(embeddings.dtype), "values": embeddings.tolist()})

        with log_stage("Clustering HDBSCAN"):
            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=15,
                min_samples=5,
                metric="euclidean",
                cluster_selection_method="eom",
                prediction_data=False,
            )

            cluster_signature = dependencies("dictionary_clustering", packages=("hdbscan", "numpy", "scipy"))
            # Include exact embedding bytes: preserve results for this model output.
            cluster_key = fingerprint([cluster_signature, str(embeddings.dtype),
                                       embeddings.shape, hashlib.sha256(embeddings.tobytes()).hexdigest()])
            saved_labels = cache.get("cluster_labels", cluster_key) if cache is not None else None
            if saved_labels is None:
                labels = clusterer.fit_predict(embeddings)
                if cache is not None:
                    cache.put("cluster_labels", cluster_key, labels.tolist())
            else:
                logger.info("CACHÉ | REUTILIZADO | clustering")
                labels = np.asarray(saved_labels, dtype=int)

    else:
        labels = np.array([])

    cluster_examples = defaultdict(list)

    if len(labels):
        for label, article, text in zip(labels, embedding_articles, embedding_texts):
            label = str(label)

            if len(cluster_examples[label]) >= 10:
                continue

            cluster_examples[label].append({
                "title": article.get("title", ""),
                "source": article.get("source", ""),
                "published_date": article.get("published_date", ""),
                "main_section": article.get("main_section", ""),
                "url": article.get("url", ""),
                "text_preview": text[:300],
            })

    return labels, dict(cluster_examples)
