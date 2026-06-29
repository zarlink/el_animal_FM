from __future__ import annotations

from collections import Counter

import yake
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer

from el_animal_fm.news.application.dictionary_config import TOKEN_PATTERN, get_stopwords
from el_animal_fm.news.application.dictionary_text import clean


STOP = get_stopwords()


def extract_ngrams(texts_source: list[str], min_df: int = 5) -> list[dict]:
    if not texts_source:
        return []

    cv = CountVectorizer(
        ngram_range=(1, 3),
        min_df=min_df,
        max_df=0.6,
        stop_words=list(STOP),
        token_pattern=TOKEN_PATTERN,
    )

    X = cv.fit_transform(texts_source)

    term_counts = X.sum(axis=0).A1
    doc_freq = (X > 0).sum(axis=0).A1
    terms = cv.get_feature_names_out()

    return sorted(
        [
            {
                "term": term,
                "count": int(count),
                "df": int(df),
                "df_pct": float(df / len(texts_source)),
            }
            for term, count, df in zip(terms, term_counts, doc_freq)
        ],
        key=lambda x: (x["df"], x["count"]),
        reverse=True
    )[:2000]


def extract_tfidf(texts_source: list[str], min_df: int = 3) -> list[dict]:
    if not texts_source:
        return []

    tfv = TfidfVectorizer(
        ngram_range=(1, 3),
        min_df=min_df,
        max_df=0.6,
        stop_words=list(STOP),
        token_pattern=TOKEN_PATTERN,
        sublinear_tf=True,
    )

    T = tfv.fit_transform(texts_source)
    tfidf_mean = T.mean(axis=0).A1
    terms = tfv.get_feature_names_out()

    return sorted(
        [
            {
                "term": term,
                "score": float(score),
            }
            for term, score in zip(terms, tfidf_mean)
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:2000]


def is_bad_candidate_term(term: str) -> bool:
    term = clean(term)

    if not term:
        return True

    tokens = term.split()

    if len(tokens) == 1 and tokens[0] in STOP:
        return True

    if all(token in STOP for token in tokens):
        return True

    if len(term) < 4:
        return True

    bad_fragments = [
        "pan pan",
        "programa full measure",
        "tribeca",
        "san sebastián guadalajara",
        "bío bío",
        "radio bío bío",
        "señor director",
        "director señor director",
        "mundo editorial planeta",
        "súmate informado",
        "súmate informado precisas",
        "política súmate",
        "política súmate informado",
        "informado precisas",
        "informado precisas seguimiento",
        "precisas seguimiento",
        "precisas seguimiento detallado",
        "seguimiento detallado",
        "seguimiento detallado políticas",
        "detallado políticas",
        "detallado políticas públicas",
        "políticas públicas entrevistas",
        "públicas entrevistas",
        "públicas entrevistas personajes",
        "entrevistas personajes",
        "entrevistas personajes influyen",
    ]

    if any(fragment in term for fragment in bad_fragments):
        return True

    return False


def extract_yake_keywords(texts_source: list[str]) -> list[tuple[str, float]]:
    kw = yake.KeywordExtractor(lan="es", n=3, top=20)
    yake_scores = Counter()

    for txt in texts_source:
        for term, score in kw.extract_keywords(txt):
            term = clean(term)

            if is_bad_candidate_term(term):
                continue

            yake_scores[term] += (1.0 / (score + 1e-9))

    return yake_scores.most_common(1000)
