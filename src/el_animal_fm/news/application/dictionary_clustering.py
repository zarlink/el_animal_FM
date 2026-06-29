from __future__ import annotations

from collections import defaultdict

import hdbscan
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

from el_animal_fm.news.application.dictionary_classifier import should_use_for_financial_dictionary
from el_animal_fm.news.application.dictionary_text import build_embedding_text


def build_embedding_clusters(articles: list[dict]) -> tuple[np.ndarray, dict[str, list[dict]]]:
    embedding_articles = []
    embedding_texts = []

    for article in articles:
        if not should_use_for_financial_dictionary(article):
            continue

        text = build_embedding_text(article)

        if text and len(text.split()) >= 5:
            embedding_articles.append(article)
            embedding_texts.append(text)

    if embedding_texts:
        device = "cuda" if torch.cuda.is_available() else "cpu"

        model = SentenceTransformer(
            "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        )

        embeddings = model.encode(
            embedding_texts,
            show_progress_bar=True,
            normalize_embeddings=True,
            batch_size=128 if device == "cuda" else 64,
        )

        clusterer = hdbscan.HDBSCAN(
            min_cluster_size=15,
            min_samples=5,
            metric="euclidean",
            cluster_selection_method="eom",
            prediction_data=False,
        )

        labels = clusterer.fit_predict(embeddings)

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
