from __future__ import annotations

import hashlib
import json
import logging
import platform
import unicodedata
import sqlite3
import zlib
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path


logger = logging.getLogger("creador_diccionario")
CACHE_SCHEMA = 1


def fingerprint(value) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                         default=_json_default)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _json_default(value):
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    raise TypeError(f"Unsupported fingerprint value: {type(value).__name__}")


def dependencies(*modules: str, values=None, packages=()) -> str:
    """Fingerprint code and only the configuration used by this particular stage."""
    root = Path(__file__).parent
    versions = {}
    for package in packages:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = None
    return fingerprint({
        "schema": CACHE_SCHEMA,
        "python": platform.python_version(),
        "unicode": unicodedata.unidata_version,
        "code": {name: hashlib.sha256((root / f"{name}.py").read_bytes()).hexdigest()
                 for name in modules},
        "values": values,
        "packages": versions,
    })


class DictionaryCache:
    """Parent-process cache. JSON payloads, compressed and committed in transactions."""

    def __init__(self, directory: Path | None):
        self.connection = None
        self.pending = 0
        if directory is not None:
            directory.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(directory / "dictionary.sqlite3", timeout=60)
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS entries "
                "(stage TEXT, key TEXT, payload BLOB, PRIMARY KEY(stage, key))"
            )
            self.connection.commit()
            logger.info("CACHÉ | directorio=%s", directory)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        if self.connection is not None:
            self.connection.commit()
            self.connection.close()

    def get(self, stage: str, key: str):
        if self.connection is None:
            return None
        row = self.connection.execute(
            "SELECT payload FROM entries WHERE stage=? AND key=?", (stage, key)
        ).fetchone()
        if row is None:
            return None
        try:
            return json.loads(zlib.decompress(row[0]))
        except (ValueError, zlib.error, UnicodeError):
            logger.warning("CACHÉ | entrada ilegible | etapa=%s | recalculando", stage)
            return None

    def put(self, stage: str, key: str, value):
        if self.connection is None:
            return
        payload = zlib.compress(json.dumps(value, ensure_ascii=False, allow_nan=False).encode())
        self.connection.execute(
            "INSERT OR REPLACE INTO entries VALUES (?, ?, ?)", (stage, key, payload)
        )
        self.pending += 1
        if self.pending >= 250:
            self.connection.commit()
            self.pending = 0

    def compute(self, stage: str, signature: str, inputs, function):
        key = fingerprint([signature, inputs])
        cached = self.get(stage, key)
        if cached is not None:
            logger.info("CACHÉ | REUTILIZADO | %s", stage)
            return cached
        logger.info("CACHÉ | CALCULAR | %s", stage)
        result = function()
        self.put(stage, key, result)
        return result
