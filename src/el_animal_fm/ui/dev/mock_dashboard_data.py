from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MockFundSignal:
    index: str
    title: str
    metrics: dict[str, str]
    semaforo: str
    decision_if_out: str
    decision_if_in: str


MOCK_FUND_SIGNALS: tuple[MockFundSignal, ...] = (
    MockFundSignal(
        index="01",
        title="Crecimiento Balanceado",
        metrics={
            "pred_prob_up": "--",
            "pred_up": "--",
            "momentum_10": "--",
            "vs_ma20": "--",
            "drawdown_20": "--",
            "entry_score": "--",
        },
        semaforo="SIN SENAL",
        decision_if_out="NO DATA",
        decision_if_in="NO DATA",
    ),
    MockFundSignal(
        index="02",
        title="Ahorro UF Itau",
        metrics={
            "pred_prob_up": "0.469",
            "pred_up": "0",
            "momentum_10": "-0.0019",
            "vs_ma20": "-0.0015",
            "drawdown_20": "-0.0038",
            "entry_score": "1",
        },
        semaforo="ROJO",
        decision_if_out="ESPERAR",
        decision_if_in="SALIR O MOVER DEFENSIVO",
    ),
    MockFundSignal(
        index="03",
        title="National Equity",
        metrics={
            "pred_prob_up": "0.385",
            "pred_up": "0",
            "momentum_10": "-0.0199",
            "vs_ma20": "+0.0047",
            "drawdown_20": "-0.0163",
            "entry_score": "2",
        },
        semaforo="AMARILLO",
        decision_if_out="ESPERAR",
        decision_if_in="MANTENER CON ALERTA",
    ),
    MockFundSignal(
        index="04",
        title="Toesca Equity",
        metrics={
            "pred_prob_up": "0.195",
            "pred_up": "0",
            "momentum_10": "-0.0219",
            "vs_ma20": "+0.0050",
            "drawdown_20": "-0.0161",
            "entry_score": "2",
        },
        semaforo="VERDE",
        decision_if_out="MANTENER",
        decision_if_in="ENTRAR CON VERDE",
    ),
    MockFundSignal(
        index="05",
        title="National Equity",
        metrics={
            "pred_prob_up": "0.385",
            "pred_up": "0",
            "momentum_10": "-0.0199",
            "vs_ma20": "+0.0047",
            "drawdown_20": "-0.0163",
            "entry_score": "2",
        },
        semaforo="ROJO",
        decision_if_out="ESPERAR",
        decision_if_in="MANTENER CON ALERTA",
    ),
    MockFundSignal(
        index="06",
        title="Ahorro UF Itau",
        metrics={
            "pred_prob_up": "0.469",
            "pred_up": "0",
            "momentum_10": "-0.0019",
            "vs_ma20": "-0.0015",
            "drawdown_20": "-0.0038",
            "entry_score": "1",
        },
        semaforo="AMARILLO",
        decision_if_out="ESPERAR",
        decision_if_in="SALIR O MOVER DEFENSIVO",
    ),
)


MOCK_SYSTEM_STATUS: dict[str, str] = {
    "Model loaded": "OK",
    "BioBio sources": "427",
    "Mostrador sources": "283",
    "Feature sets": "574 / 574",
    "Funds analyzed": "6",
    "Live signals": "5",
    "Warnings": "1",
}


MOCK_EVENT_LOG: tuple[str, ...] = (
    "21:04:12  [INFO]  Modelo cargado correctamente",
    "21:04:13  [INFO]  Prediccion live ejecutada",
    "21:04:13  [WARN]  Crecimiento Balanceado sin fila live",
    "21:04:13  [INFO]  Proceso terminado",
)


MOCK_CONSOLE_LINES: tuple[str, ...] = (
    "$ python run_live_predictions.py \\",
    "    --date 2026-06-25 \\",
    "    --config configs/live_config.yaml",
    "> Ejecutando prediccion live para 2026-06-25 ...",
    "> Generando senales ...",
    "> Proceso finalizado OK",
)


MOCK_SIGNAL_DISTRIBUTION: tuple[tuple[str, str], ...] = (
    ("ROJO", "2 (33%)"),
    ("AMARILLO", "2 (33%)"),
    ("VERDE", "1 (17%)"),
    ("SIN SENAL", "1 (17%)"),
)


MOCK_ENTRY_SCORE_MAP: tuple[tuple[str, str], ...] = (
    ("3", "0"),
    ("2", "3"),
    ("1", "2"),
    ("0", "1"),
)


MOCK_SECONDARY_VIEWS: dict[str, tuple[str, ...]] = {
    "Pipeline Monitor": (
        "Noticias BioBio: pendiente de ultima descarga",
        "Noticias Mostrador: pendiente de ultima descarga",
        "Normalizacion: lista para ejecucion manual",
        "Unificacion: esperando confirmacion visual",
        "Prediccion: desacoplada de la vista en esta etapa",
    ),
    "News Enrichment": (
        "Diccionarios base: 6 familias activas",
        "Candidatos adicionales: mock sin lectura real",
        "Resumen enriquecimiento: pendiente de integrar features_summary",
        "Validacion manual: pendiente",
    ),
    "Dictionary Lab": (
        "Macro indicadores: disponible como familia de trabajo",
        "Empresas Chile: disponible como familia de trabajo",
        "Politico corporativo: disponible como familia de trabajo",
        "Revision de candidatos: vista pendiente de diseno",
    ),
    "Models": (
        "Crecimiento Balanceado: modelo mock cargado",
        "Ahorro UF Itau: modelo mock cargado",
        "National Equity: modelo mock cargado",
        "Toesca Equity: modelo mock cargado",
    ),
}
