from __future__ import annotations

def import_ml_dependencies():
    try:
        from xgboost import XGBClassifier
        from sklearn.metrics import (
            accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
            precision_score, recall_score, roc_auc_score,
        )
        import joblib
    except ImportError as exc:
        print("Faltan dependencias. Ejecuta: pip install pandas numpy scikit-learn xgboost joblib")
        raise exc
    return locals()

def import_optuna_dependency():
    try:
        import optuna
    except ImportError as exc:
        print("Falta Optuna. Ejecuta: pip install optuna")
        raise exc
    return optuna
