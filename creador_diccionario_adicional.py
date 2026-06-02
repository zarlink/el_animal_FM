import json, re, unicodedata, html
from collections import Counter, defaultdict
from sklearn.feature_extraction.text import CountVectorizer, TfidfVectorizer
import yake, spacy, hdbscan
from sentence_transformers import SentenceTransformer
import numpy as np

STOP = set("""de la el y en a los del se las por un para con no una su al lo como más pero sus
le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde""".split())

def clean(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)              # html
    text = re.sub(r"https?://\S+", " ", text)         # urls
    text = unicodedata.normalize("NFKC", text).lower()
    text = re.sub(r"ver resumen|lee también|suscríbete.*", " ", text)
    text = re.sub(r"[^a-záéíóúñü0-9%$/\-\.\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

data = json.load(open("noticias_unificadas.txt", encoding="utf-8"))
articles = data["articles"] if isinstance(data, dict) else data
texts = [clean(a.get("classification_text", "")) for a in articles if a.get("classification_text")]

# n-gramas
cv = CountVectorizer(ngram_range=(1,3), min_df=3, stop_words=list(STOP))
X = cv.fit_transform(texts)
freq = X.sum(axis=0).A1
terms = cv.get_feature_names_out()
ngrams_top = sorted(zip(terms, freq), key=lambda x: x[1], reverse=True)[:2000]

# TF-IDF
tfv = TfidfVectorizer(ngram_range=(1,3), min_df=3, stop_words=list(STOP))
T = tfv.fit_transform(texts)
tfidf_mean = T.mean(axis=0).A1
tfidf_top = sorted(zip(tfv.get_feature_names_out(), tfidf_mean), key=lambda x: x[1], reverse=True)[:2000]

# YAKE
kw = yake.KeywordExtractor(lan="es", n=3, top=20)
yake_scores = Counter()
for txt in texts:
    for term, score in kw.extract_keywords(txt):
        yake_scores[term] += (1.0 / (score + 1e-9))
yake_top = yake_scores.most_common(1000)

# NER
nlp = spacy.load("es_core_news_lg")
ents = Counter()
for doc in nlp.pipe(texts, batch_size=32):
    for e in doc.ents:
        if e.label_ in {"ORG","PER","LOC","MISC"}:
            ents[(e.text.lower(), e.label_)] += 1

# Embeddings + clustering
model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
emb = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
labels = hdbscan.HDBSCAN(min_cluster_size=20, metric="euclidean").fit_predict(emb)

# Salida
out = {
    "ngrams_top": ngrams_top[:300],
    "tfidf_top": tfidf_top[:300],
    "yake_top": yake_top[:300],
    "entities_top": [{"text": k[0], "label": k[1], "count": v} for k, v in ents.most_common(300)],
    "clusters": Counter(labels)
}
def make_json_serializable(obj):
    """
    Convierte tipos de numpy/pandas/sklearn a tipos nativos de Python
    para que puedan guardarse con json.dump().
    """
    if isinstance(obj, dict):
        return {str(k): make_json_serializable(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, tuple):
        return [make_json_serializable(v) for v in obj]

    if isinstance(obj, set):
        return [make_json_serializable(v) for v in sorted(obj)]

    if isinstance(obj, np.integer):
        return int(obj)

    if isinstance(obj, np.floating):
        return float(obj)

    if isinstance(obj, np.ndarray):
        return obj.tolist()

    if obj is None:
        return None

    return obj

out_serializable = make_json_serializable(out)

with open("candidatos_diccionario.json", "w", encoding="utf-8") as f:
    json.dump(out_serializable, f, ensure_ascii=False, indent=2)